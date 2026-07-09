# 🤖 Quantum Bot (AI Quant Auto-Trading Bot)

[English](README_EN.md) | [한국어](README.md)

![Python Version](https://img.shields.io/badge/python-3.9+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Toss API](https://img.shields.io/badge/Toss_Invest-Open_API-0050FF.svg)
![Telegram](https://img.shields.io/badge/Telegram-Bot-2CA5E0.svg)

Quantum Bot is a personal AI assistant that integrates with the Toss Invest API and Telegram to automatically manage the portfolio weight of **5 US quantum computing stocks**. It analyzes buy/sell timings using Wall Street-level quantitative algorithms.

---

## 🎯 Target Portfolio

The bot targets the 5 core quantum computing companies below, infinitely maintaining the "golden ratio" (Target Weight) set by the user.

*   🔵 **IONQ (IonQ)** - 35%
*   🔵 **INFQ (Infleqtion)** - 25%
*   🔵 **QBTS (D-Wave Quantum)** - 15%
*   🔵 **RGTI (Rigetti Computing)** - 15%
*   🔵 **QUBT (Quantum Computing Inc)** - 10%

*(The target weights can be freely adjusted anytime in `config.py`.)*

---

## 🌟 Core Features

1. **Virtual Wallet-Based Midnight Rebalancing**: Every midnight (KST), it automatically buys and sells stocks to match your preset target weights. By introducing a **Virtual Wallet System**, it maintains the account's cash balance at $0 while perfectly preventing portfolio asset deflation by recording and storing the fractional dollar remainders caused by decimal trading limits.
2. **Dual API Safety & Self-Healing**: It preemptively checks the actual cash balance in the Toss Invest server and automatically blocks orders if the balance is insufficient. Also, if the user manually withdraws money causing a discrepancy between the ledger cash and actual cash, the bot detects this and synchronizes by deducting the virtual wallet balance (Self-Healing).
3. **Auto Token Renewal & Error Recovery**: Equipped with powerful survival logic, it automatically issues a new token and retries if the Toss API token expires (401) or if there's an overload from frequent requests (429).
4. **Multi-Currency Market Briefing**: It provides a summary report 4 times a day, including exchange rates, portfolio status, quant scores per stock, and the latest Google news. It clearly separates the assets and daily returns of **Korean stocks (₩) and US stocks ($)** in your account status.
5. **Intraday Real-Time Monitoring**: While the US market is open, it monitors charts every 5 minutes and shoots an emergency signal notification to Telegram when a strong buy/sell point occurs. (For spam prevention, it only sends notifications without auto-trading).
6. **Perfect US Market Calendar Integration (Holiday Evasion)**: Using the `holidays` library to reflect time zones, it independently identifies **official US and KR market holidays (e.g., Independence Day, Thanksgiving substitute holidays) and weekends**, smartly skipping all notifications and rebalancing to rest. It also works perfectly on half-day early close markets.
7. **Global Timezone Lock (KST)**: Even if you travel abroad with your laptop and the system time changes, the bot internally maintains **Korean Standard Time (KST, Asia/Seoul)** to prevent schedule deviations.

---

## ⚙️ Getting Started

### 1. Prerequisites
* Python 3.9 or higher
* Toss Invest Real/Mock Open API Key and Secret Key
* Telegram Bot Token and Chat ID

### 2. Installation
```bash
git clone https://github.com/USERNAME/quantum_bot.git
cd quantum_bot
pip install -r requirements.txt
```
*(Note: Requires packages like `requests`, `schedule`, `holidays`, `beautifulsoup4`, etc.)*

### 3. Environment Variables (`.env`)
Create a `.env` file in the project root directory and fill in your information.

```ini
# Toss Invest API Credentials
TOSS_API_KEY=your_api_key_here
TOSS_SECRET_KEY=your_secret_key_here

# Telegram Bot Settings
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
```

### 4. Configuration (`config.py`)
You can set the portfolio target weights and real trading mode in `config.py`.
* `PAPER_TRADE = True`: Mock Trading Mode (Blocks actual trades, only sends Telegram notifications)
* `PAPER_TRADE = False`: Real Trading Mode (Actual buy/sell orders are executed in the account)

---

## ⏰ Total Workflow (24/7 Schedule)

If you keep the bot running in the terminal, it operates fully automatically according to the schedule below (**strictly based on Korean Standard Time**). *(The bot automatically rests on weekends and holidays)*

*   `08:30` - 🇰🇷 Pre-market Briefing (Weekdays only)
*   `15:40` - 🇰🇷 Market Close Briefing (Weekdays only)
*   `22:00` - 🇺🇸 US Pre-market Briefing (Mon-Fri, excluding US holidays)
*   **`22:30 ~ 05:00` - 🇺🇸 Intraday Real-time Signal Monitoring (Every 5 mins)**
*   **`00:00` - 🔄 Midnight Auto Rebalancing (Tue-Sat, excluding US holidays)**
*   `05:10` - 🇺🇸 US Market Close Briefing (Tue-Sat, excluding US holidays)

---

## 🧠 Scoring Engine (Quant Algorithm)
The bot mathematically analyzes the past 100 days of candlestick data to grade a trading score out of 100 points.
1.  **Multiple Moving Averages (10 pts)**: Identifies golden/death crosses of 5, 20, and 50-day lines.
2.  **Bollinger Bands (20 pts)**: Identifies overbought and oversold conditions through standard deviation calculations.
3.  **MACD & Signal Line (20 pts)**: Identifies trend momentum utilizing Exponential Moving Averages (EMA).
4.  **RSI (20 pts)**: Identifies overbought/oversold states via the 14-day Relative Strength Index.
5.  **Return vs. Average Price (30 pts)**: Assigns points for averaging down (buying low) and profit realization timings.

---

## 💻 Manual Trade Commands
When you need to inject additional cash or withdraw some funds, type the commands below in the terminal. The bot will smartly calculate the deficit/surplus and buy/sell accordingly.

*   **To invest an additional $2,000 (Buy):**
    ```bash
    python3 trade_cash.py buy 2000
    ```
*   **When you need $500 cash and want to partially sell:**
    ```bash
    python3 trade_cash.py sell 500
    ```

---

## 🚀 How to Run
To keep the bot running 24/7, use the background execution command (`nohup`). **(For MacBooks, using Clamshell mode and the Amphetamine app is recommended)**

```bash
# Run the bot in background mode
nohup python3 main.py > nohup.out 2>&1 &

# Check logs in real-time
tail -f nohup.out

# Force stop the bot
kill $(pgrep -f "main.py")
```

---

## ⚠️ Disclaimer
This bot was developed for personal quantitative trading learning and automation purposes. **All financial losses and investment responsibilities arising from the use of this code lie entirely with the user.** Before switching to real trading mode (`PAPER_TRADE = False`), please ensure sufficient testing in mock trading mode.

## 📄 License
This project is licensed under the MIT License. Feel free to fork it and add your own strategies!
