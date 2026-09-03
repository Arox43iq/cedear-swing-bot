import yfinance as yf
import pandas as pd
from datetime import datetime
import os

# Universo masivo de ETFs y CEDEARs de alta liquidez en BYMA (Actualizado)
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
    "AVGO.BA", # Broadcom
    "ASML.BA", # ASML Holding
    "PLTR.BA", # Palantir Technologies
    "HOOD.BA", # Robinhood Markets
    "SHOP.BA", # Shopify
    "SNOW.BA", # Snowflake
    "MRVL.BA", # Marvell Technology
    "SPOT.BA", # Spotify
    "ZM.BA",   # Zoom Video
    "TWLO.BA", # Twilio
    "EBAY.BA", # Ebay
    "PANW.BA", # Palo Alto Networks

    # --- Sector Financiero y Conglomerados ---
    "BRKB.BA", # Berkshire Hathaway
    "JPM.BA",  # JPMorgan Chase
    "BAC.BA",  # Bank of America
    "C.BA",    # Citigroup
    "GS.BA",   # Goldman Sachs
    "WFC.BA",  # Wells Fargo
    "AXP.BA",  # American Express
    "XP.BA",   # XP Inc.
    "NU.BA",   # Nu Bank
    "PAGS.BA", # PagSeguro
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
    "HIMS.BA", # Hims & Hers Health

    # --- Energía, Petróleo y Minería ---
    "XOM.BA",  # Exxon Mobil
    "CVX.BA",  # Chevron
    "PBR.BA",  # Petrobras brasileiro
    "VIST.BA", # Visto Oil & Gas
    "VALE.BA", # Vale
    "RIO.BA",  # Rio Tinto
    "KGC.BA",  # Kinross Gold
    "MUX.BA",  # McEwen
    "PKS.BA",  # Posco
    "SID.BA",  # Cia. Siderurgica Nacional

    # --- Industria, Autos y Aeroespacial ---
    "CAT.BA",  # Caterpillar
    "BA.C.BA", # Bank of America / Industrial
    "DE.BA",   # Deere
    "GE.BA",   # General Electric
    "TM.BA",   # Toyota Motors
    "F.BA",    # Ford
    "GM.BA",   # General Motors
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
    "FISV.BA", # Fiserv
    "AAP.BA",  # Advance Auto Parts
    "SONY.BA", # Sony
    "CAR.BA",  # Avis Budget Group
    "NUE.BA",  # Nucor
    "MSI.BA",  # Motorola
    "LRCX.BA", # Lam Research
    "JD.BA",   # Jingdong (JD.com)
    "UPST.BA", # Upstart
    "MO.BA",   # Altria
    "ADI.BA",  # Analog Devices
    "RKLB.BA", # Rocket Lab Corp
    "OXY.BA",  # Occidental Petroleum Corp
    "TMUS.BA", # T-Mobile US Inc.
    "DOW.BA",  # Dow
    "TSM.BA",  # Taiwan Semiconductor
    "BABA.BA", # Alibaba
    "BIOX.BA", # Bioceres
    "T.BA",    # AT&T
    "MU.BA",   # Micron Technology
    "AAL.BA",  # American Airlines
    "V.BA",    # Visa
    "TXR.BA",  # Ternium
    "SNDK.BA", # SanDisk Corporation
    "LAC.BA",  # Lithium Americas
    "LLY.BA",  # Eli Lilly & Co
    "AMAT.BA", # Applied Materials
    "ASTS.BA", # AST SpaceMobile Inc
    "SATL.BA", # Satellogic
    "NBIS.BA", # Nebius Group N.V
    "IREN.BA", # Iren LTD
    "CLS.BA",  # Celestica
    "RBLX.BA", # Roblox Corp
    "XYZ.BA",  # Block Inc.
    "TEN.BA",  # Tenaris
    "NATU3.BA",# Natura
    "MP.BA",   # MP Materials Corp.
    "CCL.BA",  # Carnival Corp
    "DESP.BA"  # Despegar
]

ARCHIVO_LOG = "oportunidades.csv"

def verificar_alertas():
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Analizando y ordenando cartera masiva de {len(ACTIVOS)} activos...")
    
    resultados_analisis = []
    nuevas_oportunidades = []

    for simbolo in ACTIVOS:
        try:
            # Descargamos datos diarios de los últimos 2 años
            df = yf.download(simbolo, period="2y", interval="1d", progress=False)
            
            if df.empty or len(df) < 200:
                print(f"-> {simbolo}: Datos insuficientes ({len(df)} registros).")
                continue

            # Limpieza de MultiIndex si yfinance lo devuelve agrupado
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

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

            # Distancia porcentual a la Banda Inferior
            distancia_banda_pct = ((precio_actual - banda_inf) / banda_inf) * 100

            # Validar tendencia de fondo alcista
            tendencia_alcista = precio_actual > ema_200

            # Índice de cercanía global
            if tendencia_alcista:
                puntuacion_cercania = max(0, stoch_rsi) + max(0, distancia_banda_pct * 5)
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
                "puntuacion": puntuacion_cercania
            })

            # Comprobar si cumple el gatillo estricto de compra
            if tendencia_alcista and precio_actual <= banda_inf and stoch_rsi < 25:
                registro = {
                    "Fecha_Hora": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "Activo": simbolo,
                    "Precio": round(precio_actual, 2),
                    "Banda_Inferior": round(banda_inf, 2),
                    "EMA_200": round(ema_200, 2),
                    "Stoch_RSI": round(stoch_rsi, 2),
                    "Estrategia": "Pullback Diario Alcista (Bollinger + StochRSI)"
                }
                nuevas_oportunidades.append(registro)

        except Exception as e:
            print(f"Error procesando {simbolo}: {e}")

    # --- 3. ORDENAR Y MOSTRAR RESULTADOS ---
    resultados_analisis.sort(key=lambda x: x['puntuacion'])

    print("\n" + "="*70)
    print(" RANKING DE CERCANÍA A OPORTUNIDAD DE COMPRA (TENDENCIA ALCISTA VÁLIDA)")
    print("="*70)
    
    for i, res in enumerate(resultados_analisis, 1):
        estado_alerta = " "
        if res['tendencia_alcista'] and res['precio'] <= res['banda_inf'] and res['stoch_rsi'] < 25:
            estado_alerta = " 🎯 ¡OPORTUNIDAD DE COMPRA!"
        elif not res['tendencia_alcista']:
            estado_alerta = " ⚠️ Tendencia Bajista (Descartado)"

        print(f"{i:2d}. {res['simbolo']:<8} -> Precio: ${res['precio']:>8.2f} | Banda Inf: ${res['banda_inf']:>8.2f} | StochRSI: {res['stoch_rsi']:>5.1f} | Dist. Banda: {res['distancia_pct']:>+.2f}%{estado_alerta}")

    print("="*70)

    # Guardado automático en la bitácora local CSV si hubo alertas
    if nuevas_oportunidades:
        df_nuevos = pd.DataFrame(nuevas_oportunidades)
        if os.path.exists(ARCHIVO_LOG):
            df_nuevos.to_csv(ARCHIVO_LOG, mode='a', header=False, index=False)
        else:
            df_nuevos.to_csv(ARCHIVO_LOG, index=False)
            
        print(f"\n[ÉXITO] Se guardaron {len(nuevas_oportunidades)} alertas en '{ARCHIVO_LOG}'.")
    else:
        print("\n[INFO] Ningún activo cumplió los requisitos estrictos en este ciclo, pero arriba tienes el ranking de quiénes están más cerca.")

if __name__ == "__main__":
    verificar_alertas()