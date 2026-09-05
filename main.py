from datetime import datetime, date
import os
import pandas as pd
import yfinance as yf
import contextlib
import io

# Universo ampliado de CEDEARs, ETFs y Cripto-activos funcionales en BYMA (Cocos)
ACTIVOS = [
    "SPY.BA", "QQQ.BA", "DIA.BA", "IWM.BA", "ARKK.BA", "IBIT.BA", "ETHA.BA",
    "IEUR.BA", "EFA.BA", "VXX.BA", "XLY.BA", "XLB.BA", "XME.BA", "IJH.BA",
    "ICLN.BA", "ESGU.BA", "IVW.BA", "SPHQ.BA", "ACWI.BA", "IVE.BA", "CIBR.BA",
    "XLC.BA", "XLRE.BA", "IEMG.BA", "ILF.BA", "IBB.BA", "EWJ.BA", "ITA.BA",
    "URA.BA", "XLI.BA", "RSP.BA", "VEA.BA", "XLV.BA", "USO.BA", "SPXL.BA",
    "PSQ.BA", "XLK.BA", "VIG.BA", "FXI.BA", "IVV.BA", "EWZ.BA", "GLD.BA",
    "SLV.BA", "COPX.BA", "SMH.BA", "GDX.BA", "XLE.BA", "XLP.BA", "EEM.BA",
    "XLF.BA", "XLU.BA", "TQQQ.BA", "EWY.BA", "SH.BA", "MSTR.BA", "HUT.BA",
    "COIN.BA", "KEEL.BA", "RIOT.BA", "AAPL.BA", "MSFT.BA", "MELI.BA", "GOOGL.BA",
    "NVDA.BA", "AMZN.BA", "TSLA.BA", "NFLX.BA", "AMD.BA", "INTC.BA", "QCOM.BA",
    "IBM.BA", "ORCL.BA", "ADBE.BA", "CRM.BA", "PYPL.BA", "UBER.BA", "ABNB.BA",
    "ASML.BA", "PLTR.BA", "MRVL.BA", "SPOT.BA", "EBAY.BA", "PANW.BA", "BRKB.BA",
    "JPM.BA", "C.BA", "GS.BA", "WFC.BA", "AXP.BA", "NU.BA", "STNE.BA", "BBD.BA",
    "KO.BA", "PEP.BA", "WMT.BA", "MCD.BA", "NKE.BA", "PG.BA", "DISN.BA",
    "TGT.BA", "ABEV.BA", "ARCO.BA", "JNJ.BA", "PFE.BA", "MRNA.BA", "ABBV.BA",
    "AMGN.BA", "ABT.BA", "XOM.BA", "CVX.BA", "VALE.BA", "RIO.BA", "KGC.BA",
    "MUX.BA", "PKS.BA", "SID.BA", "CAT.BA", "DE.BA", "GE.BA", "TM.BA", "F.BA",
    "LMT.BA", "RTX.BA", "EMBJ.BA", "NOKA.BA", "CSCO.BA", "MDT.BA", "SPGI.BA",
    "ADGO.BA", "GLOB.BA", "DECK.BA", "SYY.BA", "XROX.BA", "AAP.BA", "SONY.BA",
    "CAR.BA", "NUE.BA", "MSI.BA", "JD.BA", "UPST.BA", "MO.BA", "ADI.BA",
    "OXY.BA", "TMUS.BA", "TSM.BA", "BABA.BA", "T.BA", "MU.BA", "V.BA", "TXR.BA",
    "LAC.BA", "LLY.BA", "AMAT.BA", "SATL.BA", "CLS.BA", "RBLX.BA", "CCL.BA"
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
                print("\n⚠️ [ALERTA MACRO] El S&P 500 (SPY.BA) está por debajo de su EMA 200. Mercado bajista general: operar rebotes con cautela extra.")
            else:
                print("\n✅ [ESTADO MACRO] El S&P 500 (SPY.BA) está alcista (Precio > EMA 200). Entorno favorable para rebotes.")
    except Exception as e:
        print(f"No se pudo verificar el contexto de mercado general: {e}")


def obtener_ticker_original(simbolo_ba):
    return simbolo_ba.replace(".BA", "")


def analizar_sentimiento_noticia(titulo):
    """Clasifica el sentimiento de una noticia financiera."""
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
    """Extrae noticias, calcula sentimiento y obtiene la fecha exacta del próximo balance."""
    ticker_original = obtener_ticker_original(simbolo_ba)
    ticker_yf = yf.Ticker(ticker_original)
    
    noticias_con_sentimiento = []
    try:
        with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
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
    dias_para_earnings = 999  # Por defecto un número alto si es ETF o no hay datos

    try:
        with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
            cal = ticker_yf.calendar
            
        edates = None
        if cal is not None:
            if isinstance(cal, dict) and "Earnings Date" in cal:
                edates = cal["Earnings Date"]
            elif isinstance(cal, pd.DataFrame) and not cal.empty:
                edates = cal.index.tolist()

            if edates:
                fecha_ing = pd.to_datetime(edates[0]).date()
                proximo_earnings = str(fecha_ing)
                dias_para_earnings = (fecha_ing - date.today()).days
    except Exception:
        pass

    return noticias_con_sentimiento, proximo_earnings, dias_para_earnings


def auditar_rendimiento_alertas():
    """Audita el Win Rate histórico de las alertas guardadas en el CSV."""
    if not os.path.exists(ARCHIVO_LOG):
        print("\n📊 [AUDITORÍA DE WIN RATE] No hay historial de alertas previo ('oportunidades.csv').")
        return

    try:
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
        hoy = datetime.now().strftime("%Y-%m-%d")

        for _, row in df_log.iterrows():
            simbolo = row["Activo"]
            precio_entrada = float(row["Precio"])
            
            try:
                fecha_str = str(row["Fecha_Hora"]).split(" ")[0]
            except Exception:
                continue

            if fecha_str == hoy:
                continue

            df_hist = yf.download(simbolo, start=fecha_str, end=hoy, progress=False)
            if df_hist.empty or len(df_hist) <= 1:
                continue

            if isinstance(df_hist.columns, pd.MultiIndex):
                df_hist.columns = df_hist.columns.get_level_values(0)

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
            print(f"🔹 Total de Alertas Registradas: {total_alertas} | Evaluables: {evaluadas} | Exitosas: {exitos}")
            print(f"🎯 WIN RATE GLOBAL DE LA ESTRATEGIA: {win_rate:.2f}%\n")
            
            print("📋 Detalle de las últimas alertas auditadas:")
            for res in detalles_resultados[-5:]:
                print(f"   • [{res['Fecha']}] {res['Activo']} | Entrada: ${res['Entrada']:>8.2f} | Máx: ${res['Max_Alcanzado']:>8.2f} | Retorno: {res['Retorno_Max']:>+.2f}% | {res['Estado']}")
        else:
            print("ℹ️ [INFO] Las alertas son muy recientes y aún no completaron el ciclo de 5 ruedas.")
        print("=" * 95)

    except Exception as e:
        print(f"No se pudo completar la auditoría de rendimiento: {e}")


def auditar_cartera_personal():
    """Aplica la gestión de riesgo del bot a tu cartera actual (AAPL, Walmart, Shopify) con manejo de datos escasos."""
    mis_activos = ["AAPL.BA", "WMT.BA", "SHOP.BA"]
    
    print("\n" + "=" * 95)
    print("🛡️ GESTIÓN DE RIESGO BLINDADA PARA TU CARTERA ACTUAL (STOP LOSS / TAKE PROFIT)")
    print("=" * 95)

    for simbolo in mis_activos:
        try:
            df = yf.download(simbolo, period="1y", interval="1d", progress=False)
            if df.empty:
                print(f"\n🔹 Activo: {simbolo} -> ⚠️ No se pudieron obtener datos de yfinance.")
                continue

            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            df["EMA_20"] = df["Close"].ewm(span=20, adjust=False).mean()
            df["Soporte_60d"] = df["Low"].rolling(window=60).min()

            ultimo = df.iloc[-1]
            precio_actual = float(ultimo["Close"])
            ema_20 = float(ultimo["EMA_20"])
            
            # Blindaje por si el activo tiene menos de 60 ruedas de historia
            soporte_60d = float(ultimo["Soporte_60d"]) if not pd.isna(ultimo["Soporte_60d"]) else float(df["Low"].min())

            stop_loss = round(soporte_60d * 0.99, 2)
            take_profit = round(ema_20, 2)

            print(f"\n🔹 Activo: {simbolo}")
            print(f"   • Precio de Mercado:         ${precio_actual:>8.2f}")
            print(f"   • 🛑 Stop Loss (Estructural):  ${stop_loss:>8.2f}  ---> ¡Línea roja inquebrantable del sistema!")
            print(f"   • 🎯 Take Profit (EMA 20):     ${take_profit:>8.2f}  ---> ¡Objetivo técnico de salida!")
        except Exception as e:
            print(f"\n🔹 Activo: {simbolo} -> ⚠️ Error procesando datos: {e}")
            
    print("=" * 95)


def verificar_alertas():
    verificar_mercado_general()
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Analizando cartera masiva de {len(ACTIVOS)} activos con blindaje institucional...")

    resultados_analisis = []
    nuevas_oportunidades = []

    for simbolo in ACTIVOS:
        try:
            df = yf.download(simbolo, period="2y", interval="1d", progress=False)

            if df.empty or len(df) < 200:
                continue

            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            # Filtro de liquidez optimizado (volumen mínimo de 300 ruedas)
            volumen_promedio_20 = df["Volume"].rolling(window=20).mean().iloc[-1]
            if pd.isna(volumen_promedio_20) or volumen_promedio_20 < 300:
                continue

            # --- INDICADORES TÉCNICOS ---
            df["EMA_200"] = df["Close"].ewm(span=200, adjust=False).mean()
            df["EMA_20"] = df["Close"].ewm(span=20, adjust=False).mean()
            df["SMA_20"] = df["Close"].rolling(window=20).mean()
            df["STD_20"] = df["Close"].rolling(window=20).std()
            df["Banda_Inferior"] = df["SMA_20"] - (df["STD_20"] * 2)

            # Soporte estructural de mediano plazo (Mínimo de las últimas 60 ruedas)
            df["Soporte_60d"] = df["Low"].rolling(window=60).min()

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
            soporte_60d = float(ultimo["Soporte_60d"])
            stoch_rsi = float(ultimo["StochRSI_K"])
            rsi_7 = float(ultimo["RSI_7"])
            volumen_actual = float(ultimo["Volume"])

            distancia_banda_pct = ((precio_actual - banda_inf) / banda_inf) * 100
            tendencia_alcista = precio_actual > ema_200
            volumen_exhausto = volumen_actual < volumen_promedio_20
            cumple_soporte_estructural = precio_actual <= (soporte_60d * 1.025)

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
                "soporte_60d": soporte_60d,
                "ema_200": ema_200,
                "ema_20": ema_20,
                "stoch_rsi": stoch_rsi,
                "rsi_7": rsi_7,
                "distancia_pct": distancia_banda_pct,
                "tendencia_alcista": tendencia_alcista,
                "volumen_exhausto": volumen_exhausto,
                "cumple_soporte": cumple_soporte_estructural,
                "puntuacion": puntuacion_cercania,
            })

            # Disparo preliminar de alerta base
            if tendencia_alcista and precio_actual <= banda_inf and stoch_rsi < 25 and volumen_exhausto:
                _, _, dias_para_earnings = extraer_datos_fundamentales(simbolo)
                
                # REGLA BLINDADA ANTI-EARNINGS: Si hay balance en los próximos 7 días, se descarta la alerta
                if dias_para_earnings >= 7:
                    stop_loss = round(soporte_60d * 0.99, 2)  # 1% debajo del soporte estructural
                    take_profit = round(ema_20, 2)            # Objetivo inicial en la media móvil de 20 ruedas

                    registro = {
                        "Fecha_Hora": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "Activo": simbolo,
                        "Precio": round(precio_actual, 2),
                        "Stop_Loss": stop_loss,
                        "Take_Profit": take_profit,
                        "Banda_Inferior": round(banda_inf, 2),
                        "Soporte_60d": round(soporte_60d, 2),
                        "Stoch_RSI_7": round(stoch_rsi, 2),
                        "Estrategia": "Pullback Blindado (Bollinger + StochRSI + Stop Loss Estructural)",
                    }
                    nuevas_oportunidades.append(registro)

        except Exception:
            pass

    resultados_analisis.sort(key=lambda x: x["puntuacion"])
    top_10 = resultados_analisis[:10]

    print("\n" + "=" * 95)
    print(" TOP 10 RANKING DE CERCANÍA + GESTIÓN DE RIESGO (STOP LOSS / TAKE PROFIT) & FUNDAMENTALES")
    print("=" * 95)

    for i, res in enumerate(top_10, 1):
        estado_alerta = " "
        vol_tag = "📊 Vol. Normal" if not res["volumen_exhausto"] else "📉 Vol. Exhausto (Ideal)"
        tag_soporte = " 🛡️ [Soporte 60d OK]" if res["cumple_soporte"] else ""

        sl_sugerido = round(res["soporte_60d"] * 0.99, 2)
        tp_sugerido = round(res["ema_20"], 2)

        if res["tendencia_alcista"] and res["precio"] <= res["banda_inf"] and res["stoch_rsi"] < 25 and res["volumen_exhausto"]:
            estado_alerta = " 🎯 ¡OPORTUNIDAD IDEAL BLINDADA!"
        elif res["tendencia_alcista"] and res["precio"] <= res["banda_inf"] and res["stoch_rsi"] < 25:
            estado_alerta = " ⚠️ Cerca, Vol Alto"
        elif not res["tendencia_alcista"]:
            estado_alerta = " ⚠️ Tendencia Bajista"

        print(f"\n{i:2d}. [{res['simbolo']}] -> Precio: ${res['precio']:>8.2f} | Banda Inf: ${res['banda_inf']:>8.2f}"
              f"\n    🛑 Stop Loss Sugerido: ${sl_sugerido:>8.2f} | 🎯 Take Profit Sugerido: ${tp_sugerido:>8.2f}"
              f"\n    StochRSI(7): {res['stoch_rsi']:>5.1f} | Dist: {res['distancia_pct']:>+.2f}% | {vol_tag}{estado_alerta}{tag_soporte}")

        print("    🔍 [CONTEXTO FUNDAMENTAL Y SENTIMIENTO]:")
        noticias, proximo_earnings, dias_earn = extraer_datos_fundamentales(res["simbolo"])
        aviso_earn = f" (⚠️ ¡Atención! Balance en {dias_earn} días)" if dias_earn < 7 and dias_earn != 999 else " (Seguro)"
        print(f"       📅 Próximo Balance: {proximo_earnings}{aviso_earn}")
        print("       📰 Últimas Noticias y Sentimiento:")
        for titulo, sentimiento in noticias:
            print(f"         • {sentimiento} {titulo}")
        print("-" * 95)

    print("=" * 95)

    if nuevas_oportunidades:
        df_nuevos = pd.DataFrame(nuevas_oportunidades)
        if os.path.exists(ARCHIVO_LOG):
            df_nuevos.to_csv(ARCHIVO_LOG, mode="a", header=False, index=False)
        else:
            df_nuevos.to_csv(ARCHIVO_LOG, index=False)
        print(f"\n[ÉXITO] Se guardaron {len(nuevas_oportunidades)} alertas blindadas con Stop Loss en '{ARCHIVO_LOG}'.")
    else:
        print("\n[INFO] Ningún activo cumplió todos los filtros estrictos y de seguridad en este ciclo.")

    auditar_rendimiento_alertas()
    auditar_cartera_personal()


if __name__ == "__main__":
    verificar_alertas()