import datetime
import numpy as np
import pandas as pd
import yfinance as yf

# Cartera Completa: 103 Activos originales + ETFs globales y Cripto-CEDEARs de tu broker
ASSETS = [
    # Cripto-activos y ETFs de criptomonedas de tu broker (.BA)
    "IBIT.BA",
    "ETHA.BA",
    "MSTR.BA",
    "HUT.BA",
    "COIN.BA",
    "KEEL.BA",
    "RIOT.BA",
    # ETFs Globales y Macro
    "SPY.BA",
    "QQQ.BA",
    "IWM.BA",
    "GLD.BA",
    "TLT.BA",
    # Los 103 Activos del panel general y CEDEARs avanzados
    "AAPL.BA",
    "MSFT.BA",
    "GOOGL.BA",
    "AMZN.BA",
    "NVDA.BA",
    "META.BA",
    "TSLA.BA",
    "AMD.BA",
    "MELI.BA",
    "KO.BA",
    "JNJ.BA",
    "NFLX.BA",
    "V.BA",
    "MA.BA",
    "PANW.BA",
    "LMT.BA",
    "RTX.BA",
    "ADI.BA",
    "AMAT.BA",
    "ABT.BA",
    "GE.BA",
    "DIS.BA",
    "PYPL.BA",
    "INTC.BA",
    "QCOM.BA",
    "CSCO.BA",
    "IBM.BA",
    "ORCL.BA",
    "CRM.BA",
    "ADBE.BA",
    "TXN.BA",
    "AMGN.BA",
    "GILD.BA",
    "SBUX.BA",
    "NKE.BA",
    "MCD.BA",
    "WMT.BA",
    "PG.BA",
    "JPM.BA",
    "BAC.BA",
    "WFC.BA",
    "C.BA",
    "GS.BA",
    "MS.BA",
    "AXP.BA",
    "BLK.BA",
    "CAT.BA",
    "DE.BA",
    "BA.BA",
    "HON.BA",
    "UPS.BA",
    "FDX.BA",
    "MMM.BA",
    "GE.BA",
    "XOM.BA",
    "CVX.BA",
    "COP.BA",
    "SLB.BA",
    "EOG.BA",
    "PXD.BA",
    "OXY.BA",
    "NEE.BA",
    "DUK.BA",
    "SO.BA",
    "D.BA",
    "AEP.BA",
    "T.BA",
    "VZ.BA",
    "TM.BA",
    "HMC.BA",
    "NLY.BA",
    "BABA.BA",
    "JD.BA",
    "BIDU.BA",
    "PDD.BA",
    "NIO.BA",
    "TCOM.BA",
    "VALO.BA",
    "YPFD.BA",
    "GGAL.BA",
    "BMA.BA",
    "CRES.BA",
    "TECO2.BA",
    "TXAR.BA",
    "ALUA.BA",
    "CEPU.BA",
    "EDN.BA",
    "PAMP.BA",
    "BYMA.BA",
    "LOMA.BA",
    "IRSA.BA",
    "SUPV.BA",
    "CVH.BA",
    "TGNO4.BA",
    "TGSU2.BA",
]

# Eliminamos duplicados por si acaso quedó alguno repetido
ASSETS = list(dict.fromkeys(ASSETS))


def calculate_stoch_rsi(close, period=14):
  delta = close.diff()
  gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
  loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
  rs = gain / loss
  rsi = 100 - (100 / (1 + rs))

  min_rsi = rsi.rolling(window=period).min()
  max_rsi = rsi.rolling(window=period).max()
  stoch_rsi = (rsi - min_rsi) / (max_rsi - min_rsi) * 100
  return stoch_rsi.fillna(0)


def main():
  print("\n✅ [ESTADO MACRO] Analizando régimen de mercado global (SPY.BA)...")

  # Macro check con SPY.BA
  spy_df = yf.download("SPY.BA", period="1y", interval="1d", progress=False)
  if spy_df.empty:
    print("No se pudo obtener datos macro de SPY.BA.")
    return

  if isinstance(spy_df.columns, pd.MultiIndex):
    spy_close = spy_df["Close"].iloc[:, 0]
  else:
    spy_close = spy_df["Close"]

  spy_ema200 = spy_close.ewm(span=200, adjust=False).mean().iloc[-1]
  spy_current = spy_close.iloc[-1]

  if spy_current > spy_ema200:
    print(
        "✅ [ESTADO MACRO] El S&P 500 (SPY.BA) está alcista (Precio > EMA"
        " 200). Entorno favorable."
    )
  else:
    print(
        "⚠️ [ESTADO MACRO] El S&P 500 (SPY.BA) está bajista o neutral."
        " Precaución extrema."
    )

  print(
      f"\n[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Analizando"
      f" cartera masiva global de {len(ASSETS)} activos...\n"
  )

  results = []

  for ticker in ASSETS:
    try:
      df = yf.download(ticker, period="1y", interval="1d", progress=False)
      if df.empty or len(df) < 200:
        continue

      if isinstance(df.columns, pd.MultiIndex):
        close = df["Close"].iloc[:, 0]
        volume = df["Volume"].iloc[:, 0]
      else:
        close = df["Close"]
        volume = df["Volume"]

      current_price = float(close.iloc[-1])

      # 1. Filtro de Tendencia (EMA 200)
      ema200 = float(close.ewm(span=200, adjust=False).mean().iloc[-1])
      if current_price < ema200:
        continue

      # 2. Bollinger Bands (20, 2)
      sma20 = close.rolling(window=20).mean()
      std20 = close.rolling(window=20).std()
      lower_band = float((sma20 - (2 * std20)).iloc[-1])

      # 3. StochRSI
      stoch_rsi_series = calculate_stoch_rsi(close)
      current_stoch_rsi = float(stoch_rsi_series.iloc[-1])

      # 4. Filtro de Liquidez / Volumen Exhausto
      vol_sma20 = volume.rolling(window=20).mean().iloc[-1]
      current_vol = volume.iloc[-1]
      is_exhaustion = current_vol < vol_sma20

      # Distancia a la banda inferior
      dist = ((current_price - lower_band) / lower_band) * 100

      # Filtro de cercanía y sobreventa
      if dist <= 3.0 and current_stoch_rsi <= 20.0:
        vol_label = (
            "📉 Vol. Exhausto (Ideal)" if is_exhaustion else "📊 Vol. Normal"
        )
        results.append({
            "ticker": ticker,
            "price": current_price,
            "lower_band": lower_band,
            "stoch_rsi": current_stoch_rsi,
            "dist": dist,
            "vol_status": vol_label,
        })
    except Exception as e:
      continue

  # Ordenar por cercanía a la banda inferior
  results.sort(key=lambda x: x["dist"])

  print(
      "=" * 85
      + "\n RANKING DE OPORTUNIDADES (CARTERA GLOBAL Y AMPLIADA)\n"
      + "=" * 85
  )
  if not results:
    print("No hay activos cumpliendo los criterios estrictos en este momento.")
  else:
    for i, r in enumerate(results, 1):
      print(
          f"{i:2d}. {r['ticker']:<10} -> Precio: ${r['price']:<10.2f} | Banda"
          f" Inf: ${r['lower_band']:<10.2f} | StochRSI: {r['stox_rsi'] if 'stox_rsi' in r else r['stoch_rsi']:>5.1f} |"
          f" Dist: {r['dist']:>+5.2f}% | {r['vol_status']}"
      )


if __name__ == "__main__":
  main()