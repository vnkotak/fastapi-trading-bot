# main.py

from fastapi import FastAPI, Form, HTTPException
import requests
from typing import Optional

# 👇 Add screener import
from screener import run_screener

app = FastAPI()

# ------------------------------------------------------------------------------
# YOUR CREDENTIALS HERE
# ------------------------------------------------------------------------------
SUPABASE_URL = "https://lfwgposvyckptsrjkkyx.supabase.co"  # e.g. "https://yourproject.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imxmd2dwb3N2eWNrcHRzcmpra3l4Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc0OTg0MjI3MSwiZXhwIjoyMDY1NDE4MjcxfQ.7Pjsw_HpyE5RHHFshsRT3Ibpn1b6N4CO3F4rIw_GSvc"

TELEGRAM_BOT_TOKEN = "7468828306:AAG6uOChhOSFLZwfhnNMdljQLHTcdPcQTa4"
TELEGRAM_CHAT_ID = "980258123"

# ------------------------------------------------------------------------------
# Telegram Bot - Send Message
# ------------------------------------------------------------------------------
def send_telegram_message(text: str) -> bool:
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    response = requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": text})
    return response.status_code == 200

# ------------------------------------------------------------------------------
# API Endpoints
# ------------------------------------------------------------------------------

@app.get("/")
def root():
    return {"message": "✅ FastAPI is running. Use /run-screener or /webhook as needed."}

@app.get("/run-screener")
def trigger_screener():
    run_screener()
    return {"status": "✅ Screener executed. Check Telegram for results."}

@app.post("/webhook")
def webhook(data: dict):
    """
    This endpoint is called by TradingView with alerts.
    """
    print("📩 Received webhook!", data)
    send_telegram_message("📩 Received a webhook event")
    return {"status": "success"}

# ------------------------------------------------------------------------------
# FYERS (Optional) - Commented out for now
# ------------------------------------------------------------------------------
# FYERS_API_KEY = "<FYERS_API_KEY>"
# FYERS_SECRET = "<FYERS_SECRET>"
# FYERS_REDIRECT_URI = "<FYERS_REDIRECT_URI>"

from fastapi import Request
from fastapi.middleware.cors import CORSMiddleware

# Optional: allow all CORS (in case you later connect frontend)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 🚀 Notify on startup
@app.on_event("startup")
async def notify_on_startup():
    message = "🚀 Your FastAPI trading bot is *deployed successfully* and is *online!*"
    send_telegram_message(message)
