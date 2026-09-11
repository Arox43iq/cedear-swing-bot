"""
V11 LIVE DESK v4 — OPERACIONAL
===============================

Objetivo
--------
Una capa diaria para:
1) consultar las señales EXACTAS del V11 congelado;
2) analizar posiciones reales SIN mezclarlas con el forward científico;
3) mantener la cartera en un CSV editable;
4) guardar snapshots operativos en live/ (nunca en results/);
5) impedir que una señal vieja sea presentada como una entrada nueva.

NO modifica:
- results/
- v11_shadow_state
- v11_shadow_trades
- v11_shadow_equity
- parámetros del V11

Uso:
    py v11_live_desk_v4.py

Primera ejecución:
    crea live/portfolio_live.csv si no existe.

CSV:
    ticker,ba_ticker,qty,avg_cost_ars
"""

from __future__ import annotations

from pathlib import Path
from datetime import datetime
import json
import math

import numpy as np
import pandas as pd
import yfinance as yf

import research_engine as re
import v6_falsification_lab as v6


# =============================================================================
# PATHS — completamente separados del experimento
# =============================================================================

ROOT = Path(__file__).resolve().parent
LIVE_DIR = ROOT / "live"
PORTFOLIO_FILE = LIVE_DIR / "portfolio_live.csv"
SNAPSHOT_FILE = LIVE_DIR / "latest_snapshot.csv"
DECISION_FILE = LIVE_DIR / "latest_decisions.csv"
META_FILE = LIVE_DIR / "latest_meta.json"

DEFAULT_PORTFOLIO = [
    {"ticker": "AMZN",  "ba_ticker": "AMZN.BA",  "qty": 10, "avg_cost_ars": 2840.00},
    {"ticker": "AAPL",  "ba_ticker": "AAPL.BA",  "qty": 1,  "avg_cost_ars": 25940.00},
    {"ticker": "WMT",   "ba_ticker": "WMT.BA",   "qty": 2,  "avg_cost_ars": 9430.00},
    {"ticker": "SHOP",  "ba_ticker": "SHOP.BA",  "qty": 5,  "avg_cost_ars": 2114.16},
    {"ticker": "GOOGL", "ba_ticker": "GOOGL.BA", "qty": 1,  "avg_cost_ars": 9275.00},
]

COMPONENTS = ("trend", "pullback", "rs20", "volume", "candle")
FILTER_SPEC = {"atr_min": 0.030, "atr_max": 0.050, "volrel_min": 1.15}

FROZEN_OVERRIDES = {
    "rs20_min": 0.01,
    "tp_r": 1.8,
    "stop_atr": 1.5,
    "risk_per_trade": 0.005,
    "max_gross_exposure": 0.90,
    "max_portfolio_risk": 0.025,
    "commission": 0.0005,
    "slippage": 0.0005,
}


# =============================================================================
# PORTFOLIO
# =============================================================================

def ensure_live_dir():
    LIVE_DIR.mkdir(parents=True, exist_ok=True)


def ensure_portfolio():
    ensure_live_dir()
    if not PORTFOLIO_FILE.exists():
        pd.DataFrame(DEFAULT_PORTFOLIO).to_csv(PORTFOLIO_FILE, index=False)
        print(f"📝 Creado: {PORTFOLIO_FILE}")
        print("   Desde ahora actualizá ese CSV cuando cambie tu cartera.")


def load_portfolio():
    ensure_portfolio()
    p = pd.read_csv(PORTFOLIO_FILE)

    required = {"ticker", "ba_ticker", "qty", "avg_cost_ars"}
    missing = required - set(p.columns)
    if missing:
        raise ValueError(
            f"{PORTFOLIO_FILE.name} carece de columnas: {sorted(missing)}"
        )

    p["ticker"] = p["ticker"].astype(str).str.upper().str.strip()
    p["ba_ticker"] = p["ba_ticker"].astype(str).str.upper().str.strip()
    p["qty"] = pd.to_numeric(p["qty"], errors="coerce")
    p["avg_cost_ars"] = pd.to_numeric(p["avg_cost_ars"], errors="coerce")

    p = p.dropna(subset=["ticker", "ba_ticker", "qty", "avg_cost_ars"])
    p = p[(p["qty"] > 0) & (p["avg_cost_ars"] > 0)].copy()

    if p.empty:
        raise ValueError("portfolio_live.csv no contiene posiciones válidas.")

    return p


# =============================================================================
# EXACT V11
# =============================================================================

def frozen_cfg():
    c = dict(re.CONFIG)
    c.update(FROZEN_OVERRIDES)
    return c


def exact_v11_signals():
    """
    Misma ruta que research_engine.scan_live().
    Devuelve sólo señales de barras daily oficiales.
    """
    raw = re.download_universe("USA", force_refresh=True)
    spy_raw = re.download_spy()
    data, spy = re.prepare(raw, spy_raw)

    if not data:
        return None, {}, data, spy

    with v6._signal_filter_patch(FILTER_SPEC):
        signals = re.precompute_signals(data, frozen_cfg(), COMPONENTS)

    latest = max(d for df in data.values() for d in df.index)

    candidates = {}
    for ticker, rows in signals.items():
        for x in rows:
            if x["date"] == latest:
                candidates[ticker] = x
                break

    return pd.Timestamp(latest), candidates, data, spy


# =============================================================================
# MARKET DATA / PREVIEW
# =============================================================================

def normalize_index(x):
    x = x.copy()
    if isinstance(x.index, pd.DatetimeIndex):
        try:
            x.index = x.index.tz_localize(None)
        except TypeError:
            x.index = x.index.tz_convert(None)
        x.index = pd.to_datetime(x.index).normalize()
    return x[~x.index.duplicated(keep="last")].sort_index()


def history(ticker, period="1y"):
    try:
        x = yf.Ticker(ticker).history(
            period=period, interval="1d", auto_adjust=False
        )
    except Exception:
        return pd.DataFrame()

    if x is None or x.empty:
        return pd.DataFrame()

    x = normalize_index(x)
    wanted = [
        c for c in ["Open", "High", "Low", "Close", "Adj Close", "Volume"]
        if c in x.columns
    ]
    return x[wanted].copy()


def intraday_bar(ticker):
    """
    Barra provisional construida con 1m. Nunca se usa en exact_v11_signals().
    """
    try:
        x = yf.Ticker(ticker).history(
            period="1d", interval="1m", auto_adjust=False
        )
    except Exception:
        return None

    if x is None or x.empty or "Close" not in x.columns:
        return None

    x = x.dropna(subset=["Close"])
    if x.empty:
        return None

    day = x.index[-1].date()
    z = x[x.index.date == day]
    if z.empty:
        return None

    return {
        "date": pd.Timestamp(day),
        "Open": float(z["Open"].dropna().iloc[0]),
        "High": float(z["High"].max()),
        "Low": float(z["Low"].min()),
        "Close": float(z["Close"].dropna().iloc[-1]),
        "Adj Close": float(z["Close"].dropna().iloc[-1]),
        "Volume": float(z["Volume"].fillna(0).sum()),
    }


def official_plus_preview(ticker):
    d = history(ticker)
    if d.empty:
        return d, False

    official = d.dropna(subset=["Close"]).copy()
    pv = intraday_bar(ticker)
    if pv is None:
        return official, False

    pdate = pd.Timestamp(pv["date"]).normalize()
    last = official.index.max() if not official.empty else None

    if last is not None and pdate <= pd.Timestamp(last).normalize():
        return official, False

    row = pd.DataFrame([pv], index=[pdate])
    out = pd.concat([official, row])
    out = out[~out.index.duplicated(keep="last")].sort_index()
    return out, True


def last_ba_price(ticker):
    pv = intraday_bar(ticker)
    if pv is not None:
        return float(pv["Close"]), str(pv["date"].date()), "1m"

    d = history(ticker, "1mo")
    d = d.dropna(subset=["Close"]) if not d.empty else d
    if d.empty:
        return np.nan, "N/D", "N/D"

    return float(d["Close"].iloc[-1]), str(d.index[-1].date()), "daily"


# =============================================================================
# DIAGNOSTICS
# =============================================================================

def atr14(df):
    prev = df["Close"].shift()
    tr = pd.concat(
        [
            df["High"] - df["Low"],
            (df["High"] - prev).abs(),
            (df["Low"] - prev).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.ewm(alpha=1/14, adjust=False, min_periods=14).mean()


def rsi14(close):
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    ag = gain.ewm(alpha=1/14, adjust=False, min_periods=14).mean()
    al = loss.ewm(alpha=1/14, adjust=False, min_periods=14).mean()
    rs = ag / al.replace(0, np.nan)
    return 100 - 100 / (1 + rs)


def enrich(df, spy):
    d = df.copy()
    s = spy.copy()

    d["EMA20"] = d["Close"].ewm(span=20, adjust=False).mean()
    d["EMA50"] = d["Close"].ewm(span=50, adjust=False).mean()
    d["EMA200"] = d["Close"].ewm(span=200, adjust=False).mean()
    d["ATR14"] = atr14(d)
    d["ATR_PCT"] = d["ATR14"] / d["Close"]
    d["VOL20"] = d["Volume"].rolling(20).mean()
    d["VOLREL"] = d["Volume"] / d["VOL20"]
    d["RSI14"] = rsi14(d["Close"])
    d["RET20"] = d["Close"].pct_change(20)

    common = d.index.intersection(s.index)
    d = d.loc[common].copy()
    s = s.loc[common].copy()

    d["RS20"] = d["RET20"] - s["Close"].pct_change(20)
    return d


def structural_state(r):
    """
    Estado descriptivo. NO pretende ser un predictor calibrado.
    """
    close = float(r["Close"])
    e20 = float(r["EMA20"])
    e50 = float(r["EMA50"])
    e200 = float(r["EMA200"])
    rs = float(r["RS20"]) if pd.notna(r["RS20"]) else np.nan

    above20 = close > e20
    above50 = close > e50
    above200 = close > e200

    if above20 and above50 and above200 and pd.notna(rs) and rs >= 0.01:
        return "FUERTE"
    if above50 and above200 and (pd.isna(rs) or rs > -0.03):
        return "SANA"
    if above200 and not above50:
        return "VIGILAR"
    if not above200 and not above50:
        return "DETERIORADA"
    return "DEBIL"


def technical_levels(d):
    r = d.iloc[-1]
    close = float(r["Close"])
    atr = float(r["ATR14"]) if pd.notna(r["ATR14"]) else np.nan

    support5 = float(d["Low"].tail(5).min())
    support10 = float(d["Low"].tail(10).min())
    support20 = float(d["Low"].tail(20).min())

    # No se presentan como stops V11 validados.
    alert = support5

    if pd.notna(atr):
        technical = max(support10, close - 1.5 * atr)
        invalidation = min(support20, close - 2.0 * atr)
    else:
        technical = support10
        invalidation = support20

    return alert, technical, invalidation


def management_action(state, exact_candidate):
    """
    Etiqueta operativa conservadora. No ejecuta órdenes.
    """
    if exact_candidate:
        return "POSICION + NUEVA SEÑAL V11"
    if state in ("FUERTE", "SANA"):
        return "MANTENER"
    if state in ("VIGILAR", "DEBIL"):
        return "VIGILAR / NO AUMENTAR"
    return "REVISAR SALIDA / NO AUMENTAR"


def signal_is_actionable(signal_date, market_preview_date):
    """
    Evita llamar NUEVA ENTRADA a una señal cuyo T+1 ya pasó.

    Si existe una barra preview posterior a signal_date, la apertura causal
    de esa sesión ya ocurrió -> señal histórica/no perseguir.
    Si no existe barra posterior, queda como pendiente para próxima apertura.
    """
    if signal_date is None:
        return False

    if market_preview_date is None:
        return True

    return pd.Timestamp(market_preview_date).normalize() <= pd.Timestamp(signal_date).normalize()


# =============================================================================
# MAIN
# =============================================================================

def main():
    ensure_live_dir()
    portfolio = load_portfolio()

    print("=" * 154)
    print("V11 LIVE DESK v4 — OPERACIONAL")
    print("=" * 154)
    print(f"Cartera: {PORTFOLIO_FILE}")
    print("Forward científico: INTACTO")

    print("\n[1/4] V11 EXACTO — última barra daily oficial")
    exact_date = None
    exact = {}
    prepared = {}
    spy_exact = None

    try:
        exact_date, exact, prepared, spy_exact = exact_v11_signals()
        print(
            f"Fecha señal oficial: "
            f"{exact_date.date() if exact_date is not None else 'N/D'}"
        )

        if exact:
            ranked = sorted(
                exact.values(),
                key=lambda x: (x["rank"], x["score"], x["ticker"]),
                reverse=True,
            )
            for i, x in enumerate(ranked, 1):
                r = x["signal_row"]
                print(
                    f" {i:2d}. {x['ticker']:5s} | rank {x['rank']:.3f} | "
                    f"score {x['score']:.3f} | close {float(r.get('Close', np.nan)):.2f} | "
                    f"RS20 {100*float(r.get('RS20', np.nan)):+.2f}% | "
                    f"VolRel {float(r.get('VolRel', np.nan)):.2f} | "
                    f"ATR {100*float(r.get('ATR_PCT', np.nan)):.2f}%"
                )
        else:
            print(" Sin candidatos V11 en la última barra oficial.")

    except Exception as e:
        print(f"⚠️ Pipeline V11 exacto no disponible: {type(e).__name__}: {e}")

    print("\n[2/4] Estado del mercado / preview")
    spy_live, spy_preview = official_plus_preview("SPY")
    preview_date = spy_live.index.max() if not spy_live.empty else None

    if preview_date is not None:
        print(
            f"SPY última barra utilizable para diagnóstico: "
            f"{pd.Timestamp(preview_date).date()} | "
            f"Preview={'SI' if spy_preview else 'NO'}"
        )

    actionable = signal_is_actionable(exact_date, preview_date)

    if exact:
        if actionable:
            print("🟢 Señal V11 de la última rueda todavía puede corresponder a la próxima apertura.")
        else:
            print(
                "🟡 La apertura T+1 de la señal oficial ya ocurrió. "
                "Los candidatos se muestran como HISTÓRICOS: NO PERSEGUIR."
            )

    print("\n[3/4] Analizando cartera real")
    rows = []

    for p in portfolio.itertuples(index=False):
        ticker = p.ticker
        ba_ticker = p.ba_ticker
        qty = float(p.qty)
        avg_cost = float(p.avg_cost_ars)

        usd, used_preview = official_plus_preview(ticker)
        if usd.empty or spy_live.empty:
            print(f"⚠️ {ticker}: datos insuficientes.")
            continue

        d = enrich(usd, spy_live).dropna(subset=["Close"])
        if d.empty:
            print(f"⚠️ {ticker}: indicadores insuficientes.")
            continue

        r = d.iloc[-1]
        state = structural_state(r)
        alert, technical, invalidation = technical_levels(d)

        ba_px, ba_date, ba_source = last_ba_price(ba_ticker)
        usd_px = float(r["Close"])

        def to_ba(level):
            if pd.isna(ba_px) or usd_px <= 0:
                return np.nan
            return ba_px * level / usd_px

        value = qty * ba_px if pd.notna(ba_px) else np.nan
        pnl_pct = (ba_px / avg_cost - 1) * 100 if pd.notna(ba_px) else np.nan
        pnl_ars = qty * (ba_px - avg_cost) if pd.notna(ba_px) else np.nan

        candidate = ticker in exact
        candidate_actionable = candidate and actionable

        action = management_action(state, candidate_actionable)

        risk_technical = (
            max(0.0, value * (1 - technical / usd_px))
            if pd.notna(value) else np.nan
        )
        risk_invalidation = (
            max(0.0, value * (1 - invalidation / usd_px))
            if pd.notna(value) else np.nan
        )

        rows.append({
            "Ticker": ticker,
            "Fecha_USD": str(pd.Timestamp(d.index[-1]).date()),
            "Preview": "SI" if used_preview else "NO",
            "USD": usd_px,
            "Estado": state,
            "Accion": action,
            "V11": (
                "NUEVA" if candidate_actionable
                else "VIEJA" if candidate
                else "NO"
            ),
            "RS20%": 100 * float(r["RS20"]) if pd.notna(r["RS20"]) else np.nan,
            "ATR%": 100 * float(r["ATR_PCT"]) if pd.notna(r["ATR_PCT"]) else np.nan,
            "VolRel": float(r["VOLREL"]) if pd.notna(r["VOLREL"]) else np.nan,
            "RSI": float(r["RSI14"]) if pd.notna(r["RSI14"]) else np.nan,
            "vsEMA20%": 100 * (usd_px / float(r["EMA20"]) - 1),
            "vsEMA50%": 100 * (usd_px / float(r["EMA50"]) - 1),
            "vsEMA200%": 100 * (usd_px / float(r["EMA200"]) - 1),
            "Alerta_USD": alert,
            "Tecnico_USD": technical,
            "Invalidacion_USD": invalidation,
            "BA": ba_ticker,
            "BA_Fecha": ba_date,
            "BA_Fuente": ba_source,
            "BA_Px": ba_px,
            "Qty": qty,
            "Costo_ARS": avg_cost,
            "Valor_ARS": value,
            "PnL%": pnl_pct,
            "PnL_ARS": pnl_ars,
            "Alerta_BA_aprox": to_ba(alert),
            "Tecnico_BA_aprox": to_ba(technical),
            "Invalidacion_BA_aprox": to_ba(invalidation),
            "Riesgo_Tecnico_ARS": risk_technical,
            "Riesgo_Invalidacion_ARS": risk_invalidation,
        })

    out = pd.DataFrame(rows)

    if out.empty:
        print("No se pudo analizar ninguna posición.")
        return

    order = {
        "DETERIORADA": 0,
        "DEBIL": 1,
        "VIGILAR": 2,
        "SANA": 3,
        "FUERTE": 4,
    }
    out["_order"] = out["Estado"].map(order).fillna(9)
    out = out.sort_values(["_order", "Ticker"]).reset_index(drop=True)

    pd.set_option("display.width", 300)
    pd.set_option("display.max_columns", 60)
    pd.set_option("display.float_format", lambda x: f"{x:,.2f}")

    show = [
        "Ticker", "Fecha_USD", "Preview", "USD", "Estado", "Accion", "V11",
        "RS20%", "ATR%", "VolRel", "RSI",
        "vsEMA20%", "vsEMA50%", "vsEMA200%",
        "BA_Px", "PnL%", "Alerta_BA_aprox",
        "Tecnico_BA_aprox", "Invalidacion_BA_aprox",
    ]

    print("\n" + out[show].to_string(index=False))

    print("\n[4/4] Resumen operativo")

    total_invested = float(out["Valor_ARS"].sum(skipna=True))
    total_pnl = float(out["PnL_ARS"].sum(skipna=True))
    risk_tech = float(out["Riesgo_Tecnico_ARS"].sum(skipna=True))
    risk_inv = float(out["Riesgo_Invalidacion_ARS"].sum(skipna=True))

    print(f"Valor posiciones analizadas : ${total_invested:,.2f} ARS")
    print(f"PnL abierto aproximado      : ${total_pnl:,.2f} ARS")
    print(f"Riesgo hasta nivel técnico  : ${risk_tech:,.2f} ARS")
    print(f"Riesgo hasta invalidación   : ${risk_inv:,.2f} ARS")

    print("\nPRIORIDAD")
    for _, r in out.iterrows():
        print(
            f"  {str(r['Ticker']):5s} | {str(r['Estado']):11s} | {str(r['Accion']):28s} | "
            f"BA ${float(r['BA_Px']):,.2f} | PnL {float(r['PnL%']):+.2f}%"
        )

    if exact:
        print("\nSEÑALES V11")
        for x in sorted(
            exact.values(),
            key=lambda z: (z["rank"], z["score"], z["ticker"]),
            reverse=True,
        ):
            status = "PENDIENTE T+1" if actionable else "HISTÓRICA / NO PERSEGUIR"
            print(f"  {x['ticker']:5s} | {status}")

    # Persistencia sólo operativa.
    save = out.drop(columns=["_order"], errors="ignore")
    save.to_csv(SNAPSHOT_FILE, index=False)

    decisions = save[
        [
            "Ticker", "Fecha_USD", "Estado", "Accion", "V11",
            "BA_Px", "PnL%", "Alerta_BA_aprox",
            "Tecnico_BA_aprox", "Invalidacion_BA_aprox",
        ]
    ].copy()
    decisions.to_csv(DECISION_FILE, index=False)

    meta = {
        "generated_at_local": datetime.now().isoformat(timespec="seconds"),
        "v11_official_signal_date": (
            str(exact_date.date()) if exact_date is not None else None
        ),
        "diagnostic_market_date": (
            str(pd.Timestamp(preview_date).date())
            if preview_date is not None else None
        ),
        "diagnostic_preview": bool(spy_preview),
        "v11_signal_actionable_for_next_open": bool(actionable and exact),
        "v11_candidates": sorted(exact.keys()),
        "portfolio_rows": int(len(save)),
        "writes_to_results": False,
    }
    META_FILE.write_text(
        json.dumps(meta, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print("\nArchivos operativos actualizados:")
    print(f"  {SNAPSHOT_FILE}")
    print(f"  {DECISION_FILE}")
    print(f"  {META_FILE}")

    print("\n" + "=" * 154)
    print("INTERPRETACIÓN")
    print("=" * 154)
    print("• V11 NUEVA = candidato exacto cuya apertura T+1 todavía no pasó.")
    print("• V11 VIEJA = señal exacta ya vencida operacionalmente; no perseguir.")
    print("• Estado/Acción evalúan una posición existente; NO son reglas del backtest V11.")
    print("• ALERTA/TÉCNICO/INVALIDACIÓN son referencias de gestión, no stops V11 validados.")
    print("• Niveles .BA son aproximados: FX/CCL y ratio pueden mover el CEDEAR independientemente.")
    print("• Para una operación nacida realmente de V11, el stop científico debe fijarse desde su entrada/ATR original.")
    print("• Nada de este script modifica results/ ni el forward prospectivo.")


if __name__ == "__main__":
    main()
