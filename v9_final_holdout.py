from __future__ import annotations

"""
V9.1 — FINAL 2026 HOLDOUT TEST

One-shot validation of the architecture frozen after V8.
This module is deliberately NOT an optimizer and contains exactly one primary
strategy specification. 2026 is used only as a final holdout evaluation.

Frozen architecture (selected BEFORE opening 2026):
    components = trend + pullback + rs20 + volume + candle
    base RS20 >= 1%
    ATR% in [3%, 5%]
    VolRel >= 1.15
    TP = 1.8R
    stop = 1.5 ATR
    risk/trade = 0.5%
    max gross exposure = 90%
    max portfolio planned risk = 2.5%

Holdout window is frozen to 2026-01-02 .. 2026-09-09. The original V9 attempt
requested 2026-09-10, but Yahoo had complete joint data only through 2026-09-09.
No holdout result had been produced, so the endpoint correction is data-availability
driven rather than performance-driven. Future reruns cannot silently extend it.
"""

from pathlib import Path
import hashlib
import json
import os
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd

import research_engine as re
import v6_falsification_lab as v6
import v7_interaction_lab as v7

OUT = Path("results")
OUT.mkdir(exist_ok=True)

HOLDOUT_START = pd.Timestamp("2026-01-02")
HOLDOUT_END = pd.Timestamp("2026-09-09")
COMPONENTS = ("trend", "pullback", "rs20", "volume", "candle")
FROZEN_SPEC = {"atr_min": 0.030, "atr_max": 0.050, "volrel_min": 1.15}

MANIFEST_PATH = OUT / "v9_frozen_manifest.json"
RESULT_PATH = OUT / "v9_final_result.csv"
TRADES_PATH = OUT / "v9_holdout_trades.csv"
EQUITY_PATH = OUT / "v9_holdout_equity.csv"
MONTHLY_PATH = OUT / "v9_holdout_monthly.csv"
COST_PATH = OUT / "v9_fixed_path_cost_stress.csv"
TICKER_PATH = OUT / "v9_ticker_concentration.csv"
VERDICT_PATH = OUT / "v9_verdict.json"

# Predeclared BEFORE observing holdout results. These are survival/validation
# gates, not parameters to tune against 2026.
SURVIVAL_GATES = {
    "return_pct_gt": 0.0,
    "pf_ge": 1.05,
    "avg_R_gt": 0.0,
    "dd_pct_ge": -15.0,
    "fixed_2x_pf_ge": 1.00,
    "min_trades": 60,
}

# Strong evidence is intentionally harder. Failing a strong gate does not mean
# the strategy is certainly false; it means 2026 did not strongly confirm it.
STRONG_GATES = {
    "pf_ge": 1.20,
    "fixed_2x_pf_ge": 1.10,
    "cluster_lo95_gt": 0.0,
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


def _run(data, spy, cfg, cost_factor=1.0, label="V9 FINAL HOLDOUT"):
    c = dict(cfg)
    c["commission"] = cfg["commission"] * cost_factor
    c["slippage"] = cfg["slippage"] * cost_factor
    with v6._signal_filter_patch(FROZEN_SPEC):
        trades, equity = re.backtest(
            data, spy, c, COMPONENTS, HOLDOUT_START, HOLDOUT_END, label=label
        )
    return trades, equity, c


def _manifest(cfg):
    payload = {
        "version": "V9_1_FINAL_HOLDOUT",
        "purpose": "one-shot final holdout; no optimization on 2026",
        "endpoint_note": "Corrected from 2026-09-10 to 2026-09-09 before any result existed because 2026-09-09 was the last complete joint Yahoo session on the first attempt.",
        "holdout_start": str(HOLDOUT_START.date()),
        "holdout_end": str(HOLDOUT_END.date()),
        "components": list(COMPONENTS),
        "filter": FROZEN_SPEC,
        "config": {
            "rs20_min": cfg["rs20_min"],
            "tp_r": cfg["tp_r"],
            "stop_atr": cfg["stop_atr"],
            "risk_per_trade": cfg["risk_per_trade"],
            "max_gross_exposure": cfg["max_gross_exposure"],
            "max_portfolio_risk": cfg["max_portfolio_risk"],
            "commission": cfg["commission"],
            "slippage": cfg["slippage"],
        },
        "survival_gates": SURVIVAL_GATES,
        "strong_gates": STRONG_GATES,
        "rule_after_test": (
            "2026 must not be used to tune thresholds/components/exits. "
            "Any post-V9 architecture change requires a new future holdout."
        ),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    payload["sha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return payload


def _pf_from_pnl(pnl):
    s = pd.to_numeric(pd.Series(pnl), errors="coerce").dropna()
    wins = float(s[s > 0].sum())
    losses = float(-s[s < 0].sum())
    if losses <= 0:
        return float("inf") if wins > 0 else 0.0
    return wins / losses


def _monthly(trades):
    if trades.empty:
        return pd.DataFrame(columns=["month", "trades", "net_pnl", "pf", "avg_R", "win_rate"])
    x = trades.copy()
    x["entry_date"] = pd.to_datetime(x["entry_date"], errors="coerce")
    x["month"] = x["entry_date"].dt.to_period("M").astype(str)
    rows = []
    for month, g in x.groupby("month", sort=True):
        pnl = pd.to_numeric(g["net_pnl"], errors="coerce").dropna()
        rr = pd.to_numeric(g["R"], errors="coerce").dropna()
        rows.append({
            "month": month,
            "trades": int(len(g)),
            "net_pnl": float(pnl.sum()),
            "pf": _pf_from_pnl(pnl),
            "avg_R": float(rr.mean()) if len(rr) else 0.0,
            "win_rate": float((pnl > 0).mean() * 100.0) if len(pnl) else 0.0,
        })
    return pd.DataFrame(rows)


def _ticker_table(trades):
    if trades.empty:
        return pd.DataFrame(columns=["ticker", "trades", "net_pnl", "avg_R", "share_total_pnl_pct"])
    x = trades.copy()
    x["net_pnl"] = pd.to_numeric(x["net_pnl"], errors="coerce").fillna(0.0)
    x["R"] = pd.to_numeric(x["R"], errors="coerce")
    g = x.groupby("ticker", as_index=False).agg(
        trades=("ticker", "size"), net_pnl=("net_pnl", "sum"), avg_R=("R", "mean")
    ).sort_values("net_pnl", ascending=False)
    total = float(x["net_pnl"].sum())
    g["share_total_pnl_pct"] = np.where(abs(total) > 1e-12, g["net_pnl"] / abs(total) * 100.0, 0.0)
    return g


def _concentration(trades):
    if trades.empty:
        return {
            "pnl_without_top5": 0.0, "pf_without_top5": 0.0,
            "top1_ticker_share_pct": np.nan, "top5_ticker_share_pct": np.nan,
        }
    x = trades.copy()
    pnl = pd.to_numeric(x["net_pnl"], errors="coerce").fillna(0.0)
    order = pnl.sort_values(ascending=False).index
    stripped = pnl.drop(order[: min(5, len(order))])
    by_ticker = x.assign(_pnl=pnl).groupby("ticker")["_pnl"].sum().sort_values(ascending=False)
    total = float(pnl.sum())
    den = abs(total) if abs(total) > 1e-12 else np.nan
    return {
        "pnl_without_top5": float(stripped.sum()),
        "pf_without_top5": float(_pf_from_pnl(stripped)),
        "top1_ticker_share_pct": float(by_ticker.iloc[:1].sum() / den * 100.0) if len(by_ticker) and np.isfinite(den) else np.nan,
        "top5_ticker_share_pct": float(by_ticker.iloc[:5].sum() / den * 100.0) if len(by_ticker) and np.isfinite(den) else np.nan,
    }


def _fixed_cost_stress(base_trades, cfg):
    rows = []
    for factor in [1.0, 2.0, 3.0]:
        r = v6._fixed_path_cost_stress(base_trades, cfg, factor)
        rows.append({"cost_factor": factor, **r, "trades": len(base_trades)})
    return pd.DataFrame(rows)


def _safe_spy_return(spy):
    try:
        return float(re.benchmark(spy, HOLDOUT_START, HOLDOUT_END))
    except Exception:
        return np.nan


def _gate_verdict(result, fixed2_pf):
    survival_checks = {
        "positive_return": result["return_pct"] > SURVIVAL_GATES["return_pct_gt"],
        "pf": result["pf"] >= SURVIVAL_GATES["pf_ge"],
        "avg_R": result["avg_R"] > SURVIVAL_GATES["avg_R_gt"],
        "drawdown": result["dd_pct"] >= SURVIVAL_GATES["dd_pct_ge"],
        "fixed_2x_pf": fixed2_pf >= SURVIVAL_GATES["fixed_2x_pf_ge"],
        "minimum_trades": result["trades"] >= SURVIVAL_GATES["min_trades"],
    }
    strong_checks = {
        "pf": result["pf"] >= STRONG_GATES["pf_ge"],
        "fixed_2x_pf": fixed2_pf >= STRONG_GATES["fixed_2x_pf_ge"],
        "cluster_lower_bound": (
            np.isfinite(result["cluster_lo95"]) and result["cluster_lo95"] > STRONG_GATES["cluster_lo95_gt"]
        ),
    }
    if all(strong_checks.values()) and all(survival_checks.values()):
        classification = "STRONG_CONFIRMATION"
    elif all(survival_checks.values()):
        classification = "SURVIVES_HOLDOUT"
    else:
        classification = "FAILS_PREDECLARED_SURVIVAL_GATES"
    return classification, survival_checks, strong_checks


def run_v9_final_holdout(universe="USA"):
    if universe != "USA":
        print("\n⚠️ V9 final se ejecuta solamente sobre USA.")
        return

    print("\n" + "=" * 126)
    print("V9.1 — FINAL 2026 HOLDOUT — ONE SHOT")
    print("=" * 126)
    print("Arquitectura CONGELADA antes de abrir 2026:")
    print("  trend + pullback + rs20 + volume + candle")
    print("  RS20 >= 1% | ATR 3–5% | VolRel >= 1.15 | TP 1.8R | SL 1.5 ATR | riesgo 0.5%")
    print(f"Holdout fijo corregido: {HOLDOUT_START.date()} -> {HOLDOUT_END.date()}")
    print("Endpoint corregido por disponibilidad: el primer intento no produjo resultado y Yahoo cerraba conjuntamente en 2026-09-09.")
    print("No hay variantes, sweeps ni selección post-hoc.")

    if RESULT_PATH.exists() and os.environ.get("V9_ALLOW_RERUN", "").upper() != "YES":
        print("\n⛔ V9 ya tiene un resultado guardado.")
        print(f"   {RESULT_PATH}")
        print("   Para preservar el holdout, el programa NO lo vuelve a ejecutar.")
        print("   Analizá los CSV existentes; no uses 2026 para reajustar la estrategia.")
        return

    cfg = _base_cfg()
    manifest = _manifest(cfg)

    # Audit trail: preserve the first manifest (which requested 2026-09-10) if
    # that attempt produced no final result. This is not a strategy change.
    if MANIFEST_PATH.exists() and not RESULT_PATH.exists():
        try:
            previous = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
            if previous.get("holdout_end") != str(HOLDOUT_END.date()):
                archive = OUT / "v9_frozen_manifest_attempt1.json"
                if not archive.exists():
                    archive.write_text(
                        json.dumps(previous, indent=2, ensure_ascii=False),
                        encoding="utf-8",
                    )
                    print(f"🧾 Manifiesto anterior preservado: {archive}")
        except Exception as exc:
            print(f"⚠️ No pude archivar el manifiesto anterior: {exc}")

    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n🔒 Manifiesto congelado: {MANIFEST_PATH} | sha256 {manifest['sha256'][:16]}…")

    raw = re.download_universe("USA")
    spy_raw = re.download_spy()
    data, spy = re.prepare(raw, spy_raw)
    if not data:
        print("❌ No hay datos válidos. No se creó resultado; podés corregir la descarga y reintentar.")
        return

    # Make sure the fixed endpoint is actually present in the downloaded market data.
    max_dates = [df.index.max() for df in data.values() if df is not None and not df.empty]
    data_last = max(max_dates) if max_dates else pd.NaT
    spy_last = spy.index.max() if spy is not None and not spy.empty else pd.NaT
    effective_last = min(data_last, spy_last) if pd.notna(data_last) and pd.notna(spy_last) else pd.NaT
    if pd.isna(effective_last) or effective_last < HOLDOUT_END:
        print("\n⛔ Datos incompletos para cerrar el holdout fijo.")
        print(f"   Última fecha conjunta disponible: {effective_last}")
        print(f"   Fecha requerida: {HOLDOUT_END.date()}")
        print("   No se escribe v9_final_result.csv. Revisá la descarga/cache; V9.1 no extenderá el endpoint.")
        return

    trades, equity, used_cfg = _run(data, spy, cfg, 1.0)
    m = re.metrics(trades, equity, used_cfg)
    lo, hi = v7._cluster_bootstrap_avg_r(trades, n_boot=10000, seed=9092026)
    conc = _concentration(trades)
    spy_ret = _safe_spy_return(spy)

    fixed = _fixed_cost_stress(trades, cfg)
    f2 = fixed.loc[fixed.cost_factor == 2.0, "pf"]
    fixed2_pf = float(f2.iloc[0]) if len(f2) else np.nan

    result = {
        "architecture": "FROZEN_ATR3_5_VOLREL1.15",
        "holdout_start": str(HOLDOUT_START.date()),
        "holdout_end": str(HOLDOUT_END.date()),
        "return_pct": float(m["return_pct"]),
        "pf": float(m["pf"]),
        "dd_pct": float(m["dd_pct"]),
        "trades": int(m["trades"]),
        "win_rate": float(m["win_rate"]),
        "avg_R": float(m["avg_R"]),
        "sharpe": float(m["sharpe"]),
        "cluster_lo95": float(lo) if np.isfinite(lo) else np.nan,
        "cluster_hi95": float(hi) if np.isfinite(hi) else np.nan,
        "spy_return_pct": spy_ret,
        "simple_excess_vs_spy_pp": float(m["return_pct"] - spy_ret) if np.isfinite(spy_ret) else np.nan,
        **conc,
        "manifest_sha256": manifest["sha256"],
    }

    classification, survival_checks, strong_checks = _gate_verdict(result, fixed2_pf)
    result["fixed_2x_pf"] = fixed2_pf
    result["classification"] = classification

    result_df = pd.DataFrame([result])
    monthly = _monthly(trades)
    tickers = _ticker_table(trades)

    result_df.to_csv(RESULT_PATH, index=False)
    trades.to_csv(TRADES_PATH, index=False)
    equity.to_csv(EQUITY_PATH, index=False)
    monthly.to_csv(MONTHLY_PATH, index=False)
    fixed.to_csv(COST_PATH, index=False)
    tickers.to_csv(TICKER_PATH, index=False)

    verdict = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "manifest_sha256": manifest["sha256"],
        "classification": classification,
        "survival_checks": survival_checks,
        "strong_checks": strong_checks,
        "warning": (
            "This classification was predeclared. Do not tune the strategy using this holdout. "
            "If architecture changes after V9, collect a new future holdout."
        ),
    }
    VERDICT_PATH.write_text(json.dumps(verdict, indent=2, ensure_ascii=False), encoding="utf-8")

    print("\n" + "=" * 126)
    print("RESULTADO FINAL DEL HOLDOUT")
    print("=" * 126)
    print(
        f"Ret {result['return_pct']:+.2f}% | PF {result['pf']:.2f} | DD {result['dd_pct']:+.2f}% | "
        f"TR {result['trades']} | WR {result['win_rate']:.1f}% | AvgR {result['avg_R']:+.3f} | "
        f"Sharpe {result['sharpe']:.2f}"
    )
    print(f"cluster95 AvgR [{result['cluster_lo95']:+.3f}, {result['cluster_hi95']:+.3f}]")
    print(f"SPY {spy_ret:+.2f}% | exceso simple {result['simple_excess_vs_spy_pp']:+.2f} pp")
    print(
        f"Sin top5 trades: PnL {result['pnl_without_top5']:,.0f} | PF {result['pf_without_top5']:.2f} | "
        f"top1 ticker share {result['top1_ticker_share_pct']:.1f}% | top5 {result['top5_ticker_share_pct']:.1f}%"
    )

    print("\nFIXED-PATH COST STRESS")
    for _, r in fixed.iterrows():
        print(f"  x{r.cost_factor:g}: Ret {r.return_pct:+.2f}% | PF {r.pf:.2f} | AvgR {r.avg_R:+.3f}")

    print("\nPREDECLARED VERDICT")
    print(f"  {classification}")
    print("  Survival gates:")
    for k, ok in survival_checks.items():
        print(f"    {'✅' if ok else '❌'} {k}")
    print("  Strong-confirmation gates:")
    for k, ok in strong_checks.items():
        print(f"    {'✅' if ok else '❌'} {k}")

    print("\nArchivos generados en ./results/:")
    for p in [MANIFEST_PATH, RESULT_PATH, TRADES_PATH, EQUITY_PATH, MONTHLY_PATH, COST_PATH, TICKER_PATH, VERDICT_PATH]:
        print(f"  • {p.name}")

    print("\n⚠️ REGLA DEL PROYECTO DESPUÉS DE V9:")
    print("• No cambiar thresholds, componentes ni exits mirando este 2026 y volver a llamarlo OOS.")
    print("• Si V9 falla, se diagnostica; cualquier arquitectura nueva necesita un NUEVO holdout futuro.")
    print("• Si V9 sobrevive, el siguiente trabajo es implementación/auditoría operativa, no otro sweep histórico.")


if __name__ == "__main__":
    run_v9_final_holdout("USA")
