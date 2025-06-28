# app/main.py

from fastapi import FastAPI, Form, HTTPException
from typing import Optional
import requests
import os

app = FastAPI()

# ------------------------------------------------------------------------------
# CREDENTIALS
# ------------------------------------------------------------------------------
SUPABASE_URL = "https://lfwgposvyckptsrjkkyx.supabase.co"  # e.g. "https://yourproject.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imxmd2dwb3N2eWNrcHRzcmpra3l4Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc0OTg0MjI3MSwiZXhwIjoyMDY1NDE4MjcxfQ.7Pjsw_HpyE5RHHFshsRT3Ibpn1b6N4CO3F4rIw_GSvc"

TELEGRAM_BOT_TOKEN = "7468828306:AAG6uOChhOSFLZwfhnNMdljQLHTcdPcQTa4"
TELEGRAM_CHAT_ID = "980258123"

# ------------------------------------------------------------------------------
# Send Telegram Message
# ------------------------------------------------------------------------------
def send_telegram_message(text: str) -> bool:
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text
    }
    try:
        response = requests.post(url, data=payload)
        return response.status_code == 200
    except Exception as e:
        print(f"Telegram Error: {e}")
        return False

# ------------------------------------------------------------------------------
# Routes
# ------------------------------------------------------------------------------
@app.get("/")
def root():
    msg = "✅ FastAPI is running. Use /run-screener or /webhook as needed."
    send_telegram_message("🚀 FastAPI deployment was successful!")
    return {"message": msg}

@app.post("/webhook")
def webhook(data: dict):
    print("📩 Webhook received:", data)
    send_telegram_message("⚡ Received webhook event!")
    return {"status": "success"}

@app.get("/run-screener")
def run_screener_api():
    try:
        # Optional: call your screener function here if integrated
        return {"status": "screener ran"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ------------------------------------------------------------------------------
# (Uvicorn Entry Point not needed for Render)
# ------------------------------------------------------------------------------

