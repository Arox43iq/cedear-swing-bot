from datetime import datetime
import os
import pandas as pd
import yfinance as yf

# Universo ampliado de CEDEARs, ETFs y Cripto-activos funcionales en BYMA (Cocos)
ACTIVOS = [
    # --- ETFs Globales, Índices y Cripto previos ---
    "SPY.BA",  # S&P 500
    "QQQ.BA",  # Nasdaq 100
    "DIA.BA",  # Dow Jones
    "IWM.BA",  # Russell 2000 (Small Caps)
    "ARKK.BA",  # Ark Innovation
    "IBIT.BA",  # iShares Bitcoin Trust ETF
    "ETHA.BA",  # iShares Ethereum Trust ETF
    # --- Nuevos ETFs y Activos de las capturas (Región, Sectores, Commodities y Otros) ---
    "IEUR.BA",  # Europe ETF
    "EFA.BA",   # iShares MSCI EAFE ETF
    "VXX.BA",   # iPath Series B S&P 500 VIX
    "XLY.BA",   # S&P 500 Consumer Discretionary ETF
    "XLB.BA",   # S&P 500 Materials ETF
    "XME.BA",   # State Street SPDR S&P Metals & Mining
    "IJH.BA",   # iShares Core S&P Mid-Cap ETF
    "ICLN.BA",  # iShares Global Clean Energy
    "ESGU.BA",  # iShares ESG Aware MSCI USA ETF
    "IVW.BA",   # S&P 500 Growth ETF
    "SPHQ.BA",  # Invesco S&P 500 Quality ETF
    "ACWI.BA",  # iShares MSCI ACWI ETF
    "IVE.BA",   # S&P 500 Value ETF
    "CIBR.BA",  # First Trust NASDAQ Cybersecurity ETF
    "XLC.BA",   # S&P 500 Communication ETF
    "XLRE.BA",  # State Street Real Estate Select Sector
    "IEMG.BA",  # iShares Core MSCI Emerging Markets ETF
    "ILF.BA",   # iShares Latin America 40 ETF
    "IBB.BA",   # Nasdaq Biotechnology ETF
    "EWJ.BA",   # iShares MSCI Japan ETF
    "ITA.BA",   # iShares US Aerospace & Defense ETF
    "URA.BA",   # Global X Uranium ETF
    "XLI.BA",   # S&P 500 Industrial ETF
    "RSP.BA",   # Invesco S&P 500 Equal Weight
    "VEA.BA",   # Developed Markets ETF
    "XLV.BA",   # S&P 500 Health Care ETF
    "USO.BA",   # United States Oil Fund
    "SPXL.BA",  # Direxion Daily S&P 500 Bull 3X
    "PSQ.BA",   # Proshares Short QQQ ETF
    "XLK.BA",   # S&P 500 TECH ETF
    "VIG.BA",   # Vanguard Dividend Appreciation ETF
    "FXI.BA",   # ETF China Large-Cap
    "IVV.BA",   # iShares Core S&P 500 ETF
    "EWZ.BA",   # iShares MSCI Brazil ETF
    "GLD.BA",   # SPDR Gold Shares ETF
    "SLV.BA",   # iShares Silver Trust
    "COPX.BA",  # Global X Copper Miners ETF
    "SMH.BA",   # VanEck Semiconductor ETF
    "GDX.BA",   # VanEck Gold Miners ETF
    "XLE.BA",   # State Street Energy Select Sector SPDR
    "XLP.BA",   # S&P 500 Consumer ETF
    "EEM.BA",   # MSCI Emerging Markets
    "XLF.BA",   # Financial SPDR
    "XLU.BA",   # Utilities Select Sector SPDR Fund ETF
    "TQQQ.BA",  # ProShares UltraPro QQQ
    "EWY.BA",   # iShares MSCI South Korea
    "SH.BA",    # Short S&P 500
    # --- Acciones Sector Cripto / Minería / Blockchain ---
    "MSTR.BA",  # MicroStrategy
    "HUT.BA",   # Hut 8 Mining
    "COIN.BA",  # Coinbase
    "KEEL.BA",  # Keel Infrastructure / Bitfarms
    "RIOT.BA",  # Riot Platforms
    # --- Gigantes Tecnológicos / Crecimiento ---
    "AAPL.BA",  # Apple
    "MSFT.BA",  # Microsoft
    "MELI.BA",  # Mercado Libre
    "GOOGL.BA",  # Google (Alphabet)
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
    "ASML.BA",  # ASML Holding
    "PLTR.BA",  # Palantir Technologies
    "MRVL.BA",  # Marvell Technology
    "SPOT.BA",  # Spotify
    "EBAY.BA",  # Ebay
    "PANW.BA",  # Palo Alto Networks
    # --- Sector Financiero y Conglomerados ---
    "BRKB.BA",  # Berkshire Hathaway
    "JPM.BA",   # JPMorgan Chase
    "C.BA",     # Citigroup
    "GS.BA",    # Goldman Sachs
    "WFC.BA",   # Wells Fargo
    "AXP.BA",   # American Express
    "NU.BA",    # Nu Bank
    "STNE.BA",  # StoneCo
    "BBD.BA",   # Banco Bradesco
    # --- Consumo Masivo y Retail ---
    "KO.BA",    # Coca-Cola
    "PEP.BA",   # Pepsico
    "WMT.BA",   # Walmart
    "MCD.BA",   # McDonalds
    "NKE.BA",   # Nike
    "PG.BA",    # Procter & Gamble
    "DISN.BA",  # Disney
    "TGT.BA",   # Target
    "ABEV.BA",  # ADR Ambev
    "ARCO.BA",  # Arcos Dorados
    # --- Salud y Farmacéuticas ---
    "JNJ.BA",   # Johnson & Johnson
    "PFE.BA",   # Pfizer
    "MRNA.BA",  # Moderna
    "ABBV.BA",  # AbbVie
    "AMGN.BA",  # Amgen
    "ABT.BA",   # Abbott
    # --- Energía, Petróleo y Minería ---
    "XOM.BA",   # Exxon Mobil
    "CVX.BA",   # Chevron
    "VALE.BA",  # Vale
    "RIO.BA",   # Rio Tinto
    "KGC.BA",   # Kinross Gold
    "MUX.BA",   # McEwen
    "PKS.BA",   # Posco
    "SID.BA",   # Cia. Siderurgica Nacional
    # --- Industria, Autos y Aeroespacial ---
    "CAT.BA",   # Caterpillar
    "DE.BA",    # Deere
    "GE.BA",    # General Electric
    "TM.BA",    # Toyota Motors
    "F.BA",     # Ford
    "LMT.BA",   # Lockheed Martin
    "RTX.BA",   # Raytheon
    "EMBJ.BA",  # Embraer
    "NOKA.BA",  # Nokia
    "CSCO.BA",  # Cisco Systems
    "MDT.BA",   # Medtronic
    "SPGI.BA",  # Standard & Poor's
    "ADGO.BA",  # Adecoagro
    "GLOB.BA",  # Globant
    "DECK.BA",  # Deckers Outdoor Corporation
    "SYY.BA",   # Sysco
    "XROX.BA",  # Xerox
    "AAP.BA",   # Advance Auto Parts
    "SONY.BA",  # Sony
    "CAR.BA",   # Avis Budget Group
    "NUE.BA",   # Nucor
    "MSI.BA",   # Motorola
    "JD.BA",    # Jingdong (JD.com)
    "UPST.BA",  # Upstart
    "MO.BA",    # Altria
    "ADI.BA",   # Analog Devices
    "OXY.BA",   # Occidental Petroleum Corp
    "TMUS.BA",  # T-Mobile US Inc.
    "TSM.BA",   # Taiwan Semiconductor
    "BABA.BA",  # Alibaba
    "T.BA",     # AT&T
    "MU.BA",    # Micron Technology
    "V.BA",     # Visa
    "TXR.BA",   # Ternium
    "LAC.BA",   # Lithium Americas
    "LLY.BA",   # Eli Lilly & Co
    "AMAT.BA",  # Applied Materials
    "SATL.BA",  # Satellogic
    "CLS.BA",   # Celestica
    "RBLX.BA",  # Roblox Corp
    "CCL.BA",   # Carnival Corp
]

# Evitar duplicados por seguridad de forma automática
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
                    "\n⚠️ [ALERTA MACRO] El S&P 500 (SPY.BA) está por debajo de su EMA"
                    " 200. Mercado bajista general: operar rebotes con cautela extra."
                )
            else:
                print(
                    "\n✅ [ESTADO MACRO] El S&P 500 (SPY.BA) está alcista (Precio > EMA"
                    " 200). Entorno favorable para rebotes."
                )
    except Exception as e:
        print(f"No se pudo verificar el contexto de mercado general: {e}")


def verificar_alertas():
    verificar_mercado_general()
    print(
        f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Analizando cartera"
        f" masiva de {len(ACTIVOS)} activos con filtros institucionales y de corto plazo..."
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
            df["EMA_20"] = df["Close"].ewm(span=20, adjust=False).mean()  # EMA Corto Plazo
            df["SMA_20"] = df["Close"].rolling(window=20).mean()
            df["STD_20"] = df["Close"].rolling(window=20).std()
            df["Banda_Inferior"] = df["SMA_20"] - (df["STD_20"] * 2)

            # RSI Rápido de Corto Plazo (7 periodos)
            delta = df["Close"].diff()
            gain_7 = (delta.where(delta > 0, 0)).rolling(window=7).mean()
            loss_7 = (-delta.where(delta < 0, 0)).rolling(window=7).mean()
            rs_7 = gain_7 / loss_7
            df["RSI_7"] = 100 - (100 / (1 + rs_7))

            # StochRSI basado en el RSI de 7 periodos (ventana de 14 para estocástico)
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
                puntuacion_cercania = max(0, stoch_rsi) + max(
                    0, distancia_banda_pct * 5
                )
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
                    "Estrategia": (
                        "Pullback Corto Plazo (Bollinger + StochRSI(7) + Volumen Exhausto)"
                    ),
                }
                nuevas_oportunidades.append(registro)

        except Exception as e:
            pass  # Evita romper por errores puntuales de yfinance en algún activo

    resultados_analisis.sort(key=lambda x: x["puntuacion"])

    print("\n" + "=" * 85)
    print(" RANKING DE CERCANÍA A OPORTUNIDAD DE COMPRA (FILTRADO Y VALIDADO)")
    print("=" * 85)

    for i, res in enumerate(resultados_analisis, 1):
        estado_alerta = " "
        vol_tag = (
            "📊 Vol. Normal"
            if not res["volumen_exhausto"]
            else "📉 Vol. Exhausto (Ideal)"
        )

        if (
            res["tendencia_alcista"]
            and res["precio"] <= res["banda_inf"]
            and res["stoch_rsi"] < 25
            and res["volumen_exhausto"]
        ):
            estado_alerta = " 🎯 ¡OPORTUNIDAD DE COMPRA IDEAL!"
        elif (
            res["tendencia_alcista"]
            and res["precio"] <= res["banda_inf"]
            and res["stoch_rsi"] < 25
        ):
            estado_alerta = " ⚠️ Cerca, pero Volumen Alto"
        elif not res["tendencia_alcista"]:
            estado_alerta = " ⚠️ Tendencia Bajista (Descartado)"

        print(
            f"{i:2d}. {res['simbolo']:<8} -> Precio: ${res['precio']:>8.2f} | Banda"
            f" Inf: ${res['banda_inf']:>8.2f} | StochRSI(7): {res['stoch_rsi']:>5.1f} |"
            f" Dist: {res['distancia_pct']:>+.2f}% | {vol_tag}{estado_alerta}"
        )

    print("=" * 85)

    if nuevas_oportunidades:
        df_nuevos = pd.DataFrame(nuevas_oportunidades)
        if os.path.exists(ARCHIVO_LOG):
            df_nuevos.to_csv(ARCHIVO_LOG, mode="a", header=False, index=False)
        else:
            df_nuevos.to_csv(ARCHIVO_LOG, index=False)
        print(
            f"\n[ÉXITO] Se guardaron {len(nuevas_oportunidades)} alertas de alta"
            f" calidad en '{ARCHIVO_LOG}'."
        )
    else:
        print(
            "\n[INFO] Ningún activo cumplió todos los filtros estrictos (incluyendo"
            " bajo volumen de retroceso) en este ciclo."
        )


if __name__ == "__main__":
    verificar_alertas()