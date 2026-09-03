import yfinance as yf
import pandas as pd
from datetime import datetime
import os

# Universo masivo: ~50 ETFs y CEDEARs de máxima calidad y liquidez en BYMA
ACTIVOS = [
    # --- ETFs Globales ---
    "SPY.BA",   # S&P 500
    "QQQ.BA",   # Nasdaq 100
    "DIA.BA",   # Dow Jones
    "IWM.BA",   # Russell 2000 (Small Caps)

    # --- Gigantes Tecnológicos / Crecimiento ---
    "AAPL.BA",  # Apple
    "MSFT.BA",  # Microsoft
    "MELI.BA",  # Mercado Libre
    "GOOGL.BA", # Google (Alphabet)
    "NVDA.BA",  # Nvidia
    "AMZN.BA",  # Amazon
    "TSLA.BA",  # Tesla
    "NFLX.BA",  # Netflix
    "AMD.BA",   # AMD
    "INTC.BA",  # Intel
    "QCOM.BA",  # Qualcomm
    "IBM.BA",   # IBM
    "ORCL.BA",  # Oracle
    "ADBE.BA",  # Adobe
    "CRM.BA",   # Salesforce
    "PYPL.BA",  # PayPal
    "UBER.BA",  # Uber
    "ABNB.BA",  # Airbnb

    # --- Sector Financiero y Bancos ---
    "JPM.BA",   # JPMorgan Chase
    "BAC.BA",   # Bank of America
    "C.BA",     # Citigroup
    "WFC.BA",   # Wells Fargo
    "GS.BA",    # Goldman Sachs
    "AXP.BA",   # American Express
    "V.BA",     # Visa
    "MA.BA",    # Mastercard
    "BRKB.BA",  # Berkshire Hathaway

    # --- Consumo Masivo y Defensivos ---
    "WMT.BA",   # Walmart
    "KO.BA",    # Coca-Cola
    "PEP.BA",   # PepsiCo
    "MCD.BA",   # McDonald's
    "NKE.BA",   # Nike
    "PG.BA",    # Procter & Gamble
    "COST.BA",  # Costco

    # --- Sector Salud y Farmacéuticas ---
    "JNJ.BA",   # Johnson & Johnson
    "PFE.BA",   # Pfizer
    "UNH.BA",   # UnitedHealth
    "LLY.BA",   # Eli Lilly
    "ABBV.BA",  # AbbVie

    # --- Industrial, Energía y Materiales ---
    "CAT.BA",   # Caterpillar
    "BA.BA",    # Boeing
    "XOM.BA",   # ExxonMobil
    "CVX.BA",   # Chevron
    "GE.BA"     # General Electric
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

            # Distancia porcentual a la Banda Inferior (positivo si está arriba, negativo si ya la rompió)
            distancia_banda_pct = ((precio_actual - banda_inf) / banda_inf) * 100

            # Validar tendencia de fondo alcista
            tendencia_alcista = precio_actual > ema_200

            # Índice de cercanía global: Combinamos qué tan cerca está del StochRSI < 25 y de la Banda Inferior
            # Si cumple tendencia alcista, le damos prioridad. Si no, penalizamos la puntuación.
            if tendencia_alcista:
                # Menor puntaje = Más cerca de la oportunidad ideal
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
    # Ordenamos de menor a mayor puntuación (los más cercanos al objetivo primero)
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