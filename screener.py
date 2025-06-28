import yfinance as yf
import pandas as pd
import numpy as np
import time
import requests

# === TELEGRAM SETUP ===
TELEGRAM_BOT_TOKEN = "7468828306:AAG6uOChh0SFLZwfhnNMdljQLHTcdPcQTa4"
TELEGRAM_CHAT_ID = "980258123"

def send_telegram(message):
    try:
        url = f"https://api.telegram.org/bot7468828306:AAG6uOChh0SFLZwfhnNMdljQLHTcdPcQTa4/sendMessage"
        payload = {
            "chat_id": 980258123,
            "text": message,
            "parse_mode": "Markdown"
        }
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            print("📬 Telegram alert sent.")
        else:
            print("❌ Telegram failed:", response.text)
    except Exception as e:
        print("⚠️ Telegram error:", e)

# === STOCKS & STRATEGY ===
nifty_100_stocks = [
    "RELIANCE.NS", "HDFCBANK.NS"]

def calculate_rsi(series, window=14):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(window=window).mean()
    avg_loss = loss.rolling(window=window).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def calculate_macd(series, slow=26, fast=12, signal=9):
    exp1 = series.ewm(span=fast, adjust=False).mean()
    exp2 = series.ewm(span=slow, adjust=False).mean()
    macd = exp1 - exp2
    signal_line = macd.ewm(span=signal, adjust=False).mean()
    return macd, signal_line

def analyze_stock(ticker):
    print(f"\n📊 Analyzing: {ticker}")
    try:
        df = yf.download(ticker, period="3mo", interval="1d", progress=False)

        # Clean up headers
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df.columns.name = None

        print(f"📋 Columns: {df.columns.tolist()}")

        if df.empty or any(col not in df.columns for col in ['Close', 'Volume']) or len(df) < 50:
            print("⚠️ Missing data or columns")
            return None, None

        df['EMA_50'] = df['Close'].ewm(span=50, adjust=False).mean()
        df['RSI'] = calculate_rsi(df['Close'])
        df['MACD'], df['Signal'] = calculate_macd(df['Close'])
        df['Volume_avg'] = df['Volume'].rolling(window=20).mean()

        latest = df.iloc[-1]

        conditions = {
            "Close > EMA_50": latest['Close'] > latest['EMA_50'],
            "RSI > 55": latest['RSI'] > 55,
            "MACD > Signal": latest['MACD'] > latest['Signal'],
            "Volume > 1.2x avg": latest['Volume'] > 1.2 * latest['Volume_avg']
        }

        matched_count = sum(conditions.values())

        print(f"🧪 Match: {matched_count}/4 → {conditions}")

        stock_info = {
            "Ticker": ticker,
            "Close": round(latest['Close'], 2),
            "RSI": round(latest['RSI'], 2),
            "MACD": round(latest['MACD'], 2),
            "Volume": int(latest['Volume'])
        }

        if matched_count == 4:
            return stock_info, "full"
        elif matched_count == 3:
            return stock_info, "partial"
        else:
            return None, None

    except Exception as e:
        print(f"❌ Error: {e}")
        return None, None

def format_stock_list(title, stock_list):
    message = f"*{title}*\n"
    for stock in stock_list:
        message += f"🔹 `{stock['Ticker']}`  | 💰 {stock['Close']}  | 💹 RSI: {stock['RSI']}\n"
    return message

def run_screener():
    full_matches = []
    partial_matches = []

    for ticker in nifty_100_stocks:
        stock, match_type = analyze_stock(ticker)
        if match_type == "full":
            full_matches.append(stock)
        elif match_type == "partial":
            partial_matches.append(stock)
        time.sleep(1.5)

    if full_matches:
        df_full = pd.DataFrame(full_matches)
        print("\n🎯 FULL MATCH STOCKS:\n", df_full)
        message = format_stock_list("🎯 *Full Match Stocks*", full_matches)
        send_telegram(message)
    else:
        send_telegram("🚫 *No full-match stocks today.*")

    if partial_matches:
        df_partial = pd.DataFrame(partial_matches)
        print("\n🟡 PARTIAL MATCH STOCKS:\n", df_partial)
        message = format_stock_list("🟡 *Partial Match Stocks (3/4)*", partial_matches)
        send_telegram(message)

# 🔁 Entry point
if __name__ == "__main__":
    run_screener()
