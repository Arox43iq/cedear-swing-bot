"""
Estrategia: señal simple y causal.
El laboratorio decide qué componentes merecen quedarse.
"""
BASE_COMPONENTS = ("trend","pullback","wpr","rs20","volume","candle","momentum")

def component_values(row, cfg):
    close=float(row["Close"]); ema20=float(row["EMA20"])
    ema50=float(row["EMA50"]); ema200=float(row["EMA200"])
    trend=float(close>ema200 and ema20>ema50>ema200)

    dist20=close/ema20-1
    pullback=float(
        -cfg["pullback_below"] <= dist20 <= cfg["pullback_above"]
        and float(row["LowEMA20Dist"]) <= cfg["low_ema20_tol"]
    )
    wpr=float(float(row["WPR"]) <= cfg["wpr_threshold"])
    rs20=float(float(row["RS20"]) >= cfg["rs20_min"])
    volume=float(float(row["VolRel"]) >= cfg["volume_min"])
    candle=float(float(row["CloseLocation"]) >= cfg["location_min"])
    momentum=float(
        float(row["Ret5"]) > cfg["ret5_min"]
        and float(row["Ret20"]) > cfg["ret20_min"]
    )
    return {
        "trend":trend, "pullback":pullback, "wpr":wpr,
        "rs20":rs20, "volume":volume, "candle":candle,
        "momentum":momentum
    }

def signal(row, cfg, active=None):
    active=set(active or BASE_COMPONENTS)
    vals=component_values(row,cfg)

    if "trend" in active and not vals["trend"]:
        return False,0.0,vals

    others=[x for x in active if x!="trend"]
    if not others:
        return True,1.0,vals

    score=sum(vals[x] for x in others)/len(others)

    # WPR remains the rebound trigger whenever it is active.
    if "wpr" in active and not vals["wpr"]:
        return False,score,vals

    confirmations=[x for x in others if x!="wpr"]
    required=min(cfg["min_confirm"],len(confirmations))
    if confirmations and sum(vals[x] for x in confirmations)<required:
        return False,score,vals

    return True,score,vals
