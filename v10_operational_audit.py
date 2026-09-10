from __future__ import annotations

"""
V10 — DEPLOYMENT READINESS / OPERATIONAL AUDIT

IMPORTANT
---------
This is NOT a strategy optimizer.

It does not change:
    components = trend + pullback + rs20 + volume + candle
    RS20 >= 1%
    ATR% in [3%, 5%]
    VolRel >= 1.15
    TP = 1.8R
    stop = 1.5 ATR
    risk/trade = 0.5%

V10 consumes the immutable V8/V9 result files and audits whether the frozen
architecture is operationally robust enough for PAPER-TRADING / shadow mode.

It never uses 2026 to choose a new threshold, component or exit.
"""

from pathlib import Path
import json
import math

import numpy as np
import pandas as pd

OUT = Path("results")
OUT.mkdir(exist_ok=True)

V8_TRADES = OUT / "v8_all_trades.csv"
V9_TRADES = OUT / "v9_holdout_trades.csv"
V9_EQUITY = OUT / "v9_holdout_equity.csv"
V9_RESULT = OUT / "v9_final_result.csv"
V9_STRESS = OUT / "v9_fixed_path_cost_stress.csv"
V9_VERDICT = OUT / "v9_verdict.json"
V9_MANIFEST = OUT / "v9_frozen_manifest.json"

SUMMARY_PATH = OUT / "v10_readiness_summary.csv"
PERIOD_PATH = OUT / "v10_period_diagnostics.csv"
SHOCK_PATH = OUT / "v10_execution_shock.csv"
STREAK_PATH = OUT / "v10_loss_streaks.csv"
ROLLING_PATH = OUT / "v10_rolling_edge.csv"
MONTE_PATH = OUT / "v10_monte_carlo.csv"
CONC_PATH = OUT / "v10_concentration.csv"
VERDICT_PATH = OUT / "v10_readiness_verdict.json"

FROZEN_EXPERIMENT = "VREL_1.15_LEAD"
INITIAL_CAPITAL = 1_000_000.0


def _pf(pnl):
    s = pd.to_numeric(pd.Series(pnl), errors="coerce").dropna()
    wins = float(s[s > 0].sum())
    losses = float(-s[s < 0].sum())
    if losses <= 0:
        return float("inf") if wins > 0 else 0.0
    return wins / losses


def _max_loss_streak(pnl):
    best = cur = 0
    for x in pnl:
        if x < 0:
            cur += 1
            best = max(best, cur)
        else:
            cur = 0
    return int(best)


def _trade_r_drawdown(r_values):
    r = pd.to_numeric(pd.Series(r_values), errors="coerce").fillna(0.0).to_numpy()
    curve = np.cumsum(r)
    curve = np.insert(curve, 0, 0.0)
    peak = np.maximum.accumulate(curve)
    dd = curve - peak
    return float(dd.min())


def _basic_stats(trades, label):
    if trades.empty:
        return {
            "period": label, "trades": 0, "net_pnl": 0.0, "pf": 0.0,
            "avg_R": 0.0, "win_rate": 0.0, "max_loss_streak": 0,
            "trade_R_drawdown": 0.0,
        }
    pnl = pd.to_numeric(trades["net_pnl"], errors="coerce").fillna(0.0)
    rr = pd.to_numeric(trades["R"], errors="coerce").fillna(0.0)
    return {
        "period": label,
        "trades": int(len(trades)),
        "net_pnl": float(pnl.sum()),
        "pf": float(_pf(pnl)),
        "avg_R": float(rr.mean()),
        "win_rate": float((pnl > 0).mean() * 100.0),
        "max_loss_streak": _max_loss_streak(pnl.to_numpy()),
        "trade_R_drawdown": _trade_r_drawdown(rr),
    }


def _load():
    required = [
        V8_TRADES, V9_TRADES, V9_EQUITY, V9_RESULT,
        V9_STRESS, V9_VERDICT, V9_MANIFEST,
    ]
    missing = [str(p) for p in required if not p.exists()]
    if missing:
        print("\n❌ Faltan archivos requeridos de V8/V9:")
        for p in missing:
            print("   •", p)
        print("Ejecutá V8/V9 o copiá sus resultados dentro de ./results/.")
        return None

    v8 = pd.read_csv(V8_TRADES)
    train = v8.loc[v8["experiment"].astype(str) == FROZEN_EXPERIMENT].copy()
    hold = pd.read_csv(V9_TRADES)
    eq = pd.read_csv(V9_EQUITY)
    result = pd.read_csv(V9_RESULT)
    stress = pd.read_csv(V9_STRESS)

    with open(V9_VERDICT, "r", encoding="utf-8") as f:
        verdict = json.load(f)
    with open(V9_MANIFEST, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    for df in [train, hold]:
        df["entry_date"] = pd.to_datetime(df["entry_date"], errors="coerce")
        df["exit_date"] = pd.to_datetime(df["exit_date"], errors="coerce")
        df["net_pnl"] = pd.to_numeric(df["net_pnl"], errors="coerce").fillna(0.0)
        df["R"] = pd.to_numeric(df["R"], errors="coerce").fillna(0.0)
        df["entry_value"] = pd.to_numeric(df["entry_value"], errors="coerce").fillna(0.0)

    eq["date"] = pd.to_datetime(eq["date"], errors="coerce")
    return train, hold, eq, result, stress, verdict, manifest


def _period_diagnostics(train, hold):
    rows = []

    # Training/reference period — descriptive only.
    for year, g in train.groupby(train["entry_date"].dt.year):
        rows.append(_basic_stats(g, f"REFERENCE_{int(year)}"))

    # True final holdout.
    rows.append(_basic_stats(hold, "HOLDOUT_2026"))

    for month, g in hold.groupby(hold["entry_date"].dt.to_period("M")):
        rows.append(_basic_stats(g, f"HOLDOUT_{month}"))

    # Recent windows are monitoring diagnostics only, never filters.
    hs = hold.sort_values("entry_date")
    for n in [20, 40, 60]:
        if len(hs) >= n:
            rows.append(_basic_stats(hs.tail(n), f"HOLDOUT_LAST_{n}_TRADES"))

    return pd.DataFrame(rows)


def _execution_shock(hold):
    """
    Fixed-path extra friction.

    extra_round_trip_bps is charged ON TOP of the already included V9
    commission/slippage. We keep the exact same trades and sizes.
    """
    rows = []
    for bps in [0, 5, 10, 20, 30, 50, 75, 100]:
        extra_cost = hold["entry_value"] * (bps / 10000.0)
        adj = hold["net_pnl"] - extra_cost
        rows.append({
            "extra_round_trip_bps": int(bps),
            "trades": int(len(hold)),
            "extra_cost": float(extra_cost.sum()),
            "net_pnl": float(adj.sum()),
            "return_on_initial_capital_pct": float(adj.sum() / INITIAL_CAPITAL * 100.0),
            "pf": float(_pf(adj)),
        })
    return pd.DataFrame(rows)


def _loss_streak_table(train, hold):
    rows = []
    for label, df in [("REFERENCE_2023_2025", train), ("HOLDOUT_2026", hold)]:
        x = df.sort_values(["entry_date", "ticker"]).copy()
        pnl = x["net_pnl"].to_numpy()
        rr = x["R"].to_numpy()

        rows.append({
            "period": label,
            "trades": int(len(x)),
            "max_consecutive_losses": _max_loss_streak(pnl),
            "trade_R_drawdown": _trade_r_drawdown(rr),
            "worst_trade_R": float(np.min(rr)) if len(rr) else 0.0,
            "p05_trade_R": float(np.quantile(rr, 0.05)) if len(rr) else 0.0,
            "median_trade_R": float(np.median(rr)) if len(rr) else 0.0,
            "p95_trade_R": float(np.quantile(rr, 0.95)) if len(rr) else 0.0,
        })
    return pd.DataFrame(rows)


def _rolling_edge(hold):
    x = hold.sort_values(["entry_date", "ticker"]).reset_index(drop=True).copy()
    rows = []
    for window in [20, 40, 60]:
        if len(x) < window:
            continue
        for end in range(window, len(x) + 1):
            g = x.iloc[end-window:end]
            rows.append({
                "window": window,
                "end_trade_number": end,
                "end_date": g["entry_date"].iloc[-1],
                "trades": window,
                "pf": _pf(g["net_pnl"]),
                "avg_R": float(g["R"].mean()),
                "net_pnl": float(g["net_pnl"].sum()),
                "win_rate": float((g["net_pnl"] > 0).mean() * 100.0),
            })
    return pd.DataFrame(rows)


def _monte_carlo_month_blocks(hold, seed=10092026, n_sims=20000):
    """
    Resample complete entry-month blocks from V9.

    This preserves much of the same-month cross-sectional dependence instead of
    pretending 124 trades are fully independent. It is a risk scenario, not a
    new significance test and not a strategy-selection device.
    """
    x = hold.copy()
    x["month"] = x["entry_date"].dt.to_period("M").astype(str)
    blocks = []
    for _, g in x.groupby("month", sort=True):
        blocks.append({
            "pnl": float(g["net_pnl"].sum()),
            "R": float(g["R"].sum()),
            "trades": int(len(g)),
        })

    if not blocks:
        return pd.DataFrame()

    rng = np.random.default_rng(seed)
    n_blocks = len(blocks)
    pnl_arr = np.array([b["pnl"] for b in blocks], dtype=float)
    r_arr = np.array([b["R"] for b in blocks], dtype=float)
    tr_arr = np.array([b["trades"] for b in blocks], dtype=float)

    sim_rows = []
    for _ in range(n_sims):
        idx = rng.integers(0, n_blocks, size=n_blocks)
        bp = pnl_arr[idx]
        br = r_arr[idx]
        bt = tr_arr[idx]
        curve = np.cumsum(bp)
        curve0 = np.insert(curve, 0, 0.0)
        peak = np.maximum.accumulate(curve0)
        dd = curve0 - peak

        sim_rows.append((
            float(bp.sum()),
            float(br.sum()),
            int(bt.sum()),
            float(dd.min()),
        ))

    sim = pd.DataFrame(
        sim_rows,
        columns=["net_pnl", "sum_R", "trades", "max_drawdown_dollars"]
    )

    summary = pd.DataFrame([{
        "method": "holdout_month_block_bootstrap",
        "simulations": int(n_sims),
        "sampled_blocks_per_sim": int(n_blocks),
        "p_loss_pct": float((sim["net_pnl"] <= 0).mean() * 100.0),
        "p05_net_pnl": float(sim["net_pnl"].quantile(0.05)),
        "p25_net_pnl": float(sim["net_pnl"].quantile(0.25)),
        "median_net_pnl": float(sim["net_pnl"].median()),
        "p75_net_pnl": float(sim["net_pnl"].quantile(0.75)),
        "p95_net_pnl": float(sim["net_pnl"].quantile(0.95)),
        "p05_sum_R": float(sim["sum_R"].quantile(0.05)),
        "median_sum_R": float(sim["sum_R"].median()),
        "p95_sum_R": float(sim["sum_R"].quantile(0.95)),
        "p05_max_drawdown_dollars": float(sim["max_drawdown_dollars"].quantile(0.05)),
        "median_max_drawdown_dollars": float(sim["max_drawdown_dollars"].median()),
    }])
    return summary


def _concentration(train, hold):
    rows = []
    for label, df in [("REFERENCE_2023_2025", train), ("HOLDOUT_2026", hold)]:
        by = (
            df.groupby("ticker", as_index=False)
              .agg(trades=("ticker", "size"), net_pnl=("net_pnl", "sum"), avg_R=("R", "mean"))
              .sort_values("net_pnl", ascending=False)
        )
        total = float(df["net_pnl"].sum())
        pos = by.loc[by["net_pnl"] > 0, "net_pnl"].sum()
        for n in [1, 3, 5, 10]:
            top = float(by.head(n)["net_pnl"].sum())
            rows.append({
                "period": label,
                "top_n": n,
                "tickers": int(by["ticker"].nunique()),
                "total_net_pnl": total,
                "top_n_net_pnl": top,
                "top_n_share_of_net_pnl_pct": float(top / total * 100.0) if abs(total) > 1e-12 else np.nan,
                "top_n_share_of_positive_ticker_pnl_pct": float(top / pos * 100.0) if pos > 0 else np.nan,
            })
    return pd.DataFrame(rows)


def _readiness(train, hold, eq, result, stress, shock, rolling, monte, verdict, manifest):
    r = result.iloc[0]
    cap_viol = int(pd.to_numeric(eq.get("entry_cap_violations", pd.Series([0])), errors="coerce").fillna(0).sum())
    max_exp = float(pd.to_numeric(eq["gross_exposure"], errors="coerce").max()) if "gross_exposure" in eq else np.nan
    max_risk = float(pd.to_numeric(eq["portfolio_risk"], errors="coerce").max()) if "portfolio_risk" in eq else np.nan

    pf_20bps = float(shock.loc[shock["extra_round_trip_bps"] == 20, "pf"].iloc[0])
    pnl_20bps = float(shock.loc[shock["extra_round_trip_bps"] == 20, "net_pnl"].iloc[0])

    fixed3 = stress.loc[pd.to_numeric(stress["cost_factor"], errors="coerce") == 3.0]
    fixed3_pf = float(fixed3["pf"].iloc[0]) if len(fixed3) else np.nan

    # Monitoring-only recent diagnostic. It does NOT alter the frozen system.
    last40 = rolling.loc[rolling["window"] == 40].tail(1)
    last40_pf = float(last40["pf"].iloc[0]) if len(last40) else np.nan
    last40_avgR = float(last40["avg_R"].iloc[0]) if len(last40) else np.nan

    mc_loss = float(monte["p_loss_pct"].iloc[0]) if len(monte) else np.nan

    checks = {
        "v9_survived_predeclared_holdout": verdict.get("classification") in {
            "SURVIVES_HOLDOUT", "STRONG_CONFIRMATION"
        },
        "fixed_3x_pf_ge_1_20": bool(np.isfinite(fixed3_pf) and fixed3_pf >= 1.20),
        "extra_20bps_pf_ge_1_20": bool(np.isfinite(pf_20bps) and pf_20bps >= 1.20),
        "extra_20bps_pnl_positive": bool(pnl_20bps > 0),
        "no_entry_cap_violations": cap_viol == 0,
        "holdout_pf_without_top5_ge_1_20": bool(float(r["pf_without_top5"]) >= 1.20),
        "holdout_trades_ge_100": int(r["trades"]) >= 100,
    }

    hard_ok = all(checks.values())

    # Recent deterioration is deliberately a warning, not a reason to rewrite
    # the strategy using 2026.
    warnings = []
    if np.isfinite(last40_pf) and last40_pf < 1.0:
        warnings.append("Recent last-40-trade PF is below 1.0; monitor in paper trading, do not retune on 2026.")
    if np.isfinite(last40_avgR) and last40_avgR < 0:
        warnings.append("Recent last-40-trade AvgR is negative; monitor regime drift without changing frozen thresholds.")
    if float(r.get("top5_ticker_share_pct", np.nan)) > 100:
        warnings.append("Top-5 ticker contribution exceeds total net PnL; ticker concentration remains material.")
    if np.isfinite(mc_loss) and mc_loss > 20:
        warnings.append("Month-block Monte Carlo shows meaningful loss probability; size expectations conservatively.")

    classification = "PAPER_TRADE_READY_WITH_MONITORING" if hard_ok else "OPERATIONAL_REVIEW_REQUIRED"

    payload = {
        "version": "V10_DEPLOYMENT_READINESS",
        "architecture_manifest_sha256": manifest.get("sha256"),
        "strategy_parameters_changed": False,
        "classification": classification,
        "hard_checks": checks,
        "monitoring_warnings": warnings,
        "policy": (
            "V10 is an operational audit only. Do not alter thresholds/components/exits "
            "using V9/V10. Any strategy architecture change requires a new future holdout."
        ),
    }
    return payload, {
        "classification": classification,
        "v9_return_pct": float(r["return_pct"]),
        "v9_pf": float(r["pf"]),
        "v9_avg_R": float(r["avg_R"]),
        "v9_dd_pct": float(r["dd_pct"]),
        "v9_trades": int(r["trades"]),
        "v9_pf_without_top5": float(r["pf_without_top5"]),
        "fixed_3x_pf": fixed3_pf,
        "extra_20bps_pf": pf_20bps,
        "extra_20bps_pnl": pnl_20bps,
        "max_gross_exposure": max_exp,
        "max_portfolio_risk": max_risk,
        "entry_cap_violations": cap_viol,
        "last40_pf": last40_pf,
        "last40_avg_R": last40_avgR,
        "monte_carlo_loss_probability_pct": mc_loss,
        "warnings": " | ".join(warnings),
    }


def run_v10_audit():
    print("\n" + "=" * 126)
    print("V10 — DEPLOYMENT READINESS / OPERATIONAL AUDIT")
    print("=" * 126)
    print("NO optimiza la estrategia.")
    print("Arquitectura congelada: ATR 3–5% + VolRel >= 1.15 + RS20 base 1%.")
    print("Objetivo: stress operativo, concentración, secuencias de pérdida y paper-trading readiness.")

    loaded = _load()
    if loaded is None:
        return

    train, hold, eq, result, stress, verdict, manifest = loaded

    print(f"\nReferencia V8 congelada: {len(train)} trades")
    print(f"Holdout V9:             {len(hold)} trades")
    print(f"Manifest:               {manifest.get('sha256', '')[:16]}…")
    print(f"V9 classification:      {verdict.get('classification')}")

    periods = _period_diagnostics(train, hold)
    shock = _execution_shock(hold)
    streaks = _loss_streak_table(train, hold)
    rolling = _rolling_edge(hold)
    monte = _monte_carlo_month_blocks(hold)
    conc = _concentration(train, hold)

    payload, summary_row = _readiness(
        train, hold, eq, result, stress, shock, rolling, monte, verdict, manifest
    )

    summary = pd.DataFrame([summary_row])

    periods.to_csv(PERIOD_PATH, index=False)
    shock.to_csv(SHOCK_PATH, index=False)
    streaks.to_csv(STREAK_PATH, index=False)
    rolling.to_csv(ROLLING_PATH, index=False)
    monte.to_csv(MONTE_PATH, index=False)
    conc.to_csv(CONC_PATH, index=False)
    summary.to_csv(SUMMARY_PATH, index=False)
    VERDICT_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    print("\n" + "=" * 126)
    print("AUDITORÍA DE EJECUCIÓN — HOLDOUT 2026")
    print("=" * 126)
    for _, row in shock.iterrows():
        print(
            f"extra {int(row.extra_round_trip_bps):>3} bps RT | "
            f"PF {row.pf:>5.2f} | PnL {row.net_pnl:>10,.0f} | "
            f"Ret/Capital {row.return_on_initial_capital_pct:+6.2f}%"
        )

    print("\n" + "=" * 126)
    print("SECUENCIAS / DRAWDOWN POR TRADES")
    print("=" * 126)
    for _, row in streaks.iterrows():
        print(
            f"{row.period:<22} | TR {int(row.trades):>4} | "
            f"max pérdidas seguidas {int(row.max_consecutive_losses):>2} | "
            f"trade-R DD {row.trade_R_drawdown:+.2f}R | "
            f"worst {row.worst_trade_R:+.2f}R"
        )

    print("\n" + "=" * 126)
    print("MONTE CARLO — BLOQUES MENSUALES DEL HOLDOUT")
    print("=" * 126)
    if len(monte):
        m = monte.iloc[0]
        print(
            f"{int(m.simulations):,} simulaciones | P(PnL <= 0) {m.p_loss_pct:.1f}% | "
            f"P05 PnL {m.p05_net_pnl:,.0f} | mediana {m.median_net_pnl:,.0f} | "
            f"P95 {m.p95_net_pnl:,.0f}"
        )

    s = summary.iloc[0]
    print("\n" + "=" * 126)
    print("READINESS VERDICT")
    print("=" * 126)
    print(f"{s.classification}")
    print(
        f"V9 PF {s.v9_pf:.2f} | fixed 3x PF {s.fixed_3x_pf:.2f} | "
        f"+20bps PF {s.extra_20bps_pf:.2f} | cap violations {int(s.entry_cap_violations)}"
    )
    if np.isfinite(s.last40_pf):
        print(f"Últimos 40 trades: PF {s.last40_pf:.2f} | AvgR {s.last40_avg_R:+.3f}")

    warnings = payload["monitoring_warnings"]
    if warnings:
        print("\n⚠️ WARNINGS DE MONITOREO — NO SON SEÑALES PARA RETUNEAR:")
        for w in warnings:
            print("  •", w)

    print("\nArchivos generados en ./results/:")
    for p in [
        SUMMARY_PATH, PERIOD_PATH, SHOCK_PATH, STREAK_PATH,
        ROLLING_PATH, MONTE_PATH, CONC_PATH, VERDICT_PATH,
    ]:
        print("  •", p.name)

    print("\nREGLA DESPUÉS DE V10:")
    print("• No se toca la arquitectura con información de 2026.")
    print("• El siguiente paso, si pasa, es shadow/paper trading con señales reales.")
    print("• Los datos futuros del paper trading forman el próximo holdout genuino.")
