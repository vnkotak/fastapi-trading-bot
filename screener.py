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
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
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

# === DYNAMIC STOCK FETCHING ===
def fetch_nifty_100():
    try:
        return [
            "RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS", "ICICIBANK.NS"
        ]
    except Exception as e:
        print(f"⚠️ Could not fetch NIFTY 100 from NSE: {e}")
        return [
            "RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS", "ICICIBANK.NS"
        ]

# === INDICATOR CALCULATIONS ===
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

# === STRATEGY THRESHOLDS ===
RSI_THRESHOLD = 60
VOLUME_MULTIPLIER = 2.5
MACD_SIGNAL_DIFF = 1.0

# === SCREENING FUNCTION ===
def analyze_stock(ticker):
    print(f"\n📊 Analyzing: {ticker}")
    try:
        df = yf.download(ticker, period="3mo", interval="1d", progress=False)

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df.columns.name = None

        if df.empty or any(col not in df.columns for col in ['Close', 'Volume']) or len(df) < 50:
            print("⚠️ Missing data or columns")
            return None

        df['EMA_50'] = df['Close'].ewm(span=50, adjust=False).mean()
        df['RSI'] = calculate_rsi(df['Close'])
        df['MACD'], df['Signal'] = calculate_macd(df['Close'])
        df['Volume_avg'] = df['Volume'].rolling(window=20).mean()
        df['Signal_Trigger'] = (
            (df['Close'] > df['EMA_50']) &
            (df['RSI'] > 55) &
            (df['MACD'] > df['Signal']) &
            (df['Volume'] > 1.2 * df['Volume_avg'])
        )

        df.dropna(inplace=True)

        latest = df.iloc[-1]
        history = df.tail(30).copy()
        history_json = [
            {
                "date": str(idx.date()),
                "close": round(row.Close, 2),
                "ema": round(row.EMA_50, 2),
                "rsi": round(row.RSI, 2),
                "macd": round(row.MACD, 2),
                "signal": round(row.Signal, 2),
                "volume": int(row.Volume),
                "volumeAvg": int(row.Volume_avg),
                "signal_trigger": bool(row.Signal_Trigger)
            }
            for idx, row in history.iterrows()
        ]

        stock_info = {
            "ticker": ticker,
            "close": round(latest['Close'], 2),
            "rsi": round(latest['RSI'], 2),
            "macd": round(latest['MACD'], 2),
            "volume": int(latest['Volume']),
            "history": history_json
        }

        return stock_info

    except Exception as e:
        print(f"❌ Error for {ticker}: {e}")
        return None

# === FORMAT & SEND RESULTS ===
def format_stock_list(title, stock_list):
    message = f"*{title}*\n"
    for stock in stock_list:
        message += f"🔹 `{stock['ticker']}`  | 💰 {stock['close']}  | 💹 RSI: {stock['rsi']}\n"
    return message

def run_screener():
    full_matches = []
    partial_matches = []

    tickers = fetch_nifty_100()
    for ticker in tickers:
        stock = analyze_stock(ticker)
        if not stock:
            continue

        latest = stock["history"][-1]
        conditions = [
            latest["close"] > latest["ema"],
            latest["rsi"] > RSI_THRESHOLD,
            latest["macd"] > latest["signal"] + MACD_SIGNAL_DIFF,
            latest["volume"] > VOLUME_MULTIPLIER * latest["volumeAvg"]
        ]
        matched_count = sum(conditions)

        if matched_count == 4:
            full_matches.append(stock)
        elif matched_count == 3:
            partial_matches.append(stock)

        time.sleep(0.2)

    if full_matches:
        message = format_stock_list("🎯 *Full Match Stocks*", full_matches)
        send_telegram(message)
    else:
        send_telegram("🚫 *No full-match stocks today.*")

    if partial_matches:
        message = format_stock_list("🟡 *Partial Match Stocks (3/4)*", partial_matches)
        send_telegram(message)

# === RUN ===
if __name__ == "__main__":
    run_screener()
