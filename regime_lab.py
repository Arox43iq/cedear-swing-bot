from __future__ import annotations

"""
V5 — REGIME & EDGE DECOMPOSITION

Purpose
-------
Diagnose *where* the current candidate strategy has historically made or lost
money without optimizing parameters and without looking at 2026 for selection.

This module deliberately reuses the audited engine in research_engine.py.
It does not modify strategy.py and it does not replace the portfolio simulator.

Research window used here: 2023-01-03 through 2025-12-31 only.
2026 is intentionally excluded from every V5 table.
"""

from pathlib import Path
import math

import numpy as np
import pandas as pd

import research_engine as re


OUT = Path("results")
OUT.mkdir(exist_ok=True)

# Candidate selected for diagnosis from V4 simplification evidence.
# No WPR, no momentum. The point is diagnosis, not parameter search.
V5_COMPONENTS = ("trend", "pullback", "rs20", "volume", "candle")
V5_START = pd.Timestamp("2023-01-03")
V5_END = pd.Timestamp("2025-12-31")


def _safe_float(x, default=np.nan):
    try:
        x = float(x)
        return x if np.isfinite(x) else default
    except Exception:
        return default


def _safe_div(a, b, default=0.0):
    a = _safe_float(a)
    b = _safe_float(b)
    if np.isfinite(a) and np.isfinite(b) and abs(b) > 1e-12:
        return a / b
    return default


def _profit_factor_from_pnl(s: pd.Series) -> float:
    s = pd.to_numeric(s, errors="coerce").dropna()
    wins = s[s > 0].sum()
    losses = -s[s < 0].sum()
    if losses <= 0:
        return np.inf if wins > 0 else 0.0
    return float(wins / losses)


def _trade_group_summary(df: pd.DataFrame, group_col: str, family: str) -> pd.DataFrame:
    rows = []
    if df.empty or group_col not in df.columns:
        return pd.DataFrame()

    for key, g in df.groupby(group_col, dropna=False, sort=False):
        if len(g) == 0:
            continue
        pnl = pd.to_numeric(g.get("net_pnl", pd.Series(dtype=float)), errors="coerce")
        r = pd.to_numeric(g.get("R", pd.Series(dtype=float)), errors="coerce")
        rows.append({
            "family": family,
            "bucket": str(key),
            "trades": int(len(g)),
            "win_rate_pct": float((pnl > 0).mean() * 100) if len(pnl) else 0.0,
            "profit_factor": _profit_factor_from_pnl(pnl),
            "avg_R": float(r.mean()) if r.notna().any() else 0.0,
            "median_R": float(r.median()) if r.notna().any() else 0.0,
            "sum_R": float(r.sum()) if r.notna().any() else 0.0,
            "net_pnl": float(pnl.sum()) if pnl.notna().any() else 0.0,
            "avg_net_pnl": float(pnl.mean()) if pnl.notna().any() else 0.0,
            "avg_bars": float(pd.to_numeric(g.get("bars"), errors="coerce").mean()) if "bars" in g else np.nan,
            "avg_MFE_R": float(pd.to_numeric(g.get("mfe_R"), errors="coerce").mean()) if "mfe_R" in g else np.nan,
            "avg_MAE_R": float(pd.to_numeric(g.get("mae_R"), errors="coerce").mean()) if "mae_R" in g else np.nan,
        })
    return pd.DataFrame(rows)


def _prior_session_map(df: pd.DataFrame) -> dict[pd.Timestamp, pd.Timestamp]:
    idx = pd.DatetimeIndex(df.index).sort_values().unique()
    return {idx[i]: idx[i - 1] for i in range(1, len(idx))}


def _spy_context(spy: pd.DataFrame) -> pd.DataFrame:
    x = spy.copy().sort_index()
    close = pd.to_numeric(x["Close"], errors="coerce")

    if "EMA20" not in x:
        x["EMA20"] = close.ewm(span=20, adjust=False).mean()
    if "EMA50" not in x:
        x["EMA50"] = close.ewm(span=50, adjust=False).mean()
    if "EMA200" not in x:
        x["EMA200"] = close.ewm(span=200, adjust=False).mean()

    x["SPY_RET20"] = close.pct_change(20)
    x["SPY_RET60"] = close.pct_change(60)
    x["SPY_DIST_EMA20"] = close / x["EMA20"] - 1.0
    x["SPY_DIST_EMA200"] = close / x["EMA200"] - 1.0
    x["SPY_VOL20"] = close.pct_change().rolling(20).std() * math.sqrt(252)

    strong = (close > x["EMA20"]) & (x["EMA20"] > x["EMA50"]) & (x["EMA50"] > x["EMA200"])
    above200 = close > x["EMA200"]
    x["SPY_REGIME"] = np.select(
        [strong, above200],
        ["STRONG_BULL", "ABOVE_EMA200"],
        default="BELOW_EMA200",
    )

    x["SPY_RET20_BUCKET"] = pd.cut(
        x["SPY_RET20"],
        bins=[-np.inf, 0.0, 0.05, np.inf],
        labels=["RET20_NEG", "RET20_0_5", "RET20_GT5"],
        right=False,
    ).astype("object")

    x["SPY_VOL_BUCKET"] = pd.cut(
        x["SPY_VOL20"],
        bins=[-np.inf, 0.15, 0.25, np.inf],
        labels=["VOL_LT15", "VOL_15_25", "VOL_GT25"],
        right=False,
    ).astype("object")

    keep = [
        "Close", "EMA20", "EMA50", "EMA200", "SPY_RET20", "SPY_RET60",
        "SPY_DIST_EMA20", "SPY_DIST_EMA200", "SPY_VOL20", "SPY_REGIME",
        "SPY_RET20_BUCKET", "SPY_VOL_BUCKET",
    ]
    return x[keep].copy()


def _breadth_context(data: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Cross-sectional breadth using only information available at each close."""
    pieces = []
    for ticker, df in data.items():
        z = df.loc[(df.index >= V5_START) & (df.index <= V5_END)].copy()
        if z.empty:
            continue
        tmp = pd.DataFrame(index=z.index)
        tmp["n"] = 1
        tmp["above20"] = (z["Close"] > z["EMA20"]).astype(float)
        tmp["above50"] = (z["Close"] > z["EMA50"]).astype(float)
        tmp["above200"] = (z["Close"] > z["EMA200"]).astype(float)
        tmp["trend_stack"] = (
            (z["Close"] > z["EMA20"])
            & (z["EMA20"] > z["EMA50"])
            & (z["EMA50"] > z["EMA200"])
        ).astype(float)
        pieces.append(tmp)

    if not pieces:
        return pd.DataFrame()

    all_rows = pd.concat(pieces, axis=0)
    agg = all_rows.groupby(level=0).agg(
        breadth_n=("n", "sum"),
        breadth_above20=("above20", "mean"),
        breadth_above50=("above50", "mean"),
        breadth_above200=("above200", "mean"),
        breadth_trend_stack=("trend_stack", "mean"),
    )

    for col in ["breadth_above20", "breadth_above50", "breadth_above200", "breadth_trend_stack"]:
        agg[col] *= 100.0

    agg["BREADTH20_BUCKET"] = pd.cut(
        agg["breadth_above20"],
        bins=[-np.inf, 40, 60, np.inf],
        labels=["BREADTH_LT40", "BREADTH_40_60", "BREADTH_GT60"],
        right=False,
    ).astype("object")
    agg["BREADTH200_BUCKET"] = pd.cut(
        agg["breadth_above200"],
        bins=[-np.inf, 50, 70, np.inf],
        labels=["BREADTH200_LT50", "BREADTH200_50_70", "BREADTH200_GT70"],
        right=False,
    ).astype("object")
    return agg.sort_index()


def _setup_context(data, cfg, active) -> tuple[pd.DataFrame, dict[str, list[dict]]]:
    sigs = re.precompute_signals(data, cfg, active)
    rows = []
    for ticker, items in sigs.items():
        for item in items:
            d = pd.Timestamp(item["date"])
            if V5_START <= d <= V5_END:
                rows.append((d, ticker, _safe_float(item.get("score")), _safe_float(item.get("rank"))))

    if not rows:
        return pd.DataFrame(columns=["setup_count", "setup_score_mean", "setup_rank_mean"]), sigs

    s = pd.DataFrame(rows, columns=["date", "ticker", "score", "rank"])
    daily = s.groupby("date").agg(
        setup_count=("ticker", "count"),
        setup_score_mean=("score", "mean"),
        setup_rank_mean=("rank", "mean"),
    ).sort_index()

    # Descriptive only. Quantile boundaries are NOT proposed as trading rules.
    q1 = float(daily["setup_count"].quantile(1 / 3))
    q2 = float(daily["setup_count"].quantile(2 / 3))
    if q2 <= q1:
        q2 = q1 + 1.0
    daily["SETUP_INTENSITY"] = pd.cut(
        daily["setup_count"],
        bins=[-np.inf, q1, q2, np.inf],
        labels=["LOW_SETUPS", "MID_SETUPS", "HIGH_SETUPS"],
        include_lowest=True,
        duplicates="drop",
    ).astype("object")
    return daily, sigs


def _daily_context(data, spy, cfg, active) -> tuple[pd.DataFrame, dict[str, list[dict]]]:
    ctx = _spy_context(spy)
    breadth = _breadth_context(data)
    setups, sigs = _setup_context(data, cfg, active)
    ctx = ctx.join(breadth, how="outer").join(setups, how="outer").sort_index()
    ctx = ctx.loc[(ctx.index >= V5_START) & (ctx.index <= V5_END)].copy()
    ctx.index.name = "date"
    return ctx, sigs


def _attach_signal_context(trades: pd.DataFrame, data, daily_ctx: pd.DataFrame) -> pd.DataFrame:
    if trades.empty:
        return trades.copy()

    t = trades.copy()
    t["entry_date"] = pd.to_datetime(t["entry_date"])
    t["exit_date"] = pd.to_datetime(t["exit_date"])

    prior_maps = {ticker: _prior_session_map(df) for ticker, df in data.items()}
    signal_dates = []
    for row in t.itertuples(index=False):
        ticker = getattr(row, "ticker")
        entry_date = pd.Timestamp(getattr(row, "entry_date"))
        signal_dates.append(prior_maps.get(ticker, {}).get(entry_date, pd.NaT))
    t["signal_date"] = pd.to_datetime(signal_dates)

    context_cols = [
        "SPY_RET20", "SPY_RET60", "SPY_DIST_EMA20", "SPY_DIST_EMA200", "SPY_VOL20",
        "SPY_REGIME", "SPY_RET20_BUCKET", "SPY_VOL_BUCKET",
        "breadth_n", "breadth_above20", "breadth_above50", "breadth_above200",
        "breadth_trend_stack", "BREADTH20_BUCKET", "BREADTH200_BUCKET",
        "setup_count", "setup_score_mean", "setup_rank_mean", "SETUP_INTENSITY",
    ]
    ctx = daily_ctx[[c for c in context_cols if c in daily_ctx.columns]].copy()
    t = t.merge(ctx, how="left", left_on="signal_date", right_index=True)
    t["year"] = t["signal_date"].dt.year.astype("Int64")

    # Fixed, interpretable signal-feature buckets.
    if "RS20" in t:
        t["RS20_BUCKET"] = pd.cut(
            pd.to_numeric(t["RS20"], errors="coerce"),
            bins=[-np.inf, 0.03, 0.06, 0.10, np.inf],
            labels=["RS20_LT3", "RS20_3_6", "RS20_6_10", "RS20_GT10"],
            right=False,
        ).astype("object")
    if "VolRel" in t:
        t["VOLREL_BUCKET"] = pd.cut(
            pd.to_numeric(t["VolRel"], errors="coerce"),
            bins=[-np.inf, 1.0, 1.25, 1.5, np.inf],
            labels=["VOLREL_LT1", "VOLREL_1_1.25", "VOLREL_1.25_1.5", "VOLREL_GT1.5"],
            right=False,
        ).astype("object")
    if "ATR_PCT" in t:
        t["ATR_BUCKET"] = pd.cut(
            pd.to_numeric(t["ATR_PCT"], errors="coerce") * 100.0,
            bins=[-np.inf, 2.0, 3.0, 4.5, np.inf],
            labels=["ATR_LT2", "ATR_2_3", "ATR_3_4.5", "ATR_GT4.5"],
            right=False,
        ).astype("object")

    # Score quartiles are descriptive diagnostics only and never used as V5 filters.
    if "score" in t and pd.to_numeric(t["score"], errors="coerce").notna().sum() >= 8:
        score = pd.to_numeric(t["score"], errors="coerce")
        try:
            t["SCORE_QUARTILE"] = pd.qcut(score, 4, labels=["Q1", "Q2", "Q3", "Q4"], duplicates="drop").astype("object")
        except ValueError:
            t["SCORE_QUARTILE"] = "UNAVAILABLE"

    return t


def _make_decomposition(trades: pd.DataFrame) -> pd.DataFrame:
    specs = [
        ("year", "YEAR"),
        ("SPY_REGIME", "SPY_REGIME"),
        ("SPY_RET20_BUCKET", "SPY_RET20"),
        ("SPY_VOL_BUCKET", "SPY_VOL20"),
        ("BREADTH20_BUCKET", "BREADTH_EMA20"),
        ("BREADTH200_BUCKET", "BREADTH_EMA200"),
        ("SETUP_INTENSITY", "SETUP_INTENSITY"),
        ("RS20_BUCKET", "SIGNAL_RS20"),
        ("VOLREL_BUCKET", "SIGNAL_VOLREL"),
        ("ATR_BUCKET", "SIGNAL_ATR"),
        ("SCORE_QUARTILE", "SIGNAL_SCORE_QUARTILE"),
        ("reason", "EXIT_REASON"),
    ]
    tables = []
    for col, fam in specs:
        if col in trades.columns:
            x = _trade_group_summary(trades.dropna(subset=[col]), col, fam)
            if not x.empty:
                tables.append(x)
    return pd.concat(tables, ignore_index=True) if tables else pd.DataFrame()


def _annual_validation(data, spy, cfg, active) -> pd.DataFrame:
    rows = []
    windows = [
        (2023, pd.Timestamp("2023-01-03"), pd.Timestamp("2023-12-29")),
        (2024, pd.Timestamp("2024-01-02"), pd.Timestamp("2024-12-31")),
        (2025, pd.Timestamp("2025-01-02"), pd.Timestamp("2025-12-31")),
    ]
    for year, start, end in windows:
        tr, eq = re.backtest(data, spy, cfg, active, start, end, label=f"V5 {year}")
        m = re.metrics(tr, eq, cfg)
        spy_ret = re.benchmark(spy, start, end)
        rows.append({
            "period": str(year),
            "return_pct": m["return_pct"],
            "pf": m["pf"],
            "dd_pct": m["dd_pct"],
            "trades": m["trades"],
            "win_rate": m["win_rate"],
            "avg_R": m["avg_R"],
            "sharpe": m["sharpe"],
            "commission": m["commission"],
            "spy_return_pct": spy_ret,
            "excess_vs_spy_pp": m["return_pct"] - spy_ret,
        })
    return pd.DataFrame(rows)


def _cost_stress_2023_2025(data, spy, cfg, active) -> pd.DataFrame:
    """Small robustness check. No parameter search and no 2026."""
    rows = []
    for factor in [1.0, 2.0, 3.0]:
        c = dict(cfg)
        c["commission"] = cfg["commission"] * factor
        c["slippage"] = cfg["slippage"] * factor
        tr, eq = re.backtest(data, spy, c, active, V5_START, V5_END, label=f"V5 COST x{factor:g}")
        m = re.metrics(tr, eq, c)
        rows.append({
            "cost_factor": factor,
            "return_pct": m["return_pct"],
            "pf": m["pf"],
            "dd_pct": m["dd_pct"],
            "trades": m["trades"],
            "win_rate": m["win_rate"],
            "avg_R": m["avg_R"],
            "commission": m["commission"],
        })
    return pd.DataFrame(rows)


def _print_top_bottom(decomp: pd.DataFrame, family: str, min_trades: int = 20) -> None:
    g = decomp[(decomp["family"] == family) & (decomp["trades"] >= min_trades)].copy()
    if g.empty:
        return
    g = g.sort_values(["avg_R", "profit_factor"], ascending=False)
    print(f"\n{family}")
    print("-" * 92)
    print(f"{'BUCKET':<24}{'TR':>7}{'WR':>9}{'PF':>10}{'AvgR':>10}{'MedR':>10}{'PnL':>14}")
    for _, r in g.iterrows():
        pf = "inf" if np.isinf(r.profit_factor) else f"{r.profit_factor:.2f}"
        print(
            f"{str(r.bucket):<24}{int(r.trades):>7}{r.win_rate_pct:>8.1f}%"
            f"{pf:>10}{r.avg_R:>10.3f}{r.median_R:>10.3f}{r.net_pnl:>14,.0f}"
        )


def run_regime_lab(universe: str = "USA") -> None:
    if universe != "USA":
        print("\n⚠️ V5 se ejecuta solamente sobre USA.")
        print("CEDEAR queda fuera hasta construir un modelo ARS/FX y ratios específico.")
        return

    print("\n" + "=" * 112)
    print("V5 — REGIME & EDGE DECOMPOSITION — USA")
    print("=" * 112)
    print("Objetivo: diagnosticar dónde existe el edge; NO optimizar parámetros.")
    print("Ventana de investigación: 2023-01-03 -> 2025-12-31.")
    print("2026 está EXCLUIDO de V5 y no se usa para seleccionar nada.")
    print("Candidata: trend + pullback + rs20 + volume + candle (sin WPR ni momentum).")

    raw = re.download_universe("USA")
    spy_raw = re.download_spy()
    data, spy = re.prepare(raw, spy_raw)
    if not data:
        print("❌ No hay datos válidos.")
        return

    cfg = dict(re.CONFIG)
    cfg["rs20_min"] = 0.01
    cfg["tp_r"] = 1.8
    cfg["stop_atr"] = 1.5
    cfg["risk_per_trade"] = 0.005
    cfg["max_gross_exposure"] = 0.90
    cfg["max_portfolio_risk"] = 0.025

    print(f"\nActivos preparados: {len(data)}")
    print("Construyendo contexto causal de mercado, breadth y setups...")
    daily_ctx, _ = _daily_context(data, spy, cfg, V5_COMPONENTS)

    print("Ejecutando candidata sobre 2023-2025...")
    trades, equity = re.backtest(data, spy, cfg, V5_COMPONENTS, V5_START, V5_END, label="V5 CORE")
    m = re.metrics(trades, equity, cfg)
    spy_ret = re.benchmark(spy, V5_START, V5_END)

    enriched = _attach_signal_context(trades, data, daily_ctx)
    decomp = _make_decomposition(enriched)
    annual = _annual_validation(data, spy, cfg, V5_COMPONENTS)
    stress = _cost_stress_2023_2025(data, spy, cfg, V5_COMPONENTS)

    # Persist everything before printing conclusions.
    daily_ctx.reset_index().to_csv(OUT / "v5_daily_context.csv", index=False)
    enriched.to_csv(OUT / "v5_trades_enriched.csv", index=False)
    decomp.to_csv(OUT / "v5_edge_decomposition.csv", index=False)
    annual.to_csv(OUT / "v5_year_summary.csv", index=False)
    stress.to_csv(OUT / "v5_cost_stress.csv", index=False)
    if not equity.empty:
        equity.to_csv(OUT / "v5_equity_2023_2025.csv", index=False)

    print("\n" + "=" * 112)
    print("RESULTADO GLOBAL 2023-2025 — SOLO DIAGNÓSTICO")
    print("=" * 112)
    print(
        f"Strategy {m['return_pct']:+.2f}% | PF {m['pf']:.2f} | DD {m['dd_pct']:+.2f}% | "
        f"Trades {m['trades']} | WR {m['win_rate']:.1f}% | AvgR {m['avg_R']:.3f} | Sharpe {m['sharpe']:.2f}"
    )
    print(f"SPY      {spy_ret:+.2f}% | exceso simple {m['return_pct'] - spy_ret:+.2f} pp")

    print("\n" + "=" * 112)
    print("VALIDACIÓN POR AÑO")
    print("=" * 112)
    print(f"{'AÑO':<8}{'RET':>10}{'PF':>8}{'DD':>10}{'TR':>7}{'AvgR':>10}{'SPY':>10}{'EXCESS':>11}")
    for _, r in annual.iterrows():
        print(
            f"{r.period:<8}{r.return_pct:>+9.2f}%{r.pf:>8.2f}{r.dd_pct:>+9.2f}%"
            f"{int(r.trades):>7}{r.avg_R:>10.3f}{r.spy_return_pct:>+9.2f}%{r.excess_vs_spy_pp:>+10.2f}"
        )

    print("\n" + "=" * 112)
    print("DESCOMPOSICIÓN DEL EDGE — RESULTADOS DE TRADES SEGÚN CONTEXTO EN LA FECHA DE SEÑAL")
    print("=" * 112)
    for family in [
        "SPY_REGIME", "SPY_RET20", "SPY_VOL20", "BREADTH_EMA20", "BREADTH_EMA200",
        "SETUP_INTENSITY", "SIGNAL_RS20", "SIGNAL_VOLREL", "SIGNAL_ATR", "SIGNAL_SCORE_QUARTILE",
    ]:
        _print_top_bottom(decomp, family)

    print("\n" + "=" * 112)
    print("STRESS DE COSTOS 2023-2025")
    print("=" * 112)
    for _, r in stress.iterrows():
        print(
            f"x{r.cost_factor:g}: {r.return_pct:+.2f}% | PF {r.pf:.2f} | DD {r.dd_pct:+.2f}% | "
            f"{int(r.trades)} trades | AvgR {r.avg_R:.3f}"
        )

    print("\nArchivos generados en ./results/:")
    for name in [
        "v5_daily_context.csv",
        "v5_trades_enriched.csv",
        "v5_edge_decomposition.csv",
        "v5_year_summary.csv",
        "v5_cost_stress.csv",
        "v5_equity_2023_2025.csv",
    ]:
        print(f"  • {name}")

    print("\nIMPORTANTE:")
    print("• Los buckets de V5 son diagnóstico, no nuevas reglas de trading.")
    print("• SCORE_QUARTILE y SETUP_INTENSITY usan cuantiles solo para describir la muestra.")
    print("• No se ejecuta ningún backtest de 2026 en este módulo.")
    print("• No modifiques strategy.py después de ver estos resultados; primero hay que analizarlos.")
