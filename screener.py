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
    return [
        "ADANIENT.NS", "ADANIGREEN.NS", "ADANIPORTS.NS", "ADANIPOWER.NS", "AMBUJACEM.NS",
        "APOLLOHOSP.NS", "ASIANPAINT.NS", "AXISBANK.NS", "BAJAJ-AUTO.NS", "BAJAJFINSV.NS",
        "BAJFINANCE.NS", "BANDHANBNK.NS", "BANKBARODA.NS", "BEL.NS", "BERGEPAINT.NS",
        "BHARTIARTL.NS", "BPCL.NS", "BRITANNIA.NS", "CIPLA.NS", "COALINDIA.NS",
        "COLPAL.NS", "DABUR.NS", "DIVISLAB.NS", "DLF.NS", "DRREDDY.NS",
        "EICHERMOT.NS", "GAIL.NS", "GLAND.NS", "GODREJCP.NS", "GRASIM.NS",
        "HAVELLS.NS", "HCLTECH.NS", "HDFC.NS", "HDFCBANK.NS", "HDFCLIFE.NS",
        "HEROMOTOCO.NS", "HINDALCO.NS", "HINDUNILVR.NS", "ICICIBANK.NS", "IDFCFIRSTB.NS",
        "IGL.NS", "INDIGO.NS", "INDUSINDBK.NS", "INFY.NS", "IOC.NS",
        "ITC.NS", "JINDALSTEL.NS", "JSWSTEEL.NS", "KOTAKBANK.NS", "LT.NS",
        "LTI.NS", "LTTS.NS", "M&M.NS", "MARICO.NS", "MARUTI.NS",
        "MOTHERSUMI.NS", "MPHASIS.NS", "MRF.NS", "MUTHOOTFIN.NS", "NAUKRI.NS",
        "NESTLEIND.NS", "NTPC.NS", "ONGC.NS", "PAGEIND.NS", "PEL.NS",
        "PETRONET.NS", "PFC.NS", "PIDILITIND.NS", "PIIND.NS", "PNB.NS",
        "POWERGRID.NS", "RECLTD.NS", "RELIANCE.NS", "SAIL.NS", "SBILIFE.NS",
        "SBIN.NS", "SHREECEM.NS", "SIEMENS.NS", "SRF.NS", "SUNPHARMA.NS",
        "TATACHEM.NS", "TATACONSUM.NS", "TATAMOTORS.NS", "TATAPOWER.NS", "TATASTEEL.NS",
        "TCS.NS", "TECHM.NS", "TITAN.NS", "TORNTPHARM.NS", "TRENT.NS",
        "TVSMOTOR.NS", "UBL.NS", "ULTRACEMCO.NS", "UPL.NS", "VEDL.NS",
        "VOLTAS.NS", "WIPRO.NS", "ZEEL.NS"
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

def run_screener():
    return screener_data()

@app.get("/")
def root():
    return {"message": "✅ Screener API is live. Use /screener-data."}
