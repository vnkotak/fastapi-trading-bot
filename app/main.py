# main.py

from fastapi import FastAPI, Form, HTTPException
import requests
import time
from typing import Optional

# 👇 Add screener import
from screener import run_screener, analyze_stock, fetch_nifty_100
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # You can restrict to StackBlitz domain later
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------------------------------------------------------------------
# YOUR CREDENTIALS HERE
# ------------------------------------------------------------------------------
SUPABASE_URL = "https://lfwgposvyckptsrjkkyx.supabase.co"  # e.g. "https://yourproject.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imxmd2dwb3N2eWNrcHRzcmpra3l4Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc0OTg0MjI3MSwiZXhwIjoyMDY1NDE4MjcxfQ.7Pjsw_HpyE5RHHFshsRT3Ibpn1b6N4CO3F4rIw_GSvc"

TELEGRAM_BOT_TOKEN = "7468828306:AAG6uOChh0SFLZwfhnNMdljQLHTcdPcQTa4"
TELEGRAM_CHAT_ID = "980258123"

# === STRATEGY THRESHOLDS ===
RSI_THRESHOLD = 60
VOLUME_MULTIPLIER = 2.5
MACD_SIGNAL_DIFF = 1.0


# ------------------------------------------------------------------------------
# Telegram Bot - Send Message
# ------------------------------------------------------------------------------
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

# ------------------------------------------------------------------------------
# API Endpoints
# ------------------------------------------------------------------------------

@app.get("/screener-data")
def screener_data():
    full_matches = []

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
        if sum(conditions) == 4:
            full_matches.append(stock)

        time.sleep(0.2)

    return {"stocks": full_matches}

@app.get("/")
def root():
    send_telegram("🚀 FastAPI has been deployed and is live.")
    return {"message": "✅ FastAPI is running. Use /run-screener or /webhook as needed."}

@app.get("/run-screener")
def trigger_screener():
    run_screener()
    return {"status": "✅ Screener executed. Check Telegram for results."}

@app.get("/screener-meta")
def screener_meta():
    tickers = fetch_nifty_100()  # You can hardcode or load from a JSON/CSV
    return {"total": len(tickers), "tickers": tickers}

@app.get("/screener-stock")
def screener_stock(ticker: str):
    result = analyze_stock(ticker)
    return result

@app.post("/webhook")
def webhook(data: dict):
    print("📩 Received webhook!", data)
    send_telegram("📩 Received a webhook event")
    return {"status": "success"}

# ------------------------------------------------------------------------------
# FYERS (Optional) - Commented out for now
# ------------------------------------------------------------------------------
# FYERS_API_KEY = "<FYERS_API_KEY>"
# FYERS_SECRET = "<FYERS_SECRET>"
# FYERS_REDIRECT_URI = "<FYERS_REDIRECT_URI>"
