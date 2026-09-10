from __future__ import annotations

"""
V11.3 — FORWARD MONITORING & DRIFT GUARD
========================================

Passive monitoring layer for the frozen V11.1 prospective paper engine.

It DOES NOT:
- generate signals,
- open/close positions,
- change thresholds,
- change exits,
- change sizing,
- modify V11 prospective state/history.

It ONLY reads V11/V11.2 outputs and writes V11.3 monitoring reports.

The monitoring rules below are predeclared before the first prospective
observation. They are diagnostic/operational rules, not strategy parameters.
"""

from pathlib import Path
import hashlib
import json
import math

import numpy as np
import pandas as pd

import research_engine as re
import v11_shadow_engine as sh


OUT = Path("results")
OUT.mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# Frozen provenance
# ---------------------------------------------------------------------------

EXPECTED_V11_MANIFEST_SHA = (
    "77a3834de2ce4fb1df1c9c8006d5d1a0c10a23494f0e92e39673b412e9dd792a"
)
EXPECTED_V9_MANIFEST_SHA = (
    "08aebe4a77bc71466f04e14a350979dcb8e129bd13115eb42b98dda9ccec9c26"
)
EXPECTED_PARITY_SIGNAL_SHA = (
    "94418393a6cd44795f4ffc7f044a166c763befd32111565a9975e68e8cb67020"
)

PROSPECTIVE_START = pd.Timestamp("2026-09-10")

V11_MANIFEST = OUT / "v11_shadow_manifest.json"
V11_STATE = OUT / "v11_shadow_state.json"
V11_SIGNALS = OUT / "v11_shadow_signals.csv"
V11_TRADES = OUT / "v11_shadow_trades.csv"
V11_DAILY = OUT / "v11_shadow_daily.csv"
V11_EQUITY = OUT / "v11_shadow_equity.csv"
V11_SUMMARY = OUT / "v11_shadow_summary.csv"

V9_MANIFEST = OUT / "v9_frozen_manifest.json"
V112_VERDICT = OUT / "v11_2_verdict.json"

MONITOR_MANIFEST = OUT / "v11_3_monitor_manifest.json"
STATUS_PATH = OUT / "v11_3_monitor_status.csv"
ROLLING_PATH = OUT / "v11_3_rolling_metrics.csv"
CONCENTRATION_PATH = OUT / "v11_3_concentration.csv"
INTEGRITY_PATH = OUT / "v11_3_integrity_checks.csv"
REPORT_PATH = OUT / "v11_3_report.json"

# ---------------------------------------------------------------------------
# PREDECLARED FORWARD MONITORING RULES
# ---------------------------------------------------------------------------

CHECKPOINTS = {
    "diagnostic_1_trades": 25,
    "diagnostic_2_trades": 50,
    "first_formal_review_trades": 100,
    "mature_review_trades": 150,
    "mature_review_min_calendar_days": 183,  # ~6 months
}

# These DO NOT authorize retuning. They only classify future evidence.
FIRST_REVIEW_GATES = {
    "pf_ge": 1.05,
    "avg_R_gt": 0.0,
    "max_drawdown_pct_ge": -15.0,
    "entry_cap_violations_eq": 0,
}

# More demanding evidence tier before even DISCUSSING a real-money pilot.
# Passing this still does not automatically authorize live capital.
MATURE_REVIEW_GATES = {
    "pf_ge": 1.10,
    "avg_R_ge": 0.05,
    "max_drawdown_pct_ge": -15.0,
    "entry_cap_violations_eq": 0,
    "rolling_60_pf_ge": 0.90,
}

# Monitoring alarms. These are investigation triggers, NOT automatic retuning.
ALERT_RULES = {
    "hard_drawdown_pct_le": -15.0,
    "rolling_60_pf_lt": 0.80,
    "rolling_60_avg_R_lt": 0.0,
    "rolling_40_pf_lt": 0.80,
    "rolling_40_avg_R_lt": 0.0,
    "top5_ticker_share_warn_gt_pct": 100.0,
}

ROLLING_WINDOWS = (20, 40, 60, 100)


def _sha_file(path: Path):
    if not path.exists():
        return None
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _json(path: Path):
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _csv(path: Path):
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def _f(x, default=np.nan):
    try:
        z = float(x)
        return z if np.isfinite(z) else default
    except Exception:
        return default


def _pf(pnl):
    x = pd.to_numeric(pd.Series(pnl), errors="coerce").dropna()
    if x.empty:
        return 0.0
    wins = x[x > 0].sum()
    losses = -x[x < 0].sum()
    if losses <= 1e-12:
        return np.inf if wins > 0 else 0.0
    return float(wins / losses)


def _drawdown_pct(equity):
    e = pd.to_numeric(pd.Series(equity), errors="coerce").dropna()
    if e.empty:
        return 0.0
    peak = e.cummax()
    return float(((e / peak) - 1.0).min() * 100.0)


def _manifest_payload():
    p = {
        "version": "V11_3_FORWARD_MONITOR",
        "purpose": (
            "Passive prospective monitoring only. No signal/entry/exit/sizing "
            "logic is changed by this module."
        ),
        "created_before_first_forward_observation": True,
        "prospective_start": str(PROSPECTIVE_START.date()),
        "frozen_provenance": {
            "expected_v11_manifest_sha256": EXPECTED_V11_MANIFEST_SHA,
            "expected_v9_manifest_sha256": EXPECTED_V9_MANIFEST_SHA,
            "expected_v11_2_signal_fingerprint_sha256": EXPECTED_PARITY_SIGNAL_SHA,
        },
        "checkpoints": CHECKPOINTS,
        "first_review_gates": FIRST_REVIEW_GATES,
        "mature_review_gates": MATURE_REVIEW_GATES,
        "alert_rules": ALERT_RULES,
        "rolling_windows": list(ROLLING_WINDOWS),
        "policy": (
            "Monitoring results cannot be used to retune the frozen V11 strategy. "
            "Any architecture change is a new research branch and requires a new "
            "future holdout. PASS does not itself authorize real-money deployment."
        ),
    }
    raw = json.dumps(p, sort_keys=True, separators=(",", ":")).encode("utf-8")
    p["sha256"] = hashlib.sha256(raw).hexdigest()
    return p


def _ensure_monitor_manifest():
    new = _manifest_payload()
    if MONITOR_MANIFEST.exists():
        old = _json(MONITOR_MANIFEST)
        if old.get("sha256") != new["sha256"]:
            raise RuntimeError(
                "⛔ El manifiesto V11.3 existente no coincide con las reglas "
                "predeclaradas del código actual. No lo sobrescribo."
            )
        return old

    MONITOR_MANIFEST.write_text(
        json.dumps(new, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return new


def _integrity_checks():
    checks = []

    def add(name, passed, detail, severity="HARD"):
        checks.append({
            "check": name,
            "passed": bool(passed),
            "severity": severity,
            "detail": str(detail),
        })

    # 1) Frozen manifests / provenance.
    v11m = _json(V11_MANIFEST)
    if v11m is None:
        add("v11_manifest_present", False, "missing results/v11_shadow_manifest.json")
    else:
        add(
            "v11_manifest_sha_exact",
            v11m.get("sha256") == EXPECTED_V11_MANIFEST_SHA,
            f"actual={v11m.get('sha256')}",
        )
        add(
            "v11_prospective_start_exact",
            v11m.get("prospective_start") == str(PROSPECTIVE_START.date()),
            f"actual={v11m.get('prospective_start')}",
        )
        add(
            "v11_components_exact",
            tuple(v11m.get("components", [])) == tuple(sh.COMPONENTS),
            f"manifest={v11m.get('components')} code={list(sh.COMPONENTS)}",
        )
        vf = v11m.get("filter", {})
        add(
            "v11_filter_exact",
            vf == sh.FILTER_SPEC,
            f"manifest={vf} code={sh.FILTER_SPEC}",
        )

    v9m = _json(V9_MANIFEST)
    if v9m is None:
        add("v9_manifest_present", False, "missing results/v9_frozen_manifest.json")
    else:
        add(
            "v9_manifest_sha_exact",
            v9m.get("sha256") == EXPECTED_V9_MANIFEST_SHA,
            f"actual={v9m.get('sha256')}",
        )

    parity = _json(V112_VERDICT)
    if parity is None:
        add("v11_2_parity_verdict_present", False, "missing results/v11_2_verdict.json")
    else:
        add(
            "v11_2_parity_confirmed",
            parity.get("verdict") == "PARITY_CONFIRMED",
            f"actual={parity.get('verdict')}",
        )
        fp = (parity.get("signal_fingerprint") or {}).get("sha256")
        add(
            "v11_2_signal_fingerprint_exact",
            fp == EXPECTED_PARITY_SIGNAL_SHA,
            f"actual={fp}",
        )
        mm = parity.get("mismatches") or {}
        add(
            "v11_2_zero_mismatches",
            mm.get("trade_fields") == 0 and mm.get("equity_fields") == 0,
            f"trade={mm.get('trade_fields')} equity={mm.get('equity_fields')}",
        )
        add(
            "v11_2_prospective_untouched",
            parity.get("prospective_files_untouched") is True,
            f"actual={parity.get('prospective_files_untouched')}",
        )

    # 2) Prospective state integrity. State may legitimately not exist before first session.
    state = _json(V11_STATE)
    if state is None:
        add(
            "v11_state_valid_or_not_started",
            True,
            "no state yet: prospective processing has not begun",
        )
    else:
        add(
            "v11_state_version",
            state.get("version") == "V11_1_PROSPECTIVE_SHADOW",
            f"actual={state.get('version')}",
        )
        lpd = state.get("last_processed_date")
        if lpd is None:
            add("last_processed_date_valid", True, "not started")
        else:
            d = pd.Timestamp(lpd)
            add(
                "last_processed_date_not_before_start",
                d >= PROSPECTIVE_START,
                f"actual={d.date()}",
            )
        add(
            "state_cash_nonnegative",
            _f(state.get("cash"), -1) >= -1e-6,
            f"cash={state.get('cash')}",
        )
        add(
            "state_cap_violations_zero",
            int(state.get("entry_cap_violations_total", 0)) == 0,
            f"violations={state.get('entry_cap_violations_total', 0)}",
        )

    signals = _csv(V11_SIGNALS)
    trades = _csv(V11_TRADES)
    daily = _csv(V11_DAILY)
    equity = _csv(V11_EQUITY)

    # 3) Duplicate / chronological integrity.
    if not signals.empty:
        sdup = int(signals.duplicated(["ticker", "signal_date"]).sum())
        sd = pd.to_datetime(signals["signal_date"], errors="coerce")
        add("signals_no_duplicates", sdup == 0, f"duplicates={sdup}")
        add(
            "signals_dates_valid",
            bool(sd.notna().all()) and bool((sd >= PROSPECTIVE_START).all()),
            f"rows={len(signals)}",
        )
    else:
        add("signals_file_clean_or_empty", True, "no prospective signals yet")

    if not trades.empty:
        tdup = int(trades.duplicated(["ticker", "entry_date", "exit_date"]).sum())
        sigd = pd.to_datetime(trades["signal_date"], errors="coerce")
        entd = pd.to_datetime(trades["entry_date"], errors="coerce")
        exitd = pd.to_datetime(trades["exit_date"], errors="coerce")
        add("trades_no_duplicates", tdup == 0, f"duplicates={tdup}")
        add(
            "trades_causal_dates",
            bool(sigd.notna().all() and entd.notna().all() and exitd.notna().all())
            and bool((sigd < entd).all())
            and bool((entd <= exitd).all())
            and bool((sigd >= PROSPECTIVE_START).all()),
            f"rows={len(trades)}",
        )
        q = pd.to_numeric(trades.get("qty"), errors="coerce")
        add(
            "trades_positive_qty",
            bool(q.notna().all()) and bool((q > 0).all()),
            f"rows={len(trades)}",
        )
    else:
        add("trades_file_clean_or_empty", True, "no closed prospective trades yet")

    if not daily.empty:
        dd = pd.to_datetime(daily["date"], errors="coerce")
        ddup = int(daily.duplicated(["date"]).sum())
        add("daily_no_duplicates", ddup == 0, f"duplicates={ddup}")
        add(
            "daily_dates_monotonic",
            bool(dd.notna().all()) and bool(dd.is_monotonic_increasing),
            f"rows={len(daily)}",
        )
        cap = pd.to_numeric(
            daily.get("entry_cap_violations_total"), errors="coerce"
        ).fillna(0)
        add(
            "daily_entry_cap_violations_zero",
            bool((cap == 0).all()),
            f"max={int(cap.max()) if len(cap) else 0}",
        )

        gx = pd.to_numeric(daily.get("entry_exposure_max"), errors="coerce")
        rp = pd.to_numeric(daily.get("entry_portfolio_risk_max"), errors="coerce")
        # Use tiny numerical tolerance. These are entry-time caps.
        add(
            "entry_gross_cap_respected",
            bool((gx.dropna() <= 0.9000001).all()),
            f"max={gx.max() if gx.notna().any() else np.nan}",
        )
        add(
            "entry_risk_cap_respected",
            bool((rp.dropna() <= 0.0250001).all()),
            f"max={rp.max() if rp.notna().any() else np.nan}",
        )
    else:
        add("daily_file_clean_or_empty", True, "no prospective sessions yet")

    if not equity.empty:
        ed = pd.to_datetime(equity["date"], errors="coerce")
        edup = int(equity.duplicated(["date"]).sum())
        add("equity_no_duplicates", edup == 0, f"duplicates={edup}")
        add(
            "equity_dates_monotonic",
            bool(ed.notna().all()) and bool(ed.is_monotonic_increasing),
            f"rows={len(equity)}",
        )
        ev = pd.to_numeric(equity.get("equity"), errors="coerce")
        add(
            "equity_positive",
            bool(ev.notna().all()) and bool((ev > 0).all()),
            f"min={ev.min() if ev.notna().any() else np.nan}",
        )
    else:
        add("equity_file_clean_or_empty", True, "no prospective equity yet")

    if not daily.empty and not equity.empty:
        d1 = pd.to_datetime(daily["date"], errors="coerce").dt.strftime("%Y-%m-%d")
        d2 = pd.to_datetime(equity["date"], errors="coerce").dt.strftime("%Y-%m-%d")
        add(
            "daily_equity_date_sets_match",
            list(d1) == list(d2),
            f"daily={len(d1)} equity={len(d2)}",
        )
        if "equity" in daily.columns and "equity" in equity.columns and len(daily) == len(equity):
            a = pd.to_numeric(daily["equity"], errors="coerce").to_numpy()
            b = pd.to_numeric(equity["equity"], errors="coerce").to_numpy()
            ok = np.allclose(a, b, rtol=1e-10, atol=1e-6, equal_nan=True)
            add("daily_equity_values_match", ok, f"rows={len(a)}")

    return pd.DataFrame(checks)


def _rolling_metrics(trades):
    if trades.empty:
        return pd.DataFrame(columns=[
            "window", "available", "n", "pf", "avg_R", "win_rate_pct",
            "net_pnl", "start_exit_date", "end_exit_date",
        ])

    t = trades.copy()
    t["exit_date"] = pd.to_datetime(t["exit_date"], errors="coerce")
    t = t.sort_values(["exit_date", "ticker", "entry_date"]).reset_index(drop=True)

    rows = []
    for w in ROLLING_WINDOWS:
        if len(t) < w:
            rows.append({
                "window": w, "available": False, "n": len(t),
                "pf": np.nan, "avg_R": np.nan, "win_rate_pct": np.nan,
                "net_pnl": np.nan, "start_exit_date": None, "end_exit_date": None,
            })
            continue

        x = t.tail(w)
        pnl = pd.to_numeric(x["net_pnl"], errors="coerce").fillna(0.0)
        rr = pd.to_numeric(x["R"], errors="coerce").dropna()
        rows.append({
            "window": w,
            "available": True,
            "n": w,
            "pf": _pf(pnl),
            "avg_R": float(rr.mean()) if len(rr) else 0.0,
            "win_rate_pct": float((pnl > 0).mean() * 100),
            "net_pnl": float(pnl.sum()),
            "start_exit_date": str(x["exit_date"].iloc[0].date()),
            "end_exit_date": str(x["exit_date"].iloc[-1].date()),
        })
    return pd.DataFrame(rows)


def _concentration(trades):
    if trades.empty:
        return pd.DataFrame(columns=[
            "ticker", "trades", "net_pnl", "share_of_total_net_pct",
            "avg_R", "pf",
        ])

    t = trades.copy()
    t["net_pnl"] = pd.to_numeric(t["net_pnl"], errors="coerce").fillna(0.0)
    t["R"] = pd.to_numeric(t["R"], errors="coerce")

    total = float(t["net_pnl"].sum())
    rows = []
    for ticker, g in t.groupby("ticker"):
        pnl = g["net_pnl"]
        net = float(pnl.sum())
        rows.append({
            "ticker": ticker,
            "trades": len(g),
            "net_pnl": net,
            "share_of_total_net_pct": (
                float(net / total * 100) if abs(total) > 1e-12 else np.nan
            ),
            "avg_R": float(g["R"].mean()) if g["R"].notna().any() else np.nan,
            "pf": _pf(pnl),
        })

    return pd.DataFrame(rows).sort_values("net_pnl", ascending=False).reset_index(drop=True)


def _metrics(trades, equity, state):
    if trades.empty:
        pnl = pd.Series(dtype=float)
        rr = pd.Series(dtype=float)
        pf = avg_r = wr = net = 0.0
    else:
        pnl = pd.to_numeric(trades["net_pnl"], errors="coerce").fillna(0.0)
        rr = pd.to_numeric(trades["R"], errors="coerce").dropna()
        pf = _pf(pnl)
        avg_r = float(rr.mean()) if len(rr) else 0.0
        wr = float((pnl > 0).mean() * 100)
        net = float(pnl.sum())

    if equity.empty:
        final_equity = float((state or {}).get("cash", re.CONFIG["capital"]))
        ret = (final_equity / re.CONFIG["capital"] - 1.0) * 100.0
        dd = 0.0
        first_date = last_date = None
        calendar_days = 0
    else:
        e = pd.to_numeric(equity["equity"], errors="coerce").dropna()
        final_equity = float(e.iloc[-1]) if len(e) else re.CONFIG["capital"]
        ret = (final_equity / re.CONFIG["capital"] - 1.0) * 100.0
        dd = _drawdown_pct(e)
        dates = pd.to_datetime(equity["date"], errors="coerce").dropna()
        first_date = dates.iloc[0] if len(dates) else None
        last_date = dates.iloc[-1] if len(dates) else None
        calendar_days = (
            int((last_date - PROSPECTIVE_START).days + 1)
            if last_date is not None else 0
        )

    capviol = int((state or {}).get("entry_cap_violations_total", 0))

    return {
        "closed_trades": int(len(trades)),
        "net_pnl": net,
        "pf": float(pf),
        "avg_R": float(avg_r),
        "win_rate_pct": float(wr),
        "paper_return_pct": float(ret),
        "max_drawdown_pct": float(dd),
        "final_equity": float(final_equity),
        "entry_cap_violations": capviol,
        "calendar_days_from_start": calendar_days,
        "first_equity_date": str(first_date.date()) if first_date is not None else None,
        "last_equity_date": str(last_date.date()) if last_date is not None else None,
    }


def _window_row(rolling, w):
    if rolling.empty:
        return None
    x = rolling.loc[rolling["window"] == w]
    if x.empty or not bool(x.iloc[0]["available"]):
        return None
    return x.iloc[0]


def _checkpoint_stage(n, calendar_days):
    if n < CHECKPOINTS["diagnostic_1_trades"]:
        return "COLLECTING_0_24"
    if n < CHECKPOINTS["diagnostic_2_trades"]:
        return "DIAGNOSTIC_25_49"
    if n < CHECKPOINTS["first_formal_review_trades"]:
        return "DEVELOPING_50_99"
    if (
        n < CHECKPOINTS["mature_review_trades"]
        or calendar_days < CHECKPOINTS["mature_review_min_calendar_days"]
    ):
        return "FIRST_FORMAL_REVIEW_100_PLUS"
    return "MATURE_REVIEW_ELIGIBLE"


def _gate_results(metrics, rolling):
    n = metrics["closed_trades"]
    first = {
        "eligible": n >= CHECKPOINTS["first_formal_review_trades"],
        "checks": {},
        "passed": None,
    }
    if first["eligible"]:
        checks = {
            "pf_ge_1.05": metrics["pf"] >= FIRST_REVIEW_GATES["pf_ge"],
            "avg_R_gt_0": metrics["avg_R"] > FIRST_REVIEW_GATES["avg_R_gt"],
            "dd_ge_minus15": (
                metrics["max_drawdown_pct"]
                >= FIRST_REVIEW_GATES["max_drawdown_pct_ge"]
            ),
            "cap_violations_eq_0": (
                metrics["entry_cap_violations"]
                == FIRST_REVIEW_GATES["entry_cap_violations_eq"]
            ),
        }
        first["checks"] = checks
        first["passed"] = all(checks.values())

    mature_eligible = (
        n >= CHECKPOINTS["mature_review_trades"]
        and metrics["calendar_days_from_start"]
        >= CHECKPOINTS["mature_review_min_calendar_days"]
    )
    mature = {"eligible": mature_eligible, "checks": {}, "passed": None}
    if mature_eligible:
        r60 = _window_row(rolling, 60)
        checks = {
            "pf_ge_1.10": metrics["pf"] >= MATURE_REVIEW_GATES["pf_ge"],
            "avg_R_ge_0.05": metrics["avg_R"] >= MATURE_REVIEW_GATES["avg_R_ge"],
            "dd_ge_minus15": (
                metrics["max_drawdown_pct"]
                >= MATURE_REVIEW_GATES["max_drawdown_pct_ge"]
            ),
            "cap_violations_eq_0": (
                metrics["entry_cap_violations"]
                == MATURE_REVIEW_GATES["entry_cap_violations_eq"]
            ),
            "rolling_60_pf_ge_0.90": (
                r60 is not None
                and _f(r60["pf"], -np.inf)
                >= MATURE_REVIEW_GATES["rolling_60_pf_ge"]
            ),
        }
        mature["checks"] = checks
        mature["passed"] = all(checks.values())

    return first, mature


def _monitor_status(metrics, rolling, concentration, integrity):
    hard_fail = integrity.loc[
        (integrity["severity"] == "HARD") & (~integrity["passed"].astype(bool))
    ]
    alerts = []
    warnings = []

    if len(hard_fail):
        return "ENGINEERING_HALT", alerts, [
            f"integrity failure: {r['check']}" for _, r in hard_fail.iterrows()
        ]

    n = metrics["closed_trades"]

    if metrics["max_drawdown_pct"] <= ALERT_RULES["hard_drawdown_pct_le"]:
        alerts.append(
            f"drawdown {metrics['max_drawdown_pct']:.2f}% <= "
            f"{ALERT_RULES['hard_drawdown_pct_le']:.2f}%"
        )

    r60 = _window_row(rolling, 60)
    if r60 is not None:
        if (
            _f(r60["pf"], np.inf) < ALERT_RULES["rolling_60_pf_lt"]
            and _f(r60["avg_R"], np.inf) < ALERT_RULES["rolling_60_avg_R_lt"]
        ):
            alerts.append(
                f"last60 PF={r60['pf']:.2f} and AvgR={r60['avg_R']:+.3f}"
            )

    r40 = _window_row(rolling, 40)
    if r40 is not None:
        if (
            _f(r40["pf"], np.inf) < ALERT_RULES["rolling_40_pf_lt"]
            and _f(r40["avg_R"], np.inf) < ALERT_RULES["rolling_40_avg_R_lt"]
        ):
            warnings.append(
                f"last40 PF={r40['pf']:.2f} and AvgR={r40['avg_R']:+.3f}"
            )

    if n >= 30 and not concentration.empty and abs(metrics["net_pnl"]) > 1e-12:
        top5 = float(concentration.head(5)["net_pnl"].sum())
        share = top5 / metrics["net_pnl"] * 100.0
        if share > ALERT_RULES["top5_ticker_share_warn_gt_pct"]:
            warnings.append(f"top5 ticker share of total net={share:.1f}%")

    if alerts:
        return "INVESTIGATE", alerts, warnings
    if warnings:
        return "WARNING", alerts, warnings
    return "NORMAL", alerts, warnings


def run_v11_3_monitor():
    print("\n" + "=" * 126)
    print("V11.3 — FORWARD MONITORING & DRIFT GUARD")
    print("=" * 126)
    print("Capa PASIVA: no genera ni modifica operaciones.")
    print("Reglas de evaluación predeclaradas antes del primer dato prospectivo.")

    manifest = _ensure_monitor_manifest()

    integrity = _integrity_checks()
    trades = _csv(V11_TRADES)
    equity = _csv(V11_EQUITY)
    state = _json(V11_STATE) or {}

    rolling = _rolling_metrics(trades)
    concentration = _concentration(trades)
    metrics = _metrics(trades, equity, state)

    stage = _checkpoint_stage(
        metrics["closed_trades"], metrics["calendar_days_from_start"]
    )
    first_review, mature_review = _gate_results(metrics, rolling)
    status, alerts, warnings = _monitor_status(
        metrics, rolling, concentration, integrity
    )

    # Concentration diagnostics.
    if concentration.empty or abs(metrics["net_pnl"]) <= 1e-12:
        top1_share = np.nan
        top5_share = np.nan
    else:
        top1_share = float(
            concentration.head(1)["net_pnl"].sum() / metrics["net_pnl"] * 100
        )
        top5_share = float(
            concentration.head(5)["net_pnl"].sum() / metrics["net_pnl"] * 100
        )

    failed_integrity = int((~integrity["passed"].astype(bool)).sum())

    status_row = {
        "version": "V11_3_FORWARD_MONITOR",
        "monitor_manifest_sha256": manifest["sha256"],
        "status": status,
        "checkpoint_stage": stage,
        **metrics,
        "top1_ticker_share_net_pct": top1_share,
        "top5_ticker_share_net_pct": top5_share,
        "integrity_failed_checks": failed_integrity,
        "first_review_eligible": first_review["eligible"],
        "first_review_passed": first_review["passed"],
        "mature_review_eligible": mature_review["eligible"],
        "mature_review_passed": mature_review["passed"],
        "alerts": " | ".join(alerts),
        "warnings": " | ".join(warnings),
    }

    pd.DataFrame([status_row]).to_csv(STATUS_PATH, index=False)
    rolling.to_csv(ROLLING_PATH, index=False)
    concentration.to_csv(CONCENTRATION_PATH, index=False)
    integrity.to_csv(INTEGRITY_PATH, index=False)

    report = {
        "version": "V11_3_FORWARD_MONITOR",
        "monitor_manifest_sha256": manifest["sha256"],
        "status": status,
        "checkpoint_stage": stage,
        "metrics": metrics,
        "alerts": alerts,
        "warnings": warnings,
        "integrity": {
            "failed_checks": failed_integrity,
            "failures": integrity.loc[
                ~integrity["passed"].astype(bool),
                ["check", "severity", "detail"],
            ].to_dict("records"),
        },
        "first_formal_review": first_review,
        "mature_review": mature_review,
        "concentration": {
            "top1_ticker_share_net_pct": top1_share,
            "top5_ticker_share_net_pct": top5_share,
        },
        "policy": (
            "This monitor never retunes V11. A warning/investigate state triggers "
            "analysis only. Strategy changes require a new research branch and "
            "new future holdout. Passing monitoring gates does not automatically "
            "authorize real-money trading."
        ),
    }
    REPORT_PATH.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )

    print("\n" + "=" * 126)
    print("ESTADO V11.3")
    print("=" * 126)
    print(f"Status                 : {status}")
    print(f"Checkpoint             : {stage}")
    print(f"Trades cerrados        : {metrics['closed_trades']}")
    print(
        f"Equity                  : {metrics['final_equity']:,.2f} | "
        f"Ret {metrics['paper_return_pct']:+.2f}%"
    )
    print(
        f"PF / AvgR / WR          : {metrics['pf']:.2f} / "
        f"{metrics['avg_R']:+.3f} / {metrics['win_rate_pct']:.1f}%"
    )
    print(f"Max DD                  : {metrics['max_drawdown_pct']:+.2f}%")
    print(f"Cap violations          : {metrics['entry_cap_violations']}")
    print(f"Integrity failed checks : {failed_integrity}")

    for w in ROLLING_WINDOWS:
        r = _window_row(rolling, w)
        if r is None:
            print(f"Last {w:3d} trades          : N/D")
        else:
            print(
                f"Last {w:3d} trades          : "
                f"PF {r['pf']:.2f} | AvgR {r['avg_R']:+.3f} | "
                f"PnL {r['net_pnl']:+,.2f}"
            )

    if np.isfinite(top5_share):
        print(f"Top-5 ticker share      : {top5_share:.1f}%")

    print("\nREVISIONES PREDECLARADAS:")
    print(
        f"  25 trades  : diagnóstico solamente\n"
        f"  50 trades  : diagnóstico solamente\n"
        f" 100 trades  : primera revisión formal\n"
        f" 150 trades + >=183 días : revisión madura"
    )

    if first_review["eligible"]:
        print(
            f"\nPrimera revisión formal: "
            f"{'PASS' if first_review['passed'] else 'FAIL'}"
        )
    else:
        faltan = max(
            0, CHECKPOINTS["first_formal_review_trades"] - metrics["closed_trades"]
        )
        print(f"\nPrimera revisión formal: todavía no elegible ({faltan} trades faltantes)")

    if mature_review["eligible"]:
        print(
            f"Revisión madura         : "
            f"{'PASS' if mature_review['passed'] else 'FAIL'}"
        )
    else:
        print("Revisión madura         : todavía no elegible")

    if alerts:
        print("\n🚨 ALERTAS:")
        for x in alerts:
            print(f"  • {x}")
    if warnings:
        print("\n⚠️ WARNINGS:")
        for x in warnings:
            print(f"  • {x}")

    if failed_integrity:
        print("\n⛔ Hay fallos de integridad. NO tocar la estrategia; primero se audita ingeniería.")
    elif status == "INVESTIGATE":
        print("\n🔎 Evidencia de degradación: investigar, sin retunear automáticamente.")
    elif status == "WARNING":
        print("\n⚠️ Hay señales de vigilancia, pero V11 continúa congelado.")
    else:
        print("\n✅ Sin alarmas operativas según las reglas predeclaradas.")

    print("\nArchivos:")
    for p in [
        MONITOR_MANIFEST,
        STATUS_PATH,
        ROLLING_PATH,
        CONCENTRATION_PATH,
        INTEGRITY_PATH,
        REPORT_PATH,
    ]:
        print(f"  • {p.name}")
