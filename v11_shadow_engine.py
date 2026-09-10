from __future__ import annotations

"""
V11.1 — PROSPECTIVE SHADOW / PAPER TRADING ENGINE
=================================================

Persistent forward tracker for the FROZEN V9 architecture.

This is NOT a backtest optimizer and DOES NOT change the strategy.

Frozen architecture:
    trend + pullback + rs20 + volume + candle
    RS20 >= 1%
    ATR% in [3%, 5%]
    VolRel >= 1.15
    TP = 1.8R
    stop = 1.5 ATR
    risk/trade = 0.5%
    max gross exposure = 90%
    max portfolio risk = 2.5%

Signal timing:
    CLOSE(D) -> OPEN(next available session)

Prospective data:
    sessions >= 2026-09-10 only.

The tracker is persistent. Never delete/edit v11_shadow_state.json once real
prospective observations have begun.
"""

from pathlib import Path
from contextlib import contextmanager
import hashlib
import json
import math

import numpy as np
import pandas as pd

import research_engine as re
import v6_falsification_lab as v6


OUT = Path("results")
OUT.mkdir(exist_ok=True)

STATE_PATH = OUT / "v11_shadow_state.json"
MANIFEST_PATH = OUT / "v11_shadow_manifest.json"
SIGNALS_PATH = OUT / "v11_shadow_signals.csv"
TRADES_PATH = OUT / "v11_shadow_trades.csv"
DAILY_PATH = OUT / "v11_shadow_daily.csv"
EQUITY_PATH = OUT / "v11_shadow_equity.csv"
SUMMARY_PATH = OUT / "v11_shadow_summary.csv"

PROSPECTIVE_START = pd.Timestamp("2026-09-10")
COMPONENTS = ("trend", "pullback", "rs20", "volume", "candle")

FILTER_SPEC = {
    "atr_min": 0.030,
    "atr_max": 0.050,
    "volrel_min": 1.15,
}

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


def _cfg():
    """research_engine uses a CONFIG dict, not a Config class."""
    c = dict(re.CONFIG)
    c.update(FROZEN_OVERRIDES)
    return c


def _manifest_payload():
    p = {
        "version": "V11_1_PROSPECTIVE_SHADOW",
        "prospective_start": str(PROSPECTIVE_START.date()),
        "components": list(COMPONENTS),
        "filter": FILTER_SPEC,
        "config_overrides": FROZEN_OVERRIDES,
        "policy": (
            "Prospective shadow tracking only. No thresholds/components/exits may "
            "be retuned using V9/V10/V11 observations. Architecture changes require "
            "a separate research cycle and a new future holdout."
        ),
    }
    raw = json.dumps(p, sort_keys=True, separators=(",", ":")).encode("utf-8")
    p["sha256"] = hashlib.sha256(raw).hexdigest()
    return p


def _ensure_manifest():
    new = _manifest_payload()
    if MANIFEST_PATH.exists():
        old = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        if old.get("sha256") == new["sha256"]:
            return old

        # The broken V11.0 wrote its manifest BEFORE failing at re.Config().
        # If no persistent state exists, no prospective trade/session could
        # have been processed, so archive that failed-attempt manifest safely.
        if (
            not STATE_PATH.exists()
            and old.get("version") == "V11_PROSPECTIVE_SHADOW"
        ):
            archive = OUT / "v11_shadow_manifest_failed_v11_0.json"
            if not archive.exists():
                archive.write_text(
                    json.dumps(old, indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )
            print(
                "🧾 Manifiesto del V11.0 fallido preservado como "
                "v11_shadow_manifest_failed_v11_0.json"
            )
        else:
            raise RuntimeError(
                "El manifiesto V11 existente no coincide con V11.1 y existe "
                "estado prospectivo o una versión desconocida. No continúo "
                "para proteger el historial."
            )

    MANIFEST_PATH.write_text(
        json.dumps(new, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return new


def _fresh_state(cfg):
    return {
        "version": "V11_1_PROSPECTIVE_SHADOW",
        "cash": float(cfg["capital"]),
        "last_processed_date": None,
        "prev_equity": float(cfg["capital"]),
        "positions": {},
        "pending": {},
        "cooldown": {},
        "entry_cap_violations_total": 0,
    }


def _load_state(cfg):
    if not STATE_PATH.exists():
        return _fresh_state(cfg)
    s = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    if s.get("version") != "V11_1_PROSPECTIVE_SHADOW":
        # The original broken V11 could only have written a manifest before failing
        # at _make_cfg(); it could not legitimately create a working state.
        raise RuntimeError(
            "Existe un state de otra versión de V11. "
            "No lo convierto automáticamente para proteger el historial."
        )
    return s


def _save_state(state):
    STATE_PATH.write_text(
        json.dumps(state, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )


def _append(path, rows, dedup=None):
    if not rows:
        return
    new = pd.DataFrame(rows)
    if path.exists():
        old = pd.read_csv(path)
        out = pd.concat([old, new], ignore_index=True)
    else:
        out = new
    if dedup:
        cols = [c for c in dedup if c in out.columns]
        if cols:
            out = out.drop_duplicates(subset=cols, keep="first")
    else:
        out = out.drop_duplicates(keep="first")
    out.to_csv(path, index=False)


def _load_prepared_data():
    raw = re.download_universe("USA")
    spy_raw = re.download_spy()
    data, spy = re.prepare(raw, spy_raw)
    if not data:
        raise RuntimeError("No quedaron activos válidos después de preparar indicadores.")
    return data, spy


def _filtered_signals(data, cfg):
    # Uses exactly the same robust filter machinery as V6/V7/V8/V9.
    with v6._signal_filter_patch(FILTER_SPEC):
        return re.precompute_signals(data, cfg, COMPONENTS)


def _row_price(prices, ticker, date):
    return prices.get(ticker, {}).get(date)


def _ticker_next_available(data, ticker, after_date):
    df = data.get(ticker)
    if df is None or df.empty:
        return None
    idx = df.index
    j = idx.searchsorted(pd.Timestamp(after_date), side="right")
    if j >= len(idx):
        return None
    return pd.Timestamp(idx[j])


def _resolve_pending_dates(state, data):
    """
    A close-of-latest-day signal cannot know tomorrow's Yahoo row yet.
    Keep execution_date=None, then resolve it once a later session exists.
    """
    for ticker, order in state["pending"].items():
        if order.get("execution_date"):
            continue
        nxt = _ticker_next_available(data, ticker, order["signal_date"])
        if nxt is not None:
            order["execution_date"] = str(nxt.date())


def _mark_equity(state, prices, date):
    cash = float(state["cash"])
    mv = 0.0
    risk = 0.0

    for ticker, p in state["positions"].items():
        pxrow = _row_price(prices, ticker, date)
        if pxrow is not None:
            mark = float(pxrow[3])
        else:
            mark = float(p.get("last_mark", p["entry"]))
        p["last_mark"] = mark
        mv += int(p["qty"]) * mark
        risk += float(p["risk_dollars"])

    eq = cash + mv
    return eq, mv, risk


def _trade_record(p, px, date, reason, cfg):
    qty = int(p["qty"])
    entry = float(p["entry"])
    gross = qty * (float(px) - entry)
    exit_comm = qty * float(px) * cfg["commission"]
    total_comm = float(p["entry_commission"]) + exit_comm
    net = gross - total_comm
    risk_dollars = float(p["risk_dollars"])
    risk_share = risk_dollars / qty if qty else np.nan

    return {
        "ticker": p["ticker"],
        "signal_date": p["signal_date"],
        "entry_date": p["entry_date"],
        "exit_date": str(pd.Timestamp(date).date()),
        "entry": entry,
        "exit": float(px),
        "qty": qty,
        "entry_value": float(p["entry_value"]),
        "gross_pnl": float(gross),
        "commission": float(total_comm),
        "net_pnl": float(net),
        "return_pct": re.sdiv(net, p["entry_value"]) * 100,
        "risk_dollars": risk_dollars,
        "planned_risk_pct_equity": float(p["planned_risk_pct_equity"]),
        "R": re.sdiv(net, risk_dollars),
        "mfe_R": re.sdiv(p["mfe"], risk_share),
        "mae_R": re.sdiv(p["mae"], risk_share),
        "gap_loss_R": float(p.get("gap_loss_R", 0.0)),
        "reason": reason,
        "score": float(p["score"]),
        "rank": float(p["rank"]),
    }


def _execute_entries(state, prices, date, cfg):
    entries_today = 0
    exposure_max = 0.0
    risk_max = 0.0
    opened = []

    for ticker, order in list(state["pending"].items()):
        ex = order.get("execution_date")
        if ex is None:
            continue

        exdate = pd.Timestamp(ex)

        # Pending orders are valid ONLY for their intended next session.
        if exdate < date:
            del state["pending"][ticker]
            continue
        if exdate != date:
            continue

        del state["pending"][ticker]

        if entries_today >= int(order["entry_limit"]):
            continue
        if ticker in state["positions"]:
            continue

        row = _row_price(prices, ticker, date)
        if row is None:
            continue

        o, h, l, c = row
        atr = re.sf(order["atr"])
        if not np.isfinite(o) or not np.isfinite(atr) or atr <= 0:
            continue

        entry = o * (1 + cfg["slippage"])
        stop = entry - cfg["stop_atr"] * atr
        risk_share = entry - stop
        if risk_share <= 0:
            continue

        equity, current_mv, _ = _mark_equity(state, prices, date)
        if equity <= 0:
            continue

        current_risk = sum(float(p["risk_dollars"]) for p in state["positions"].values())

        desired_risk = equity * cfg["risk_per_trade"]
        available_risk = max(0.0, equity * cfg["max_portfolio_risk"] - current_risk)
        cap_buffer = float(cfg.get("cap_buffer", 1.0))
        desired_risk = min(desired_risk, available_risk * cap_buffer)
        if desired_risk <= 0:
            continue

        max_notional = equity * cfg["max_position_pct"] * cap_buffer
        gross_room = max(
            0.0,
            equity * cfg["max_gross_exposure"] * cap_buffer - current_mv
        )
        risk_room = max(
            0.0,
            equity * cfg["max_portfolio_risk"] * cap_buffer - current_risk
        )

        qty_risk = math.floor(desired_risk / risk_share)
        qty_notional = math.floor(max_notional / entry)
        qty_gross = math.floor(gross_room / entry)
        qty_cash = math.floor(
            float(state["cash"]) / (entry * (1 + cfg["commission"]))
        )
        qty = min(qty_risk, qty_notional, qty_gross, qty_cash)

        if qty <= 0:
            continue

        while qty > 0:
            value = qty * entry
            entry_comm = value * cfg["commission"]
            post_equity = equity - entry_comm
            post_gross = current_mv + value
            actual_risk = qty * risk_share
            post_risk = current_risk + actual_risk

            gross_ok = (
                re.sdiv(post_gross, post_equity)
                <= cfg["max_gross_exposure"] * cap_buffer
            )
            risk_ok = (
                re.sdiv(post_risk, post_equity)
                <= cfg["max_portfolio_risk"] * cap_buffer
            )
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
        state["cash"] = float(state["cash"]) - value - entry_comm

        pos = {
            "ticker": ticker,
            "signal_date": order["signal_date"],
            "entry_date": str(date.date()),
            "entry": float(entry),
            "entry_value": float(value),
            "entry_commission": float(entry_comm),
            "qty": int(qty),
            "stop": float(stop),
            "target": float(entry + cfg["tp_r"] * risk_share),
            "risk_dollars": float(actual_risk),
            "planned_risk_pct_equity": float(actual_risk / equity),
            "bars": 0,
            "mfe": 0.0,
            "mae": 0.0,
            "gap_loss_R": 0.0,
            "score": float(order["score"]),
            "rank": float(order["rank"]),
            "last_mark": float(entry),
            "scheduled_exit": None,
        }
        state["positions"][ticker] = pos

        post_equity = equity - entry_comm
        entry_exposure = re.sdiv(current_mv + value, post_equity)
        entry_risk = re.sdiv(current_risk + actual_risk, post_equity)
        exposure_max = max(exposure_max, entry_exposure)
        risk_max = max(risk_max, entry_risk)

        if (
            entry_exposure > cfg["max_gross_exposure"]
            or entry_risk > cfg["max_portfolio_risk"]
        ):
            state["entry_cap_violations_total"] += 1

        entries_today += 1
        opened.append({
            "ticker": ticker,
            "signal_date": order["signal_date"],
            "entry_date": str(date.date()),
            "entry": float(entry),
            "qty": int(qty),
            "stop": float(stop),
            "target": float(pos["target"]),
            "risk_dollars": float(actual_risk),
        })

    return opened, exposure_max, risk_max


def _scheduled_expiry_exits(state, prices, date, cfg):
    closed = []
    for ticker, p in list(state["positions"].items()):
        sx = p.get("scheduled_exit")
        if not sx or pd.Timestamp(sx) != date:
            continue
        row = _row_price(prices, ticker, date)
        if row is None:
            continue
        o = float(row[0])
        px = o * (1 - cfg["slippage"])
        rec = _trade_record(p, px, date, "EXPIRY", cfg)
        closed.append(rec)
        state["cash"] += p["qty"] * px * (1 - cfg["commission"])
        del state["positions"][ticker]
    return closed


def _manage_positions(state, data, prices, date, cfg):
    closed = []

    for ticker, p in list(state["positions"].items()):
        row = _row_price(prices, ticker, date)
        if row is None:
            continue

        o, h, l, c = row
        p["bars"] = int(p["bars"]) + 1

        if np.isfinite(h):
            p["mfe"] = max(float(p["mfe"]), h - float(p["entry"]))
        if np.isfinite(l):
            p["mae"] = min(float(p["mae"]), l - float(p["entry"]))

        px = None
        reason = None

        if np.isfinite(o) and o <= p["stop"]:
            px = o * (1 - cfg["slippage"])
            reason = "SL_GAP"
        elif np.isfinite(o) and o >= p["target"]:
            px = o * (1 - cfg["slippage"])
            reason = "TP_GAP"
        elif np.isfinite(l) and l <= p["stop"]:
            # Same conservative ordering as audited research engine.
            px = p["stop"] * (1 - cfg["slippage"])
            reason = "SL"
        elif np.isfinite(h) and h >= p["target"]:
            px = p["target"] * (1 - cfg["slippage"])
            reason = "TP"

        if px is not None:
            if reason == "SL_GAP":
                risk_share = p["risk_dollars"] / p["qty"]
                p["gap_loss_R"] = max(
                    0.0,
                    (p["stop"] - px) / risk_share
                )
            rec = _trade_record(p, px, date, reason, cfg)
            closed.append(rec)
            state["cash"] += p["qty"] * px * (1 - cfg["commission"])
            if reason.startswith("SL"):
                state["cooldown"][ticker] = str(date.date())
            del state["positions"][ticker]
            continue

        if p["bars"] >= cfg["max_bars"] and not p.get("scheduled_exit"):
            nxt = _ticker_next_available(data, ticker, date)
            if nxt is not None:
                p["scheduled_exit"] = str(nxt.date())
            else:
                # Unlike a finite historical backtest, DO NOT force-liquidate
                # just because tomorrow's Yahoo bar does not exist yet.
                p["scheduled_exit"] = "NEXT_SESSION"

    return closed


def _resolve_scheduled_exits(state, data, date):
    for ticker, p in state["positions"].items():
        if p.get("scheduled_exit") != "NEXT_SESSION":
            continue
        nxt = _ticker_next_available(data, ticker, date - pd.Timedelta(days=1))
        if nxt is not None and nxt >= date:
            p["scheduled_exit"] = str(nxt.date())


def _signal_candidates(signal_maps, state, date):
    rows = []
    for ticker, mp in signal_maps.items():
        x = mp.get(date)
        if x is None:
            continue
        if ticker in state["positions"] or ticker in state["pending"]:
            continue

        cd = state["cooldown"].get(ticker)
        if cd is not None:
            if (date - pd.Timestamp(cd)).days < 7:
                continue

        rows.append(x)

    rows.sort(
        key=lambda x: (x["rank"], x["score"], x["ticker"]),
        reverse=True
    )
    return rows


def _generate_signals(state, data, spy, signal_maps, date, equity, cfg):
    level = re.market_level(spy, date)
    maxpos = cfg["max_positions"] if level >= 1 else cfg["max_positions_weak"]
    maxent = (
        cfg["max_entries_day"] if level >= 1
        else cfg["max_entries_day_weak"]
    )

    slots = min(
        max(0, maxpos - len(state["positions"]) - len(state["pending"])),
        maxent
    )
    if slots <= 0 or equity <= 0:
        return []

    candidates = _signal_candidates(signal_maps, state, date)
    selected = candidates[:slots]
    rows = []

    for cand in selected:
        ticker = cand["ticker"]
        sr = cand["signal_row"]
        atr = re.sf(sr.get("ATR"))
        if not np.isfinite(atr) or atr <= 0:
            continue

        execution_date = _ticker_next_available(data, ticker, date)

        order = {
            "ticker": ticker,
            "signal_date": str(date.date()),
            "execution_date": (
                str(execution_date.date())
                if execution_date is not None else None
            ),
            "atr": float(atr),
            "score": float(cand["score"]),
            "rank": float(cand["rank"]),
            "entry_limit": int(maxent),
        }
        state["pending"][ticker] = order

        # Signal audit fields from the actual causal row.
        rows.append({
            **order,
            "signal_close": re.sf(sr.get("Close")),
            "ATR_PCT": re.sf(sr.get("ATR_PCT")),
            "VolRel": re.sf(sr.get("VolRel")),
            "RS20": re.sf(sr.get("RS20")),
            "market_level": int(level),
        })

    return rows


def _summary(state):
    trades = pd.read_csv(TRADES_PATH) if TRADES_PATH.exists() else pd.DataFrame()
    equity = pd.read_csv(EQUITY_PATH) if EQUITY_PATH.exists() else pd.DataFrame()

    if not trades.empty:
        pnl = pd.to_numeric(trades["net_pnl"], errors="coerce").fillna(0.0)
        rr = pd.to_numeric(trades["R"], errors="coerce").dropna()
        wins = pnl[pnl > 0].sum()
        losses = -pnl[pnl < 0].sum()
        pf = re.sdiv(wins, losses)
        wr = float((pnl > 0).mean() * 100)
        avg_r = float(rr.mean()) if len(rr) else 0.0
        net = float(pnl.sum())
    else:
        pf = wr = avg_r = net = 0.0

    if not equity.empty:
        e = pd.to_numeric(equity["equity"], errors="coerce").dropna()
        if len(e):
            ret = (e.iloc[-1] / re.CONFIG["capital"] - 1) * 100
            peak = e.cummax()
            dd = ((e / peak) - 1).min() * 100
            final_eq = float(e.iloc[-1])
        else:
            ret = dd = 0.0
            final_eq = float(state["cash"])
    else:
        ret = dd = 0.0
        final_eq = float(state["cash"])

    return pd.DataFrame([{
        "version": "V11_1_PROSPECTIVE_SHADOW",
        "last_processed_date": state["last_processed_date"],
        "final_equity": final_eq,
        "cash": float(state["cash"]),
        "open_positions": len(state["positions"]),
        "pending_entries": len(state["pending"]),
        "closed_trades": len(trades),
        "net_pnl_closed": net,
        "paper_return_pct": float(ret),
        "pf": float(pf),
        "avg_R": float(avg_r),
        "win_rate": float(wr),
        "max_drawdown_pct": float(dd),
        "entry_cap_violations_total": int(
            state["entry_cap_violations_total"]
        ),
    }])


def run_v11_shadow():
    print("\n" + "=" * 126)
    print("V11.1 — PROSPECTIVE SHADOW / PAPER TRADING ENGINE")
    print("=" * 126)
    print("Arquitectura congelada: trend + pullback + rs20 + volume + candle")
    print("RS20 >= 1% | ATR 3–5% | VolRel >= 1.15 | TP 1.8R | SL 1.5 ATR | riesgo 0.5%")
    print("Inicio prospectivo: 2026-09-10")
    print("No hay sweeps, selección post-hoc ni liquidación artificial al final de cada ejecución.")

    cfg = _cfg()
    manifest = _ensure_manifest()
    state = _load_state(cfg)

    data, spy = _load_prepared_data()
    signals = _filtered_signals(data, cfg)
    signal_maps = re.signal_maps(signals)
    prices = re.price_row_maps(data)

    # Resolve orders/signals whose future session was unknown on the previous run.
    _resolve_pending_dates(state, data)

    all_dates = re.build_calendar(
        data,
        PROSPECTIVE_START,
        pd.Timestamp.max,
    )

    if state["last_processed_date"]:
        last = pd.Timestamp(state["last_processed_date"])
        new_dates = [d for d in all_dates if d > last]
    else:
        new_dates = list(all_dates)

    if not new_dates:
        latest = max((df.index.max() for df in data.values()), default=None)
        print("\nℹ️ No hay una rueda nueva para procesar.")
        print(f"Última fecha disponible en el universo: {latest}")
        print("El estado prospectivo no fue alterado.")
        return

    print(f"\nRuedas nuevas: {len(new_dates)}")
    print(f"Procesando {new_dates[0].date()} -> {new_dates[-1].date()}")

    signal_rows = []
    trade_rows = []
    daily_rows = []
    equity_rows = []

    for date in new_dates:
        # If a time-exit was waiting for the next as-yet-unknown session,
        # resolve it now before the open.
        _resolve_scheduled_exits(state, data, date)

        opened, entry_exp_max, entry_risk_max = _execute_entries(
            state, prices, date, cfg
        )

        expiry_closed = _scheduled_expiry_exits(
            state, prices, date, cfg
        )
        managed_closed = _manage_positions(
            state, data, prices, date, cfg
        )
        closed = expiry_closed + managed_closed
        trade_rows.extend(closed)

        equity, market_value, risk_dollars = _mark_equity(
            state, prices, date
        )

        gross_exposure = re.sdiv(market_value, equity)
        portfolio_risk = re.sdiv(risk_dollars, equity)

        new_signals = _generate_signals(
            state, data, spy, signal_maps, date, equity, cfg
        )
        signal_rows.extend(new_signals)

        daily_pnl = equity - float(state["prev_equity"])
        daily_return = (
            re.sdiv(equity, state["prev_equity"]) - 1
            if state["prev_equity"] > 0 else 0.0
        )

        daily_rows.append({
            "date": str(date.date()),
            "new_signals": len(new_signals),
            "entries": len(opened),
            "exits": len(closed),
            "open_positions": len(state["positions"]),
            "pending_entries": len(state["pending"]),
            "cash": float(state["cash"]),
            "market_value": float(market_value),
            "equity": float(equity),
            "gross_exposure": float(gross_exposure),
            "portfolio_risk": float(portfolio_risk),
            "entry_exposure_max": float(entry_exp_max),
            "entry_portfolio_risk_max": float(entry_risk_max),
            "entry_cap_violations_total": int(
                state["entry_cap_violations_total"]
            ),
            "daily_pnl": float(daily_pnl),
            "daily_return": float(daily_return),
        })

        equity_rows.append({
            "date": str(date.date()),
            "cash": float(state["cash"]),
            "market_value": float(market_value),
            "equity": float(equity),
            "positions": len(state["positions"]),
            "gross_exposure": float(gross_exposure),
            "portfolio_risk": float(portfolio_risk),
        })

        state["prev_equity"] = float(equity)
        state["last_processed_date"] = str(date.date())

        # Save after EACH session so interruption cannot erase prior forward data.
        _save_state(state)

    _append(
        SIGNALS_PATH,
        signal_rows,
        dedup=["ticker", "signal_date"],
    )
    _append(
        TRADES_PATH,
        trade_rows,
        dedup=["ticker", "entry_date", "exit_date"],
    )
    _append(
        DAILY_PATH,
        daily_rows,
        dedup=["date"],
    )
    _append(
        EQUITY_PATH,
        equity_rows,
        dedup=["date"],
    )

    summary = _summary(state)
    summary.to_csv(SUMMARY_PATH, index=False)

    s = summary.iloc[0]

    print("\n" + "=" * 126)
    print("ESTADO PROSPECTIVO")
    print("=" * 126)
    print(f"Manifest SHA256: {manifest['sha256'][:16]}…")
    print(f"Última rueda procesada: {s.last_processed_date}")
    print(f"Nuevas señales en este lote: {len(signal_rows)}")
    print(f"Nuevas salidas en este lote: {len(trade_rows)}")
    print(f"Posiciones abiertas: {int(s.open_positions)}")
    print(f"Entradas pendientes D+1: {int(s.pending_entries)}")
    print(f"Trades cerrados acumulados: {int(s.closed_trades)}")
    print(
        f"Equity {s.final_equity:,.0f} | Ret {s.paper_return_pct:+.2f}% | "
        f"PF {s.pf:.2f} | AvgR {s.avg_R:+.3f} | DD {s.max_drawdown_pct:+.2f}%"
    )
    print(f"Entry-cap violations: {int(s.entry_cap_violations_total)}")

    if state["pending"]:
        print("\nÓRDENES PENDIENTES:")
        for ticker, o in state["pending"].items():
            ex = o.get("execution_date") or "próxima rueda todavía desconocida"
            print(
                f"  • {ticker}: señal {o['signal_date']} -> open {ex} "
                f"| score {o['score']:.2f} | rank {o['rank']:.3f}"
            )

    if state["positions"]:
        print("\nPOSICIONES SHADOW ABIERTAS:")
        for ticker, p in state["positions"].items():
            print(
                f"  • {ticker}: qty {p['qty']} | entry {p['entry']:.2f} | "
                f"SL {p['stop']:.2f} | TP {p['target']:.2f} | bars {p['bars']}"
            )

    print("\nArchivos:")
    for p in [
        MANIFEST_PATH,
        STATE_PATH,
        SIGNALS_PATH,
        TRADES_PATH,
        DAILY_PATH,
        EQUITY_PATH,
        SUMMARY_PATH,
    ]:
        if p.exists():
            print(f"  • {p.name}")

    print("\nREGLAS:")
    print("• Ejecutar después del cierre cuando Yahoo tenga la rueda completa.")
    print("• No borrar/editar los v11_shadow_* una vez iniciado el seguimiento.")
    print("• No retunear la arquitectura mirando V11.")
    print("• Los datos futuros acumulados constituyen la nueva validación prospectiva.")
