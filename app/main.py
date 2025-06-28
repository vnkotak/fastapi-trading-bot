import yfinance as yf
import pandas as pd
import numpy as np
import time
import requests
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SUPABASE_URL = "https://lfwgposvyckptsrjkkyx.supabase.co"  # e.g. "https://yourproject.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imxmd2dwb3N2eWNrcHRzcmpra3l4Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc0OTg0MjI3MSwiZXhwIjoyMDY1NDE4MjcxfQ.7Pjsw_HpyE5RHHFshsRT3Ibpn1b6N4CO3F4rIw_GSvc"

TELEGRAM_BOT_TOKEN = "7468828306:AAG6uOChhOSFLZwfhnNMdljQLHTcdPcQTa4"
TELEGRAM_CHAT_ID = "980258123"


# === TELEGRAM SETUP ===
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
    return ["HDFCLIFE.NS", "SBILIFE.NS", "SHREECEM.NS", "TORNTPHARM.NS", "TVSMOTOR.NS"]

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

# === SCREENING FUNCTION ===
def analyze_stock(ticker):
    try:
        df = yf.download(ticker, period="6mo", interval="1d", progress=False)

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df.columns.name = None

        if df.empty or any(col not in df.columns for col in ['Close', 'Volume']) or len(df) < 50:
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

@app.get("/screener-data")
def screener_data():
    tickers = fetch_nifty_100()
    results = []
    for ticker in tickers:
        stock = analyze_stock(ticker)
        if stock:
            results.append(stock)
            time.sleep(0.2)
    return {"stocks": results}

@app.get("/")
def root():
    return {"message": "✅ Screener API is live. Use /screener-data."}
