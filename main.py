from datetime import datetime, date, timedelta
import os
import pandas as pd
import yfinance as yf
import contextlib
import io

# UNIVERSO DE CEDEARS Y ACCIONES LOCALES (BYMA) AMPLIADO E HIPERLÍQUIDO
ACTIVOS = [
    # --- TECNOLOGÍA & SEMICONDUCTORES ---
    "AAPL", "MSFT", "GOOGL", "NVDA", "AMZN", "META", "NFLX", "AMD", "INTC", 
    "QCOM", "IBM", "ORCL", "ADBE", "CRM", "PYPL", "UBER", "ABNB", "ASML", 
    "PLTR", "MRVL", "SPOT", "EBAY", "PANW", "AVGO", "TXN", "MU", "AMAT", 
    "LRCX", "SNOW", "SHOP", "CRWV", "DDOG", "NET", "ZS", "NBIS", "OKLO", 
    "RKLB", "ALAB", "TEM", "CRWD",

    # --- FINANCIERO & BANCOS ---
    "BRKB", "JPM", "C", "GS", "WFC", "AXP", "BAC", "MS", "BLK", "V", 
    "MA", "SQ", "HOOD", "NU", "STNE", "BBD", "ITUB", "PAGS", "XP",

    # --- CONSUMO MASIVO & RETAIL ---
    "KO", "PEP", "WMT", "MCD", "NKE", "PG", "DIS", "TGT", "COST", "PM", 
    "MO", "EL", "CL", "KHC", "SBUX", "MDLZ", "YUM", "ABEV", "ARCO", "MELI", 
    "ETSY",

    # --- SALUD & FARMACÉUTICAS ---
    "JNJ", "PFE", "MRNA", "ABBV", "AMGN", "ABT", "LLY", "UNH", "CVS", 
    "BMY", "MRK", "TMO", "DHR", "GILD", "ISRG", "NVO", "HIMS", "DOCU",

    # --- ENERGÍA, PETRÓLEO & MATERIALES ---
    "XOM", "CVX", "COP", "SLB", "EOG", "PXD", "OXY", "VALE", "RIO", "KGC", 
    "MUX", "SID", "BHP", "FCX", "SCCO", "PAAS", "GOLD", "LAC", "CEG", 
    "NEE", "FSLR", "MP", "ADGO",

    # --- INDUSTRIALES, DEFENSA & AUTOMOTRICES ---
    "CAT", "DE", "GE", "TM", "F", "GM", "LMT", "RTX", "BA", "HON", 
    "UNP", "UPS", "FDX", "NOC", "GD", "TSLA", "RIVN", "NIO", "SPCX", 
    "SDA", "STLA", "RACE", "ONDS",

    # --- TELECOMUNICACIONES, SERVICIOS & OTROS ---
    "T", "VZ", "TMUS", "CMCSA", "SONY", "CHTR", "BKNG", "BIDU", "BB", 
    "TEAM", "PG", "JPM", "TIMB",

    # --- OTROS POPULARES EN BYMA (INTERNACIONALES) ---
    "CSCO", "MDT", "SPGI", "GLOB", "DECK", "SYY", "AAP", "CAR", "NUE", 
    "MSI", "JD", "UPST", "ADI", "CLS", "RBLX", "CCL", "SNDK", "IREN", 
    "VST", "NOW", "SATL", "ASTS", "GPRK", "LREN3", "MGLU3", "XROX", 
    "SPCE", "O", "BBAS3", "IBM", "MRVL", "SNOW", "CRM", "PANW", "ASML",

    # --- ACCIONES ARGENTINAS (PANEL LÍDER / BYMA) ---
    "YPFD", "GGAL", "PAMP", "TGSU2", "CEPU", "BMA", "BBAR", "SUPV", 
    "BYMA", "TGNO4", "TXAR", "TECO2", "TRAN", "METR", "LOMA", "CRES", 
    "VALO", "EDN", "COME", "ALUA", "IRSA"
]

ACTIVOS = list(dict.fromkeys(ACTIVOS))
HISTORIAL_FILE = "historial_senales_williams_pro.csv"

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

    for idx, row in df_hist.iterrows():
        if row.get("Estado") == "En seguimiento":
            try:
                fecha_emision = pd.to_datetime(row["Fecha"]).date()
                dias_transcurridos = (date.today() - fecha_emision).days
                
                # REGLA DE LARRY WILLIAMS: Salida estricta por tiempo (máximo 5 ruedas de duración en corto plazo)
                if dias_transcurridos > 5:
                    df_hist.at[idx, "Estado"] = "Expirado (Regla Larry Williams: 5 ruedas max)"
                    continue

                df_test = yf.download(row["Simbolo"], period="2mo", interval="1d", progress=False)
                if not df_test.empty:
                    if isinstance(df_test.columns, pd.MultiIndex): df_test.columns = df_test.columns.get_level_values(0)
                    df_test.index = pd.to_datetime(df_test.index).date()
                    df_post = df_test[df_test.index >= fecha_emision]
                    
                    if not df_post.empty:
                        tóco_tp, tocó_sl = False, False
                        for _, r_dia in df_post.iterrows():
                            h_dia, l_dia = float(r_dia["High"]), float(r_dia["Low"])
                            tp_val, sl_val = float(row["TakeProfit"]), float(row["StopLoss"])
                            if h_dia >= tp_val: tocó_tp = True
                            if l_dia <= sl_val: tocó_sl = True
                        
                        if tocó_tp and not tocó_sl:
                            df_hist.at[idx, "Estado"] = "TP Alcanzado"
                        elif tocó_sl and not tocó_tp:
                            df_hist.at[idx, "Estado"] = "SL Tocado"
                        elif tocó_tp and tocó_sl:
                            p_actual = float(df_post.iloc[-1]["Close"])
                            df_hist.at[idx, "Estado"] = "TP Alcanzado" if p_actual >= tp_val else "SL Tocado"
            except Exception:
                pass

    hoy_str = date.today().strftime("%Y-%m-%d")
    for s in nuevas_senales:
        if not df_hist.empty and "Simbolo" in df_hist.columns and "Estado" in df_hist.columns:
            condicion = (df_hist["Simbolo"] == s["simbolo"]) & (df_hist["Estado"] == "En seguimiento")
            if condicion.any(): continue
        
        nueva_fila = pd.DataFrame([{
            "Fecha": hoy_str, "Simbolo": s["simbolo"], "PrecioEntrada": s["precio"],
            "StopLoss": s["sl"], "TakeProfit": s["tp"], "Estado": "En seguimiento"
        }])
        df_hist = pd.concat([df_hist, nueva_fila], ignore_index=True)

    df_hist.to_csv(HISTORIAL_FILE, index=False)
    
    total = len(df_hist)
    aciertos = len(df_hist[df_hist["Estado"] == "TP Alcanzado"]) if "Estado" in df_hist.columns else 0
    tropiezos = len(df_hist[df_hist["Estado"] == "SL Tocado"]) if "Estado" in df_hist.columns else 0
    seguimiento = len(df_hist[df_hist["Estado"] == "En seguimiento"]) if "Estado" in df_hist.columns else 0
    expirados = len(df_hist[df_hist["Estado"].str.contains("Expirado", na=False)]) if "Estado" in df_hist.columns else 0

    print("\n" + "=" * 105)
    print("🧠 MÓDULO DE AUTOMEJORA PRO (ESTRATEGIA LARRY WILLIAMS 100% REAL)")
    print("=" * 105)
    print(f" 📊 Estadísticas acumuladas -> Total: {total} | TP: {aciertos} | SL: {tropiezos} | Seguimiento: {seguimiento} | Expirados (Tiempo): {expirados}")
    print("=" * 105)

def auditar_cartera_personal():
    mis_activos = ["AAPL.BA", "WMT.BA", "SHOP.BA"]
    print("\n" + "=" * 105)
    print("🛡️ GESTIÓN DE RIESGO PROFESIONAL (ATR + FILTROS DE VOLATILIDAD)")
    print("=" * 105)

    for simbolo in mis_activos:
        try:
            df = yf.download(simbolo, period="1y", interval="1d", progress=False)
            if df.empty: continue
            if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)

            hl = df["High"] - df["Low"]
            hc = (df["High"] - df["Close"].shift()).abs()
            lc = (df["Low"] - df["Close"].shift()).abs()
            df["ATR_14"] = pd.concat([hl, hc, lc], axis=1).max(axis=1).rolling(14).mean()

            ultimo = df.iloc[-1]
            p_ars = float(ultimo["Close"])
            atr = float(ultimo["ATR_14"]) if not pd.isna(ultimo["ATR_14"]) else p_ars * 0.05
            riesgo_pct = max(0.04, min((atr / p_ars) * 2, 0.12))
            sl_ars = round(p_ars * (1 - riesgo_pct), 2)
            tp_ars = round(p_ars * (1 + (riesgo_pct * 1.5)), 2)

            print(f"🔹 Cartera Personal: [{simbolo}] | Precio: ${p_ars:,.2f} | SL: ${sl_ars:,.2f} | TP: ${tp_ars:,.2f}")
        except Exception:
            pass
    print("=" * 105)

def verificar_alertas():
    verificar_mercado_general()
    usa_abierto = verificar_estado_usa()
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Escaneo institucional avanzado (Williams %R + Reglas Puras 100%)...\n")

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

            # 1. Filtro de Tendencia Macro (EMA 200)
            df["EMA_200"] = df["Close"].ewm(span=200, adjust=False).mean()

            # 2. Williams %R (14 periodos)
            high_14 = df["High"].rolling(window=14).max()
            low_14 = df["Low"].rolling(window=14).min()
            df["Williams_R"] = ((high_14 - df["Close"]) / (high_14 - low_14)) * -100

            # 3. ATR de 14 periodos
            hl, hc, lc = df["High"] - df["Low"], (df["High"] - df["Close"].shift()).abs(), (df["Low"] - df["Close"].shift()).abs()
            df["ATR_14"] = pd.concat([hl, hc, lc], axis=1).max(axis=1).rolling(14).mean()

            # REGLA PURA LARRY WILLIAMS: Volatilidad de rango diario contra el promedio del ATR (Expansión de rango)
            df["ATR_Rango_Ratio"] = (df["High"] - df["Low"]) / df["ATR_14"]

            ult = df.iloc[-1]
            p_ars, h_ars, l_ars = float(ult["Close"]), float(ult["High"]), float(ult["Low"])
            will_r = float(ult["Williams_R"]) if not pd.isna(ult["Williams_R"]) else -50.0
            atr = float(ult["ATR_14"]) if not pd.isna(ult["ATR_14"]) else p_ars * 0.05
            vol_actual = float(ult["Volume"])
            atr_ratio = float(ult["ATR_Rango_Ratio"]) if not pd.isna(ult["ATR_Rango_Ratio"]) else 1.0

            # Criterios técnicos de Larry Williams refinados al 100%
            rango_dia = h_ars - l_ars
            vela_alcista = ((p_ars - l_ars) / rango_dia >= 0.40) if rango_dia > 0 else True
            vol_climax = vol_actual >= (vol_prom * 0.75)
            tendencia = p_ars > float(ult["EMA_200"])
            
            # Williams exigía que la barra de giro tenga una expansión de rango o volatilidad saludable
            expansion_volatilidad = atr_ratio >= 0.85

            # Gestión de riesgo adaptada (ATR)
            riesgo_pct = max(0.04, min((atr / p_ars) * 2.0, 0.12))
            sl_ars = max(p_ars * (1 - riesgo_pct), p_ars * 0.88)
            riesgo_real_pct = (p_ars - sl_ars) / p_ars
            tp_ars = round(p_ars * (1 + (riesgo_real_pct * 1.5)), 2)

            # Earnings
            _, _, dias_earnings = extraer_datos_fundamentales(simbolo)
            riesgo_earnings = dias_earnings < 7

            # CÁLCULO DE PUNTUACIÓN DE CALIDAD
            puntuacion = 0.0
            if tendencia:
                puntuacion += 100.0
                puntuacion += abs(will_r) 
            if vela_alcista:
                puntuacion += 50.0
            if vol_climax:
                puntuacion += 30.0
            if expansion_volatilidad:
                puntuacion += 40.0
            
            if riesgo_earnings:
                puntuacion -= 500.0

            ideal = tendencia and will_r <= -80.0 and vela_alcista and vol_climax and expansion_volatilidad and not riesgo_earnings

            resultados.append({
                "simbolo": simbolo, "precio_ars": p_ars, "will_r": will_r,
                "sl": round(sl_ars, 2), "tp": tp_ars, "riesgo_pct": riesgo_real_pct, 
                "vela": vela_alcista, "vol": vol_climax, "exp_vol": expansion_volatilidad, 
                "riesgo_earn": riesgo_earnings, "ideal": ideal and usa_abierto, "puntuacion": puntuacion
            })

            if ideal and usa_abierto:
                nuevas_senales_para_historial.append({
                    "simbolo": f"{simbolo}.BA", "precio": p_ars, 
                    "sl": round(sl_ars, 2), "tp": tp_ars
                })
        except Exception:
            pass

    # ORDENAMIENTO CORRECTO: De mayor puntuación a menor puntuación
    resultados.sort(key=lambda x: x["puntuacion"], reverse=True)
    
    print("=" * 105)
    print("TOP 10 CEDEARS - RANKING VERDADERO LARRY WILLIAMS PRO (100% FIDEDIGNO)")
    print("=" * 105)

    for i, res in enumerate(resultados[:10], 1):
        estado = "   🎯 ¡OPORTUNIDAD IDEAL PRO!" if res["ideal"] else ("   ⚠️ [DESCARTADA: FERIADO]" if (res["puntuacion"] > 0 and not usa_abierto) else ("   🛡️ [DESCARTADA: EARNINGS CERCA]" if res["riesgo_earn"] else ""))

        print(f"\n {i:2d}. [{res['simbolo']}.BA] -> Precio: ${res['precio_ars']:,.2f} | Williams %R: {res['will_r']:5.1f} | Score: {res['puntuacion']:.1f}")
        print(f"    🛑 Stop Loss: ${res['sl']:,.2f} (Riesgo: {res['riesgo_pct']*100:.1f}%) | 🎯 Take Profit: ${res['tp']:,.2f}")
        print(f"    Patrón Vela: {'✅' if res['vela'] else '❌'} | Volumen Inst.: {'✅' if res['vol'] else '❌'} | Expansión ATR: {'✅' if res['exp_vol'] else '❌'}{estado}")
        
        noticias, prox, dias = extraer_datos_fundamentales(res['simbolo'])
        print(f"    🔎 [CONTEXTO FUNDAMENTAL Y SENTIMIENTO]:")
        print(f"      📅 Próximo Balance: {prox} {'⚠️ (¡Peligro de Balance Cerca!)' if dias < 7 else '(Seguro)'}")
        print(f"      📰 Últimas Noticias y Sentimiento:")
        for tit, sent in noticias: print(f"        • {sent} {tit}")
        print("-" * 105)

    gestionar_historial_y_automejora(nuevas_senales_para_historial)

if __name__ == "__main__":
    auditar_cartera_personal()
    verificar_alertas()
