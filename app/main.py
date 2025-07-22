# main.py

from fastapi import FastAPI, Form, HTTPException
import requests
import time
import asyncio
from typing import Optional
from trading import analyze_for_trading, get_trades_with_summary
from indicators import send_telegram
from screener import run_screener, analyze_stock, fetch_nifty_stocks
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()
print("✅ FastAPI app created")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # You can restrict to StackBlitz domain later
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------------------------------------------------------------------
# Constants
# ------------------------------------------------------------------------------
RSI_THRESHOLD = 60
VOLUME_MULTIPLIER = 2.5
MACD_SIGNAL_DIFF = 1.0

# ------------------------------------------------------------------------------
# Helper for Screener Data (Non-blocking)
# ------------------------------------------------------------------------------
def generate_screener_data():
    full_matches = []

    tickers = fetch_nifty_stocks()
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

# ------------------------------------------------------------------------------
# API Endpoints
# ------------------------------------------------------------------------------

@app.get("/screener-data")
async def screener_data():
    return await asyncio.to_thread(generate_screener_data)


@app.get("/")
def root():
    send_telegram("🚀 FastAPI has been deployed and is live.")
    return {"message": "✅ FastAPI is running. Use /run-screener or /webhook as needed."}


@app.get("/run-screener")
def trigger_screener():
    run_screener()
    return {"status": "✅ Screener executed. Check Telegram for results."}


@app.get("/screener-meta")
async def screener_meta():
    print(f"🔍 Screener Meta Initiated")
    tickers = await asyncio.to_thread(fetch_nifty_stocks)
    return {"tickers": tickers}

@app.get("/screener-stock")
async def screener_stock(ticker: str):
    print(f"🔍 Fetching screener data for {ticker}")
    return await asyncio.to_thread(analyze_stock, ticker)


@app.post("/webhook")
def webhook(data: dict):
    print("📩 Received webhook!", data)
    send_telegram("📩 Received a webhook event")
    return {"status": "success"}


@app.get("/run-trades")
def run_trading_strategy():
    results = []
    tickers = fetch_nifty_stocks()

    for ticker in tickers:
        try:
            analyze_for_trading(ticker)
            results.append({"ticker": ticker, "status": "processed"})
        except Exception as e:
            results.append({"ticker": ticker, "status": f"error - {str(e)}"})

    return {"message": "Trading logic executed", "results": results}

@app.get("/ping")
def ping():
    print("Shree Ganeshay Namah! Jai Bhavani Maa! Jai Meladi Maa! Jai Surapura Dada! Om Namah Sivay!")
    return {"status": "ok"}

@app.get("/screener-latest")
def screener_latest():
    print("Fetch latest stocks from Screener")
    return get_latest_screener_batch()

@app.get("/trades-summary")
def get_trades_summary(status: str = "open"):
    try:
        result = get_trades_with_summary(status)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
