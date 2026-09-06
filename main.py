from datetime import datetime, date
import os
import pandas as pd
import yfinance as yf
import contextlib
import io

# UNIVERSO DE CEDEARS LIMPIO (TICKERS COMPATIBLES CON YFINANCE BSAS)
ACTIVOS = [
    "AAPL", "MSFT", "MELI", "GOOGL", "NVDA", "AMZN", "TSLA", "NFLX", 
    "AMD", "INTC", "QCOM", "IBM", "ORCL", "ADBE", "CRM", "PYPL", 
    "UBER", "ABNB", "ASML", "PLTR", "MRVL", "SPOT", "EBAY", "PANW", 
    "BRKB", "JPM", "C", "GS", "WFC", "AXP", "NU", "STNE", "BBD", 
    "KO", "PEP", "WMT", "MCD", "NKE", "PG", "DIS", "TGT", "ABEV", 
    "ARCO", "JNJ", "PFE", "MRNA", "ABBV", "AMGN", "ABT", "XOM", 
    "CVX", "VALE", "RIO", "KGC", "MUX", "SID", "CAT", "DE", "GE", 
    "TM", "F", "LMT", "RTX", "CSCO", "MDT", "SPGI", "GLOB", "DECK", 
    "SYY", "AAP", "SONY", "CAR", "NUE", "MSI", "JD", "UPST", "MO", 
    "ADI", "OXY", "TMUS", "TSM", "BABA", "T", "MU", "V", "LAC", 
    "LLY", "AMAT", "CLS", "RBLX", "CCL"
]

ACTIVOS = list(dict.fromkeys(ACTIVOS))
HISTORIAL_FILE = "historial_senales.csv"

def verificar_estado_usa():
    try:
        df_us = yf.download("SPY", period="5d", interval="1d", progress=False)
        if df_us.empty: return True
        if isinstance(df_us.columns, pd.MultiIndex): df_us.columns = df_us.columns.get_level_values(0)
        ultima_fecha = pd.to_datetime(df_us.index[-1]).date()
        hoy = date.today()
        if hoy.weekday() >= 5: return True
        if ultima_fecha < hoy:
            print(f"\n⚠️ [ESCUDO ANTI-FERIADO] Wall Street está cerrado en EE.UU. (Última rueda: {ultima_fecha}).")
            return False
    except Exception:
        pass
    return True

def verificar_mercado_general():
    try:
        df_spy = yf.download("SPY.BA", period="1y", interval="1d", progress=False)
        if not df_spy.empty:
            if isinstance(df_spy.columns, pd.MultiIndex): df_spy.columns = df_spy.columns.get_level_values(0)
            df_spy["EMA_200"] = df_spy["Close"].ewm(span=200, adjust=False).mean()
            if df_spy.iloc[-1]["Close"] < df_spy.iloc[-1]["EMA_200"]:
                print("\n⚠️ [ALERTA MACRO] El S&P 500 local está por debajo de la EMA 200. Precaución extrema.")
            else:
                print("\n✅ [ESTADO MACRO] El S&P 500 (SPY.BA) está alcista. Entorno favorable para operar CEDEARs.")
    except Exception:
        pass

def analizar_sentimiento_noticia(titulo):
    titulo_lower = titulo.lower()
    positivas = ["best", "buy", "growth", "rebound", "gain", "up", "bull", "boost", "upgrade", "profit", "beat", "rally"]
    negativas = ["down", "fall", "slip", "drop", "bear", "loss", "miss", "risk", "cut", "warning", "crash"]
    score = sum(1 for p in positivas if p in titulo_lower) - sum(1 for p in negativas if p in titulo_lower)
    return "🟢 [Positivo]" if score > 0 else "🔴 [Negativo]" if score < 0 else "⚪ [Neutral]"

def extraer_datos_fundamentales(ticker):
    tkr = yf.Ticker(ticker)
    noticias = []
    try:
        with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
            for item in (tkr.news or [])[:2]:
                tit = item.get("title") or item.get("content", {}).get("title", "Sin título")
                noticias.append((tit, analizar_sentimiento_noticia(tit)))
    except Exception:
        pass
    if not noticias: noticias.append(("Sin noticias recientes.", "⚪ [Neutral]"))
    
    prox_earn = "N/D"
    dias = 999
    try:
        with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
            cal = tkr.calendar
        edates = cal.get("Earnings Date") if isinstance(cal, dict) else (cal.index.tolist() if isinstance(cal, pd.DataFrame) and not cal.empty else None)
        if edates:
            f = pd.to_datetime(edates[0]).date()
            prox_earn = str(f)
            dias = (f - date.today()).days
    except Exception:
        pass
    return noticias, prox_earn, dias

def gestionar_historial_y_automejora(nuevas_senales):
    columnas = ["Fecha", "Simbolo", "PrecioEntrada", "StopLoss", "TakeProfit", "Estado"]
    
    if os.path.exists(HISTORIAL_FILE):
        try:
            df_hist = pd.read_csv(HISTORIAL_FILE)
            if not all(col in df_hist.columns for col in columnas):
                df_hist = pd.DataFrame(columns=columnas)
        except Exception:
            df_hist = pd.DataFrame(columns=columnas)
    else:
        df_hist = pd.DataFrame(columns=columnas)

    # Actualizar estado de señales anteriores en seguimiento
    for idx, row in df_hist.iterrows():
        if row.get("Estado") == "En seguimiento":
            try:
                df_test = yf.download(row["Simbolo"], period="5d", interval="1d", progress=False)
                if not df_test.empty:
                    if isinstance(df_test.columns, pd.MultiIndex): df_test.columns = df_test.columns.get_level_values(0)
                    p_actual = float(df_test.iloc[-1]["Close"])
                    if p_actual >= float(row["TakeProfit"]):
                        df_hist.at[idx, "Estado"] = "TP Alcanzado"
                    elif p_actual <= float(row["StopLoss"]):
                        df_hist.at[idx, "Estado"] = "SL Tocado"
            except Exception:
                pass

    # Agregar nuevas señales ideales
    hoy_str = date.today().strftime("%Y-%m-%d")
    for s in nuevas_senales:
        if not df_hist.empty and "Simbolo" in df_hist.columns and "Estado" in df_hist.columns:
            condicion = (df_hist["Simbolo"] == s["simbolo"]) & (df_hist["Estado"] == "En seguimiento")
            if condicion.any():
                continue
        
        nueva_fila = pd.DataFrame([{
            "Fecha": hoy_str, "Simbolo": s["simbolo"], "PrecioEntrada": s["precio"],
            "StopLoss": s["sl"], "TakeProfit": s["tp"], "Estado": "En seguimiento"
        }])
        df_hist = pd.concat([df_hist, nueva_fila], ignore_index=True)

    df_hist.to_csv(HISTORIAL_FILE, index=False)

    # Calcular estadísticas seguras
    total = len(df_hist)
    aciertos = len(df_hist[df_hist["Estado"] == "TP Alcanzado"]) if "Estado" in df_hist.columns else 0
    tropiezos = len(df_hist[df_hist["Estado"] == "SL Tocado"]) if "Estado" in df_hist.columns else 0
    seguimiento = len(df_hist[df_hist["Estado"] == "En seguimiento"]) if "Estado" in df_hist.columns else 0

    print("\n" + "=" * 105)
    print("🧠 MÓDULO DE AUTOMEJORA & HISTORIAL DE OPORTUNIDADES IDEALES BLINDADAS")
    print("=" * 105)
    print(" 📊 Estadísticas acumuladas del Bot:")
    print(f"    • Total de señales ideales emitidas históricamente: {total}")
    print(f"    • Aciertos (Take Profit alcanzado): {aciertos} | Tropiezos (Stop Loss tocado): {tropiezos} | En seguimiento: {seguimiento}")
    print(" 🤖 Estado de Automejora: Activo (Filtros de riesgo estrictos aplicados).")
    print("=" * 105)

def auditar_cartera_personal():
    mis_activos = ["AAPL.BA", "WMT.BA", "SHOP.BA"]
    print("\n" + "=" * 105)
    print("🛡️ GESTIÓN DE RIESGO DINÁMICA (ATR + SOPORTES TÉCNICOS) PARA CARTERA PERSONAL")
    print("=" * 105)

    for simbolo in mis_activos:
        try:
            df = yf.download(simbolo, period="1y", interval="1d", progress=False)
            if df.empty: continue
            if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)

            df["EMA_20"] = df["Close"].ewm(span=20, adjust=False).mean()
            df["Soporte_60d"] = df["Low"].rolling(window=60).min()
            
            hl = df["High"] - df["Low"]
            hc = (df["High"] - df["Close"].shift()).abs()
            lc = (df["Low"] - df["Close"].shift()).abs()
            df["ATR_14"] = pd.concat([hl, hc, lc], axis=1).max(axis=1).rolling(14).mean()

            ultimo = df.iloc[-1]
            p_ars = float(ultimo["Close"])
            ema_ars = float(ultimo["EMA_20"])
            sop_60d = float(ultimo["Soporte_60d"]) if not pd.isna(ultimo["Soporte_60d"]) else p_ars * 0.95
            atr = float(ultimo["ATR_14"]) if not pd.isna(ultimo["ATR_14"]) else p_ars * 0.05

            riesgo_pct = max(0.04, min((atr / p_ars) * 2, 0.12))
            sl_volatilidad = p_ars * (1 - riesgo_pct)
            sl_soportes = min(sop_60d, ema_ars) * 0.98 
            
            # PARCHE: Piso estricto del 12% de pérdida máxima
            piso_absoluto = p_ars * 0.88
            sl_ars = round(max(min(sl_volatilidad, sl_soportes), piso_absoluto), 2)
            
            riesgo_real_pct = (p_ars - sl_ars) / p_ars
            
            # Take profit dinámico ajustado al riesgo (Ratio mínimo 1.5x)
            tp_ars = round(max(ema_ars * 1.05, p_ars * (1 + (riesgo_real_pct * 1.5))), 2)

            print(f"\n🔹 Cartera Personal: [{simbolo}]")
            print(f"   • Precio Local (ARS):  $ {p_ars:>10,.2f}")
            print(f"   • 🛑 Stop Loss (ARS):  $ {sl_ars:>10,.2f}   ---> ¡Blindado! (Riesgo: {riesgo_real_pct*100:.1f}%)")
            print(f"   • 🎯 Take Profit (ARS): $ {tp_ars:>10,.2f}   ---> ¡Ratio R:B garantizado (Min 1.5x)!")
        except Exception:
            pass
    print("=" * 105)

def verificar_alertas():
    verificar_mercado_general()
    usa_abierto = verificar_estado_usa()
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Analizando CEDEARs con ATR dinámico y filtros técnicos...\n")

    resultados = []
    nuevas_senales_para_historial = []

    for simbolo in ACTIVOS:
        simba = f"{simbolo}.BA"
        try:
            with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
                df = yf.download(simba, period="2y", interval="1d", progress=False)
            if df.empty or len(df) < 200: continue
            if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)

            vol_prom = df["Volume"].rolling(window=20).mean().iloc[-1]
            if pd.isna(vol_prom) or vol_prom < 100: continue

            df["EMA_200"] = df["Close"].ewm(span=200, adjust=False).mean()
            df["EMA_20"] = df["Close"].ewm(span=20, adjust=False).mean()
            df["SMA_20"] = df["Close"].rolling(window=20).mean()
            df["STD_20"] = df["Close"].rolling(window=20).std()
            df["Banda_Inferior"] = df["SMA_20"] - (df["STD_20"] * 2)
            df["Soporte_60d"] = df["Low"].rolling(window=60).min()

            hl, hc, lc = df["High"] - df["Low"], (df["High"] - df["Close"].shift()).abs(), (df["Low"] - df["Close"].shift()).abs()
            df["ATR_14"] = pd.concat([hl, hc, lc], axis=1).max(axis=1).rolling(14).mean()

            delta = df["Close"].diff()
            df["RSI_7"] = 100 - (100 / (1 + ((delta.where(delta > 0, 0)).rolling(7).mean() / (-delta.where(delta < 0, 0)).rolling(7).mean())))
            stoch_rsi = ((df["RSI_7"] - df["RSI_7"].rolling(14).min()) / (df["RSI_7"].rolling(14).max() - df["RSI_7"].rolling(14).min())) * 100

            ult = df.iloc[-1]
            p_ars, h_ars, l_ars = float(ult["Close"]), float(ult["High"]), float(ult["Low"])
            banda_inf = float(ult["Banda_Inferior"])
            sop_60d = float(ult["Soporte_60d"]) if not pd.isna(ult["Soporte_60d"]) else p_ars * 0.95
            ema_20 = float(ult["EMA_20"])
            atr = float(ult["ATR_14"]) if not pd.isna(ult["ATR_14"]) else p_ars * 0.05
            stoch = float(stoch_rsi.iloc[-1]) if not pd.isna(stoch_rsi.iloc[-1]) else 50.0

            vela_alcista = ((p_ars - l_ars) / (h_ars - l_ars) if (h_ars - l_ars) > 0 else 0.5) >= 0.40
            vol_climax = float(ult["Volume"]) >= (vol_prom * 0.8)
            tendencia = p_ars > float(ult["EMA_200"])
            
            riesgo_pct = max(0.04, min((atr / p_ars) * 2.5, 0.12))
            
            # PARCHE: Piso estricto del 12% máximo de pérdida
            sl_ars = max(min(p_ars * (1 - riesgo_pct), min(sop_60d, ema_20, banda_inf) * 0.985), p_ars * 0.88)
            riesgo_real_pct = (p_ars - sl_ars) / p_ars
            
            # TP Dinámico asegurando ratio 1.5x
            tp_ars = round(max(ema_20 * 1.05, p_ars * (1 + (riesgo_real_pct * 1.5))), 2)

            dist = ((p_ars - banda_inf) / banda_inf) * 100
            puntuacion = max(0, stoch) + max(0, dist * 50) if tendencia else 9999.0

            ideal = tendencia and p_ars <= banda_inf * 1.01 and stoch < 25 and vela_alcista and vol_climax

            resultados.append({
                "simbolo": simbolo, "precio_ars": p_ars, "banda_inf": banda_inf,
                "sl": round(sl_ars, 2), "tp": tp_ars, "riesgo_pct": riesgo_real_pct, 
                "stoch": stoch, "vela": vela_alcista, "vol": vol_climax, 
                "ideal": ideal and usa_abierto, "puntuacion": puntuacion
            })

            if ideal and usa_abierto:
                nuevas_senales_para_historial.append({
                    "simbolo": f"{simbolo}.BA", "precio": p_ars, 
                    "sl": round(sl_ars, 2), "tp": tp_ars
                })
        except Exception:
            pass

    resultados.sort(key=lambda x: x["puntuacion"])
    
    print("=" * 105)
    print("TOP 10 CEDEARS EN PESOS REALES (SL DINÁMICO POR VOLATILIDAD + SOPORTES)")
    print("=" * 105)

    for i, res in enumerate(resultados[:10], 1):
        estado = "   🎯 ¡OPORTUNIDAD IDEAL BLINDADA!" if res["ideal"] else ("   ⚠️ [DESCARTADA: FERIADO]" if (res["puntuacion"] != 9999 and not usa_abierto) else "")

        print(f"\n {i:2d}. [{res['simbolo']}.BA] -> Precio: ${res['precio_ars']:,.2f} | Banda Inf: ${res['banda_inf']:,.2f}")
        print(f"    🛑 Stop Loss Sugerido: ${res['sl']:,.2f} (Riesgo: {res['riesgo_pct']*100:.1f}%) | 🎯 Take Profit Sugerido: ${res['tp']:,.2f}")
        print(f"    StochRSI(7): {res['stoch']:5.1f} | Giro Precio: {'✅' if res['vela'] else '❌'} | Vol Giro: {'✅' if res['vol'] else '❌'}{estado}")
        
        noticias, prox, dias = extraer_datos_fundamentales(res['simbolo'])
        print(f"    🔎 [CONTEXTO FUNDAMENTAL Y SENTIMIENTO]:")
        print(f"      📅 Próximo Balance: {prox} {'⚠️ (Cerca!)' if dias < 7 else '(Seguro)'}")
        print(f"      📰 Últimas Noticias y Sentimiento:")
        for tit, sent in noticias: print(f"        • {sent} {tit}")
        print("-" * 105)

    # Gestionar y registrar historial en CSV de forma limpia
    gestionar_historial_y_automejora(nuevas_senales_para_historial)

if __name__ == "__main__":
    auditar_cartera_personal()
    verificar_alertas()