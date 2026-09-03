import yfinance as yf
import pandas as pd
from datetime import datetime
import os

# Universo optimizado de CEDEARs y ETFs funcionales en BYMA
ACTIVOS = [
    # --- ETFs Globales ---
    "SPY.BA",  # S&P 500
    "QQQ.BA",  # Nasdaq 100
    "DIA.BA",  # Dow Jones
    "IWM.BA",  # Russell 2000 (Small Caps)
    "ARKK.BA", # Ark Innovation

    # --- Gigantes Tecnológicos / Crecimiento ---
    "AAPL.BA", # Apple
    "MSFT.BA", # Microsoft
    "MELI.BA", # Mercado Libre
    "GOOGL.BA",# Google (Alphabet)
    "NVDA.BA", # Nvidia
    "AMZN.BA", # Amazon
    "TSLA.BA", # Tesla
    "NFLX.BA", # Netflix
    "AMD.BA",  # AMD
    "INTC.BA", # Intel
    "QCOM.BA", # Qualcomm
    "IBM.BA",  # IBM
    "ORCL.BA", # Oracle
    "ADBE.BA", # Adobe
    "CRM.BA",  # Salesforce
    "PYPL.BA", # PayPal
    "UBER.BA", # Uber
    "ABNB.BA", # Airbnb
    "ASML.BA", # ASML Holding
    "PLTR.BA", # Palantir Technologies
    "MRVL.BA", # Marvell Technology
    "SPOT.BA", # Spotify
    "EBAY.BA", # Ebay
    "PANW.BA", # Palo Alto Networks

    # --- Sector Financiero y Conglomerados ---
    "BRKB.BA", # Berkshire Hathaway
    "JPM.BA",  # JPMorgan Chase
    "C.BA",    # Citigroup
    "GS.BA",   # Goldman Sachs
    "WFC.BA",  # Wells Fargo
    "AXP.BA",  # American Express
    "NU.BA",   # Nu Bank
    "STNE.BA", # StoneCo
    "BBD.BA",  # Banco Bradesco

    # --- Consumo Masivo y Retail ---
    "KO.BA",   # Coca-Cola
    "PEP.BA",  # Pepsico
    "WMT.BA",  # Walmart
    "MCD.BA",  # McDonalds
    "NKE.BA",  # Nike
    "PG.BA",   # Procter & Gamble
    "DISN.BA", # Disney
    "TGT.BA",  # Target
    "ABEV.BA", # ADR Ambev
    "ARCO.BA", # Arcos Dorados

    # --- Salud y Farmacéuticas ---
    "JNJ.BA",  # Johnson & Johnson
    "PFE.BA",  # Pfizer
    "MRNA.BA", # Moderna
    "ABBV.BA", # AbbVie
    "AMGN.BA", # Amgen
    "ABT.BA",  # Abbott

    # --- Energía, Petróleo y Minería ---
    "XOM.BA",  # Exxon Mobil
    "CVX.BA",  # Chevron
    "VALE.BA", # Vale
    "RIO.BA",  # Rio Tinto
    "KGC.BA",  # Kinross Gold
    "MUX.BA",  # McEwen
    "PKS.BA",  # Posco
    "SID.BA",  # Cia. Siderurgica Nacional

    # --- Industria, Autos y Aeroespacial ---
    "CAT.BA",  # Caterpillar
    "DE.BA",   # Deere
    "GE.BA",   # General Electric
    "TM.BA",   # Toyota Motors
    "F.BA",    # Ford
    "LMT.BA",  # Lockheed Martin
    "RTX.BA",  # Raytheon
    "EMBJ.BA", # Embraer
    "NOKA.BA", # Nokia
    "CSCO.BA", # Cisco Systems
    "MDT.BA",  # Medtronic
    "SPGI.BA", # Standard & Poor's
    "ADGO.BA", # Adecoagro
    "GLOB.BA", # Globant
    "DECK.BA", # Deckers Outdoor Corporation
    "SYY.BA",  # Sysco
    "XROX.BA", # Xerox
    "AAP.BA",  # Advance Auto Parts
    "SONY.BA", # Sony
    "CAR.BA",  # Avis Budget Group
    "NUE.BA",  # Nucor
    "MSI.BA",  # Motorola
    "JD.BA",   # Jingdong (JD.com)
    "UPST.BA", # Upstart
    "MO.BA",   # Altria
    "ADI.BA",  # Analog Devices
    "OXY.BA",  # Occidental Petroleum Corp
    "TMUS.BA", # T-Mobile US Inc.
    "TSM.BA",  # Taiwan Semiconductor
    "BABA.BA", # Alibaba
    "T.BA",    # AT&T
    "MU.BA",   # Micron Technology
    "V.BA",    # Visa
    "TXR.BA",  # Ternium
    "LAC.BA",  # Lithium Americas
    "LLY.BA",  # Eli Lilly & Co
    "AMAT.BA", # Applied Materials
    "SATL.BA", # Satellogic
    "CLS.BA",  # Celestica
    "RBLX.BA", # Roblox Corp
    "CCL.BA"   # Carnival Corp
]

ARCHIVO_LOG = "oportunidades.csv"

def verificar_mercado_general():
    """Filtro 2: Contexto de Mercado (Regime Filter con SPY.BA)"""
    try:
        df_spy = yf.download("SPY.BA", period="1y", interval="1d", progress=False)
        if not df_spy.empty:
            if isinstance(df_spy.columns, pd.MultiIndex):
                df_spy.columns = df_spy.columns.get_level_values(0)
            df_spy['EMA_200'] = df_spy['Close'].ewm(span=200, adjust=False).mean()
            ultimo_spy = df_spy.iloc[-1]
            if ultimo_spy['Close'] < ultimo_spy['EMA_200']:
                print("\n⚠️ [ALERTA MACRO] El S&P 500 (SPY.BA) está por debajo de su EMA 200. Mercado bajista general: operar rebotes con cautela extra.")
            else:
                print("\n✅ [ESTADO MACRO] El S&P 500 (SPY.BA) está alcista (Precio > EMA 200). Entorno favorable para rebotes.")
    except Exception as e:
        print(f"No se pudo verificar el contexto de mercado general: {e}")

def verificar_alertas():
    verificar_mercado_general()
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Analizando cartera avanzada de {len(ACTIVOS)} activos con filtros institucionales...")
    
    resultados_analisis = []
    nuevas_oportunidades = []

    for simbolo in ACTIVOS:
        try:
            # Descargamos datos diarios de los últimos 2 años
            df = yf.download(simbolo, period="2y", interval="1d", progress=False)
            
            if df.empty or len(df) < 200:
                continue

            # Limpieza de MultiIndex si yfinance lo devuelve agrupado
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            # --- FILTRO 1: LIQUIDEZ REAL ---
            # Descartar si el volumen promedio de 20 ruedas es menor a 200 acciones operadas diarias
            volumen_promedio_20 = df['Volume'].rolling(window=20).mean().iloc[-1]
            if pd.isna(volumen_promedio_20) or volumen_promedio_20 < 200:
                continue

            # --- 1. INDICADORES TÉCNICOS ---
            df['EMA_200'] = df['Close'].ewm(span=200, adjust=False).mean()
            df['SMA_20'] = df['Close'].rolling(window=20).mean()
            df['STD_20'] = df['Close'].rolling(window=20).std()
            df['Banda_Inferior'] = df['SMA_20'] - (df['STD_20'] * 2)

            delta = df['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            df['RSI'] = 100 - (100 / (1 + rs))

            min_rsi = df['RSI'].rolling(window=14).min()
            max_rsi = df['RSI'].rolling(window=14).max()
            df['StochRSI_K'] = ((df['RSI'] - min_rsi) / (max_rsi - min_rsi)) * 100

            # --- 2. EXTRACCIÓN DE VALORES ACTUALES ---
            ultimo = df.iloc[-1]
            precio_actual = float(ultimo['Close'])
            ema_200 = float(ultimo['EMA_200'])
            banda_inf = float(ultimo['Banda_Inferior'])
            stoch_rsi = float(ultimo['StochRSI_K'])
            volumen_actual = float(ultimo['Volume'])

            # Distancia porcentual a la Banda Inferior
            distancia_banda_pct = ((precio_actual - banda_inf) / banda_inf) * 100

            # Validar tendencia de fondo alcista
            tendencia_alcista = precio_actual > ema_200

            # --- FILTRO 3: VOLUMEN DE EXHAUSTIÓN EN EL PULLBACK ---
            # True si el volumen actual es menor al promedio (indica ausencia de vendedores en pánico)
            volumen_exhausto = volumen_actual < volumen_promedio_20

            # Índice de cercanía global (premiamos si hay volumen exhausto reduciendo la puntuación)
            if tendencia_alcista:
                puntuacion_cercania = max(0, stoch_rsi) + max(0, distancia_banda_pct * 5)
                if volumen_exhausto:
                    puntuacion_cercania *= 0.9  # Bonificación por pullback en volumen bajo
            else:
                puntuacion_cercania = 9999.0  # Descartado por tendencia bajista

            resultados_analisis.append({
                "simbolo": simbolo,
                "precio": precio_actual,
                "banda_inf": banda_inf,
                "ema_200": ema_200,
                "stoch_rsi": stoch_rsi,
                "distancia_pct": distancia_banda_pct,
                "tendencia_alcista": tendencia_alcista,
                "volumen_exhausto": volumen_exhausto,
                "puntuacion": puntuacion_cercania
            })

            # Comprobar si cumple el gatillo estricto de compra (incluyendo volumen de exhaustión)
            if tendencia_alcista and precio_actual <= banda_inf and stoch_rsi < 25 and volumen_exhausto:
                registro = {
                    "Fecha_Hora": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "Activo": simbolo,
                    "Precio": round(precio_actual, 2),
                    "Banda_Inferior": round(banda_inf, 2),
                    "EMA_200": round(ema_200, 2),
                    "Stoch_RSI": round(stoch_rsi, 2),
                    "Estrategia": "Pullback Diario Alcista (Bollinger + StochRSI + Volumen Exhausto)"
                }
                nuevas_oportunidades.append(registro)

        except Exception as e:
            print(f"Error procesando {simbolo}: {e}")

    # --- 3. ORDENAR Y MOSTRAR RESULTADOS ---
    resultados_analisis.sort(key=lambda x: x['puntuacion'])

    print("\n" + "="*85)
    print(" RANKING DE CERCANÍA A OPORTUNIDAD DE COMPRA (FILTRADO Y VALIDADO)")
    print("="*85)
    
    for i, res in enumerate(resultados_analisis, 1):
        estado_alerta = " "
        vol_tag = "📊 Vol. Normal" if not res['volumen_exhausto'] else "📉 Vol. Exhausto (Ideal)"
        
        if res['tendencia_alcista'] and res['precio'] <= res['banda_inf'] and res['stoch_rsi'] < 25 and res['volumen_exhausto']:
            estado_alerta = " 🎯 ¡OPORTUNIDAD DE COMPRA IDEAL!"
        elif res['tendencia_alcista'] and res['precio'] <= res['banda_inf'] and res['stoch_rsi'] < 25:
            estado_alerta = " ⚠️ Cerca, pero Volumen Alto"
        elif not res['tendencia_alcista']:
            estado_alerta = " ⚠️ Tendencia Bajista (Descartado)"

        print(f"{i:2d}. {res['simbolo']:<8} -> Precio: ${res['precio']:>8.2f} | Banda Inf: ${res['banda_inf']:>8.2f} | StochRSI: {res['stoch_rsi']:>5.1f} | Dist: {res['distancia_pct']:>+.2f}% | {vol_tag}{estado_alerta}")

    print("="*85)

    # Guardado automático en la bitácora local CSV si hubo alertas
    if nuevas_oportunidades:
        df_nuevos = pd.DataFrame(nuevas_oportunidades)
        if os.path.exists(ARCHIVO_LOG):
            df_nuevos.to_csv(ARCHIVO_LOG, mode='a', header=False, index=False)
        else:
            df_nuevos.to_csv(ARCHIVO_LOG, index=False)
            
        print(f"\n[ÉXITO] Se guardaron {len(nuevas_oportunidades)} alertas de alta calidad en '{ARCHIVO_LOG}'.")
    else:
        print("\n[INFO] Ningún activo cumplió todos los filtros estrictos (incluyendo bajo volumen de retroceso) en este ciclo.")

if __name__ == "__main__":
    verificar_alertas()