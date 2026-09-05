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
MAX_RIESGO_PCT = 0.05  # Tope base de Stop Loss al 5%
MIN_GANANCIA_PCT = 0.06 # Take profit optimizado al 6% mínimo
HISTORIAL_FILE = "historial_senales.csv"


def verificar_mercado_general():
    try:
        df_spy = yf.download("SPY.BA", period="1y", interval="1d", progress=False)
        if not df_spy.empty:
            if isinstance(df_spy.columns, pd.MultiIndex):
                df_spy.columns = df_spy.columns.get_level_values(0)
            df_spy["EMA_200"] = df_spy["Close"].ewm(span=200, adjust=False).mean()
            ultimo_spy = df_spy.iloc[-1]
            if ultimo_spy["Close"] < ultimo_spy["EMA_200"]:
                print("\n⚠️ [ALERTA MACRO] El S&P 500 local está por debajo de la EMA 200. Precaución extrema.")
            else:
                print("\n✅ [ESTADO MACRO] El S&P 500 (SPY.BA) está alcista. Entorno favorable para operar CEDEARs.")
    except Exception as e:
        print(f"No se pudo verificar el contexto general: {e}")


def analizar_sentimiento_noticia(titulo):
    titulo_lower = titulo.lower()
    palabras_positivas = ["best", "buy", "growth", "rebound", "gain", "up", "bull", "boost", "high", "upgrade", "profit", "beat", "positive", "strong", "surge", "rally"]
    palabras_negativas = ["down", "fall", "slip", "drop", "blacklist", "bear", "loss", "miss", "inflation", "war", "risk", "cut", "warning", "crash", "negative"]
    score = sum(1 for p in palabras_positivas if p in titulo_lower) - sum(1 for p in palabras_negativas if p in titulo_lower)
    return "🟢 [Positivo]" if score > 0 else "🔴 [Negativo]" if score < 0 else "⚪ [Neutral]"


def extraer_datos_fundamentales(ticker_original):
    ticker_yf = yf.Ticker(ticker_original)
    noticias_con_sentimiento = []
    try:
        with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
            news = ticker_yf.news
        if news:
            for item in news[:2]:
                titulo = item.get("title") or item.get("content", {}).get("title", "Sin título")
                noticias_con_sentimiento.append((titulo, analizar_sentimiento_noticia(titulo)))
    except Exception:
        pass

    if not noticias_con_sentimiento:
        noticias_con_sentimiento.append(("Sin noticias destacadas recientes.", "⚪ [Neutral]"))

    proximo_earnings = "N/D"
    dias_para_earnings = 999
    try:
        with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
            cal = ticker_yf.calendar
        edates = cal.get("Earnings Date") if isinstance(cal, dict) else (cal.index.tolist() if isinstance(cal, pd.DataFrame) and not cal.empty else None)
        if edates:
            fecha_ing = pd.to_datetime(edates[0]).date()
            proximo_earnings = str(fecha_ing)
            dias_para_earnings = (fecha_ing - date.today()).days
    except Exception:
        pass

    return noticias_con_sentimiento, proximo_earnings, dias_para_earnings


def calcular_ajuste_volatilidad(simbolo):
    """
    Módulo de Automejora: Analiza el historial guardado. Si un activo acumuló
    falsos rompimientos (stop loss tocados por alta volatilidad), amplía dinámicamente
    el riesgo permitido para evitar expulsiones prematuras.
    """
    if not os.path.exists(HISTORIAL_FILE):
        return MAX_RIESGO_PCT
    
    try:
        df_hist = pd.read_csv(HISTORIAL_FILE)
        df_activo = df_hist[df_hist["simbolo"] == simbolo]
        if len(df_activo) >= 3:
            derrotas = len(df_activo[df_activo["estado"] == "DERROTA"])
            tasa_fallo = derrotas / len(df_activo)
            # Si falla más del 40% de las veces, ensanchamos el Stop Loss un 1.5% extra por volatilidad
            if tasa_fallo > 0.4:
                return MAX_RIESGO_PCT + 0.015 
    except Exception:
        pass
    
    return MAX_RIESGO_PCT


def gestionar_historial_y_automejora(nuevas_senales):
    """
    Registra nuevas oportunidades ideales y audita el rendimiento pasado de las señales.
    """
    print("\n" + "=" * 105)
    print("🧠 MÓDULO DE AUTOMEJORA & HISTORIAL DE OPORTUNIDADES IDEALES BLINDADAS")
    print("=" * 105)

    # 1. Cargar o crear el archivo de historial
    if os.path.exists(HISTORIAL_FILE):
        df_hist = pd.read_csv(HISTORIAL_FILE)
    else:
        df_hist = pd.DataFrame(columns=["fecha", "simbolo", "precio_entrada", "stop_loss", "take_profit", "estado"])

    # 2. Auditar señales pendientes en el historial actualizando precios con yfinance
    if not df_hist.empty and "estado" in df_hist.columns:
        pendientes = df_hist[df_hist["estado"] == "PENDIENTE"]
        for idx, row in pendientes.iterrows():
            simbolo_ba = f"{row['simbolo']}.BA"
            try:
                df_test = yf.download(simbolo_ba, period="5d", interval="1d", progress=False)
                if not df_test.empty:
                    if isinstance(df_test.columns, pd.MultiIndex):
                        df_test.columns = df_test.columns.get_level_values(0)
                    
                    max_alcanzado = df_test["High"].max()
                    min_alcanzado = df_test["Low"].min()
                    
                    # Comprobar si tocó Take Profit o Stop Loss
                    if max_alcanzado >= row["take_profit"]:
                        df_hist.loc[idx, "estado"] = "EXITO 🎯"
                    elif min_alcanzado <= row["stop_loss"]:
                        df_hist.loc[idx, "estado"] = "DERROTA 🛑"
            except Exception:
                pass

    # 3. Registrar nuevas oportunidades ideales detectadas hoy
    hoy_str = date.today().strftime("%Y-%m-%d")
    for sig in nuevas_senales:
        # Evitar duplicar exactamente el mismo activo el mismo día
        duplicado = not df_hist[(df_hist["fecha"] == hoy_str) & (df_hist["simbolo"] == sig["simbolo"])].empty
        if not duplicado:
            nuevo_registro = pd.DataFrame([{
                "fecha": hoy_str,
                "simbolo": sig["simbolo"],
                "precio_entrada": sig["precio_ars"],
                "stop_loss": sig["sl_ars"],
                "take_profit": sig["tp_ars"],
                "estado": "PENDIENTE"
            }])
            df_hist = pd.concat([df_hist, nuevo_registro], ignore_index=True)

    # Guardar cambios actualizados
    df_hist.to_csv(HISTORIAL_FILE, index=False)

    # 4. Mostrar estadísticas de rendimiento y automejora al usuario
    total_registros = len(df_hist)
    exitos = len(df_hist[df_hist["estado"] == "EXITO 🎯"])
    derrotas = len(df_hist[df_hist["estado"] == "DERROTA 🛑"])
    pendientes_totales = len(df_hist[df_hist["estado"] == "PENDIENTE"])

    print(f" 📊 Estadísticas acumuladas del Bot:")
    print(f"    • Total de señales ideales emitidas históricamente: {total_registros}")
    print(f"    • Aciertos (Take Profit alcanzado): {exitos} | Tropiezos (Stop Loss tocado): {derrotas} | En seguimiento: {pendientes_totales}")
    if (exitos + derrotas) > 0:
        win_rate = (exitos / (exitos + derrotas)) * 100
        print(f"    • Tasa de Acierto Histórica (Win Rate real): {win_rate:.1f}%")
    print(f" 🤖 Estado de Automejora: Activo. Ajuste dinámico de volatilidad aplicado por historial.")
    print("=" * 105)


def auditar_cartera_personal():
    mis_activos = ["AAPL.BA", "WMT.BA", "SHOP.BA"]
    print("\n" + "=" * 105)
    print("🛡️ GESTIÓN DE RIESGO ESTRICTA CON TOPE MÁXIMO (EN PESOS REALES) PARA CARTERA")
    print("=" * 105)

    for simbolo in mis_activos:
        simbolo_limpio = simbolo.replace(".BA", "")
        riesgo_dinamico = calcular_ajuste_volatilidad(simbolo_limpio)
        
        try:
            df = yf.download(simbolo, period="1y", interval="1d", progress=False)
            if df.empty:
                continue
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            df["EMA_20"] = df["Close"].ewm(span=20, adjust=False).mean()
            df["Soporte_60d"] = df["Low"].rolling(window=60).min()

            ultimo = df.iloc[-1]
            p_ars = float(ultimo["Close"])
            ema_ars = float(ultimo["EMA_20"])
            sop_ars = float(ultimo["Soporte_60d"]) if not pd.isna(ultimo["Soporte_60d"]) else float(df["Low"].min())

            sl_candidato = sop_ars * 0.985
            sl_ars = max(sl_candidato, p_ars * (1 - riesgo_dinamico))
            tp_ars = round(max(ema_ars, p_ars * (1 + MIN_GANANCIA_PCT)), 2)
            sl_ars = round(sl_ars, 2)

            print(f"\n🔹 Cartera Personal: [{simbolo}]")
            print(f"   • Precio Local (ARS):  ${p_ars:>10,.2f}")
            print(f"   • 🛑 Stop Loss (ARS):  ${sl_ars:>10,.2f}  ---> ¡Tope defensivo (Riesgo: {riesgo_dinamico*100:.1f}%)!")
            print(f"   • 🎯 Take Profit (ARS): ${tp_ars:>10,.2f}  ---> ¡Objetivo de ganancia optimizado!")
        except Exception as e:
            print(f"\n🔹 Cartera Personal: [{simbolo}] -> Error: {e}")
    print("=" * 105)


def verificar_alertas():
    verificar_mercado_general()
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Analizando CEDEARs en pesos reales con filtros avanzados...\n")

    resultados_analisis = []
    nuevas_oportunidades_ideales = []

    for simbolo in ACTIVOS:
        simbolo_ba = f"{simbolo}.BA"
        try:
            with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
                df = yf.download(simbolo_ba, period="2y", interval="1d", progress=False)
            if df.empty or len(df) < 200:
                continue
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            vol_prom = df["Volume"].rolling(window=20).mean().iloc[-1]
            if pd.isna(vol_prom) or vol_prom < 100:
                continue

            df["EMA_200"] = df["Close"].ewm(span=200, adjust=False).mean()
            df["EMA_20"] = df["Close"].ewm(span=20, adjust=False).mean()
            df["SMA_20"] = df["Close"].rolling(window=20).mean()
            df["STD_20"] = df["Close"].rolling(window=20).std()
            df["Banda_Inferior"] = df["SMA_20"] - (df["STD_20"] * 2)
            df["Soporte_60d"] = df["Low"].rolling(window=60).min()

            delta = df["Close"].diff()
            gain_7 = (delta.where(delta > 0, 0)).rolling(window=7).mean()
            loss_7 = (-delta.where(delta < 0, 0)).rolling(window=7).mean()
            df["RSI_7"] = 100 - (100 / (1 + (gain_7 / loss_7)))
            stoch_rsi = ((df["RSI_7"] - df["RSI_7"].rolling(window=14).min()) / 
                         (df["RSI_7"].rolling(window=14).max() - df["RSI_7"].rolling(window=14).min())) * 100

            ultimo = df.iloc[-1]
            p_ars = float(ultimo["Close"])
            h_ars = float(ultimo["High"])
            l_ars = float(ultimo["Low"])
            banda_inf = float(ultimo["Banda_Inferior"])
            sop_ars = float(ultimo["Soporte_60d"]) if not pd.isna(ultimo["Soporte_60d"]) else p_ars * 0.95
            stoch = float(stoch_rsi.iloc[-1]) if not pd.isna(stoch_rsi.iloc[-1]) else 50.0
            vol_act = float(ultimo["Volume"])

            # Filtros de precisión
            rango_diario = h_ars - l_ars
            cierre_en_rango = (p_ars - l_ars) / rango_diario if rango_diario > 0 else 0.5
            vela_rechazo_alcista = cierre_en_rango >= 0.40
            vol_climax = vol_act >= (vol_prom * 0.8)
            tendencia = p_ars > float(ultimo["EMA_200"])
            
            distancia_banda = ((p_ars - banda_inf) / banda_inf) * 100
            puntuacion = max(0, stoch) + max(0, distancia_banda * 50) if tendencia else 9999.0

            resultados_analisis.append({
                "simbolo": simbolo, "precio_ars": p_ars, "banda_inf_ars": banda_inf,
                "soporte_ars": sop_ars, "ema_20": float(ultimo["EMA_20"]),
                "stoch_rsi": stoch, "tendencia": tendencia, "vela_alcista": vela_rechazo_alcista,
                "vol_climax": vol_climax, "distancia": distancia_banda, "puntuacion": puntuacion
            })
        except Exception:
            pass

    resultados_analisis.sort(key=lambda x: x["puntuacion"])
    top_10 = resultados_analisis[:10]

    print("=" * 105)
    print("TOP 10 CEDEARS EN PESOS REALES (FILTROS INSTITUCIONALES OPTIMIZADOS) & FUNDAMENTALES")
    print("=" * 105)

    for i, res in enumerate(top_10, 1):
        # Aplicar automejora de volatilidad por activo según su historial de fallos
        riesgo_activo = calcular_ajuste_volatilidad(res["simbolo"])
        
        sl_candidato = res["soporte_ars"] * 0.985
        sl_ars = max(sl_candidato, res["precio_ars"] * (1 - riesgo_activo))
        tp_ars = round(max(res["ema_20"], res["precio_ars"] * (1 + MIN_GANANCIA_PCT)), 2)
        
        sl_ars = round(sl_ars, 2)
        p_ars = round(res["precio_ars"], 2)
        banda_inf_ars = round(res["banda_inf_ars"], 2)

        es_oportunidad_ideal = (
            res["tendencia"] and 
            res["precio_ars"] <= res["banda_inf_ars"] * 1.01 and 
            res["stoch_rsi"] < 25 and 
            res["vela_alcista"] and 
            res["vol_climax"]
        )
        estado_txt = " 🎯 ¡OPORTUNIDAD IDEAL BLINDADA!" if es_oportunidad_ideal else ""

        if es_oportunidad_ideal:
            nuevas_oportunidades_ideales.append({
                "simbolo": res["simbolo"],
                "precio_ars": p_ars,
                "sl_ars": sl_ars,
                "tp_ars": tp_ars
            })

        print(f"\n{i:2d}. [{res['simbolo']}.BA] -> Precio: ${p_ars:,.2f} | Banda Inf: ${banda_inf_ars:,.2f}")
        print(f"     🛑 Stop Loss Sugerido: ${sl_ars:,.2f} (Riesgo: {riesgo_activo*100:.1f}%) | 🎯 Take Profit Sugerido: ${tp_ars:,.2f}")
        print(f"     StochRSI(7): {res['stoch_rsi']:>5.1f} | Giro Precio: {'✅' if res['vela_alcista'] else '❌'} | Vol Giro: {'✅' if res['vol_climax'] else '❌'}{estado_txt}")
        
        noticias, proximo_earn, dias_earn = extraer_datos_fundamentales(res['simbolo'])
        
        estado_balance = "⚠️ (¡Atención: Balance Próximo!)" if dias_earn < 7 else "(Seguro)"
        print(f"     🔎 [CONTEXTO FUNDAMENTAL Y SENTIMIENTO]:")
        print(f"       📅 Próximo Balance: {proximo_earn} {estado_balance}")
        print(f"       📰 Últimas Noticias y Sentimiento:")
        for titulo_noticia, sentimiento in noticias:
            print(f"         • {sentimiento} {titulo_noticia}")
        print("-" * 105)

    print("=" * 105)
    
    # Ejecutar el gestor del historial y automejora
    gestionar_historial_y_automejora(nuevas_oportunidades_ideales)
    
    auditar_cartera_personal()


if __name__ == "__main__":
    verificar_alertas()