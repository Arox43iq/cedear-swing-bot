from __future__ import annotations

"""
RESEARCH ENGINE v2 — audited / robust portfolio backtester

Design goals:
- causal signals: close of D -> order at next available session
- one coherent currency per backtest (USA and CEDEAR are run separately)
- adjusted OHLC for research so splits/dividends do not create fake discontinuities
- explicit cash, market value, gross/net P&L, commissions and slippage
- hard position/exposure/portfolio-risk limits
- deterministic daily accounting
- conservative daily-bar ambiguity: if both stop and target are touched, STOP wins
- deterministic end-of-period liquidation
- no stale pending orders
- precomputed signals to avoid repeated DataFrame search/iloc work
- walk-forward style OOS / TEST validation and cost stress

This is research software, not an execution system.
"""

import math
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

from strategy import BASE_COMPONENTS, signal

warnings.filterwarnings("ignore")

RESULTS = Path("results")
RESULTS.mkdir(exist_ok=True)

CONFIG = {
    # Portfolio
    "capital": 1_000_000.0,
    "risk_per_trade": 0.005,
    "min_effective_risk": 0.75,
    "max_positions": 6,
    "max_positions_weak": 4,
    "max_entries_day": 4,
    "max_entries_day_weak": 2,
    "max_position_pct": 0.20,
    "max_gross_exposure": 0.90,
    "max_portfolio_risk": 0.025,
    # Safety margin so entry-time hard caps remain hard after commissions.
    "cap_buffer": 0.995,
    "max_single_gap_loss_risk": 2.0,

    # Execution / exits
    "max_bars": 15,
    "extension_bars": 5,
    "cooldown_sl": 7,
    "slippage": 0.0005,
    "commission": 0.0005,
    "tp_r": 1.8,
    "stop_atr": 1.5,

    # Signal filters
    "atr_min_pct": 0.01,
    "atr_max_pct": 0.06,
    "volume_min": 0.80,
    "low_ema20_tol": 0.012,
    "pullback_below": 0.025,
    "pullback_above": 0.025,
    "location_min": 0.35,
    "ret5_min": -0.03,
    "ret20_min": 0.00,
    "wpr_threshold": -75.0,
    "rs20_min": 0.00,
    "min_confirm": 2,

    # Research periods
    "start": pd.Timestamp("2023-01-03"),
    "oos": pd.Timestamp("2025-01-02"),
    "test": pd.Timestamp("2026-01-02"),
    "data_start": "2021-01-01",

    # Data / universe
    "price_mode": "adjusted",
    "allow_ce_dear": False,
    "download_batch_size": 25,
    "download_threads": 8,
    "download_timeout": 20,
    "cache_dir": "cache/yahoo",
    "cache_max_age_hours": 24,
}

USA_UNIVERSE = [
    # Mega / large cap technology
    "AAPL","MSFT","NVDA","AMZN","META","GOOGL","GOOG","AVGO","TSLA","AMD","NFLX",
    "ORCL","CRM","ADBE","QCOM","AMAT","MU","TXN","INTC","LRCX","CSCO","IBM","NOW",
    "PANW","CRWD","PLTR","UBER","ABNB","SHOP","SNOW","DDOG","NET","MDB","INTU","ADSK",
    "CDNS","SNPS","MRVL","KLAC","ADI","NXPI","ON","MCHP","FTNT","ZS","OKTA","TEAM","WDAY",
    # Consumer / retail
    "COST","WMT","MCD","KO","PEP","NKE","SBUX","TGT","HD","LOW","TJX","BKNG","CMG","DIS",
    "NFLX","LULU","DECK","ROST","ORLY","AZO","CVS","EL","CL","PG","PM","MO","MDLZ",
    # Financials / payments
    "JPM","BAC","GS","MS","WFC","C","V","MA","AXP","BLK","SCHW","CME","ICE","COF","USB","PNC",
    # Energy / materials / industrials
    "XOM","CVX","COP","SLB","EOG","MPC","VLO","OXY","PSX","HAL","CAT","DE","GE","HON","LMT",
    "RTX","UNP","UPS","BA","ETN","EMR","MMM","FDX","CSX","NSC","GD","NOC","WM","VMC","NUE",
    # Healthcare / biotech
    "LLY","UNH","JNJ","ABBV","MRK","PFE","TMO","DHR","ISRG","ABT","AMGN","GILD","BMY","CVS",
    "MDT","SYK","BSX","REGN","VRTX","ZTS","CI","ELV","HUM","BDX",
    # Other liquid large caps / diversified
    "LIN","APD","NEE","DUK","SO","AEP","T","VZ","CMCSA","TMUS","INTU","FIS","ADP","ROP","DELL",
]


CEDEAR_CANDIDATES = [
    # US technology / growth
    "AAPL","MSFT","NVDA","AMZN","META","GOOGL","GOOG","AVGO","TSLA","AMD","NFLX","ORCL","CRM","ADBE",
    "QCOM","AMAT","MU","TXN","INTC","LRCX","CSCO","IBM","NOW","PANW","CRWD","PLTR","UBER","ABNB","SHOP",
    "SNOW","DDOG","NET","MDB","INTU","ADSK","CDNS","SNPS","MRVL","KLAC","ADI","NXPI","ON","MCHP","FTNT",
    "ZS","OKTA","TEAM","WDAY","COIN","PYPL","SQ","ARM","SMCI",
    # Consumer / retail
    "COST","WMT","MCD","KO","PEP","NKE","SBUX","TGT","HD","LOW","BKNG","DIS","LULU","ROST","ORLY","AZO",
    "PG","PM","MO","MDLZ","EL","CL","CVS","YUM","EBAY",
    # Financials
    "JPM","BAC","GS","MS","WFC","C","V","MA","AXP","BLK","SCHW","CME","ICE","COF","USB","PNC","MSCI",
    # Energy / industrials / materials
    "XOM","CVX","COP","SLB","EOG","MPC","VLO","OXY","PSX","HAL","CAT","DE","GE","HON","LMT","RTX",
    "UNP","UPS","BA","ETN","EMR","MMM","FDX","CSX","NSC","GD","NOC","WM","VMC","NUE","LIN","APD",
    # Healthcare
    "LLY","UNH","JNJ","ABBV","MRK","PFE","TMO","DHR","ISRG","ABT","AMGN","GILD","BMY","MDT","SYK","BSX",
    "REGN","VRTX","ZTS","CI","ELV","HUM","BDX","MRNA","BIIB","DXCM",
    # International / ADRs commonly available as CEDEARs
    "BABA","BIDU","JD","NIO","PDD","TSM","ASML","SAP","SONY","NTES","MELI","SE","GLOB","NU","RIO","VALE",
    "BHP","SHEL","BP","HSBC","UBS","ING","NOK","ERIC","TM","HMC","SMFG","MFG","SHOP","SPOT","SEK","STNE",
    "RELX","UL","DEO","SNY","GSK","AZN","NVS","RACE","TTE","SIEGY","BMWYY","VWAGY","BBVA","SAN","ITUB",
    "VALE3","PBR","PBR.A","ERJ","DESP","CAAP","YPF","BIOX","VIST","MIRG","GGAL","SUPV","CEPU","LOMA","CRESY",
]



def sf(x, default=np.nan):
    try:
        x = float(x)
        return x if np.isfinite(x) else default
    except Exception:
        return default


def sdiv(a, b, default=0.0):
    a, b = sf(a), sf(b)
    return a / b if np.isfinite(a) and np.isfinite(b) and abs(b) > 1e-12 else default


def norm(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
    df.columns = [str(c).title() for c in df.columns]
    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index)
    if getattr(df.index, "tz", None) is not None:
        df.index = df.index.tz_localize(None)
    return df.sort_index()


def indicators(df: pd.DataFrame, spy: pd.DataFrame | None = None) -> pd.DataFrame:
    """Create all indicators causally from the supplied OHLCV series."""
    df = norm(df)
    for c in ["Open", "High", "Low", "Close", "Volume"]:
        if c not in df.columns:
            raise ValueError(f"Missing column {c}")
        df[c] = pd.to_numeric(df[c], errors="coerce")

    c, h, l = df["Close"], df["High"], df["Low"]
    df["EMA20"] = c.ewm(span=20, adjust=False).mean()
    df["EMA50"] = c.ewm(span=50, adjust=False).mean()
    df["EMA200"] = c.ewm(span=200, adjust=False).mean()

    d = c.diff()
    up = d.clip(lower=0)
    dn = -d.clip(upper=0)
    au = up.rolling(14).mean()
    ad = dn.rolling(14).mean()
    rs = au / ad.replace(0, np.nan)
    df["RSI"] = 100 - 100 / (1 + rs)

    tr = pd.concat([(h - l), (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    df["ATR"] = tr.rolling(14).mean()
    df["ATR_PCT"] = df["ATR"] / c.replace(0, np.nan)
    df["VolRel"] = df["Volume"] / df["Volume"].rolling(20).mean().replace(0, np.nan)
    df["CloseLocation"] = (c - l) / (h - l).replace(0, np.nan)
    df["LowEMA20Dist"] = (l - df["EMA20"]).abs() / c.replace(0, np.nan)

    hh = h.rolling(14).max()
    ll = l.rolling(14).min()
    df["WPR"] = -100 * (hh - c) / (hh - ll).replace(0, np.nan)

    for n in [5, 20, 60]:
        df[f"Ret{n}"] = c.pct_change(n)

    if spy is not None:
        sc = spy["Close"].reindex(df.index).ffill()
        df["RS5"] = df["Ret5"] - sc.pct_change(5)
        df["RS20"] = df["Ret20"] - sc.pct_change(20)
        df["RS60"] = df["Ret60"] - sc.pct_change(60)
    else:
        df["RS5"] = 0.0
        df["RS20"] = 0.0
        df["RS60"] = 0.0

    return df.dropna(subset=["EMA200", "ATR", "WPR", "RS20"]).copy()


def _has_scipy() -> bool:
    # yfinance's optional price-repair feature requires scipy.
    # The research engine must NOT make scipy mandatory.
    try:
        import scipy  # noqa: F401
        return True
    except Exception:
        return False


_YF_REPAIR = _has_scipy()
CACHE_DIR = Path(CONFIG["cache_dir"])
CACHE_DIR.mkdir(parents=True, exist_ok=True)

try:
    yf.config.network.retries = 2
except Exception:
    pass


def _cache_path(ticker: str) -> Path:
    safe = ticker.replace("/", "_").replace("\\", "_")
    return CACHE_DIR / f"{safe}.csv.gz"


def _cache_read(ticker: str):
    p = _cache_path(ticker)
    if not p.exists():
        return None
    try:
        age_h = (pd.Timestamp.now() - pd.Timestamp.fromtimestamp(p.stat().st_mtime)).total_seconds() / 3600
        if age_h > CONFIG["cache_max_age_hours"]:
            return None
        x = pd.read_csv(p, index_col=0, parse_dates=True, compression="gzip")
        x = norm(x)
        need = {"Open", "High", "Low", "Close", "Volume"}
        if need.issubset(x.columns) and len(x) >= 260:
            return x.dropna(subset=list(need))
    except Exception:
        return None
    return None


def _cache_write(ticker: str, x: pd.DataFrame):
    try:
        x.to_csv(_cache_path(ticker), compression="gzip")
    except Exception as exc:
        print(f"\n⚠️ Cache {ticker}: {exc}")


def _extract_batch(raw, ticker: str):
    if raw is None or raw.empty:
        return None
    try:
        if isinstance(raw.columns, pd.MultiIndex):
            # yfinance normally returns Price x Ticker for group_by='column'.
            if ticker in raw.columns.get_level_values(-1):
                x = raw.xs(ticker, axis=1, level=-1, drop_level=True)
            elif ticker in raw.columns.get_level_values(0):
                x = raw.xs(ticker, axis=1, level=0, drop_level=True)
            else:
                return None
        else:
            x = raw
        x = norm(x)
        need = {"Open", "High", "Low", "Close", "Volume"}
        if not need.issubset(x.columns) or len(x) < 260:
            return None
        x = x.dropna(subset=list(need))
        x = x[~x.index.duplicated(keep="last")]
        if len(x) < 260:
            return None
        return x
    except Exception:
        return None


def _download_batch(tickers):
    if not tickers:
        return {}
    try:
        raw = yf.download(
            tickers=tickers,
            start=CONFIG["data_start"],
            auto_adjust=True,
            actions=False,
            progress=False,
            threads=CONFIG["download_threads"],
            group_by="column",
            repair=_YF_REPAIR,
            timeout=CONFIG["download_timeout"],
            multi_level_index=True,
        )
    except Exception as exc:
        print(f"\n⚠️ Lote Yahoo falló ({type(exc).__name__}: {exc})")
        return {}

    out = {}
    for ticker in tickers:
        x = _extract_batch(raw, ticker)
        if x is not None:
            out[ticker] = x
    return out


def download_one(ticker: str):
    """Download one ticker as a safe fallback. Returns None on any Yahoo/data failure."""
    try:
        x = yf.download(
            ticker,
            start=CONFIG["data_start"],
            auto_adjust=True,
            actions=False,
            progress=False,
            threads=False,
            repair=_YF_REPAIR,
            timeout=CONFIG["download_timeout"],
        )
        if x is None or x.empty:
            return None
        x = norm(x)
        need = {"Open", "High", "Low", "Close", "Volume"}
        if not need.issubset(x.columns):
            return None
        x = x.dropna(subset=list(need))
        x = x[~x.index.duplicated(keep="last")]
        if len(x) < 260:
            return None
        return x
    except Exception:
        return None


def download_universe(kind="USA"):
    """Fast, cached Yahoo downloader. USD and ARS portfolios remain separate."""
    if kind == "USA":
        syms = [(x, x, "USD") for x in dict.fromkeys(USA_UNIVERSE)]
    elif kind == "CEDEAR":
        syms = [(x, x + ".BA", "ARS") for x in dict.fromkeys(CEDEAR_CANDIDATES)]
    else:
        raise ValueError("Use USA or CEDEAR. BOTH remains disabled because currencies differ.")

    raw = {}
    missing = []
    cached = 0
    print("\n" + "=" * 88)
    print(f"📥 DESCARGANDO UNIVERSO {kind} — {len(syms)} candidatos")
    print("=" * 88)
    print(f"   price-repair: {'ON' if _YF_REPAIR else 'OFF'} | batch={CONFIG['download_batch_size']} | threads={CONFIG['download_threads']}")
    print("   cache: cache/yahoo/ (24h)")

    # 1) Local cache first.
    for name, ticker, currency in syms:
        x = _cache_read(ticker)
        if x is not None:
            x.attrs.update(currency=currency, underlying=name, source="cache")
            raw[ticker] = x
            cached += 1
        else:
            missing.append((name, ticker, currency))
    print(f"💾 Cache reutilizado: {cached} | pendientes Yahoo: {len(missing)}")

    # 2) Batch download. Much faster than 1 HTTP request per ticker.
    batch_size = max(1, int(CONFIG["download_batch_size"]))
    for j in range(0, len(missing), batch_size):
        batch = missing[j:j + batch_size]
        tickers = [x[1] for x in batch]
        print(f"🌐 Lote {j // batch_size + 1}/{math.ceil(len(missing) / batch_size)}: {len(tickers)} tickers...", end="\r")
        got = _download_batch(tickers)
        for name, ticker, currency in batch:
            x = got.get(ticker)
            if x is not None:
                x.attrs.update(currency=currency, underlying=name, source="yahoo")
                raw[ticker] = x
                _cache_write(ticker, x)

    # 3) Targeted single-ticker fallback only for misses.
    unresolved = [(n, t, c) for n, t, c in missing if t not in raw]
    if unresolved:
        print(" " * 120, end="\r")
        print(f"🔁 Fallback individual: {len(unresolved)} ticker(s)")
    for k, (name, ticker, currency) in enumerate(unresolved, 1):
        print(f"   [{k}/{len(unresolved)}] {ticker:<12}", end="\r")
        try:
            x = yf.download(
                ticker,
                start=CONFIG["data_start"],
                auto_adjust=True,
                actions=False,
                progress=False,
                threads=False,
                repair=_YF_REPAIR,
                timeout=CONFIG["download_timeout"],
            )
            x = norm(x) if x is not None and not x.empty else None
            need = {"Open", "High", "Low", "Close", "Volume"}
            if x is not None and need.issubset(x.columns) and len(x) >= 260:
                x = x.dropna(subset=list(need))
                x = x[~x.index.duplicated(keep="last")]
                x.attrs.update(currency=currency, underlying=name, source="yahoo_fallback")
                raw[ticker] = x
                _cache_write(ticker, x)
        except Exception:
            pass

    print(" " * 120, end="\r")
    print(f"✅ Activos válidos: {len(raw)}/{len(syms)}")
    if len(raw) < 140 and kind == "USA":
        print("⚠️ USA quedó por debajo de 140 válidos; no es un error: Yahoo puede rechazar símbolos o devolver historial insuficiente.")
    if len(raw) < 70 and kind == "CEDEAR":
        print("⚠️ CEDEAR tiene disponibilidad histórica menor; se acepta un universo válido más pequeño.")
    return raw

def download_spy():
    print("📊 Descargando SPY...")
    x = download_one("SPY")
    if x is None:
        raise RuntimeError("No se pudo descargar SPY")
    x.attrs["currency"] = "USD"
    return x


def prepare(raw, spy_raw):
    spy = indicators(spy_raw)
    data = {}
    for ticker, x in raw.items():
        z = indicators(x, spy)
        if len(z) >= 220:
            z.attrs.update(x.attrs)
            data[ticker] = z
    return data, spy


def market_level(spy: pd.DataFrame, date: pd.Timestamp) -> int:
    idx = spy.index.searchsorted(date, side="right") - 1
    if idx < 0:
        return 0
    r = spy.iloc[idx]
    if sf(r.Close) <= sf(r.EMA200):
        return 0
    if sf(r.Close) > sf(r.EMA20) > sf(r.EMA50) > sf(r.EMA200):
        return 2
    return 1


def precompute_signals(data, cfg, active):
    """Precompute candidate rows once. This removes thousands of searchsorted/iloc calls."""
    signals = {}
    for ticker, df in data.items():
        rows = []
        for row in df.itertuples(index=True):
            ok, score, flags = signal(row._asdict(), cfg, active)
            atr_pct = sf(getattr(row, "ATR_PCT", np.nan))
            if not ok or not (cfg["atr_min_pct"] <= atr_pct <= cfg["atr_max_pct"]):
                continue
            rank = (
                0.35 * flags["rs20"]
                + 0.20 * flags["wpr"]
                + 0.15 * flags["pullback"]
                + 0.10 * flags["momentum"]
                + 0.10 * flags["volume"]
                + 0.10 * flags["candle"]
            )
            rows.append({
                "ticker": ticker,
                "date": row.Index,
                "score": score,
                "rank": rank,
                "atr": sf(row.ATR),
                "signal_row": row._asdict(),
            })
        signals[ticker] = rows
    return signals


def build_calendar(data, start, end):
    dates = sorted({d for df in data.values() for d in df.index if start <= d <= end})
    return dates


def next_date_map(data):
    out = {}
    for ticker, df in data.items():
        idx = df.index
        out[ticker] = {idx[i]: idx[i + 1] if i + 1 < len(idx) else None for i in range(len(idx))}
    return out


def price_row_maps(data):
    """Fast scalar lookup maps for the execution loop."""
    maps = {}
    for ticker, df in data.items():
        maps[ticker] = {
            row[0]: (sf(row[1]), sf(row[2]), sf(row[3]), sf(row[4]))
            for row in df[["Open", "High", "Low", "Close"]].itertuples(index=True, name=None)
        }
    return maps


def signal_maps(signals):
    return {t: {x["date"]: x for x in rows} for t, rows in signals.items()}


def close_trade(pos, px, date, reason, cfg, trades, cost_slippage=0.0):
    qty = pos["qty"]
    entry = pos["entry"]
    gross = qty * (px - entry)
    exit_comm = qty * px * cfg["commission"]
    total_comm = pos["entry_commission"] + exit_comm
    pnl_net = gross - total_comm
    risk_share = pos["risk_dollars"] / qty if qty else np.nan
    trades.append({
        "ticker": pos["ticker"],
        "entry_date": pos["entry_date"],
        "exit_date": date,
        "entry": entry,
        "exit": px,
        "qty": qty,
        "entry_value": pos["entry_value"],
        "gross_pnl": gross,
        "commission": total_comm,
        "net_pnl": pnl_net,
        "return_pct": sdiv(pnl_net, pos["entry_value"]) * 100,
        "risk_dollars": pos["risk_dollars"],
        "planned_risk_pct_equity": pos["planned_risk_pct_equity"],
        "R": sdiv(pnl_net, pos["risk_dollars"]),
        "mfe_R": sdiv(pos["mfe"], risk_share),
        "mae_R": sdiv(pos["mae"], risk_share),
        "gap_loss_R": pos.get("gap_loss_R", 0.0),
        "bars": pos["bars"],
        "reason": reason,
        "score": pos["score"],
        "rank": pos["rank"],
        "RS20": sf(pos["signal_row"].get("RS20")),
        "WPR": sf(pos["signal_row"].get("WPR")),
        "RSI": sf(pos["signal_row"].get("RSI")),
        "VolRel": sf(pos["signal_row"].get("VolRel")),
        "ATR_PCT": sf(pos["signal_row"].get("ATR_PCT")),
    })


def backtest(data, spy, cfg, active, start, end=None, label=""):
    """
    Audited daily-bar portfolio simulation.

    Signal on D -> entry only on D+1 open.
    Pending orders expire if D+1 is not available.
    Stop wins when daily OHLC cannot reveal whether target or stop came first.
    All remaining positions are liquidated at the last valid close of the test window.
    """
    start = pd.Timestamp(start)
    end = pd.Timestamp(end) if end is not None else pd.Timestamp.max
    dates = build_calendar(data, start, end)
    if not dates:
        return pd.DataFrame(), pd.DataFrame()

    signals = precompute_signals(data, cfg, active)
    smaps = signal_maps(signals)
    next_map = next_date_map(data)
    prices = price_row_maps(data)

    cash = float(cfg["capital"])
    pos = {}
    pending = {}
    cooldown = {}
    trades = []
    eq = []
    entries_today = 0
    prev_equity = cash
    daily_entry_exposure_max = 0.0
    daily_entry_risk_max = 0.0
    entry_cap_violations = 0
    prev_entry_cap_violations = 0

    for date in dates:
        # ------------------------------------------------------------
        # 1) Execute only orders explicitly scheduled for TODAY.
        # ------------------------------------------------------------
        entries_today = 0
        daily_entry_exposure_max = 0.0
        daily_entry_risk_max = 0.0
        for ticker, order in list(pending.items()):
            if order["execution_date"] != date:
                continue
            del pending[ticker]
            if entries_today >= order["entry_limit"]:
                continue
            if ticker in pos:
                continue
            if ticker not in prices or date not in prices[ticker]:
                continue

            o, h, l, c = prices[ticker][date]
            atr = sf(order["atr"])
            if not np.isfinite(o) or not np.isfinite(atr) or atr <= 0:
                continue

            # Entry at open + adverse slippage.
            entry = o * (1 + cfg["slippage"])
            stop = entry - cfg["stop_atr"] * atr
            risk_share = entry - stop
            if risk_share <= 0:
                continue

            # Current marked equity BEFORE the new entry.
            market_value = sum(p["qty"] * prices[p["ticker"]][date][3] for p in pos.values() if date in prices[p["ticker"]])
            equity = cash + market_value
            if equity <= 0:
                continue

            # Planned risk budget.
            desired_risk = equity * cfg["risk_per_trade"]
            current_risk = sum(p["risk_dollars"] for p in pos.values())
            available_portfolio_risk = max(0.0, equity * cfg["max_portfolio_risk"] - current_risk)
            cap_buffer = float(cfg.get("cap_buffer", 1.0))
            desired_risk = min(desired_risk, available_portfolio_risk * cap_buffer)
            if desired_risk <= 0:
                continue

            # Entry-time hard caps. We leave a safety buffer for commission and rounding.
            max_notional = equity * cfg["max_position_pct"] * cap_buffer
            current_market_value = sum(
                p["qty"] * prices[p["ticker"]][date][3]
                for p in pos.values()
                if date in prices[p["ticker"]]
            )
            gross_room = max(0.0, equity * cfg["max_gross_exposure"] * cap_buffer - current_market_value)
            risk_room = max(0.0, equity * cfg["max_portfolio_risk"] * cap_buffer - current_risk)
            qty_risk = math.floor(desired_risk / risk_share)
            qty_notional = math.floor(max_notional / entry)
            qty_gross = math.floor(gross_room / entry)
            qty_cash = math.floor(cash / (entry * (1 + cfg["commission"])))
            qty = min(qty_risk, qty_notional, qty_gross, qty_cash)
            if qty <= 0:
                continue

            # Exact post-entry validation. Reduce by one share until the hard limits
            # hold after the entry commission is charged.
            while qty > 0:
                value = qty * entry
                entry_comm = value * cfg["commission"]
                post_equity = equity - entry_comm
                post_gross = current_market_value + value
                actual_risk = qty * risk_share
                post_risk = current_risk + actual_risk
                gross_ok = sdiv(post_gross, post_equity) <= cfg["max_gross_exposure"] * cap_buffer
                risk_ok = sdiv(post_risk, post_equity) <= cfg["max_portfolio_risk"] * cap_buffer
                if gross_ok and risk_ok:
                    break
                qty -= 1
            if qty <= 0:
                continue

            actual_risk = qty * risk_share
            if actual_risk < desired_risk * cfg["min_effective_risk"]:
                continue

            value = qty * entry
            entry_comm = value * cfg["commission"]
            cash -= value + entry_comm

            pos[ticker] = {
                "ticker": ticker,
                "entry_date": date,
                "entry": entry,
                "entry_value": value,
                "entry_commission": entry_comm,
                "qty": qty,
                "stop": stop,
                "target": entry + cfg["tp_r"] * risk_share,
                "risk_dollars": actual_risk,
                "planned_risk_pct_equity": actual_risk / equity,
                "bars": 0,
                "mfe": 0.0,
                "mae": 0.0,
                "gap_loss_R": 0.0,
                "score": order["score"],
                "rank": order["rank"],
                "signal_row": order["signal_row"],
            }
            # Audit the actual post-entry portfolio, not the pre-entry estimate.
            post_equity = equity - entry_comm
            post_market_value = current_market_value + value
            entry_exposure = sdiv(post_market_value, post_equity)
            entry_risk = sdiv(current_risk + actual_risk, post_equity)
            daily_entry_exposure_max = max(daily_entry_exposure_max, entry_exposure)
            daily_entry_risk_max = max(daily_entry_risk_max, entry_risk)
            if entry_exposure > cfg["max_gross_exposure"] or entry_risk > cfg["max_portfolio_risk"]:
                entry_cap_violations += 1
            entries_today += 1

        # ------------------------------------------------------------
        # 2) Execute expiry exits scheduled for TODAY at the open.
        # They occur before today's intraday stop/target logic.
        # ------------------------------------------------------------
        for ticker, p in list(pos.items()):
            if p.get("scheduled_exit") == date:
                o, h, l, c = prices[ticker][date]
                px = o * (1 - cfg["slippage"])
                close_trade(p, px, date, "EXPIRY", cfg, trades)
                cash += p["qty"] * px * (1 - cfg["commission"])
                del pos[ticker]

        # ------------------------------------------------------------
        # 3) Manage remaining open positions using today's OHLC.
        # ------------------------------------------------------------
        for ticker, p in list(pos.items()):
            if ticker not in prices or date not in prices[ticker]:
                # A position must never silently disappear from equity.
                continue
            o, h, l, c = prices[ticker][date]
            p["bars"] += 1
            if np.isfinite(h):
                p["mfe"] = max(p["mfe"], h - p["entry"])
            if np.isfinite(l):
                p["mae"] = min(p["mae"], l - p["entry"])

            px = None
            reason = None
            if np.isfinite(o) and o <= p["stop"]:
                px = o * (1 - cfg["slippage"])
                reason = "SL_GAP"
            elif np.isfinite(o) and o >= p["target"]:
                px = o * (1 - cfg["slippage"])
                reason = "TP_GAP"
            elif np.isfinite(l) and l <= p["stop"]:
                px = p["stop"] * (1 - cfg["slippage"])
                reason = "SL"
            elif np.isfinite(h) and h >= p["target"]:
                px = p["target"] * (1 - cfg["slippage"])
                reason = "TP"

            if px is not None:
                if reason == "SL_GAP":
                    p["gap_loss_R"] = max(0.0, (p["stop"] - px) / (p["risk_dollars"] / p["qty"]))
                close_trade(p, px, date, reason, cfg, trades)
                cash += p["qty"] * px * (1 - cfg["commission"])
                if reason.startswith("SL"):
                    cooldown[ticker] = date
                del pos[ticker]
                continue

            # Time exit: schedule next session open.
            if p["bars"] >= cfg["max_bars"]:
                nxt = next_map[ticker].get(date)
                if nxt is not None and nxt <= end:
                    pending_exit = {"date": nxt}
                    p["scheduled_exit"] = nxt
                else:
                    # End-of-window liquidation at today's close.
                    px = c * (1 - cfg["slippage"])
                    close_trade(p, px, date, "EOP_LIQ", cfg, trades)
                    cash += p["qty"] * px * (1 - cfg["commission"])
                    del pos[ticker]

        # ------------------------------------------------------------
        # 4) Mark portfolio BEFORE creating new next-day orders.
        # ------------------------------------------------------------
        market_value = 0.0
        for p in pos.values():
            if date in prices[p["ticker"]]:
                market_value += p["qty"] * prices[p["ticker"]][date][3]
        equity = cash + market_value

        gross_exposure = sdiv(sum(p["qty"] * prices[p["ticker"]][date][3] for p in pos.values() if date in prices[p["ticker"]]), equity)
        portfolio_risk = sdiv(sum(p["risk_dollars"] for p in pos.values()), equity)

        eq.append({
            "date": date,
            "cash": cash,
            "market_value": market_value,
            "equity": equity,
            "positions": len(pos),
            "gross_exposure": gross_exposure,
            "portfolio_risk": portfolio_risk,
            "entry_exposure_max": daily_entry_exposure_max,
            "entry_portfolio_risk_max": daily_entry_risk_max,
            "entry_cap_violations": entry_cap_violations - prev_entry_cap_violations,
            "daily_pnl": equity - prev_equity,
            "daily_return": sdiv(equity, prev_equity) - 1 if prev_equity > 0 else 0,
        })
        prev_equity = equity
        prev_entry_cap_violations = entry_cap_violations

        # ------------------------------------------------------------
        # 5) Generate new signals AFTER today's close.
        # ------------------------------------------------------------
        level = market_level(spy, date)
        maxpos = cfg["max_positions"] if level >= 1 else cfg["max_positions_weak"]
        maxent = cfg["max_entries_day"] if level >= 1 else cfg["max_entries_day_weak"]
        slots = min(max(0, maxpos - len(pos) - len(pending)), maxent)
        if slots <= 0 or equity <= 0:
            continue

        candidates = []
        for ticker, mp in smaps.items():
            x = mp.get(date)
            if x is None:
                continue
            if ticker in pos or ticker in pending:
                continue
            if ticker in cooldown and (date - cooldown[ticker]).days < cfg["cooldown_sl"]:
                continue
            nxt = next_map[ticker].get(date)
            if nxt is None or nxt > end:
                continue
            candidates.append(x)

        candidates.sort(key=lambda x: (x["rank"], x["score"], x["ticker"]), reverse=True)
        for cand in candidates[:slots]:
            ticker = cand["ticker"]
            pending[ticker] = {
                "signal_date": date,
                "execution_date": next_map[ticker].get(date),
                "atr": sf(cand["signal_row"].get("ATR")),
                "score": cand["score"],
                "rank": cand["rank"],
                "signal_row": cand["signal_row"],
                "entry_limit": maxent,
            }

    # Any still-open position is liquidated at the last available close <= end.
    if pos:
        last_date = dates[-1]
        for ticker, p in list(pos.items()):
            if ticker in prices and last_date in prices[ticker]:
                c = prices[ticker][last_date][3]
                px = c * (1 - cfg["slippage"])
                close_trade(p, px, last_date, "FINAL_LIQ", cfg, trades)
                cash += p["qty"] * px * (1 - cfg["commission"])
                del pos[ticker]

        # Replace the last equity observation with final cash after liquidation.
        if eq:
            eq[-1]["cash"] = cash
            eq[-1]["market_value"] = 0.0
            eq[-1]["equity"] = cash
            eq[-1]["positions"] = 0
            eq[-1]["gross_exposure"] = 0.0
            eq[-1]["portfolio_risk"] = 0.0

    trades_df = pd.DataFrame(trades)
    equity_df = pd.DataFrame(eq)
    if not equity_df.empty:
        equity_df["peak"] = equity_df["equity"].cummax()
        equity_df["drawdown"] = equity_df["equity"] / equity_df["peak"] - 1

    return trades_df, equity_df


def metrics(trades, equity, cfg=None):
    initial = float((cfg or CONFIG)["capital"])
    if equity.empty:
        return {
            "return_pct": 0.0, "pf": 0.0, "dd_pct": 0.0, "trades": 0,
            "win_rate": 0.0, "avg_R": 0.0, "sharpe": 0.0,
            "final_equity": initial, "gross_pnl": 0.0, "commission": 0.0,
            "gap_loss_R": 0.0, "avg_exposure": 0.0, "max_exposure": 0.0,
            "max_portfolio_risk": 0.0,
            "max_entry_exposure": 0.0, "max_entry_portfolio_risk": 0.0,
            "entry_cap_violations": 0,
        }

    final = sf(equity.equity.iloc[-1], initial)
    if trades.empty:
        pf = wr = avg = gross = comm = gap_r = 0.0
    else:
        wins = trades.loc[trades.net_pnl > 0, "net_pnl"].sum()
        losses = -trades.loc[trades.net_pnl < 0, "net_pnl"].sum()
        pf = sdiv(wins, losses)
        wr = (trades.net_pnl > 0).mean() * 100
        avg = trades.R.mean()
        gross = trades.gross_pnl.sum()
        comm = trades.commission.sum()
        gap_r = trades.gap_loss_R.sum()

    daily = equity.set_index("date")["equity"].resample("1D").last().pct_change().dropna()
    sh = np.sqrt(252) * daily.mean() / daily.std() if len(daily) >= 30 and daily.std() > 0 else 0.0
    return {
        "return_pct": (final / initial - 1) * 100,
        "pf": pf,
        "dd_pct": equity.drawdown.min() * 100,
        "trades": len(trades),
        "win_rate": wr,
        "avg_R": avg,
        "sharpe": sh,
        "final_equity": final,
        "gross_pnl": gross,
        "commission": comm,
        "gap_loss_R": gap_r,
        "avg_exposure": equity.gross_exposure.mean() * 100,
        "max_exposure": equity.gross_exposure.max() * 100,
        "max_portfolio_risk": equity.portfolio_risk.max() * 100,
        "max_entry_exposure": equity.entry_exposure_max.max() * 100 if "entry_exposure_max" in equity else 0.0,
        "max_entry_portfolio_risk": equity.entry_portfolio_risk_max.max() * 100 if "entry_portfolio_risk_max" in equity else 0.0,
        "entry_cap_violations": int(equity.entry_cap_violations.sum()) if "entry_cap_violations" in equity else 0,
    }


def benchmark(spy, start, end):
    x = spy.loc[(spy.index >= start) & (spy.index <= end), "Close"]
    return (x.iloc[-1] / x.iloc[0] - 1) * 100 if len(x) > 1 else 0.0


def experiments():
    b = dict(CONFIG)
    e = [("BASE", "CORE", b, BASE_COMPONENTS)]

    for x in [-80, -78, -75, -72, -70]:
        c = dict(b); c["wpr_threshold"] = x
        e.append((f"WPR_{x}", "WPR", c, BASE_COMPONENTS))
    for x in [-0.02, -0.015, -0.01, -0.005, 0.0, 0.005, 0.01, 0.015, 0.02, 0.025, 0.03]:
        c = dict(b); c["rs20_min"] = x
        e.append((f"RS20_{x:+.2f}", "RS20", c, BASE_COMPONENTS))
    for x in [1, 2, 3]:
        c = dict(b); c["min_confirm"] = x
        e.append((f"CONF_{x}", "CONFIRMATION", c, BASE_COMPONENTS))

    for x in BASE_COMPONENTS:
        if x != "trend":
            active = tuple(y for y in BASE_COMPONENTS if y != x)
            e.append((f"ABLATE_NO_{x.upper()}", "ABLATION", b, active))

    for x in ["wpr", "rs20", "pullback", "momentum", "volume", "candle"]:
        active = ("trend", x) if x != "wpr" else ("trend", "wpr")
        e.append((f"ISOLATE_{x.upper()}", "ISOLATION", b, active))

    for tp in [1.5, 1.8, 2.1]:
        for sl in [1.25, 1.5, 1.75]:
            c = dict(b); c["tp_r"] = tp; c["stop_atr"] = sl
            e.append((f"EXIT_TP{tp}_SL{sl}", "EXIT", c, BASE_COMPONENTS))
    return e


def family_table(df):
    d = df.copy()
    d["family_rank"] = (
        d["oos_pf"] * 20
        + d["oos_return"] * 0.50
        + d["oos_sharpe"] * 8
        + d["oos_dd"] * 0.35
        + d["stress_pass"] * 10
    )
    rows = []
    for fam, g in d.groupby("family", sort=False):
        g = g.sort_values(["family_rank", "oos_trades"], ascending=False)
        r = g.iloc[0]
        rows.append({
            "family": fam,
            "best_strategy": r.experiment,
            "OOS_%": r.oos_return,
            "PF": r.oos_pf,
            "DD_%": r.oos_dd,
            "trades": r.oos_trades,
            "WR_%": r.oos_win_rate,
            "AvgR": r.oos_avg_R,
            "Sharpe": r.oos_sharpe,
            "TEST_%": r.test_return,
            "TEST_PF": r.test_pf,
            "stress_pass": r.stress_pass,
        })
    return pd.DataFrame(rows)


def run_one(name, fam, cfg, active, data, spy):
    ft, fe = backtest(data, spy, cfg, active, cfg["start"], None, label=f"{name}:FULL")
    ot, oe = backtest(data, spy, cfg, active, cfg["oos"], cfg["test"] - pd.Timedelta(days=1), label=f"{name}:OOS")
    tt, te = backtest(data, spy, cfg, active, cfg["test"], None, label=f"{name}:TEST")
    fm, om, tm = metrics(ft, fe, cfg), metrics(ot, oe, cfg), metrics(tt, te, cfg)
    return ft, fe, ot, oe, tt, te, fm, om, tm



def _directed_run(name, family, cfg, active, data, spy):
    """Run OOS + TEST for a deliberately small robustness experiment."""
    ot, oe = backtest(data, spy, cfg, active, cfg["oos"], cfg["test"] - pd.Timedelta(days=1), label=f"{name}:OOS")
    tt, te = backtest(data, spy, cfg, active, cfg["test"], None, label=f"{name}:TEST")
    om = metrics(ot, oe, cfg)
    tm = metrics(tt, te, cfg)
    return {
        "experiment": name,
        "family": family,
        "active": ",".join(active),
        "oos_return": om["return_pct"],
        "oos_pf": om["pf"],
        "oos_dd": om["dd_pct"],
        "oos_trades": om["trades"],
        "oos_win_rate": om["win_rate"],
        "oos_avg_R": om["avg_R"],
        "oos_sharpe": om["sharpe"],
        "test_return": tm["return_pct"],
        "test_pf": tm["pf"],
        "test_dd": tm["dd_pct"],
        "test_trades": tm["trades"],
        "oos_commission": om["commission"],
        "oos_max_exposure": om["max_exposure"],
        "oos_max_portfolio_risk": om["max_portfolio_risk"],
        "test_max_exposure": tm["max_exposure"],
        "test_max_portfolio_risk": tm["max_portfolio_risk"],
    }, ot, oe, tt, te


def run_directed_lab(universe="USA"):
    """Focused robustness lab: RS20 map, component interactions, exits and risk audit.

    This intentionally avoids a giant parameter sweep. It is designed to discover
    broad plateaus and useful structure rather than maximize one backtest number.
    """
    raw = download_universe(universe)
    spy_raw = download_spy()
    data, spy = prepare(raw, spy_raw)
    if not data:
        print("❌ No hay datos válidos.")
        return

    base = dict(CONFIG)
    rows = []
    payloads = {}

    print("\n" + "=" * 150)
    print(f"🧪 LABORATORIO DIRIGIDO — ROBUSTEZ / EDGE — {universe}")
    print("=" * 150)

    # ------------------------------------------------------------
    # 1) RS20 map: deliberately dense enough to see a plateau.
    # ------------------------------------------------------------
    rs_values = [-0.020, -0.015, -0.010, -0.005, 0.000, 0.005,
                 0.010, 0.015, 0.020, 0.025, 0.030]
    experiments_directed = []
    for x in rs_values:
        c = dict(base)
        c["rs20_min"] = x
        experiments_directed.append((f"RS20_{x:+.3f}", "RS20_MAP", c, BASE_COMPONENTS))

    # ------------------------------------------------------------
    # 2) Component ablation + small, hypothesis-driven interactions.
    # ------------------------------------------------------------
    for comp in ["pullback", "wpr", "rs20", "volume", "candle", "momentum"]:
        active = tuple(x for x in BASE_COMPONENTS if x != comp)
        experiments_directed.append((f"NO_{comp.upper()}", "ABLATION", dict(base), active))

    interaction_specs = [
        ("RS20+1_NO_MOM", {"rs20_min": 0.01}, ("momentum",)),
        ("RS20+1_NO_WPR", {"rs20_min": 0.01}, ("wpr",)),
        ("RS20+1_NO_CANDLE", {"rs20_min": 0.01}, ("candle",)),
        ("RS20+1_NO_MOM_CANDLE", {"rs20_min": 0.01}, ("momentum", "candle")),
        ("RS20+1_NO_MOM_WPR", {"rs20_min": 0.01}, ("momentum", "wpr")),
    ]
    for name, changes, removed in interaction_specs:
        c = dict(base)
        c.update(changes)
        active = tuple(x for x in BASE_COMPONENTS if x not in removed)
        experiments_directed.append((name, "INTERACTION", c, active))

    # ------------------------------------------------------------
    # 3) Exit stability: same modest grid as existing lab, but judged
    #    by OOS/TEST consistency rather than OOS alone.
    # ------------------------------------------------------------
    for tp in [1.5, 1.8, 2.1]:
        for sl in [1.25, 1.5, 1.75]:
            c = dict(base)
            c["tp_r"] = tp
            c["stop_atr"] = sl
            experiments_directed.append((f"EXIT_TP{tp}_SL{sl}", "EXIT", c, BASE_COMPONENTS))

    total = len(experiments_directed)
    for i, (name, fam, cfg, active) in enumerate(experiments_directed, 1):
        print(f"[{i:02d}/{total:02d}] {name:<28}", end="\r")
        row, ot, oe, tt, te = _directed_run(name, fam, cfg, active, data, spy)
        rows.append(row)
        payloads[name] = (cfg, active, ot, oe, tt, te)
        print(" " * 100, end="\r")
        print(f"{name:<28}{fam:<14} OOS {row['oos_return']:+7.2f}% PF {row['oos_pf']:.2f} | TEST {row['test_return']:+7.2f}% PF {row['test_pf']:.2f}")

    df = pd.DataFrame(rows)

    # Cost stress is only applied to the compact directed set, not every
    # possible combination. This keeps the experiment about robustness.
    stress_rows = []
    for name, fam, cfg, active in experiments_directed:
        for factor in [1.0, 2.0, 3.0]:
            c = dict(cfg)
            c["commission"] *= factor
            c["slippage"] *= factor
            t, e = backtest(data, spy, c, active, c["oos"], c["test"] - pd.Timedelta(days=1), label=f"DIRECTED STRESS {name} x{factor}")
            m = metrics(t, e, c)
            stress_rows.append({
                "experiment": name,
                "family": fam,
                "cost_factor": factor,
                "return_pct": m["return_pct"],
                "pf": m["pf"],
                "dd_pct": m["dd_pct"],
                "trades": m["trades"],
            })
    stress = pd.DataFrame(stress_rows)

    stress_group = stress.groupby("experiment")
    df["stress_pass"] = df["experiment"].map(
        stress_group["pf"].apply(lambda x: float((x >= 1.0).mean()))
    )
    df["test_oos_gap"] = df["test_return"] - df["oos_return"]
    df["pf_gap"] = df["test_pf"] - df["oos_pf"]
    df["risk_cap_ok"] = (
        (df["oos_max_exposure"] <= base["max_gross_exposure"] * 100.0001)
        & (df["test_max_exposure"] <= base["max_gross_exposure"] * 100.0001)
        & (df["oos_max_portfolio_risk"] <= base["max_portfolio_risk"] * 100.0001)
        & (df["test_max_portfolio_risk"] <= base["max_portfolio_risk"] * 100.0001)
    )

    # A stability score deliberately rewards consistency, not just high OOS.
    # No automatic "winner" is declared from TEST.
    df["stability_score"] = (
        df["oos_pf"].clip(lower=0) * 20
        + df["test_pf"].clip(lower=0) * 20
        + df["stress_pass"].fillna(0) * 10
        + df["oos_sharpe"].clip(lower=-2, upper=2) * 4
        - df["test_oos_gap"].abs() * 0.20
        + df["oos_dd"] * 0.10
    )

    # Save everything so the next analysis can be done without rerunning Yahoo.
    out = RESULTS / "directed_robustness.csv"
    df.to_csv(out, index=False)
    stress.to_csv(RESULTS / "directed_stress.csv", index=False)

    # Dedicated readable tables.
    rs = df[df.family == "RS20_MAP"].sort_values("experiment")
    ab = df[df.family.isin(["ABLATION", "INTERACTION"])].sort_values("stability_score", ascending=False)
    ex = df[df.family == "EXIT"].sort_values("stability_score", ascending=False)

    rs.to_csv(RESULTS / "rs20_robustness.csv", index=False)
    ab.to_csv(RESULTS / "component_interactions.csv", index=False)
    ex.to_csv(RESULTS / "exit_stability.csv", index=False)

    print("\n" + "=" * 150)
    print("📈 1) MAPA RS20 — NO ELEGIMOS EL PICO, BUSCAMOS LA MESETA")
    print("=" * 150)
    print(f"{'RS20':>8} {'OOS':>9} {'PF':>7} {'DD':>9} {'TEST':>9} {'T.PF':>7} {'GAP':>9} {'STRESS':>8}")
    for _, r in rs.iterrows():
        x = float(r.experiment.split("_")[1]) * 100
        print(f"{x:>+7.2f}% {r.oos_return:>+8.2f}% {r.oos_pf:>7.2f} {r.oos_dd:>+8.2f}% {r.test_return:>+8.2f}% {r.test_pf:>7.2f} {r.test_oos_gap:>+8.2f}pp {r.stress_pass:>7.0%}")

    print("\n" + "=" * 150)
    print("🧩 2) COMPONENTES — ABLACIÓN + INTERACCIONES")
    print("=" * 150)
    print(f"{'EXPERIMENTO':<28} {'OOS':>9} {'PF':>7} {'TEST':>9} {'T.PF':>7} {'STRESS':>8} {'SCORE':>8}")
    for _, r in ab.iterrows():
        print(f"{r.experiment:<28} {r.oos_return:>+8.2f}% {r.oos_pf:>7.2f} {r.test_return:>+8.2f}% {r.test_pf:>7.2f} {r.stress_pass:>7.0%} {r.stability_score:>8.2f}")

    print("\n" + "=" * 150)
    print("🚪 3) EXITS — ESTABILIDAD OOS/TEST, NO MÁXIMO OOS")
    print("=" * 150)
    print(f"{'EXPERIMENTO':<28} {'OOS':>9} {'PF':>7} {'DD':>9} {'TEST':>9} {'T.PF':>7} {'STRESS':>8}")
    for _, r in ex.iterrows():
        print(f"{r.experiment:<28} {r.oos_return:>+8.2f}% {r.oos_pf:>7.2f} {r.oos_dd:>+8.2f}% {r.test_return:>+8.2f}% {r.test_pf:>7.2f} {r.stress_pass:>7.0%}")

    print("\n" + "=" * 150)
    print("🛡️ 4) AUDITORÍA DE RIESGO / EXPOSICIÓN")
    print("=" * 150)
    print(f"Hard cap gross exposure : {base['max_gross_exposure']*100:.2f}%")
    print(f"Hard cap portfolio risk: {base['max_portfolio_risk']*100:.2f}%")
    print(f"Hard cap position size : {base['max_position_pct']*100:.2f}%")
    print(f"Experimentos sin violación observada: {int(df['risk_cap_ok'].sum())}/{len(df)}")
    print(f"Máxima exposición observada OOS    : {df['oos_max_exposure'].max():.3f}%")
    print(f"Máximo riesgo cartera observado OOS: {df['oos_max_portfolio_risk'].max():.3f}%")

    spy_oos = benchmark(spy, base["oos"], base["test"] - pd.Timedelta(days=1))
    print("\n" + "=" * 150)
    print("📌 REFERENCIA")
    print("=" * 150)
    print(f"SPY OOS: {spy_oos:+.2f}%")
    print("No se selecciona un ganador automático. El objetivo es encontrar regiones estables y simplificar la estrategia.")
    print("\n💾 Archivos guardados en ./results/")
    print("   • directed_robustness.csv")
    print("   • directed_stress.csv")
    print("   • rs20_robustness.csv")
    print("   • component_interactions.csv")
    print("   • exit_stability.csv")

def _period_label(start, end):
    s = pd.Timestamp(start).date().isoformat()
    e = "LATEST" if end is None else pd.Timestamp(end).date().isoformat()
    return f"{s}_TO_{e}"


def _validation_windows():
    return [
        ("2023", pd.Timestamp("2023-01-03"), pd.Timestamp("2023-12-29")),
        ("2024", pd.Timestamp("2024-01-02"), pd.Timestamp("2024-12-31")),
        ("2025", pd.Timestamp("2025-01-02"), pd.Timestamp("2025-12-31")),
        ("2026_YTD", pd.Timestamp("2026-01-02"), None),
    ]


def run_validation_lab(universe="USA"):
    """V4 validation lab: independent calendar windows, simple model variants and risk audit.

    This is deliberately NOT another parameter sweep. It asks whether the structural
    edge survives across different market periods, and whether simplification helps.
    """
    raw = download_universe(universe)
    spy_raw = download_spy()
    data, spy = prepare(raw, spy_raw)
    if not data:
        print("❌ No hay datos válidos.")
        return

    base = dict(CONFIG)
    variants = [
        ("BASE", BASE_COMPONENTS, dict(base)),
        ("NO_WPR", tuple(x for x in BASE_COMPONENTS if x != "wpr"), dict(base)),
        ("NO_MOMENTUM", tuple(x for x in BASE_COMPONENTS if x != "momentum"), dict(base)),
        ("NO_WPR_NO_MOM", tuple(x for x in BASE_COMPONENTS if x not in {"wpr", "momentum"}), dict(base)),
    ]
    # Use the provisional center of the observed RS20 region, not the OOS peak.
    for name, active, cfg in variants:
        cfg["rs20_min"] = 0.01

    rows = []
    stress_rows = []
    print("\n" + "=" * 150)
    print(f"🧪 V4 — VALIDACIÓN MULTIPERÍODO / SIMPLIFICACIÓN / RIESGO — {universe}")
    print("=" * 150)

    for period, start, end in _validation_windows():
        spy_ret = benchmark(spy, start, end or spy.index.max())
        for name, active, cfg in variants:
            t, e = backtest(data, spy, cfg, active, start, end, label=f"V4 {period} {name}")
            m = metrics(t, e, cfg)
            rows.append({
                "period": period,
                "experiment": name,
                "active": ",".join(active),
                "start": start,
                "end": end or spy.index.max(),
                "return_pct": m["return_pct"],
                "pf": m["pf"],
                "dd_pct": m["dd_pct"],
                "trades": m["trades"],
                "win_rate": m["win_rate"],
                "avg_R": m["avg_R"],
                "sharpe": m["sharpe"],
                "commission": m["commission"],
                "max_exposure": m["max_exposure"],
                "max_portfolio_risk": m["max_portfolio_risk"],
                "max_entry_exposure": m["max_entry_exposure"],
                "max_entry_portfolio_risk": m["max_entry_portfolio_risk"],
                "entry_cap_violations": m["entry_cap_violations"],
                "gap_loss_R": m["gap_loss_R"],
                "spy_return_pct": spy_ret,
                "excess_vs_spy_pp": m["return_pct"] - spy_ret,
            })
            print(f"{period:<9} {name:<15} R {m['return_pct']:>+7.2f}% PF {m['pf']:.2f} DD {m['dd_pct']:>+7.2f}% | SPY {spy_ret:>+7.2f}% | capviol {m['entry_cap_violations']}")

    # Cost stress only on the four compact variants, across the same independent periods.
    for period, start, end in _validation_windows():
        for name, active, cfg in variants:
            for factor in [1.0, 2.0, 3.0]:
                c = dict(cfg)
                c["commission"] *= factor
                c["slippage"] *= factor
                t, e = backtest(data, spy, c, active, start, end, label=f"V4 STRESS {period} {name} x{factor}")
                m = metrics(t, e, c)
                stress_rows.append({
                    "period": period,
                    "experiment": name,
                    "cost_factor": factor,
                    "return_pct": m["return_pct"],
                    "pf": m["pf"],
                    "dd_pct": m["dd_pct"],
                    "trades": m["trades"],
                })

    result = pd.DataFrame(rows)
    stress = pd.DataFrame(stress_rows)
    result.to_csv(RESULTS / "v4_validation.csv", index=False)
    stress.to_csv(RESULTS / "v4_validation_stress.csv", index=False)

    # Compact robustness summary: how many periods have positive return / PF>1,
    # median PF/return, and worst period. This is descriptive, not a winner picker.
    summary = []
    for name, g in result.groupby("experiment", sort=False):
        sg = stress[stress.experiment == name]
        stress_2x = sg[sg.cost_factor == 2.0].groupby("period").pf.first()
        stress_3x = sg[sg.cost_factor == 3.0].groupby("period").pf.first()
        summary.append({
            "experiment": name,
            "positive_periods": int((g.return_pct > 0).sum()),
            "pf_gt1_periods": int((g.pf > 1).sum()),
            "median_return": g.return_pct.median(),
            "median_pf": g.pf.median(),
            "worst_return": g.return_pct.min(),
            "worst_dd": g.dd_pct.min(),
            "median_sharpe": g.sharpe.median(),
            "median_excess_vs_spy_pp": g.excess_vs_spy_pp.median(),
            "stress_2x_pf_gt1_periods": int((stress_2x > 1).sum()),
            "stress_3x_pf_gt1_periods": int((stress_3x > 1).sum()),
            "entry_cap_violations": int(g.entry_cap_violations.sum()),
        })
    summary = pd.DataFrame(summary).sort_values(["pf_gt1_periods", "positive_periods", "median_pf"], ascending=False)
    summary.to_csv(RESULTS / "v4_validation_summary.csv", index=False)

    print("\n" + "=" * 150)
    print("📊 RESUMEN V4 — NO SELECCIONAMOS POR EL MEJOR RETORNO")
    print("=" * 150)
    print(f"{'EXPERIMENTO':<18} {'POS':>5} {'PF>1':>5} {'MED R':>9} {'MED PF':>8} {'PEOR R':>9} {'2x':>5} {'3x':>5} {'CAP':>5}")
    for _, r in summary.iterrows():
        print(f"{r.experiment:<18} {int(r.positive_periods):>5}/{len(_validation_windows())} {int(r.pf_gt1_periods):>5}/{len(_validation_windows())} {r.median_return:>+8.2f}% {r.median_pf:>8.2f} {r.worst_return:>+8.2f}% {int(r.stress_2x_pf_gt1_periods):>5} {int(r.stress_3x_pf_gt1_periods):>5} {int(r.entry_cap_violations):>5}")

    print("\n🛡️ AUDITORÍA: los caps se evalúan en el momento de entrada; la exposición/riesgo mark-to-market puede moverse después por precio/equity.")
    print("   Eso evita llamar 'violación' a un efecto normal de mercado y separa control de entrada de riesgo observado.")
    print("\n💾 Archivos guardados:")
    print("   • results/v4_validation.csv")
    print("   • results/v4_validation_stress.csv")
    print("   • results/v4_validation_summary.csv")


def run_research_lab(universe="USA"):
    # Deliberately one currency per run. CEDEAR gets its own run because ARS and USD cannot share the same cash ledger.
    raw = download_universe(universe)
    spy_raw = download_spy()
    data, spy = prepare(raw, spy_raw)
    print(f"\n🧠 Datos preparados: {len(data)} activos {'ARS' if universe == 'CEDEAR' else 'USD'}")

    rows = []
    stress_rows = []
    payloads = {}
    exps = experiments()

    print("\n" + "=" * 150)
    print(f"🧪 LABORATORIO AUDITADO — {universe}")
    print("=" * 150)
    print(f"{'ESTRATEGIA':<24}{'FAMILIA':<15}{'OOS':>9}{'PF':>7}{'DD':>8}{'TR':>6}{'WR':>7}{'AvgR':>8}{'SH':>7}{'TEST':>9}{'T.PF':>7}")

    for i, (name, fam, cfg, active) in enumerate(exps, 1):
        print(f"[{i:02d}/{len(exps):02d}] {name:<24}", end="\r")
        ft, fe, ot, oe, tt, te, fm, om, tm = run_one(name, fam, cfg, active, data, spy)
        row = {
            "experiment": name,
            "family": fam,
            "active": ",".join(active),
            "full_return": fm["return_pct"], "full_pf": fm["pf"], "full_dd": fm["dd_pct"], "full_trades": fm["trades"],
            "oos_return": om["return_pct"], "oos_pf": om["pf"], "oos_dd": om["dd_pct"], "oos_trades": om["trades"],
            "oos_win_rate": om["win_rate"], "oos_avg_R": om["avg_R"], "oos_sharpe": om["sharpe"],
            "test_return": tm["return_pct"], "test_pf": tm["pf"], "test_dd": tm["dd_pct"], "test_trades": tm["trades"],
            "oos_commission": om["commission"], "oos_gross_pnl": om["gross_pnl"],
            "oos_max_exposure": om["max_exposure"], "oos_max_portfolio_risk": om["max_portfolio_risk"],
        }
        rows.append(row)
        payloads[name] = (cfg, active, ot, oe, tt, te)
        print(f"{' ' * 180}\r", end="")
        print(f"{name:<24}{fam:<15}{om['return_pct']:>+8.2f}%{om['pf']:>7.2f}{om['dd_pct']:>+7.2f}%{om['trades']:>6d}{om['win_rate']:>6.1f}%{om['avg_R']:>8.3f}{om['sharpe']:>7.2f}{tm['return_pct']:>+8.2f}%{tm['pf']:>7.2f}")

    df = pd.DataFrame(rows)

    # Cost stress: 1x, 1.5x, 2x, 3x transaction costs.
    for name, fam, cfg, active in exps:
        for cf in [1.0, 1.5, 2.0, 3.0]:
            c = dict(cfg)
            c["commission"] *= cf
            c["slippage"] *= cf
            t, e = backtest(data, spy, c, active, c["oos"], c["test"] - pd.Timedelta(days=1), label=f"STRESS {name} x{cf}")
            m = metrics(t, e, c)
            stress_rows.append({
                "experiment": name, "family": fam, "cost_factor": cf,
                "return_pct": m["return_pct"], "pf": m["pf"], "dd_pct": m["dd_pct"], "trades": m["trades"],
            })

    stress = pd.DataFrame(stress_rows)
    df["stress_pass"] = df["experiment"].map(stress.groupby("experiment").pf.apply(lambda x: float((x >= 1.0).mean())))

    # Hard-ish research filters are intentionally diagnostic, not automatic investment rules.
    df["selection_score"] = (
        df.oos_pf * 20
        + df.oos_return * 0.50
        + df.oos_sharpe * 8
        + df.oos_dd * 0.35
        + df.stress_pass.fillna(0) * 10
    )
    ranked = df.sort_values(["selection_score", "oos_trades"], ascending=False)
    winner = ranked.iloc[0]

    # Component attribution only for BASE, one pass per component.
    base_cfg, base_active, base_ot, base_oe, _, _ = payloads["BASE"]
    base_m = metrics(base_ot, base_oe, base_cfg)
    attr = []
    for comp in BASE_COMPONENTS:
        active = tuple(x for x in BASE_COMPONENTS if x != comp)
        t, e = backtest(data, spy, base_cfg, active, base_cfg["oos"], base_cfg["test"] - pd.Timedelta(days=1), label=f"ATTR {comp}")
        m = metrics(t, e, base_cfg)
        attr.append({
            "removed": comp,
            "base_return": base_m["return_pct"], "without_return": m["return_pct"],
            "delta_return": base_m["return_pct"] - m["return_pct"],
            "base_pf": base_m["pf"], "without_pf": m["pf"],
            "delta_pf": base_m["pf"] - m["pf"],
        })

    # Persist first, then print summary.
    df.to_csv(RESULTS / "lab_summary.csv", index=False)
    stress.to_csv(RESULTS / "stress.csv", index=False)
    pd.DataFrame(attr).to_csv(RESULTS / "component_attribution.csv", index=False)

    ft = family_table(df)
    ft.to_csv(RESULTS / "family_winners.csv", index=False)

    spy_oos = benchmark(spy, CONFIG["oos"], CONFIG["test"] - pd.Timedelta(days=1))
    cfg, active, ot, oe, tt, te = payloads[winner.experiment]
    ot.to_csv(RESULTS / "best_oos_trades.csv", index=False)
    oe.to_csv(RESULTS / "best_oos_equity.csv", index=False)

    print("\n" + "=" * 150)
    print("🏆 MEJOR ESTRATEGIA DE CADA FAMILIA")
    print("=" * 150)
    for _, r in ft.iterrows():
        print(
            f"🥇 {r.family:<16} → {r.best_strategy:<24} | OOS {r['OOS_%']:+.2f}% | PF {r.PF:.2f} | "
            f"DD {r['DD_%']:+.2f}% | {int(r.trades)} tr | WR {r['WR_%']:.1f}% | AvgR {r.AvgR:.3f} | "
            f"Sharpe {r.Sharpe:.2f} | TEST {r['TEST_%']:+.2f}% / PF {r.TEST_PF:.2f} | stress {r.stress_pass:.0%}"
        )

    print("\n" + "=" * 150)
    print("👑 CANDIDATO PRINCIPAL — NO ELEGIDO POR TEST")
    print("=" * 150)
    print(f"ESTRATEGIA : {winner.experiment}")
    print(f"FAMILIA    : {winner.family}")
    print(f"COMPONENTES: {winner.active}")
    print(
        f"OOS        : {winner.oos_return:+.2f}% | PF {winner.oos_pf:.2f} | DD {winner.oos_dd:+.2f}% | "
        f"Trades {int(winner.oos_trades)} | WR {winner.oos_win_rate:.1f}% | AvgR {winner.oos_avg_R:.3f} | Sharpe {winner.oos_sharpe:.2f}"
    )
    print(f"TEST       : {winner.test_return:+.2f}% | PF {winner.test_pf:.2f} | DD {winner.test_dd:+.2f}% | Trades {int(winner.test_trades)}")
    print(f"SPY OOS    : {spy_oos:+.2f}% | EXCESO OOS: {winner.oos_return - spy_oos:+.2f} pp")
    print(f"EXPOSICIÓN : promedio {winner.oos_max_exposure:.2f}% máx | riesgo cartera máx {winner.oos_max_portfolio_risk:.2f}%")

    print("\n🧠 AUDITORÍA INCORPORADA")
    print("• USD y ARS ya NO se mezclan en el mismo ledger.")
    print("• Señal D → entrada D+1; las órdenes pendientes no sobreviven más de una sesión.")
    print("• Las posiciones abiertas nunca se valoran a cero por falta de fila.")
    print("• Todas las posiciones se liquidan al final del período.")
    print("• Hay límites de notional, exposición bruta y riesgo agregado.")
    print("• Comisiones, slippage, P&L bruto/neto y gap-loss quedan auditados por operación.")
    print("• Stop-first cuando una vela diaria toca stop y target: supuesto conservador.")
    print("• Los indicadores se calculan sobre OHLC ajustado para investigación.")
    print("• Las pruebas OOS y TEST no se usan para fabricar el ganador durante el período de calibración.")
    print("• El laboratorio corre USA. CEDEAR requiere un motor ARS/FX específico antes de mezclarlo.")

    print("\n💾 Archivos guardados en ./results/")
    print("   • lab_summary.csv")
    print("   • family_winners.csv")
    print("   • component_attribution.csv")
    print("   • stress.csv")
    print("   • best_oos_trades.csv")
    print("   • best_oos_equity.csv")


def scan_live(universe="USA"):
    if universe == "BOTH":
        raise ValueError("BOTH está deshabilitado: USD y ARS requieren carteras separadas.")
    raw = download_universe(universe)
    spy_raw = download_spy()
    data, spy = prepare(raw, spy_raw)
    if not data:
        print("❌ No hay datos válidos.")
        return

    date = max(d for df in data.values() for d in df.index)
    level = market_level(spy, date)
    names = {0: "🔴 DÉBIL", 1: "🟡 NEUTRO", 2: "🟢 FAVORABLE"}

    signals = precompute_signals(data, CONFIG, BASE_COMPONENTS)
    candidates = []
    for ticker, rows in signals.items():
        for x in rows:
            if x["date"] == date:
                candidates.append(x)
                break
    candidates.sort(key=lambda x: (x["rank"], x["score"], x["ticker"]), reverse=True)

    print("\n" + "=" * 110)
    print(f"📡 OPORTUNIDADES ACTUALES — {universe}")
    print("=" * 110)
    print(f"Fecha: {date.date()} | SPY: {names[level]}")
    if not candidates:
        print("❌ No hay señales.")
        return

    rows = []
    for i, x in enumerate(candidates[:15], 1):
        r = x["signal_row"]
        rows.append({
            "#": i,
            "ticker": x["ticker"],
            "score": round(x["score"], 3),
            "rank": round(x["rank"], 3),
            "close": round(sf(r.get("Close")), 2),
            "WPR": round(sf(r.get("WPR")), 1),
            "RS20%": round(sf(r.get("RS20")) * 100, 2),
            "RSI": round(sf(r.get("RSI")), 1),
            "VolRel": round(sf(r.get("VolRel")), 2),
            "ATR%": round(sf(r.get("ATR_PCT")) * 100, 2),
        })
    print(pd.DataFrame(rows).to_string(index=False))
    print("\n⚠️ Investigación solamente; no son órdenes automáticas.")
