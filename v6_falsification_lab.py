from __future__ import annotations

"""
V6 — SIGNAL QUALITY FALSIFICATION LAB

Purpose
-------
Attempt to falsify the three signal-quality hypotheses suggested by V5:
1) stronger relative volume,
2) a medium/high ATR% band,
3) very strong RS20.

Rules
-----
- USA only.
- 2023-01-03 through 2025-12-31 only.
- 2026 is NEVER touched by this module.
- No WPR, no momentum.
- TP/SL/sizing/risk caps are frozen at the V5 values.
- Thresholds are broad, pre-declared regions. We do NOT auto-select the best point.
- Fixed-path cost stress and endogenous portfolio cost stress are reported separately.
- PnL concentration and bootstrap uncertainty are included.

This module intentionally leaves research_engine.py and strategy.py unchanged.
"""

from contextlib import contextmanager
from pathlib import Path

import numpy as np
import pandas as pd

import research_engine as re

OUT = Path("results")
OUT.mkdir(exist_ok=True)

V6_START = pd.Timestamp("2023-01-03")
V6_END = pd.Timestamp("2025-12-31")
V6_COMPONENTS = ("trend", "pullback", "rs20", "volume", "candle")

# Pre-declared broad regions from the V5 diagnostic. These are not optimized points.
EXPERIMENTS = [
    {
        "name": "CONTROL",
        "family": "CONTROL",
        "filter": {},
    },
    {"name": "VOLREL_GE_1.15", "family": "VOLREL", "filter": {"volrel_min": 1.15}},
    {"name": "VOLREL_GE_1.25", "family": "VOLREL", "filter": {"volrel_min": 1.25}},
    {"name": "VOLREL_GE_1.35", "family": "VOLREL", "filter": {"volrel_min": 1.35}},
    {"name": "ATR_2.5_4.5", "family": "ATR", "filter": {"atr_min": 0.025, "atr_max": 0.045}},
    {"name": "ATR_3.0_4.5", "family": "ATR", "filter": {"atr_min": 0.030, "atr_max": 0.045}},
    {"name": "ATR_3.0_5.0", "family": "ATR", "filter": {"atr_min": 0.030, "atr_max": 0.050}},
    {"name": "RS20_GE_8", "family": "RS20", "filter": {"rs20_min": 0.08}},
    {"name": "RS20_GE_10", "family": "RS20", "filter": {"rs20_min": 0.10}},
    {"name": "RS20_GE_12", "family": "RS20", "filter": {"rs20_min": 0.12}},
]


def _f(x, default=np.nan):
    try:
        z = float(x)
        return z if np.isfinite(z) else default
    except Exception:
        return default


def _div(a, b, default=0.0):
    a, b = _f(a), _f(b)
    if np.isfinite(a) and np.isfinite(b) and abs(b) > 1e-12:
        return a / b
    return default


def _pf_from_pnl(pnl: pd.Series) -> float:
    x = pd.to_numeric(pnl, errors="coerce").dropna()
    if x.empty:
        return 0.0
    wins = x[x > 0].sum()
    losses = -x[x < 0].sum()
    if losses <= 1e-12:
        return np.inf if wins > 0 else 0.0
    return float(wins / losses)


def _passes_filter(signal_row: dict, spec: dict) -> bool:
    if not spec:
        return True

    vol = _f(signal_row.get("VolRel"))
    atr = _f(signal_row.get("ATR_PCT"))
    rs20 = _f(signal_row.get("RS20"))

    if "volrel_min" in spec and (not np.isfinite(vol) or vol < spec["volrel_min"]):
        return False
    if "atr_min" in spec and (not np.isfinite(atr) or atr < spec["atr_min"]):
        return False
    if "atr_max" in spec and (not np.isfinite(atr) or atr > spec["atr_max"]):
        return False
    if "rs20_min" in spec and (not np.isfinite(rs20) or rs20 < spec["rs20_min"]):
        return False
    return True


@contextmanager
def _signal_filter_patch(spec: dict):
    """Patch only V6's candidate list; restore research_engine immediately after each run."""
    original = re.precompute_signals

    def filtered(data, cfg, active):
        out = original(data, cfg, active)
        if not spec:
            return out
        return {
            ticker: [x for x in rows if _passes_filter(x.get("signal_row", {}), spec)]
            for ticker, rows in out.items()
        }

    re.precompute_signals = filtered
    try:
        yield
    finally:
        re.precompute_signals = original


def _run_backtest(data, spy, cfg, spec, cost_factor=1.0, label=""):
    c = dict(cfg)
    c["commission"] = cfg["commission"] * cost_factor
    c["slippage"] = cfg["slippage"] * cost_factor
    with _signal_filter_patch(spec):
        trades, equity = re.backtest(
            data,
            spy,
            c,
            V6_COMPONENTS,
            V6_START,
            V6_END,
            label=label,
        )
    return trades, equity, c


def _year_stats(trades: pd.DataFrame, equity: pd.DataFrame, year: int, capital: float) -> dict:
    if trades.empty:
        ty = trades.copy()
    else:
        exit_dates = pd.to_datetime(trades["exit_date"], errors="coerce")
        ty = trades.loc[exit_dates.dt.year == year].copy()

    if equity.empty:
        ey = equity.copy()
    else:
        ed = pd.to_datetime(equity["date"], errors="coerce")
        ey = equity.loc[ed.dt.year == year].copy()

    if ey.empty:
        ret = dd = sharpe = 0.0
    else:
        eq = pd.to_numeric(ey["equity"], errors="coerce").dropna()
        if len(eq) >= 2:
            ret = (eq.iloc[-1] / eq.iloc[0] - 1.0) * 100.0
            peak = eq.cummax()
            dd = ((eq / peak) - 1.0).min() * 100.0
        else:
            ret = dd = 0.0
        dr = pd.to_numeric(ey.get("daily_return", pd.Series(dtype=float)), errors="coerce").dropna()
        sharpe = np.sqrt(252) * dr.mean() / dr.std() if len(dr) >= 30 and dr.std() > 0 else 0.0

    pnl = pd.to_numeric(ty.get("net_pnl", pd.Series(dtype=float)), errors="coerce").dropna()
    rr = pd.to_numeric(ty.get("R", pd.Series(dtype=float)), errors="coerce").dropna()
    return {
        "period": str(year),
        "return_pct": float(ret),
        "pf": _pf_from_pnl(pnl),
        "dd_pct": float(dd),
        "trades": int(len(ty)),
        "win_rate": float((pnl > 0).mean() * 100.0) if len(pnl) else 0.0,
        "avg_R": float(rr.mean()) if len(rr) else 0.0,
        "net_pnl": float(pnl.sum()) if len(pnl) else 0.0,
        "sharpe": float(sharpe),
    }


def _bootstrap_avg_r(trades: pd.DataFrame, n_boot=5000, seed=260910) -> tuple[float, float]:
    if trades.empty or "R" not in trades:
        return np.nan, np.nan
    r = pd.to_numeric(trades["R"], errors="coerce").dropna().to_numpy(dtype=float)
    if len(r) < 10:
        return np.nan, np.nan
    rng = np.random.default_rng(seed)
    # Chunked to avoid a large temporary matrix on small machines.
    means = np.empty(n_boot, dtype=float)
    chunk = 500
    done = 0
    while done < n_boot:
        n = min(chunk, n_boot - done)
        idx = rng.integers(0, len(r), size=(n, len(r)))
        means[done:done + n] = r[idx].mean(axis=1)
        done += n
    lo, hi = np.quantile(means, [0.025, 0.975])
    return float(lo), float(hi)


def _concentration(trades: pd.DataFrame) -> dict:
    if trades.empty:
        return {
            "pnl_total": 0.0,
            "pnl_without_top5": 0.0,
            "pnl_without_top10": 0.0,
            "pf_without_top5": 0.0,
            "pf_without_top10": 0.0,
            "avgR_without_top5": 0.0,
            "avgR_without_top10": 0.0,
            "top5_share_abs_pct": 0.0,
            "top10_share_abs_pct": 0.0,
        }

    t = trades.copy()
    t["net_pnl"] = pd.to_numeric(t["net_pnl"], errors="coerce").fillna(0.0)
    t["R"] = pd.to_numeric(t["R"], errors="coerce")
    t = t.sort_values("net_pnl", ascending=False).reset_index(drop=True)
    total = float(t["net_pnl"].sum())
    gross_abs = float(t["net_pnl"].abs().sum())

    def stripped(n):
        x = t.iloc[min(n, len(t)):].copy()
        pnl = x["net_pnl"]
        rr = x["R"].dropna()
        return float(pnl.sum()), _pf_from_pnl(pnl), float(rr.mean()) if len(rr) else 0.0

    p5, pf5, r5 = stripped(5)
    p10, pf10, r10 = stripped(10)
    top5 = float(t.head(5)["net_pnl"].sum())
    top10 = float(t.head(10)["net_pnl"].sum())
    return {
        "pnl_total": total,
        "pnl_without_top5": p5,
        "pnl_without_top10": p10,
        "pf_without_top5": pf5,
        "pf_without_top10": pf10,
        "avgR_without_top5": r5,
        "avgR_without_top10": r10,
        "top5_share_abs_pct": _div(top5, gross_abs) * 100.0 if gross_abs else 0.0,
        "top10_share_abs_pct": _div(top10, gross_abs) * 100.0 if gross_abs else 0.0,
    }


def _fixed_path_cost_stress(trades: pd.DataFrame, cfg: dict, factor: float) -> dict:
    """
    Hold trade set, quantity, entry and exit path fixed.

    Baseline net_pnl already contains 1x commissions and slippage. For factors above 1x,
    we subtract:
      - the proportional extra commission (exact from recorded commission), and
      - an incremental slippage approximation on recorded round-trip turnover.

    This deliberately does NOT change signals, sizes or portfolio capacity.
    """
    if trades.empty:
        return {"return_pct": 0.0, "pf": 0.0, "avg_R": 0.0, "net_pnl": 0.0}

    t = trades.copy()
    base_net = pd.to_numeric(t["net_pnl"], errors="coerce").fillna(0.0)
    base_comm = pd.to_numeric(t["commission"], errors="coerce").fillna(0.0)
    entry_value = pd.to_numeric(t["entry_value"], errors="coerce").fillna(0.0)
    qty = pd.to_numeric(t["qty"], errors="coerce").fillna(0.0)
    exit_px = pd.to_numeric(t["exit"], errors="coerce").fillna(0.0)
    risk = pd.to_numeric(t["risk_dollars"], errors="coerce").replace(0, np.nan)

    extra_mult = max(0.0, float(factor) - 1.0)
    turnover = entry_value + qty * exit_px
    extra_commission = extra_mult * base_comm
    extra_slippage = extra_mult * float(cfg["slippage"]) * turnover
    stressed = base_net - extra_commission - extra_slippage
    stressed_r = stressed / risk

    return {
        "return_pct": float(stressed.sum() / cfg["capital"] * 100.0),
        "pf": _pf_from_pnl(stressed),
        "avg_R": float(stressed_r.dropna().mean()) if stressed_r.notna().any() else 0.0,
        "net_pnl": float(stressed.sum()),
    }


def _plateau_summary(summary: pd.DataFrame, fixed: pd.DataFrame, concentration: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for family in ["VOLREL", "ATR", "RS20"]:
        g = summary[(summary["family"] == family) & (summary["period"] == "TOTAL")].copy()
        gy = summary[(summary["family"] == family) & (summary["period"].isin(["2023", "2024", "2025"]))].copy()
        if g.empty:
            continue
        names = set(g["experiment"])
        fx = fixed[(fixed["experiment"].isin(names)) & (fixed["cost_factor"].isin([2.0, 3.0]))]
        cc = concentration[concentration["experiment"].isin(names)]

        year_pos = gy.assign(pos=(gy["avg_R"] > 0) & (gy["pf"] > 1)).groupby("experiment")["pos"].sum()
        rows.append({
            "family": family,
            "variants": int(len(g)),
            "median_total_pf": float(g["pf"].replace([np.inf, -np.inf], np.nan).median()),
            "median_total_avg_R": float(g["avg_R"].median()),
            "worst_total_avg_R": float(g["avg_R"].min()),
            "best_total_avg_R": float(g["avg_R"].max()),
            "variants_positive_2plus_years": int((year_pos >= 2).sum()),
            "variants_positive_all_3_years": int((year_pos >= 3).sum()),
            "fixed_2x_pf_median": float(fx.loc[fx.cost_factor == 2.0, "pf"].replace([np.inf, -np.inf], np.nan).median()),
            "fixed_3x_pf_median": float(fx.loc[fx.cost_factor == 3.0, "pf"].replace([np.inf, -np.inf], np.nan).median()),
            "median_pnl_without_top5": float(cc["pnl_without_top5"].median()) if not cc.empty else np.nan,
            "median_pnl_without_top10": float(cc["pnl_without_top10"].median()) if not cc.empty else np.nan,
        })
    return pd.DataFrame(rows)


def run_falsification_lab(universe: str = "USA") -> None:
    if universe != "USA":
        print("\n⚠️ V6 se ejecuta solamente sobre USA.")
        print("CEDEAR sigue fuera hasta tener un modelo ARS/USD + ratio específico.")
        return

    print("\n" + "=" * 118)
    print("V6 — SIGNAL QUALITY FALSIFICATION LAB — USA")
    print("=" * 118)
    print("Objetivo: intentar REFUTAR las pistas de V5, no maximizar el backtest.")
    print("Ventana: 2023-01-03 -> 2025-12-31. 2026 NO se descarga ni se backtestea como período de evaluación.")
    print("Arquitectura congelada: trend + pullback + rs20 + volume + candle.")
    print("Congelado: RS20 base +1%, TP 1.8R, SL 1.5 ATR, riesgo 0.5%, caps V5.")
    print("Familias: VolRel, ATR%, RS20 fuerte. Tres regiones amplias por familia + control.")

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

    # IMPORTANT: all filtering beyond the frozen V5 control is performed by the V6
    # candidate patch above. We do not mutate strategy.py.
    print(f"\nActivos preparados: {len(data)}")
    print(f"Experimentos predeclarados: {len(EXPERIMENTS)}")

    summary_rows = []
    conc_rows = []
    fixed_rows = []
    endogenous_rows = []
    trade_frames = []

    for i, exp in enumerate(EXPERIMENTS, 1):
        name = exp["name"]
        family = exp["family"]
        spec = exp["filter"]
        print(f"\n[{i:02d}/{len(EXPERIMENTS):02d}] {name}")

        trades, equity, run_cfg = _run_backtest(
            data, spy, cfg, spec, cost_factor=1.0, label=f"V6 {name} x1"
        )
        m = re.metrics(trades, equity, run_cfg)
        lo, hi = _bootstrap_avg_r(trades, seed=260910 + i)
        conc = _concentration(trades)

        summary_rows.append({
            "experiment": name,
            "family": family,
            "period": "TOTAL",
            "return_pct": m["return_pct"],
            "pf": m["pf"],
            "dd_pct": m["dd_pct"],
            "trades": m["trades"],
            "win_rate": m["win_rate"],
            "avg_R": m["avg_R"],
            "sharpe": m["sharpe"],
            "net_pnl": float(pd.to_numeric(trades.get("net_pnl", pd.Series(dtype=float)), errors="coerce").sum()),
            "bootstrap_avgR_lo95": lo,
            "bootstrap_avgR_hi95": hi,
        })
        for year in [2023, 2024, 2025]:
            ys = _year_stats(trades, equity, year, cfg["capital"])
            ys.update({"experiment": name, "family": family, "bootstrap_avgR_lo95": np.nan, "bootstrap_avgR_hi95": np.nan})
            summary_rows.append(ys)

        conc_rows.append({"experiment": name, "family": family, **conc})

        for factor in [1.0, 2.0, 3.0]:
            fs = _fixed_path_cost_stress(trades, cfg, factor)
            fixed_rows.append({
                "experiment": name,
                "family": family,
                "cost_factor": factor,
                **fs,
                "trades": int(len(trades)),
            })

        # Endogenous stress: factor changes equity/sizing/capacity and can change later trades.
        endogenous_rows.append({
            "experiment": name,
            "family": family,
            "cost_factor": 1.0,
            "return_pct": m["return_pct"],
            "pf": m["pf"],
            "dd_pct": m["dd_pct"],
            "trades": m["trades"],
            "avg_R": m["avg_R"],
        })
        for factor in [2.0, 3.0]:
            ts, es, cs = _run_backtest(
                data, spy, cfg, spec, cost_factor=factor, label=f"V6 {name} x{factor:g}"
            )
            ms = re.metrics(ts, es, cs)
            endogenous_rows.append({
                "experiment": name,
                "family": family,
                "cost_factor": factor,
                "return_pct": ms["return_pct"],
                "pf": ms["pf"],
                "dd_pct": ms["dd_pct"],
                "trades": ms["trades"],
                "avg_R": ms["avg_R"],
            })

        if not trades.empty:
            tt = trades.copy()
            tt.insert(0, "experiment", name)
            tt.insert(1, "family", family)
            trade_frames.append(tt)

        print(
            f"  TOTAL {m['return_pct']:+.2f}% | PF {m['pf']:.2f} | DD {m['dd_pct']:+.2f}% | "
            f"TR {m['trades']} | AvgR {m['avg_R']:+.3f} | boot95 [{lo:+.3f}, {hi:+.3f}]"
        )
        print(
            f"  sin top5 PnL {conc['pnl_without_top5']:+,.0f} | "
            f"sin top10 {conc['pnl_without_top10']:+,.0f}"
        )

    summary = pd.DataFrame(summary_rows)
    concentration = pd.DataFrame(conc_rows)
    fixed = pd.DataFrame(fixed_rows)
    endogenous = pd.DataFrame(endogenous_rows)
    all_trades = pd.concat(trade_frames, ignore_index=True) if trade_frames else pd.DataFrame()
    plateau = _plateau_summary(summary, fixed, concentration)

    # Save before printing final tables.
    summary.to_csv(OUT / "v6_variant_summary.csv", index=False)
    concentration.to_csv(OUT / "v6_concentration.csv", index=False)
    fixed.to_csv(OUT / "v6_fixed_path_cost_stress.csv", index=False)
    endogenous.to_csv(OUT / "v6_endogenous_cost_stress.csv", index=False)
    plateau.to_csv(OUT / "v6_family_plateaus.csv", index=False)
    if not all_trades.empty:
        all_trades.to_csv(OUT / "v6_all_trades.csv", index=False)

    print("\n" + "=" * 118)
    print("TOTAL 2023-2025 — NO SE ELIGE GANADOR AUTOMÁTICO")
    print("=" * 118)
    total = summary[summary["period"] == "TOTAL"].copy()
    print(f"{'EXPERIMENTO':<20}{'FAM':<9}{'RET':>9}{'PF':>8}{'DD':>9}{'TR':>7}{'AvgR':>9}{'BOOT LO':>10}{'BOOT HI':>10}")
    for _, r in total.iterrows():
        pf = "inf" if np.isinf(r.pf) else f"{r.pf:.2f}"
        print(
            f"{r.experiment:<20}{r.family:<9}{r.return_pct:>+8.2f}%{pf:>8}{r.dd_pct:>+8.2f}%"
            f"{int(r.trades):>7}{r.avg_R:>+9.3f}{r.bootstrap_avgR_lo95:>+10.3f}{r.bootstrap_avgR_hi95:>+10.3f}"
        )

    print("\n" + "=" * 118)
    print("CONSISTENCIA TEMPORAL — PF / AvgR POR AÑO")
    print("=" * 118)
    for exp in EXPERIMENTS:
        name = exp["name"]
        g = summary[(summary["experiment"] == name) & summary["period"].isin(["2023", "2024", "2025"])]
        parts = [f"{int(r.period)} PF {r.pf:.2f} AvgR {r.avg_R:+.3f} TR {int(r.trades)}" for _, r in g.iterrows()]
        print(f"{name:<20} | " + " | ".join(parts))

    print("\n" + "=" * 118)
    print("FIXED-PATH COST STRESS — MISMAS OPERACIONES Y TAMAÑOS")
    print("=" * 118)
    for exp in EXPERIMENTS:
        name = exp["name"]
        g = fixed[fixed["experiment"] == name].sort_values("cost_factor")
        parts = [f"x{r.cost_factor:g} PF {r.pf:.2f} Ret {r.return_pct:+.2f}%" for _, r in g.iterrows()]
        print(f"{name:<20} | " + " | ".join(parts))

    print("\n" + "=" * 118)
    print("CONCENTRACIÓN — ¿SOBREVIVE SIN LOS MAYORES GANADORES?")
    print("=" * 118)
    print(f"{'EXPERIMENTO':<20}{'PnL':>13}{'SIN TOP5':>13}{'SIN TOP10':>13}{'PF-5':>9}{'PF-10':>9}")
    for _, r in concentration.iterrows():
        print(
            f"{r.experiment:<20}{r.pnl_total:>13,.0f}{r.pnl_without_top5:>13,.0f}{r.pnl_without_top10:>13,.0f}"
            f"{r.pf_without_top5:>9.2f}{r.pf_without_top10:>9.2f}"
        )

    print("\n" + "=" * 118)
    print("RESUMEN DE MESETAS POR FAMILIA — DESCRIPTIVO, NO SELECTOR")
    print("=" * 118)
    if plateau.empty:
        print("Sin datos suficientes.")
    else:
        print(plateau.to_string(index=False))

    print("\nArchivos generados en ./results/:")
    for name in [
        "v6_variant_summary.csv",
        "v6_concentration.csv",
        "v6_fixed_path_cost_stress.csv",
        "v6_endogenous_cost_stress.csv",
        "v6_family_plateaus.csv",
        "v6_all_trades.csv",
    ]:
        print(f"  • {name}")

    print("\nIMPORTANTE:")
    print("• V6 NO usa 2026 para selección ni validación.")
    print("• El mejor número aislado NO gana; buscamos meseta + consistencia + margen a costos + baja concentración.")
    print("• Fixed-path y endogenous stress responden preguntas distintas y se guardan por separado.")
    print("• No modifiques strategy.py ni research_engine.py después de V6. Pasame output + CSV y yo decido V7.")
