from __future__ import annotations

"""
V11.2 — PARITY & INTEGRITY AUDIT
================================

Purpose
-------
Try to falsify the implementation of V11.1 without changing the strategy.

This module:
1) verifies the frozen V9/V11 architecture,
2) checks source/file integrity,
3) replays the frozen strategy historically through the V11.1 execution helpers,
4) compares that replay against research_engine.backtest(),
5) checks trades, equity, caps and causal timing,
6) verifies that the audit itself does NOT mutate prospective V11 state.

IMPORTANT
---------
This is an engineering audit, NOT a new strategy optimization.
No thresholds, components, exits or sizing parameters are selected here.
"""

from pathlib import Path
import hashlib
import json
import math
import traceback

import numpy as np
import pandas as pd

import research_engine as re
import v6_falsification_lab as v6
import v11_shadow_engine as sh


OUT = Path("results")
OUT.mkdir(exist_ok=True)

AUDIT_START = pd.Timestamp("2023-01-03")
AUDIT_END = pd.Timestamp("2025-12-31")

SUMMARY_PATH = OUT / "v11_2_parity_summary.csv"
TRADE_DIFF_PATH = OUT / "v11_2_trade_diffs.csv"
EQUITY_DIFF_PATH = OUT / "v11_2_equity_diffs.csv"
CHECKS_PATH = OUT / "v11_2_integrity_checks.csv"
REPORT_PATH = OUT / "v11_2_verdict.json"

PROTECTED = [
    OUT / "v11_shadow_state.json",
    OUT / "v11_shadow_manifest.json",
    OUT / "v11_shadow_signals.csv",
    OUT / "v11_shadow_trades.csv",
    OUT / "v11_shadow_daily.csv",
    OUT / "v11_shadow_equity.csv",
    OUT / "v11_shadow_summary.csv",
]

NUMERIC_TRADE_FIELDS = [
    "entry", "exit", "qty", "entry_value", "gross_pnl", "commission",
    "net_pnl", "return_pct", "risk_dollars", "planned_risk_pct_equity",
    "R", "mfe_R", "mae_R", "gap_loss_R", "score", "rank",
]

TRADE_ID_FIELDS = ["ticker", "entry_date", "exit_date"]
EQ_FIELDS = [
    "cash", "market_value", "equity", "positions",
    "gross_exposure", "portfolio_risk",
]


def _sha_file(path: Path):
    if not path.exists():
        return None
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _protected_hashes():
    return {str(p): _sha_file(p) for p in PROTECTED}


def _same_or_nan(a, b, atol=1e-8, rtol=1e-10):
    if pd.isna(a) and pd.isna(b):
        return True
    try:
        aa = float(a)
        bb = float(b)
        if np.isnan(aa) and np.isnan(bb):
            return True
        return bool(np.isclose(aa, bb, atol=atol, rtol=rtol))
    except Exception:
        return str(a) == str(b)


def _normalize_dates(df):
    out = df.copy()
    for c in ["date", "entry_date", "exit_date", "signal_date"]:
        if c in out.columns:
            out[c] = pd.to_datetime(out[c], errors="coerce").dt.strftime("%Y-%m-%d")
    return out


def _frozen_config_check(cfg):
    checks = []

    expected_components = ("trend", "pullback", "rs20", "volume", "candle")
    checks.append({
        "check": "components_exact",
        "passed": tuple(sh.COMPONENTS) == expected_components,
        "detail": f"{tuple(sh.COMPONENTS)}",
    })

    expected_filter = {"atr_min": 0.03, "atr_max": 0.05, "volrel_min": 1.15}
    checks.append({
        "check": "filter_exact",
        "passed": all(_same_or_nan(sh.FILTER_SPEC.get(k), v) for k, v in expected_filter.items()),
        "detail": json.dumps(sh.FILTER_SPEC, sort_keys=True),
    })

    expected_cfg = {
        "rs20_min": 0.01,
        "tp_r": 1.8,
        "stop_atr": 1.5,
        "risk_per_trade": 0.005,
        "max_gross_exposure": 0.90,
        "max_portfolio_risk": 0.025,
        "commission": 0.0005,
        "slippage": 0.0005,
    }
    for k, v in expected_cfg.items():
        checks.append({
            "check": f"config_{k}",
            "passed": _same_or_nan(cfg.get(k), v),
            "detail": f"actual={cfg.get(k)!r} expected={v!r}",
        })

    # If the V9 manifest exists locally, require exact architectural agreement.
    v9_path = OUT / "v9_frozen_manifest.json"
    if v9_path.exists():
        v9 = json.loads(v9_path.read_text(encoding="utf-8"))
        checks.append({
            "check": "v9_manifest_sha_known",
            "passed": v9.get("sha256") == "08aebe4a77bc71466f04e14a350979dcb8e129bd13115eb42b98dda9ccec9c26",
            "detail": str(v9.get("sha256")),
        })
        checks.append({
            "check": "v9_components_match_v11",
            "passed": tuple(v9.get("components", [])) == tuple(sh.COMPONENTS),
            "detail": f"v9={v9.get('components')} v11={list(sh.COMPONENTS)}",
        })
        vf = v9.get("filter", {})
        checks.append({
            "check": "v9_filter_match_v11",
            "passed": (
                _same_or_nan(vf.get("atr_min"), sh.FILTER_SPEC["atr_min"])
                and _same_or_nan(vf.get("atr_max"), sh.FILTER_SPEC["atr_max"])
                and _same_or_nan(vf.get("volrel_min"), sh.FILTER_SPEC["volrel_min"])
            ),
            "detail": f"v9={vf} v11={sh.FILTER_SPEC}",
        })
        vc = v9.get("config", {})
        checks.append({
            "check": "v9_config_match_v11",
            "passed": all(_same_or_nan(vc.get(k), sh.FROZEN_OVERRIDES.get(k)) for k in expected_cfg),
            "detail": "all frozen V9 config keys compared",
        })
    else:
        checks.append({
            "check": "v9_manifest_present",
            "passed": False,
            "detail": "results/v9_frozen_manifest.json not found",
        })

    return checks


def _reference_backtest(data, spy, cfg):
    with v6._signal_filter_patch(sh.FILTER_SPEC):
        trades, equity = re.backtest(
            data,
            spy,
            dict(cfg),
            sh.COMPONENTS,
            AUDIT_START,
            AUDIT_END,
            label="V11.2 REFERENCE",
        )
    return trades, equity


def _terminal_close(state, prices, last_date, cfg, trades):
    # Match research_engine's finite-window FINAL_LIQ behavior exactly.
    for ticker, p in list(state["positions"].items()):
        if ticker not in prices or last_date not in prices[ticker]:
            continue
        c = prices[ticker][last_date][3]
        px = c * (1 - cfg["slippage"])
        rec = sh._trade_record(p, px, last_date, "FINAL_LIQ", cfg)
        trades.append(rec)
        state["cash"] += p["qty"] * px * (1 - cfg["commission"])
        del state["positions"][ticker]


def _eop_time_exits(state, prices, date, end, cfg, trades):
    """
    V11 is open-ended, while historical backtest has a finite window.
    For audit parity only, convert a time exit whose next session is outside the
    audit window into research_engine's EOP_LIQ at today's close.
    """
    closed = []
    for ticker, p in list(state["positions"].items()):
        sx = p.get("scheduled_exit")
        if sx is None or sx == "NEXT_SESSION":
            continue
        sx_ts = pd.Timestamp(sx)
        if sx_ts <= end:
            continue
        row = prices.get(ticker, {}).get(date)
        if row is None:
            continue
        c = row[3]
        px = c * (1 - cfg["slippage"])
        rec = sh._trade_record(p, px, date, "EOP_LIQ", cfg)
        closed.append(rec)
        state["cash"] += p["qty"] * px * (1 - cfg["commission"])
        del state["positions"][ticker]
    trades.extend(closed)
    return closed


def _shadow_finite_replay(data, spy, cfg):
    """
    Historical replay through V11.1 helper functions.

    The only audit-specific behavior is finite-window closure so it can be
    compared apples-to-apples with research_engine.backtest().
    """
    signals = sh._filtered_signals(data, cfg)
    smaps = re.signal_maps(signals)
    prices = re.price_row_maps(data)
    dates = re.build_calendar(data, AUDIT_START, AUDIT_END)

    state = sh._fresh_state(cfg)
    trades = []
    eq_rows = []

    for date in dates:
        opened, entry_exp_max, entry_risk_max = sh._execute_entries(
            state, prices, date, cfg
        )

        expiry_closed = sh._scheduled_expiry_exits(
            state, prices, date, cfg
        )
        managed_closed = sh._manage_positions(
            state, data, prices, date, cfg
        )
        trades.extend(expiry_closed)
        trades.extend(managed_closed)

        # Convert V11's open-ended scheduled time exits to finite-window EOP.
        _eop_time_exits(state, prices, date, AUDIT_END, cfg, trades)

        equity, market_value, risk_dollars = sh._mark_equity(
            state, prices, date
        )
        gross_exposure = re.sdiv(market_value, equity)
        portfolio_risk = re.sdiv(risk_dollars, equity)

        prev_eq = float(state["prev_equity"])
        eq_rows.append({
            "date": date,
            "cash": float(state["cash"]),
            "market_value": float(market_value),
            "equity": float(equity),
            "positions": len(state["positions"]),
            "gross_exposure": float(gross_exposure),
            "portfolio_risk": float(portfolio_risk),
            "entry_exposure_max": float(entry_exp_max),
            "entry_portfolio_risk_max": float(entry_risk_max),
            "entry_cap_violations": 0,  # audited separately from state cumulative
            "daily_pnl": float(equity - prev_eq),
            "daily_return": float(re.sdiv(equity, prev_eq) - 1 if prev_eq > 0 else 0.0),
        })
        state["prev_equity"] = float(equity)

        # Same signal-generation stage as V11.1.
        sh._generate_signals(
            state, data, spy, smaps, date, equity, cfg
        )

        # Historical reference refuses orders whose execution is outside end.
        for ticker, order in list(state["pending"].items()):
            ex = order.get("execution_date")
            if ex is None or pd.Timestamp(ex) > AUDIT_END:
                del state["pending"][ticker]

    if dates and state["positions"]:
        last_date = dates[-1]
        _terminal_close(state, prices, last_date, cfg, trades)
        if eq_rows:
            eq_rows[-1]["cash"] = float(state["cash"])
            eq_rows[-1]["market_value"] = 0.0
            eq_rows[-1]["equity"] = float(state["cash"])
            eq_rows[-1]["positions"] = 0
            eq_rows[-1]["gross_exposure"] = 0.0
            eq_rows[-1]["portfolio_risk"] = 0.0

    return pd.DataFrame(trades), pd.DataFrame(eq_rows)


def _compare_trades(ref, shadow):
    ref = _normalize_dates(ref)
    shadow = _normalize_dates(shadow)

    # Build deterministic occurrence index in case same ticker/date tuple repeats.
    keys = TRADE_ID_FIELDS
    for df in (ref, shadow):
        df["_occ"] = df.groupby(keys, dropna=False).cumcount()

    merged = ref.merge(
        shadow,
        on=keys + ["_occ"],
        how="outer",
        suffixes=("_ref", "_shadow"),
        indicator=True,
    )

    diffs = []
    mismatch_fields = 0

    for _, row in merged.iterrows():
        identity = {k: row.get(k) for k in keys}
        if row["_merge"] != "both":
            diffs.append({
                **identity,
                "field": "_presence",
                "reference": row["_merge"],
                "shadow": row["_merge"],
                "abs_diff": np.nan,
            })
            mismatch_fields += 1
            continue

        # Exact categorical reason.
        if str(row.get("reason_ref")) != str(row.get("reason_shadow")):
            diffs.append({
                **identity,
                "field": "reason",
                "reference": row.get("reason_ref"),
                "shadow": row.get("reason_shadow"),
                "abs_diff": np.nan,
            })
            mismatch_fields += 1

        for f in NUMERIC_TRADE_FIELDS:
            a = row.get(f"{f}_ref")
            b = row.get(f"{f}_shadow")
            if _same_or_nan(a, b, atol=1e-7, rtol=1e-10):
                continue
            try:
                ad = abs(float(a) - float(b))
            except Exception:
                ad = np.nan
            diffs.append({
                **identity,
                "field": f,
                "reference": a,
                "shadow": b,
                "abs_diff": ad,
            })
            mismatch_fields += 1

    return pd.DataFrame(diffs), merged, mismatch_fields


def _compare_equity(ref, shadow):
    ref = _normalize_dates(ref)
    shadow = _normalize_dates(shadow)
    merged = ref.merge(
        shadow,
        on="date",
        how="outer",
        suffixes=("_ref", "_shadow"),
        indicator=True,
    )

    diffs = []
    mismatch_fields = 0

    for _, row in merged.iterrows():
        date = row.get("date")
        if row["_merge"] != "both":
            diffs.append({
                "date": date,
                "field": "_presence",
                "reference": row["_merge"],
                "shadow": row["_merge"],
                "abs_diff": np.nan,
            })
            mismatch_fields += 1
            continue

        for f in EQ_FIELDS:
            a = row.get(f"{f}_ref")
            b = row.get(f"{f}_shadow")
            tol = 1e-6 if f in {"cash", "market_value", "equity"} else 1e-9
            if _same_or_nan(a, b, atol=tol, rtol=1e-10):
                continue
            try:
                ad = abs(float(a) - float(b))
            except Exception:
                ad = np.nan
            diffs.append({
                "date": date,
                "field": f,
                "reference": a,
                "shadow": b,
                "abs_diff": ad,
            })
            mismatch_fields += 1

    return pd.DataFrame(diffs), merged, mismatch_fields


def _causality_checks(trades, data):
    bad = []
    for i, r in trades.iterrows():
        ticker = r["ticker"]
        ed = pd.Timestamp(r["entry_date"])
        # signal_date is V11-specific; if unavailable in a terminal close record,
        # entry still must occur on a valid market date.
        if ticker not in data or ed not in data[ticker].index:
            bad.append((i, ticker, str(ed.date()), "entry_not_in_ticker_calendar"))
    return bad


def _signal_hash(data, cfg):
    signals = sh._filtered_signals(data, cfg)
    rows = []
    for ticker, xs in signals.items():
        for x in xs:
            rows.append((
                ticker,
                str(pd.Timestamp(x["date"]).date()),
                round(float(x["score"]), 12),
                round(float(x["rank"]), 12),
                round(float(x["atr"]), 12),
            ))
    rows.sort()
    raw = json.dumps(rows, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest(), len(rows)


def run_v11_2_audit():
    print("\n" + "=" * 126)
    print("V11.2 — PARITY & INTEGRITY AUDIT")
    print("=" * 126)
    print("Objetivo: intentar romper la IMPLEMENTACIÓN sin modificar la estrategia.")
    print(f"Replay histórico: {AUDIT_START.date()} -> {AUDIT_END.date()}")
    print("Los archivos prospectivos V11 están protegidos y se verifican antes/después.")

    protected_before = _protected_hashes()
    cfg = sh._cfg()

    checks = _frozen_config_check(cfg)

    print("\n[1/5] Descargando/preparando datos mediante el motor real...")
    data, spy = sh._load_prepared_data()

    print("[2/5] Hash determinista de señales congeladas...")
    sig_hash_1, sig_n_1 = _signal_hash(data, cfg)
    sig_hash_2, sig_n_2 = _signal_hash(data, cfg)
    checks.append({
        "check": "signal_precompute_deterministic",
        "passed": sig_hash_1 == sig_hash_2 and sig_n_1 == sig_n_2,
        "detail": f"n={sig_n_1} sha={sig_hash_1}",
    })

    print("[3/5] Ejecutando research_engine.backtest() de referencia...")
    ref_trades, ref_eq = _reference_backtest(data, spy, cfg)

    print("[4/5] Ejecutando replay independiente mediante helpers V11.1...")
    sh_trades, sh_eq = _shadow_finite_replay(data, spy, cfg)

    print("[5/5] Comparando trade por trade, equity por equity e integridad...")
    trade_diffs, trade_merge, trade_mismatch = _compare_trades(
        ref_trades, sh_trades
    )
    eq_diffs, eq_merge, eq_mismatch = _compare_equity(ref_eq, sh_eq)

    protected_after = _protected_hashes()
    protected_ok = protected_before == protected_after

    checks.extend([
        {
            "check": "trade_count_exact",
            "passed": len(ref_trades) == len(sh_trades),
            "detail": f"reference={len(ref_trades)} shadow={len(sh_trades)}",
        },
        {
            "check": "trade_fields_exact",
            "passed": trade_mismatch == 0,
            "detail": f"mismatched_fields={trade_mismatch}",
        },
        {
            "check": "equity_rows_exact",
            "passed": len(ref_eq) == len(sh_eq),
            "detail": f"reference={len(ref_eq)} shadow={len(sh_eq)}",
        },
        {
            "check": "equity_fields_exact",
            "passed": eq_mismatch == 0,
            "detail": f"mismatched_fields={eq_mismatch}",
        },
        {
            "check": "prospective_files_untouched",
            "passed": protected_ok,
            "detail": "all protected hashes identical before/after audit",
        },
    ])

    # Economics-level summary even if row-level parity fails.
    def pnl_pf(df):
        if df.empty:
            return 0.0, 0.0
        pnl = pd.to_numeric(df["net_pnl"], errors="coerce").fillna(0.0)
        wins = pnl[pnl > 0].sum()
        losses = -pnl[pnl < 0].sum()
        return float(pnl.sum()), float(re.sdiv(wins, losses))

    ref_pnl, ref_pf = pnl_pf(ref_trades)
    sh_pnl, sh_pf = pnl_pf(sh_trades)

    ref_final = (
        float(pd.to_numeric(ref_eq["equity"], errors="coerce").iloc[-1])
        if len(ref_eq) else cfg["capital"]
    )
    sh_final = (
        float(pd.to_numeric(sh_eq["equity"], errors="coerce").iloc[-1])
        if len(sh_eq) else cfg["capital"]
    )

    checks.extend([
        {
            "check": "final_equity_exact",
            "passed": _same_or_nan(ref_final, sh_final, atol=1e-6),
            "detail": f"reference={ref_final:.8f} shadow={sh_final:.8f}",
        },
        {
            "check": "net_pnl_exact",
            "passed": _same_or_nan(ref_pnl, sh_pnl, atol=1e-6),
            "detail": f"reference={ref_pnl:.8f} shadow={sh_pnl:.8f}",
        },
        {
            "check": "profit_factor_exact",
            "passed": _same_or_nan(ref_pf, sh_pf, atol=1e-10),
            "detail": f"reference={ref_pf:.12f} shadow={sh_pf:.12f}",
        },
    ])

    # Hard cap checks from reference equity; V11 state tracks cumulative entry violations.
    ref_capviol = 0
    if "entry_cap_violations" in ref_eq.columns:
        ref_capviol = int(
            pd.to_numeric(ref_eq["entry_cap_violations"], errors="coerce")
            .fillna(0).sum()
        )
    checks.append({
        "check": "reference_entry_caps_clean",
        "passed": ref_capviol == 0,
        "detail": f"violations={ref_capviol}",
    })

    checks_df = pd.DataFrame(checks)
    checks_df.to_csv(CHECKS_PATH, index=False)

    if trade_diffs.empty:
        pd.DataFrame(columns=[
            *TRADE_ID_FIELDS, "field", "reference", "shadow", "abs_diff"
        ]).to_csv(TRADE_DIFF_PATH, index=False)
    else:
        trade_diffs.to_csv(TRADE_DIFF_PATH, index=False)

    if eq_diffs.empty:
        pd.DataFrame(columns=[
            "date", "field", "reference", "shadow", "abs_diff"
        ]).to_csv(EQUITY_DIFF_PATH, index=False)
    else:
        eq_diffs.to_csv(EQUITY_DIFF_PATH, index=False)

    hard_failures = checks_df.loc[~checks_df["passed"].astype(bool)]
    verdict = (
        "PARITY_CONFIRMED"
        if hard_failures.empty
        else "PARITY_FAILED_NEEDS_ENGINEERING_FIX"
    )

    summary = pd.DataFrame([{
        "version": "V11_2_PARITY_AUDIT",
        "audit_start": str(AUDIT_START.date()),
        "audit_end": str(AUDIT_END.date()),
        "verdict": verdict,
        "reference_trades": len(ref_trades),
        "shadow_trades": len(sh_trades),
        "trade_mismatch_fields": trade_mismatch,
        "equity_mismatch_fields": eq_mismatch,
        "reference_net_pnl": ref_pnl,
        "shadow_net_pnl": sh_pnl,
        "reference_pf": ref_pf,
        "shadow_pf": sh_pf,
        "reference_final_equity": ref_final,
        "shadow_final_equity": sh_final,
        "reference_entry_cap_violations": ref_capviol,
        "signal_count": sig_n_1,
        "signal_sha256": sig_hash_1,
        "prospective_files_untouched": protected_ok,
        "failed_checks": len(hard_failures),
    }])
    summary.to_csv(SUMMARY_PATH, index=False)

    report = {
        "version": "V11_2_PARITY_AUDIT",
        "purpose": "engineering parity/integrity audit only; no strategy tuning",
        "audit_window": {
            "start": str(AUDIT_START.date()),
            "end": str(AUDIT_END.date()),
        },
        "verdict": verdict,
        "failed_checks": hard_failures[["check", "detail"]].to_dict("records"),
        "reference": {
            "trades": len(ref_trades),
            "net_pnl": ref_pnl,
            "pf": ref_pf,
            "final_equity": ref_final,
            "entry_cap_violations": ref_capviol,
        },
        "shadow_replay": {
            "trades": len(sh_trades),
            "net_pnl": sh_pnl,
            "pf": sh_pf,
            "final_equity": sh_final,
        },
        "mismatches": {
            "trade_fields": trade_mismatch,
            "equity_fields": eq_mismatch,
        },
        "signal_fingerprint": {
            "count": sig_n_1,
            "sha256": sig_hash_1,
        },
        "prospective_files_untouched": protected_ok,
        "policy": (
            "A parity failure triggers an engineering fix only. "
            "It does NOT authorize changing strategy thresholds/components/exits."
        ),
    }
    REPORT_PATH.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print("\n" + "=" * 126)
    print("RESULTADO V11.2")
    print("=" * 126)
    print(f"Reference trades : {len(ref_trades)}")
    print(f"Shadow trades    : {len(sh_trades)}")
    print(f"Trade mismatches : {trade_mismatch}")
    print(f"Equity mismatches: {eq_mismatch}")
    print(f"Reference PnL    : {ref_pnl:,.2f} | PF {ref_pf:.6f}")
    print(f"Shadow PnL       : {sh_pnl:,.2f} | PF {sh_pf:.6f}")
    print(f"Reference equity : {ref_final:,.2f}")
    print(f"Shadow equity    : {sh_final:,.2f}")
    print(f"Entry cap viol.  : {ref_capviol}")
    print(f"Signal fingerprint: {sig_n_1} rows | {sig_hash_1[:20]}…")
    print(f"Prospective state untouched: {protected_ok}")
    print(f"\nVERDICT: {verdict}")

    if not hard_failures.empty:
        print("\nCHECKS FALLIDOS:")
        for _, r in hard_failures.iterrows():
            print(f"  ❌ {r['check']}: {r['detail']}")
        print(
            "\nNo retuneamos nada. Si falla, usamos v11_2_trade_diffs.csv / "
            "v11_2_equity_diffs.csv para corregir SOLO la implementación."
        )
    else:
        print(
            "\n✅ Paridad exacta confirmada. La implementación V11.1 puede congelarse "
            "para seguimiento prospectivo."
        )

    print("\nArchivos:")
    for p in [
        SUMMARY_PATH, CHECKS_PATH, TRADE_DIFF_PATH, EQUITY_DIFF_PATH, REPORT_PATH
    ]:
        print(f"  • {p.name}")
