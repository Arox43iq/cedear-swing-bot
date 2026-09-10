from __future__ import annotations

"""
V8 — STRUCTURAL ROBUSTNESS / UNIVERSE STRESS LAB

Purpose
-------
Try to break the V7 leading architecture before touching 2026.
This is NOT an optimizer. It tests local threshold stability, independent
half-years, winner-ticker dependence, paired random-universe dropout and costs.

Leading hypothesis entering V8 (predeclared from V7):
    trend + pullback + rs20 + volume + candle
    base RS20 >= 1%
    ATR% in [3%, 5%]
    VolRel >= 1.15
    TP = 1.8R, stop = 1.5 ATR, risk/trade = 0.5%

2026 remains excluded from every evaluation in this module.
"""

from pathlib import Path
import numpy as np
import pandas as pd

import research_engine as re
import v6_falsification_lab as v6
import v7_interaction_lab as v7

OUT = Path("results")
OUT.mkdir(exist_ok=True)

START = pd.Timestamp("2023-01-03")
END = pd.Timestamp("2025-12-31")
COMPONENTS = ("trend", "pullback", "rs20", "volume", "candle")

# These are robustness perturbations, not candidates to optimize over.
PERTURBATIONS = [
    {"name": "ATR_ONLY_3_5",       "family": "ANCHOR",   "filter": {"atr_min": 0.030, "atr_max": 0.050}},
    {"name": "VREL_1.10",          "family": "VOL_NEIGH", "filter": {"atr_min": 0.030, "atr_max": 0.050, "volrel_min": 1.10}},
    {"name": "VREL_1.15_LEAD",     "family": "VOL_NEIGH", "filter": {"atr_min": 0.030, "atr_max": 0.050, "volrel_min": 1.15}},
    {"name": "VREL_1.20",          "family": "VOL_NEIGH", "filter": {"atr_min": 0.030, "atr_max": 0.050, "volrel_min": 1.20}},
    {"name": "VREL_1.25",          "family": "VOL_NEIGH", "filter": {"atr_min": 0.030, "atr_max": 0.050, "volrel_min": 1.25}},
    {"name": "VREL_1.30",          "family": "VOL_NEIGH", "filter": {"atr_min": 0.030, "atr_max": 0.050, "volrel_min": 1.30}},
    {"name": "ATR_2.8_5_V115",     "family": "ATR_NEIGH", "filter": {"atr_min": 0.028, "atr_max": 0.050, "volrel_min": 1.15}},
    {"name": "ATR_3_4.7_V115",     "family": "ATR_NEIGH", "filter": {"atr_min": 0.030, "atr_max": 0.047, "volrel_min": 1.15}},
    {"name": "ATR_3_5.3_V115",     "family": "ATR_NEIGH", "filter": {"atr_min": 0.030, "atr_max": 0.053, "volrel_min": 1.15}},
    {"name": "ATR_3.2_5_V115",     "family": "ATR_NEIGH", "filter": {"atr_min": 0.032, "atr_max": 0.050, "volrel_min": 1.15}},
]

CORE_SPECS = {
    "ATR_ONLY_3_5": {"atr_min": 0.030, "atr_max": 0.050},
    "VREL_1.15_LEAD": {"atr_min": 0.030, "atr_max": 0.050, "volrel_min": 1.15},
    "VREL_1.25": {"atr_min": 0.030, "atr_max": 0.050, "volrel_min": 1.25},
}

HALF_WINDOWS = [
    ("2023H1", pd.Timestamp("2023-01-03"), pd.Timestamp("2023-06-30")),
    ("2023H2", pd.Timestamp("2023-07-01"), pd.Timestamp("2023-12-31")),
    ("2024H1", pd.Timestamp("2024-01-01"), pd.Timestamp("2024-06-30")),
    ("2024H2", pd.Timestamp("2024-07-01"), pd.Timestamp("2024-12-31")),
    ("2025H1", pd.Timestamp("2025-01-01"), pd.Timestamp("2025-06-30")),
    ("2025H2", pd.Timestamp("2025-07-01"), pd.Timestamp("2025-12-31")),
]


def _base_cfg():
    return v7._base_cfg()


def _run(data, spy, cfg, spec, start=START, end=END, factor=1.0, label=""):
    return v7._run(data, spy, cfg, spec, start, end, cost_factor=factor, label=label)


def _pnl_pf(trades: pd.DataFrame):
    if trades is None or trades.empty:
        return 0.0, 0.0, 0.0
    pnl = pd.to_numeric(trades["net_pnl"], errors="coerce").fillna(0.0)
    rr = pd.to_numeric(trades["R"], errors="coerce").dropna()
    return float(pnl.sum()), float(v6._pf_from_pnl(pnl)), float(rr.mean()) if len(rr) else 0.0


def _metric_row(name, family, trades, equity, cfg):
    m = re.metrics(trades, equity, cfg)
    lo, hi = v7._cluster_bootstrap_avg_r(trades, n_boot=4000, seed=81173 + sum(map(ord, name)))
    c = v6._concentration(trades)
    return {
        "experiment": name,
        "family": family,
        "return_pct": m["return_pct"],
        "pf": m["pf"],
        "dd_pct": m["dd_pct"],
        "trades": m["trades"],
        "win_rate": m["win_rate"],
        "avg_R": m["avg_R"],
        "sharpe": m["sharpe"],
        "cluster_lo95": lo,
        "cluster_hi95": hi,
        "pnl_without_top5": c["pnl_without_top5"],
        "pnl_without_top10": c["pnl_without_top10"],
        "pf_without_top10": c["pf_without_top10"],
    }


def _ticker_contribution(trades, name):
    if trades.empty:
        return pd.DataFrame()
    x = trades.copy()
    x["net_pnl"] = pd.to_numeric(x["net_pnl"], errors="coerce").fillna(0.0)
    x["R"] = pd.to_numeric(x["R"], errors="coerce")
    g = x.groupby("ticker", as_index=False).agg(
        trades=("ticker", "size"),
        net_pnl=("net_pnl", "sum"),
        avg_R=("R", "mean"),
    ).sort_values("net_pnl", ascending=False)
    g.insert(0, "experiment", name)
    total = abs(float(x["net_pnl"].sum()))
    g["share_of_abs_total_pnl_pct"] = np.where(total > 0, g["net_pnl"] / total * 100.0, 0.0)
    return g


def _halfyear_tests(data, spy, cfg):
    rows = []
    for name, spec in CORE_SPECS.items():
        for period, st, en in HALF_WINDOWS:
            t, e, c = _run(data, spy, cfg, spec, st, en, 1.0, f"V8 {name} {period}")
            m = re.metrics(t, e, c)
            rows.append({
                "experiment": name,
                "period": period,
                "return_pct": m["return_pct"],
                "pf": m["pf"],
                "dd_pct": m["dd_pct"],
                "trades": m["trades"],
                "avg_R": m["avg_R"],
                "positive": int(m["pf"] > 1.0 and m["avg_R"] > 0),
            })
    return pd.DataFrame(rows)


def _winner_removal_stress(data, spy, cfg, leading_trades):
    """Endogenous reruns after removing the ex-post largest winning tickers."""
    if leading_trades.empty:
        return pd.DataFrame()
    contrib = leading_trades.groupby("ticker")["net_pnl"].sum().sort_values(ascending=False)
    winners = [x for x in contrib.index if contrib.loc[x] > 0]
    rows = []
    spec = CORE_SPECS["VREL_1.15_LEAD"]
    for n in [0, 1, 3, 5, 10]:
        removed = winners[:n]
        sub = {k: v for k, v in data.items() if k not in set(removed)}
        t, e, c = _run(sub, spy, cfg, spec, START, END, 1.0, f"V8 remove top {n} tickers")
        m = re.metrics(t, e, c)
        rows.append({
            "removed_top_winner_tickers": n,
            "removed": ";".join(removed),
            "universe_size": len(sub),
            "return_pct": m["return_pct"],
            "pf": m["pf"],
            "dd_pct": m["dd_pct"],
            "trades": m["trades"],
            "avg_R": m["avg_R"],
        })
    return pd.DataFrame(rows)


def _paired_random_universe(data, spy, cfg, reps=20, keep_frac=0.80, seed=88115):
    """
    Paired robustness test: use the SAME randomly reduced universe for anchor,
    lead and VREL1.25 so deltas are comparable. This is not model selection.
    """
    tickers = sorted(data.keys())
    n_keep = max(20, int(round(len(tickers) * keep_frac)))
    rng = np.random.default_rng(seed)
    rows = []
    for rep in range(1, reps + 1):
        keep = sorted(rng.choice(tickers, size=n_keep, replace=False).tolist())
        sub = {k: data[k] for k in keep}
        rep_metrics = {}
        for name, spec in CORE_SPECS.items():
            t, e, c = _run(sub, spy, cfg, spec, START, END, 1.0, f"V8 dropout {rep:02d} {name}")
            m = re.metrics(t, e, c)
            rep_metrics[name] = m
            rows.append({
                "rep": rep,
                "keep_frac": keep_frac,
                "universe_size": len(sub),
                "experiment": name,
                "return_pct": m["return_pct"],
                "pf": m["pf"],
                "dd_pct": m["dd_pct"],
                "trades": m["trades"],
                "avg_R": m["avg_R"],
            })
    return pd.DataFrame(rows)


def _dropout_summary(drop):
    if drop.empty:
        return pd.DataFrame()
    rows = []
    anchor = drop[drop.experiment == "ATR_ONLY_3_5"].set_index("rep")
    for name, g in drop.groupby("experiment"):
        g = g.set_index("rep").sort_index()
        common = g.index.intersection(anchor.index)
        dpf = g.loc[common, "pf"] - anchor.loc[common, "pf"]
        dret = g.loc[common, "return_pct"] - anchor.loc[common, "return_pct"]
        davg = g.loc[common, "avg_R"] - anchor.loc[common, "avg_R"]
        rows.append({
            "experiment": name,
            "reps": len(g),
            "median_return": float(g.return_pct.median()),
            "worst_return": float(g.return_pct.min()),
            "median_pf": float(g.pf.median()),
            "worst_pf": float(g.pf.min()),
            "median_avg_R": float(g.avg_R.median()),
            "positive_pf_reps_pct": float((g.pf > 1.0).mean() * 100),
            "beats_anchor_pf_pct": float((dpf > 0).mean() * 100) if len(dpf) else np.nan,
            "beats_anchor_return_pct": float((dret > 0).mean() * 100) if len(dret) else np.nan,
            "beats_anchor_avgR_pct": float((davg > 0).mean() * 100) if len(davg) else np.nan,
        })
    return pd.DataFrame(rows)


def _cost_stress(full_trades, data, spy, cfg):
    fixed_rows, endo_rows = [], []
    for name, spec in CORE_SPECS.items():
        t1 = full_trades[name]
        for factor in [1.0, 2.0, 3.0]:
            fs = v6._fixed_path_cost_stress(t1, cfg, factor)
            fixed_rows.append({"experiment": name, "cost_factor": factor, **fs, "trades": len(t1)})
            if factor == 1.0:
                # use actual base run metrics via a fresh run for clean DD reporting
                tt, ee, cc = _run(data, spy, cfg, spec, START, END, 1.0, f"V8 cost {name} x1")
            else:
                tt, ee, cc = _run(data, spy, cfg, spec, START, END, factor, f"V8 cost {name} x{factor:g}")
            m = re.metrics(tt, ee, cc)
            endo_rows.append({
                "experiment": name, "cost_factor": factor,
                "return_pct": m["return_pct"], "pf": m["pf"], "dd_pct": m["dd_pct"],
                "trades": m["trades"], "avg_R": m["avg_R"],
            })
    return pd.DataFrame(fixed_rows), pd.DataFrame(endo_rows)


def _decision_scorecard(summary, halves, dropout_summary, removal):
    """Transparent diagnostics only. No hidden optimizer and no auto-winner."""
    rows = []
    for name in ["ATR_ONLY_3_5", "VREL_1.15_LEAD", "VREL_1.25"]:
        s = summary[summary.experiment == name].iloc[0]
        h = halves[halves.experiment == name]
        d = dropout_summary[dropout_summary.experiment == name].iloc[0]
        row = {
            "experiment": name,
            "total_pf": s.pf,
            "total_avg_R": s.avg_R,
            "cluster_lo95": s.cluster_lo95,
            "positive_halfyears": int(h.positive.sum()),
            "halfyears": int(len(h)),
            "worst_halfyear_pf": float(h.pf.min()),
            "median_dropout_pf": d.median_pf,
            "worst_dropout_pf": d.worst_pf,
            "dropout_positive_pct": d.positive_pf_reps_pct,
            "beats_anchor_pf_pct": d.beats_anchor_pf_pct,
            "beats_anchor_return_pct": d.beats_anchor_return_pct,
            "pnl_without_top10": s.pnl_without_top10,
            "pf_without_top10": s.pf_without_top10,
        }
        if name == "VREL_1.15_LEAD" and not removal.empty:
            r5 = removal[removal.removed_top_winner_tickers == 5]
            if not r5.empty:
                row["pf_after_remove_top5_tickers"] = float(r5.iloc[0].pf)
                row["ret_after_remove_top5_tickers"] = float(r5.iloc[0].return_pct)
        rows.append(row)
    return pd.DataFrame(rows)


def run_v8_lab(universe="USA"):
    if universe != "USA":
        print("\n⚠️ V8 se ejecuta solamente sobre USA.")
        return

    print("\n" + "=" * 126)
    print("V8 — STRUCTURAL ROBUSTNESS / UNIVERSE STRESS LAB — USA")
    print("=" * 126)
    print("Objetivo: intentar ROMPER la candidata ATR 3–5% + VolRel >= 1.15 antes de tocar 2026.")
    print("2026 permanece CONGELADO. No se usa para seleccionar, validar ni ajustar.")
    print("Pruebas: vecindad de umbrales + semestres independientes + top-ticker removal + random universe dropout + costos.")

    raw = re.download_universe("USA")
    spy_raw = re.download_spy()
    data, spy = re.prepare(raw, spy_raw)
    if not data:
        print("❌ No hay datos válidos.")
        return

    cfg = _base_cfg()
    print(f"\nActivos preparados: {len(data)}")
    print(f"Perturbaciones predeclaradas: {len(PERTURBATIONS)}")

    summary_rows = []
    trade_frames = []
    ticker_frames = []
    full_trades = {}

    print("\n" + "=" * 126)
    print("1) PERTURBACIÓN LOCAL — BUSCAMOS MESETA, NO EL MÁXIMO")
    print("=" * 126)
    for i, exp in enumerate(PERTURBATIONS, 1):
        name, family, spec = exp["name"], exp["family"], exp["filter"]
        t, e, c = _run(data, spy, cfg, spec, START, END, 1.0, f"V8 {name}")
        row = _metric_row(name, family, t, e, c)
        summary_rows.append(row)
        if name in CORE_SPECS:
            full_trades[name] = t.copy()
        if not t.empty:
            tt = t.copy(); tt.insert(0, "experiment", name); tt.insert(1, "family", family)
            trade_frames.append(tt)
            ticker_frames.append(_ticker_contribution(t, name))
        print(
            f"[{i:02d}/{len(PERTURBATIONS):02d}] {name:<20} Ret {row['return_pct']:+7.2f}% | "
            f"PF {row['pf']:.2f} | DD {row['dd_pct']:+6.2f}% | TR {row['trades']:3d} | "
            f"AvgR {row['avg_R']:+.3f} | cluster95 [{row['cluster_lo95']:+.3f}, {row['cluster_hi95']:+.3f}]"
        )

    summary = pd.DataFrame(summary_rows)
    all_trades = pd.concat(trade_frames, ignore_index=True) if trade_frames else pd.DataFrame()
    ticker_contrib = pd.concat(ticker_frames, ignore_index=True) if ticker_frames else pd.DataFrame()

    print("\n" + "=" * 126)
    print("2) SEIS SEMESTRES INDEPENDIENTES — CAPITAL REINICIADO")
    print("=" * 126)
    halves = _halfyear_tests(data, spy, cfg)
    for name in CORE_SPECS:
        g = halves[halves.experiment == name]
        print(f"\n{name} | positivos {int(g.positive.sum())}/{len(g)} | peor PF {g.pf.min():.2f}")
        for _, r in g.iterrows():
            print(f"  {r.period}: Ret {r.return_pct:+6.2f}% | PF {r.pf:.2f} | AvgR {r.avg_R:+.3f} | TR {int(r.trades)}")

    print("\n" + "=" * 126)
    print("3) DEPENDENCIA DE TICKERS GANADORES — REBACKTEST ENDÓGENO")
    print("=" * 126)
    leading = full_trades.get("VREL_1.15_LEAD", pd.DataFrame())
    removal = _winner_removal_stress(data, spy, cfg, leading)
    for _, r in removal.iterrows():
        print(
            f"remove top {int(r.removed_top_winner_tickers):2d}: Ret {r.return_pct:+7.2f}% | PF {r.pf:.2f} | "
            f"DD {r.dd_pct:+6.2f}% | TR {int(r.trades):3d} | AvgR {r.avg_R:+.3f}"
        )

    print("\n" + "=" * 126)
    print("4) RANDOM UNIVERSE DROPOUT — 20 UNIVERSOS PAREADOS AL 80%")
    print("=" * 126)
    dropout = _paired_random_universe(data, spy, cfg, reps=20, keep_frac=0.80)
    dropout_summary = _dropout_summary(dropout)
    for _, r in dropout_summary.iterrows():
        print(
            f"{r.experiment:<18} medPF {r.median_pf:.2f} | worstPF {r.worst_pf:.2f} | "
            f"PF>1 {r.positive_pf_reps_pct:5.1f}% | beats anchor PF {r.beats_anchor_pf_pct:5.1f}% | "
            f"beats anchor Ret {r.beats_anchor_return_pct:5.1f}%"
        )

    print("\n" + "=" * 126)
    print("5) COST STRESS — FIXED PATH + ENDÓGENO")
    print("=" * 126)
    # Ensure core trades exist even if names were changed above.
    for name, spec in CORE_SPECS.items():
        if name not in full_trades:
            t, _, _ = _run(data, spy, cfg, spec, START, END, 1.0, f"V8 core {name}")
            full_trades[name] = t
    fixed, endogenous = _cost_stress(full_trades, data, spy, cfg)
    for name in CORE_SPECS:
        f = fixed[fixed.experiment == name]
        e = endogenous[endogenous.experiment == name]
        print(f"\n{name}")
        for fac in [1.0, 2.0, 3.0]:
            fr = f[f.cost_factor == fac].iloc[0]
            er = e[e.cost_factor == fac].iloc[0]
            print(
                f"  x{fac:g}: fixed PF {fr.pf:.2f} Ret {fr.return_pct:+6.2f}% | "
                f"endo PF {er.pf:.2f} Ret {er.return_pct:+6.2f}% DD {er.dd_pct:+6.2f}%"
            )

    scorecard = _decision_scorecard(summary, halves, dropout_summary, removal)

    # Save everything.
    summary.to_csv(OUT / "v8_threshold_robustness.csv", index=False)
    halves.to_csv(OUT / "v8_halfyear_independent.csv", index=False)
    removal.to_csv(OUT / "v8_top_ticker_removal.csv", index=False)
    dropout.to_csv(OUT / "v8_random_universe_dropout.csv", index=False)
    dropout_summary.to_csv(OUT / "v8_random_universe_summary.csv", index=False)
    fixed.to_csv(OUT / "v8_fixed_path_cost_stress.csv", index=False)
    endogenous.to_csv(OUT / "v8_endogenous_cost_stress.csv", index=False)
    scorecard.to_csv(OUT / "v8_scorecard.csv", index=False)
    ticker_contrib.to_csv(OUT / "v8_ticker_contribution.csv", index=False)
    all_trades.to_csv(OUT / "v8_all_trades.csv", index=False)

    print("\n" + "=" * 126)
    print("SCORECARD FINAL — DESCRIPTIVO, NO AUTOSELECTOR")
    print("=" * 126)
    cols = [
        "experiment", "total_pf", "total_avg_R", "cluster_lo95", "positive_halfyears",
        "worst_halfyear_pf", "median_dropout_pf", "worst_dropout_pf",
        "beats_anchor_pf_pct", "pnl_without_top10", "pf_without_top10",
    ]
    print(scorecard[cols].to_string(index=False))

    print("\nArchivos generados en ./results/:")
    for fn in [
        "v8_threshold_robustness.csv",
        "v8_halfyear_independent.csv",
        "v8_top_ticker_removal.csv",
        "v8_random_universe_dropout.csv",
        "v8_random_universe_summary.csv",
        "v8_fixed_path_cost_stress.csv",
        "v8_endogenous_cost_stress.csv",
        "v8_scorecard.csv",
        "v8_ticker_contribution.csv",
        "v8_all_trades.csv",
    ]:
        print(f"  • {fn}")

    print("\nIMPORTANTE:")
    print("• 2026 sigue intacto.")
    print("• V8 NO elige el máximo de la vecindad; busca continuidad alrededor de la candidata.")
    print("• Random-dropout compara arquitecturas sobre exactamente los mismos subconjuntos de tickers.")
    print("• Top-ticker removal vuelve a correr el portfolio; no es solo borrar filas de un CSV.")
    print("• Si la candidata sobrevive esto, la siguiente fase será de congelamiento / test final, no otro sweep.")


if __name__ == "__main__":
    run_v8_lab("USA")
