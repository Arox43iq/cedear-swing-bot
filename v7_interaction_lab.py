from __future__ import annotations

"""
V7 — ROBUST INTERACTION & INDEPENDENT-YEAR LAB

Purpose
-------
Take the strongest V6 family (ATR%) and try to falsify whether adding volume or
RS20 improves it robustly, without touching 2026.

Method upgrades vs V6
---------------------
- Independent annual backtests (capital reset each year).
- Cluster/bootstrap by entry month instead of IID trade bootstrap.
- Fixed-path and endogenous cost stress both retained.
- Concentration checks retained.
- Incremental deltas are measured against the broad ATR_3.0_5.0 anchor.

This module imports V6 helper functions and does not modify research_engine.py
or strategy.py.
"""

from pathlib import Path
import numpy as np
import pandas as pd

import research_engine as re
import v6_falsification_lab as v6

OUT = Path("results")
OUT.mkdir(exist_ok=True)

START = pd.Timestamp("2023-01-03")
END = pd.Timestamp("2025-12-31")
COMPONENTS = ("trend", "pullback", "rs20", "volume", "candle")

# The anchor is intentionally the broadest strong ATR plateau point from V6.
# Interactions are few and pre-declared; no giant sweep.
EXPERIMENTS = [
    {"name": "CONTROL", "family": "CONTROL", "filter": {}},
    {"name": "ATR_2.5_4.5", "family": "ATR", "filter": {"atr_min": 0.025, "atr_max": 0.045}},
    {"name": "ATR_3.0_4.5", "family": "ATR", "filter": {"atr_min": 0.030, "atr_max": 0.045}},
    {"name": "ATR_3.0_5.0", "family": "ATR", "filter": {"atr_min": 0.030, "atr_max": 0.050}},
    {"name": "ATR3_5_VOLREL1.15", "family": "ATR+VOLREL", "filter": {"atr_min": 0.030, "atr_max": 0.050, "volrel_min": 1.15}},
    {"name": "ATR3_5_VOLREL1.25", "family": "ATR+VOLREL", "filter": {"atr_min": 0.030, "atr_max": 0.050, "volrel_min": 1.25}},
    {"name": "ATR3_5_RS20_8", "family": "ATR+RS20", "filter": {"atr_min": 0.030, "atr_max": 0.050, "rs20_min": 0.08}},
    {"name": "ATR3_5_RS20_10", "family": "ATR+RS20", "filter": {"atr_min": 0.030, "atr_max": 0.050, "rs20_min": 0.10}},
    {"name": "ATR3_5_VOL1.25_RS8", "family": "TRIPLE", "filter": {"atr_min": 0.030, "atr_max": 0.050, "volrel_min": 1.25, "rs20_min": 0.08}},
]

YEAR_WINDOWS = {
    2023: (pd.Timestamp("2023-01-03"), pd.Timestamp("2023-12-31")),
    2024: (pd.Timestamp("2024-01-01"), pd.Timestamp("2024-12-31")),
    2025: (pd.Timestamp("2025-01-01"), pd.Timestamp("2025-12-31")),
}


def _base_cfg():
    cfg = dict(re.CONFIG)
    cfg["rs20_min"] = 0.01
    cfg["tp_r"] = 1.8
    cfg["stop_atr"] = 1.5
    cfg["risk_per_trade"] = 0.005
    cfg["max_gross_exposure"] = 0.90
    cfg["max_portfolio_risk"] = 0.025
    return cfg


def _run(data, spy, cfg, spec, start, end, cost_factor=1.0, label=""):
    c = dict(cfg)
    c["commission"] = cfg["commission"] * cost_factor
    c["slippage"] = cfg["slippage"] * cost_factor
    with v6._signal_filter_patch(spec):
        trades, equity = re.backtest(data, spy, c, COMPONENTS, start, end, label=label)
    return trades, equity, c


def _cluster_bootstrap_avg_r(trades: pd.DataFrame, n_boot=5000, seed=270910):
    """Bootstrap whole entry-month clusters, preserving within-month dependence."""
    if trades.empty or "R" not in trades or "entry_date" not in trades:
        return np.nan, np.nan
    x = trades[["entry_date", "R"]].copy()
    x["entry_date"] = pd.to_datetime(x["entry_date"], errors="coerce")
    x["R"] = pd.to_numeric(x["R"], errors="coerce")
    x = x.dropna()
    if len(x) < 20:
        return np.nan, np.nan
    x["month"] = x["entry_date"].dt.to_period("M").astype(str)
    clusters = [g["R"].to_numpy(dtype=float) for _, g in x.groupby("month") if len(g)]
    if len(clusters) < 6:
        return np.nan, np.nan
    rng = np.random.default_rng(seed)
    means = np.empty(n_boot, dtype=float)
    ncl = len(clusters)
    for i in range(n_boot):
        picks = rng.integers(0, ncl, size=ncl)
        vals = np.concatenate([clusters[j] for j in picks])
        means[i] = vals.mean() if len(vals) else np.nan
    means = means[np.isfinite(means)]
    if len(means) < 100:
        return np.nan, np.nan
    lo, hi = np.quantile(means, [0.025, 0.975])
    return float(lo), float(hi)


def _monthly_table(trades: pd.DataFrame, experiment: str, family: str) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame()
    x = trades.copy()
    x["entry_date"] = pd.to_datetime(x["entry_date"], errors="coerce")
    x["month"] = x["entry_date"].dt.to_period("M").astype(str)
    rows = []
    for month, g in x.groupby("month"):
        pnl = pd.to_numeric(g["net_pnl"], errors="coerce").dropna()
        rr = pd.to_numeric(g["R"], errors="coerce").dropna()
        rows.append({
            "experiment": experiment,
            "family": family,
            "month": month,
            "trades": int(len(g)),
            "net_pnl": float(pnl.sum()),
            "pf": v6._pf_from_pnl(pnl),
            "avg_R": float(rr.mean()) if len(rr) else 0.0,
            "win_rate": float((pnl > 0).mean() * 100) if len(pnl) else 0.0,
        })
    return pd.DataFrame(rows)


def _summary_row(name, family, period, trades, equity, cfg, boot=False, seed=0):
    m = re.metrics(trades, equity, cfg)
    lo, hi = _cluster_bootstrap_avg_r(trades, seed=seed) if boot else (np.nan, np.nan)
    pnl = pd.to_numeric(trades.get("net_pnl", pd.Series(dtype=float)), errors="coerce").sum() if not trades.empty else 0.0
    return {
        "experiment": name,
        "family": family,
        "period": period,
        "return_pct": m["return_pct"],
        "pf": m["pf"],
        "dd_pct": m["dd_pct"],
        "trades": m["trades"],
        "win_rate": m["win_rate"],
        "avg_R": m["avg_R"],
        "sharpe": m["sharpe"],
        "net_pnl": float(pnl),
        "cluster_boot_lo95": lo,
        "cluster_boot_hi95": hi,
    }


def _incremental(summary: pd.DataFrame, concentration: pd.DataFrame, fixed: pd.DataFrame) -> pd.DataFrame:
    anchor = "ATR_3.0_5.0"
    a = summary[(summary.experiment == anchor) & (summary.period == "TOTAL")].iloc[0]
    ac = concentration[concentration.experiment == anchor].iloc[0]
    af2 = fixed[(fixed.experiment == anchor) & (fixed.cost_factor == 2.0)].iloc[0]
    af3 = fixed[(fixed.experiment == anchor) & (fixed.cost_factor == 3.0)].iloc[0]
    rows = []
    for _, r in summary[summary.period == "TOTAL"].iterrows():
        c = concentration[concentration.experiment == r.experiment].iloc[0]
        f2 = fixed[(fixed.experiment == r.experiment) & (fixed.cost_factor == 2.0)].iloc[0]
        f3 = fixed[(fixed.experiment == r.experiment) & (fixed.cost_factor == 3.0)].iloc[0]
        years = summary[(summary.experiment == r.experiment) & summary.period.isin(["2023","2024","2025"])]
        pos_years = int(((years.pf > 1.0) & (years.avg_R > 0)).sum())
        rows.append({
            "experiment": r.experiment,
            "family": r.family,
            "delta_return_vs_ATR3_5": r.return_pct - a.return_pct,
            "delta_pf_vs_ATR3_5": r.pf - a.pf,
            "delta_avgR_vs_ATR3_5": r.avg_R - a.avg_R,
            "delta_dd_vs_ATR3_5": r.dd_pct - a.dd_pct,
            "delta_trades_vs_ATR3_5": int(r.trades - a.trades),
            "positive_independent_years": pos_years,
            "delta_pnl_without_top10": c.pnl_without_top10 - ac.pnl_without_top10,
            "delta_fixed2x_pf": f2.pf - af2.pf,
            "delta_fixed3x_pf": f3.pf - af3.pf,
        })
    return pd.DataFrame(rows)


def run_v7_lab(universe="USA"):
    if universe != "USA":
        print("\n⚠️ V7 se ejecuta solamente sobre USA.")
        return

    print("\n" + "=" * 122)
    print("V7 — ROBUST INTERACTION + INDEPENDENT-YEAR LAB — USA")
    print("=" * 122)
    print("Objetivo: intentar refutar si el edge ATR sobrevive años independientes y si volumen/RS20 agregan valor incremental.")
    print("2026 sigue CONGELADO y no se usa para seleccionar nada.")
    print("Mejoras: backtests anuales independientes + bootstrap por mes + stress fixed-path/endógeno + concentración.")

    raw = re.download_universe("USA")
    spy_raw = re.download_spy()
    data, spy = re.prepare(raw, spy_raw)
    if not data:
        print("❌ No hay datos válidos.")
        return

    cfg = _base_cfg()
    summary_rows, conc_rows, fixed_rows, endo_rows = [], [], [], []
    monthly_frames, trade_frames = [], []

    print(f"\nActivos preparados: {len(data)}")
    print(f"Experimentos predeclarados: {len(EXPERIMENTS)}")

    for i, exp in enumerate(EXPERIMENTS, 1):
        name, family, spec = exp["name"], exp["family"], exp["filter"]
        print(f"\n[{i:02d}/{len(EXPERIMENTS):02d}] {name}")

        trades, equity, c = _run(data, spy, cfg, spec, START, END, 1.0, f"V7 {name} TOTAL")
        total = _summary_row(name, family, "TOTAL", trades, equity, c, boot=True, seed=270910+i)
        summary_rows.append(total)

        conc = v6._concentration(trades)
        conc_rows.append({"experiment": name, "family": family, **conc})

        for factor in [1.0, 2.0, 3.0]:
            fs = v6._fixed_path_cost_stress(trades, cfg, factor)
            fixed_rows.append({"experiment": name, "family": family, "cost_factor": factor, **fs, "trades": int(len(trades))})

        endo_rows.append({
            "experiment": name, "family": family, "cost_factor": 1.0,
            "return_pct": total["return_pct"], "pf": total["pf"], "dd_pct": total["dd_pct"],
            "trades": total["trades"], "avg_R": total["avg_R"]
        })
        for factor in [2.0, 3.0]:
            ts, es, cs = _run(data, spy, cfg, spec, START, END, factor, f"V7 {name} x{factor:g}")
            ms = re.metrics(ts, es, cs)
            endo_rows.append({
                "experiment": name, "family": family, "cost_factor": factor,
                "return_pct": ms["return_pct"], "pf": ms["pf"], "dd_pct": ms["dd_pct"],
                "trades": ms["trades"], "avg_R": ms["avg_R"]
            })

        # Truly independent annual runs: each call restarts from CONFIG capital.
        for year, (ys, ye) in YEAR_WINDOWS.items():
            ty, ey, cy = _run(data, spy, cfg, spec, ys, ye, 1.0, f"V7 {name} {year}")
            summary_rows.append(_summary_row(name, family, str(year), ty, ey, cy, boot=False))

        mt = _monthly_table(trades, name, family)
        if not mt.empty:
            monthly_frames.append(mt)
        if not trades.empty:
            tt = trades.copy()
            tt.insert(0, "experiment", name)
            tt.insert(1, "family", family)
            trade_frames.append(tt)

        print(
            f"  TOTAL {total['return_pct']:+.2f}% | PF {total['pf']:.2f} | DD {total['dd_pct']:+.2f}% | "
            f"TR {total['trades']} | AvgR {total['avg_R']:+.3f} | cluster95 [{total['cluster_boot_lo95']:+.3f}, {total['cluster_boot_hi95']:+.3f}]"
        )
        print(f"  sin top10 PnL {conc['pnl_without_top10']:+,.0f} | PF-10 {conc['pf_without_top10']:.2f}")

    summary = pd.DataFrame(summary_rows)
    concentration = pd.DataFrame(conc_rows)
    fixed = pd.DataFrame(fixed_rows)
    endogenous = pd.DataFrame(endo_rows)
    monthly = pd.concat(monthly_frames, ignore_index=True) if monthly_frames else pd.DataFrame()
    all_trades = pd.concat(trade_frames, ignore_index=True) if trade_frames else pd.DataFrame()
    incremental = _incremental(summary, concentration, fixed)

    summary.to_csv(OUT / "v7_summary.csv", index=False)
    concentration.to_csv(OUT / "v7_concentration.csv", index=False)
    fixed.to_csv(OUT / "v7_fixed_path_cost_stress.csv", index=False)
    endogenous.to_csv(OUT / "v7_endogenous_cost_stress.csv", index=False)
    incremental.to_csv(OUT / "v7_incremental_vs_atr.csv", index=False)
    if not monthly.empty:
        monthly.to_csv(OUT / "v7_monthly_blocks.csv", index=False)
    if not all_trades.empty:
        all_trades.to_csv(OUT / "v7_all_trades.csv", index=False)

    print("\n" + "=" * 122)
    print("TOTAL + BOOTSTRAP POR MES")
    print("=" * 122)
    print(f"{'EXPERIMENTO':<23}{'RET':>9}{'PF':>8}{'DD':>9}{'TR':>7}{'AvgR':>9}{'CL LO':>10}{'CL HI':>10}")
    for _, r in summary[summary.period == "TOTAL"].iterrows():
        print(f"{r.experiment:<23}{r.return_pct:>+8.2f}%{r.pf:>8.2f}{r.dd_pct:>+8.2f}%{int(r.trades):>7}{r.avg_R:>+9.3f}{r.cluster_boot_lo95:>+10.3f}{r.cluster_boot_hi95:>+10.3f}")

    print("\n" + "=" * 122)
    print("AÑOS INDEPENDIENTES — CAPITAL REINICIADO EN CADA BACKTEST")
    print("=" * 122)
    for exp in EXPERIMENTS:
        g = summary[(summary.experiment == exp["name"]) & summary.period.isin(["2023","2024","2025"])]
        parts = [f"{r.period} Ret {r.return_pct:+.2f}% PF {r.pf:.2f} AvgR {r.avg_R:+.3f} TR {int(r.trades)}" for _, r in g.iterrows()]
        print(f"{exp['name']:<23} | " + " | ".join(parts))

    print("\n" + "=" * 122)
    print("DELTA VS ATR_3.0_5.0 — NO ES UN SELECTOR AUTOMÁTICO")
    print("=" * 122)
    cols = ["experiment","delta_return_vs_ATR3_5","delta_pf_vs_ATR3_5","delta_avgR_vs_ATR3_5","delta_trades_vs_ATR3_5","positive_independent_years","delta_pnl_without_top10","delta_fixed2x_pf","delta_fixed3x_pf"]
    print(incremental[cols].to_string(index=False))

    print("\n" + "=" * 122)
    print("ENDOGENOUS COST STRESS")
    print("=" * 122)
    for exp in EXPERIMENTS:
        g = endogenous[endogenous.experiment == exp["name"]].sort_values("cost_factor")
        parts = [f"x{r.cost_factor:g} Ret {r.return_pct:+.2f}% PF {r.pf:.2f} DD {r.dd_pct:+.2f}%" for _, r in g.iterrows()]
        print(f"{exp['name']:<23} | " + " | ".join(parts))

    print("\nArchivos generados en ./results/:")
    for fn in [
        "v7_summary.csv", "v7_concentration.csv", "v7_fixed_path_cost_stress.csv",
        "v7_endogenous_cost_stress.csv", "v7_incremental_vs_atr.csv",
        "v7_monthly_blocks.csv", "v7_all_trades.csv"
    ]:
        print(f"  • {fn}")

    print("\nIMPORTANTE:")
    print("• 2026 permanece intacto.")
    print("• Los años ahora sí son backtests independientes, no cortes de una curva continua.")
    print("• El bootstrap agrupa por mes para castigar dependencia temporal/cross-sectional.")
    print("• No elijas el mayor retorno: mandame output + CSV y la siguiente decisión se toma por robustez.")
