# 📈 CEDEAR & Wall Street Swing Trading Scanner

An automated Python tool designed to scan a massive universe of high-liquidity assets (CEDEARs and global ETFs in BYMA / Wall Street) to identify and prioritize buy opportunities using **pullbacks in an uptrend**.

## 🚀 Key Features
- **Multi-Factor Analysis:** Combines underlying trend (200-period EMA), volatility (Bollinger Bands), and advanced momentum (Stochastic RSI).
- **Proximity Ranking System:** Ranks all analyzed assets from closest to furthest from the buy triggers, allowing continuous preventive monitoring rather than binary alerts.
- **Yahoo Finance Integration:** Automatic daily historical data downloading (`yfinance`) for robust data processing.
- **Automatic Logging:** Exports detected opportunities to a local CSV file for historical tracking.

## 🛠️ Technologies & Libraries Used
- **Python 3**
- **Pandas** (Financial time-series data manipulation and analysis)
- **yfinance** (Market data extraction)

## ⚙️ How to Install and Run

1. **Clone the repository:**
   ```bash
   git clone [https://github.com/Arox43iq/cedear-swing-bot.git](https://github.com/Arox43iq/cedear-swing-bot.git)