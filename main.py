from datetime import datetime
import os
import pandas as pd
import yfinance as yf

# Universo ampliado de CEDEARs, ETFs y Cripto-activos funcionales en BYMA (Cocos)
ACTIVOS = [
    "SPY.BA",
    "QQQ.BA",
    "DIA.BA",
    "IWM.BA",
    "ARKK.BA",
    "IBIT.BA",
    "ETHA.BA",
    "IEUR.BA",
    "EFA.BA",
    "VXX.BA",
    "XLY.BA",
    "XLB.BA",
    "XME.BA",
    "IJH.BA",
    "ICLN.BA",
    "ESGU.BA",
    "IVW.BA",
    "SPHQ.BA",
    "ACWI.BA",
    "IVE.BA",
    "CIBR.BA",
    "XLC.BA",
    "XLRE.BA",
    "IEMG.BA",
    "ILF.BA",
    "IBB.BA",
    "EWJ.BA",
    "ITA.BA",
    "URA.BA",
    "XLI.BA",
    "RSP.BA",
    "VEA.BA",
    "XLV.BA",
    "USO.BA",
    "SPXL.BA",
    "PSQ.BA",
    "XLK.BA",
    "VIG.BA",
    "FXI.BA",
    "IVV.BA",
    "EWZ.BA",
    "GLD.BA",
    "SLV.BA",
    "COPX.BA",
    "SMH.BA",
    "GDX.BA",
    "XLE.BA",
    "XLP.BA",
    "EEM.BA",
    "XLF.BA",
    "XLU.BA",
    "TQQQ.BA",
    "EWY.BA",
    "SH.BA",
    "MSTR.BA",
    "HUT.BA",
    "COIN.BA",
    "KEEL.BA",
    "RIOT.BA",
    "AAPL.BA",
    "MSFT.BA",
    "MELI.BA",
    "GOOGL.BA",
    "NVDA.BA",
    "AMZN.BA",
    "TSLA.BA",
    "NFLX.BA",
    "AMD.BA",
    "INTC.BA",
    "QCOM.BA",
    "IBM.BA",
    "ORCL.BA",
    "ADBE.BA",
    "CRM.BA",
    "PYPL.BA",
    "UBER.BA",
    "ABNB.BA",
    "ASML.BA",
    "PLTR.BA",
    "MRVL.BA",
    "SPOT.BA",
    "EBAY.BA",
    "PANW.BA",
    "BRKB.BA",
    "JPM.BA",
    "C.BA",
    "GS.BA",
    "WFC.BA",
    "AXP.BA",
    "NU.BA",
    "STNE.BA",
    "BBD.BA",
    "KO.BA",
    "PEP.BA",
    "WMT.BA",
    "MCD.BA",
    "NKE.BA",
    "PG.BA",
    "DISN.BA",
    "TGT.BA",
    "ABEV.BA",
    "ARCO.BA",
    "JNJ.BA",
    "PFE.BA",
    "MRNA.BA",
    "ABBV.BA",
    "AMGN.BA",
    "ABT.BA",
    "XOM.BA",
    "CVX.BA",
    "VALE.BA",
    "RIO.BA",
    "KGC.BA",
    "MUX.BA",
    "PKS.BA",
    "SID.BA",
    "CAT.BA",
    "DE.BA",
    "GE.BA",
    "TM.BA",
    "F.BA",
    "LMT.BA",
    "RTX.BA",
    "EMBJ.BA",
    "NOKA.BA",
    "CSCO.BA",
    "MDT.BA",
    "SPGI.BA",
    "ADGO.BA",
    "GLOB.BA",
    "DECK.BA",
    "SYY.BA",
    "XROX.BA",
    "AAP.BA",
    "SONY.BA",
    "CAR.BA",
    "NUE.BA",
    "MSI.BA",
    "JD.BA",
    "UPST.BA",
    "MO.BA",
    "ADI.BA",
    "OXY.BA",
    "TMUS.BA",
    "TSM.BA",
    "BABA.BA",
    "T.BA",
    "MU.BA",
    "V.BA",
    "TXR.BA",
    "LAC.BA",
    "LLY.BA",
    "AMAT.BA",
    "SATL.BA",
    "CLS.BA",
    "RBLX.BA",
    "CCL.BA",
]

ACTIVOS = list(dict.fromkeys(ACTIVOS))
ARCHIVO_LOG = "oportunidades.csv"


def verificar_mercado_general():
    """Filtro 2: Contexto de Mercado (Regime Filter con SPY.BA)"""
    try:
        df_spy = yf.download("SPY.BA", period="1y", interval="1d", progress=False)
        if not df_spy.empty:
            if isinstance(df_spy.columns, pd.MultiIndex):
                df_spy.columns = df_spy.columns.get_level_values(0)
            df_spy["EMA_200"] = df_spy["Close"].ewm(span=200, adjust=False).mean()
            ultimo_spy = df_spy.iloc[-1]
            if ultimo_spy["Close"] < ultimo_spy["EMA_200"]:
                print(
                    "\n⚠️ [ALERTA MACRO] El S&P 500 (SPY.BA) está por debajo de su EMA 200. Mercado bajista general: operar rebotes con cautela extra."
                )
            else:
                print(
                    "\n✅ [ESTADO MACRO] El S&P 500 (SPY.BA) está alcista (Precio > EMA 200). Entorno favorable para rebotes."
                )
    except Exception as e:
        print(f"No se pudo verificar el contexto de mercado general: {e}")


def obtener_ticker_original(simbolo_ba):
    return simbolo_ba.replace(".BA", "")


def analizar_sentimiento_noticia(titulo):
    """Clasifica de forma rápida y eficiente el sentimiento de una noticia financiera."""
    titulo_lower = titulo.lower()

    palabras_positivas = [
        "best", "buy", "growth", "rebound", "gain", "up", "bull", "boost",
        "high", "upgrade", "profit", "beat", "positive", "strong", "surge"
    ]
    palabras_negativas = [
        "down", "fall", "slip", "drop", "blacklist", "bear", "loss", "miss",
        "inflation", "war", "risk", "cut", "warning", "crash", "negative"
    ]

    score = 0
    for palabra in palabras_positivas:
        if palabra in titulo_lower:
            score += 1
    for palabra in palabras_negativas:
        if palabra in titulo_lower:
            score -= 1

    if score > 0:
        return "🟢 [Positivo]"
    elif score < 0:
        return "🔴 [Negativo]"
    else:
        return "⚪ [Neutral]"


def extraer_datos_fundamentales(simbolo_ba):
    """Extrae noticias, calcula sentimiento y obtiene próximos earnings manejando excepciones de ETFs."""
    ticker_original = obtener_ticker_original(simbolo_ba)
    ticker_yf = yf.Ticker(ticker_original)
    
    noticias_con_sentimiento = []
    try:
        news = ticker_yf.news
        if news:
            for item in news[:2]:
                titulo = item.get("title") or item.get("content", {}).get("title", "Sin título")
                sentimiento = analizar_sentimiento_noticia(titulo)
                noticias_con_sentimiento.append((titulo, sentimiento))
    except Exception:
        pass

    if not noticias_con_sentimiento:
        noticias_con_sentimiento.append(("Sin noticias destacadas en el feed actual.", "⚪ [Neutral]"))

    proximo_earnings = "No disponible (ETF o N/D)"
    try:
        cal = ticker_yf.calendar
        if cal is not None:
            if isinstance(cal, dict) and "Earnings Date" in cal:
                edates = cal["Earnings Date"]
                if edates:
                    proximo_earnings = str(edates[0]).split("T")[0]
            elif isinstance(cal, pd.DataFrame) and not cal.empty:
                proximo_earnings = str(cal.index[0]).split("T")[0]
    except Exception:
        pass

    return noticias_con_sentimiento, proximo_earnings


def auditar_rendimiento_alertas():
    """Audita el Win Rate histórico de las alertas guardadas en el CSV a un horizonte de 5 ruedas."""
    if not os.path.exists(ARCHIVO_LOG):
        print("\n📊 [AUDITORÍA DE WIN RATE] No hay historial de alertas previo ('oportunidades.csv').")
        return

    try:
        # Agregamos on_bad_lines='skip' para evitar errores si el CSV tiene formatos viejos
        df_log = pd.read_csv(ARCHIVO_LOG, on_bad_lines='skip')
        if df_log.empty or "Fecha_Hora" not in df_log.columns or "Activo" not in df_log.columns:
            return

        print("\n" + "=" * 95)
        print("📊 AUDITORÍA HISTÓRICA DE SEÑALES (WIN RATE A 5 RUEDAS)")
        print("=" * 95)

        total_alertas = len(df_log)
        exitos = 0
        evaluadas = 0
        detalles_resultados = []

        for _, row in df_log.iterrows():
            simbolo = row["Activo"]
            precio_entrada = float(row["Precio"])
            
            try:
                fecha_str = str(row["Fecha_Hora"]).split(" ")[0]
            except Exception:
                continue

            # Descargar historial desde la fecha de la alerta hasta la fecha actual
            hoy = datetime.now().strftime("%Y-%m-%d")
            df_hist = yf.download(simbolo, start=fecha_str, end=hoy, progress=False)

            if df_hist.empty or len(df_hist) <= 1:
                continue

            if isinstance(df_hist.columns, pd.MultiIndex):
                df_hist.columns = df_hist.columns.get_level_values(0)

            # Tomar hasta las 5 ruedas posteriores a la alerta
            df_futuro = df_hist.iloc[1:6]
            if df_futuro.empty:
                continue

            evaluadas += 1
            precio_max_futuro = float(df_futuro["High"].max())
            rendimiento_max = ((precio_max_futuro - precio_entrada) / precio_entrada) * 100
            
            if precio_max_futuro > precio_entrada:
                exitos += 1
                estado = "✅ WIN"
            else:
                estado = "❌ LOSS"

            detalles_resultados.append({
                "Fecha": fecha_str,
                "Activo": simbolo,
                "Entrada": precio_entrada,
                "Max_Alcanzado": precio_max_futuro,
                "Retorno_Max": rendimiento_max,
                "Estado": estado
            })

        if evaluadas > 0:
            win_rate = (exitos / evaluadas) * 100
            print(f"🔹 Total de Alertas Registradas en Historial: {total_alertas}")
            print(f"🔹 Alertas Evaluables (+5 ruedas transcurridas): {evaluadas}")
            print(f"🔹 Operaciones Exitosas (Win): {exitos}")
            print(f"🎯 WIN RATE GLOBAL DE LA ESTRATEGIA: {win_rate:.2f}%\n")
            
            print("📋 Detalle de las últimas alertas auditadas:")
            for res in detalles_resultados[-5:]:
                print(f"   • [{res['Fecha']}] {res['Activo']} | Entrada: ${res['Entrada']:>8.2f} | Máx post: ${res['Max_Alcanzado']:>8.2f} | Retorno: {res['Retorno_Max']:>+.2f}% | {res['Estado']}")
        else:
            print("ℹ️ [INFO] Las alertas registradas son muy recientes y aún no completaron el ciclo de 5 ruedas para evaluar.")
        print("=" * 95)

    except Exception as e:
        print(f"No se pudo completar la auditoría de rendimiento: {e}")


def verificar_alertas():
    verificar_mercado_general()
    print(
        f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Analizando cartera masiva de {len(ACTIVOS)} activos..."
    )

    resultados_analisis = []
    nuevas_oportunidades = []

    for simbolo in ACTIVOS:
        try:
            df = yf.download(simbolo, period="2y", interval="1d", progress=False)

            if df.empty or len(df) < 200:
                continue

            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            volumen_promedio_20 = df["Volume"].rolling(window=20).mean().iloc[-1]
            if pd.isna(volumen_promedio_20) or volumen_promedio_20 < 200:
                continue

            # --- INDICADORES TÉCNICOS ---
            df["EMA_200"] = df["Close"].ewm(span=200, adjust=False).mean()
            df["EMA_20"] = df["Close"].ewm(span=20, adjust=False).mean()
            df["SMA_20"] = df["Close"].rolling(window=20).mean()
            df["STD_20"] = df["Close"].rolling(window=20).std()
            df["Banda_Inferior"] = df["SMA_20"] - (df["STD_20"] * 2)

            delta = df["Close"].diff()
            gain_7 = (delta.where(delta > 0, 0)).rolling(window=7).mean()
            loss_7 = (-delta.where(delta < 0, 0)).rolling(window=7).mean()
            rs_7 = gain_7 / loss_7
            df["RSI_7"] = 100 - (100 / (1 + rs_7))

            min_rsi7 = df["RSI_7"].rolling(window=14).min()
            max_rsi7 = df["RSI_7"].rolling(window=14).max()
            df["StochRSI_K"] = ((df["RSI_7"] - min_rsi7) / (max_rsi7 - min_rsi7)) * 100

            ultimo = df.iloc[-1]
            precio_actual = float(ultimo["Close"])
            ema_200 = float(ultimo["EMA_200"])
            ema_20 = float(ultimo["EMA_20"])
            banda_inf = float(ultimo["Banda_Inferior"])
            stoch_rsi = float(ultimo["StochRSI_K"])
            rsi_7 = float(ultimo["RSI_7"])
            volumen_actual = float(ultimo["Volume"])

            distancia_banda_pct = ((precio_actual - banda_inf) / banda_inf) * 100
            tendencia_alcista = precio_actual > ema_200
            volumen_exhausto = volumen_actual < volumen_promedio_20

            if tendencia_alcista:
                puntuacion_cercania = max(0, stoch_rsi) + max(0, distancia_banda_pct * 5)
                if volumen_exhausto:
                    puntuacion_cercania *= 0.9
            else:
                puntuacion_cercania = 9999.0

            resultados_analisis.append({
                "simbolo": simbolo,
                "precio": precio_actual,
                "banda_inf": banda_inf,
                "ema_200": ema_200,
                "ema_20": ema_20,
                "stoch_rsi": stoch_rsi,
                "rsi_7": rsi_7,
                "distancia_pct": distancia_banda_pct,
                "tendencia_alcista": tendencia_alcista,
                "volumen_exhausto": volumen_exhausto,
                "puntuacion": puntuacion_cercania,
            })

            if (
                tendencia_alcista
                and precio_actual <= banda_inf
                and stoch_rsi < 25
                and volumen_exhausto
            ):
                registro = {
                    "Fecha_Hora": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "Activo": simbolo,
                    "Precio": round(precio_actual, 2),
                    "Banda_Inferior": round(banda_inf, 2),
                    "EMA_200": round(ema_200, 2),
                    "EMA_20": round(ema_20, 2),
                    "Stoch_RSI_7": round(stoch_rsi, 2),
                    "RSI_7": round(rsi_7, 2),
                    "Estrategia": "Pullback Corto Plazo (Bollinger + StochRSI(7) + Vol Exhausto)",
                }
                nuevas_oportunidades.append(registro)

        except Exception:
            pass

    resultados_analisis.sort(key=lambda x: x["puntuacion"])
    top_10 = resultados_analisis[:10]

    print("\n" + "=" * 95)
    print(" TOP 10 RANKING DE CERCANÍA A OPORTUNIDAD DE COMPRA + SENTIMIENTO Y FUNDAMENTALES")
    print("=" * 95)

    for i, res in enumerate(top_10, 1):
        estado_alerta = " "
        vol_tag = "📊 Vol. Normal" if not res["volumen_exhausto"] else "📉 Vol. Exhausto (Ideal)"

        if (
            res["tendencia_alcista"]
            and res["precio"] <= res["banda_inf"]
            and res["stoch_rsi"] < 25
            and res["volumen_exhausto"]
        ):
            estado_alerta = " 🎯 ¡OPORTUNIDAD IDEAL!"
        elif res["tendencia_alcista"] and res["precio"] <= res["banda_inf"] and res["stoch_rsi"] < 25:
            estado_alerta = " ⚠️ Cerca, Vol Alto"
        elif not res["tendencia_alcista"]:
            estado_alerta = " ⚠️ Tendencia Bajista"

        print(
            f"\n{i:2d}. [{res['simbolo']}] -> Precio: ${res['precio']:>8.2f} | Banda Inf: ${res['banda_inf']:>8.2f}"
            f"\n    StochRSI(7): {res['stoch_rsi']:>5.1f} | Dist: {res['distancia_pct']:>+.2f}% | {vol_tag}{estado_alerta}"
        )

        print("    🔍 [CONTEXTO FUNDAMENTAL Y SENTIMIENTO]:")
        noticias, proximo_earnings = extraer_datos_fundamentales(res["simbolo"])
        print(f"       📅 Próximo Balance (Earnings): {proximo_earnings}")
        print("       📰 Últimas Noticias Relevantes y Sentimiento:")
        for titulo, sentimiento in noticias:
            print(f"          • {sentimiento} {titulo}")
        print("-" * 95)

    print("=" * 95)

    if nuevas_oportunidades:
        df_nuevos = pd.DataFrame(nuevas_oportunidades)
        if os.path.exists(ARCHIVO_LOG):
            df_nuevos.to_csv(ARCHIVO_LOG, mode="a", header=False, index=False)
        else:
            df_nuevos.to_csv(ARCHIVO_LOG, index=False)
        print(
            f"\n[ÉXITO] Se guardaron {len(nuevas_oportunidades)} alertas de alta calidad en '{ARCHIVO_LOG}'."
        )
    else:
        print("\n[INFO] Ningún activo cumplió todos los filtros estrictos en este ciclo.")

    # Ejecutar la auditoría histórica de Win Rate al finalizar el escaneo
    auditar_rendimiento_alertas()


if __name__ == "__main__":
    verificar_alertas()