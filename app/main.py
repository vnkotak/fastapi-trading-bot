# main.py

from fastapi import FastAPI, Form, HTTPException
import requests
from typing import Optional

app = FastAPI()


# ------------------------------------------------------------------------------
# YOUR CREDENTIALS HERE
# ------------------------------------------------------------------------------
SUPABASE_URL = "https://lfwgposvyckptsrjkkyx.supabase.co"  # e.g. "https://yourproject.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imxmd2dwb3N2eWNrcHRzcmpra3l4Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc0OTg0MjI3MSwiZXhwIjoyMDY1NDE4MjcxfQ.7Pjsw_HpyE5RHHFshsRT3Ibpn1b6N4CO3F4rIw_GSvc"

TELEGRAM_BOT_TOKEN = "7468828306:AAG6uOChhOSFLZwfhnNMdljQLHTcdPcQTa4"
TELEGRAM_CHAT_ID = "980258123"

# Fyers (Optional) - Currently Commented Out
# FYERS_API_KEY = "<FYERS_API_KEY>"
# FYERS_SECRET = "<FYERS_SECRET>"
# FYERS_REDIRECT_URI = "<FYERS_REDIRECT_URI>"


# ------------------------------------------------------------------------------
# Database Connection (Example)
# ------------------------------------------------------------------------------
# Uncomment if you wish to connect to Supabase
# from supersupabase import SupabaseClient
#
# db = SupabaseClient(SUPABASE_URL, SUPABASE_KEY)


# ------------------------------------------------------------------------------
# Telegram Bot - Send Message
# ------------------------------------------------------------------------------
def send_telegram_message(text: str) -> bool:
    url = f"https://api.telegram.org/bot7468828306:AAG6uOChhOSFLZwfhnNMdljQLHTcdPcQTa4/sendMessage"
    response = requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": text})
    return response.status_code == 200


# ------------------------------------------------------------------------------
# API Endpoints
# ------------------------------------------------------------------------------
@app.post("/webhook")
def webhook(data: dict):
    """
    This endpoint is called by TradingView with alerts.
    """
    # Handle the webhook event here
    print("Received webhook!", data)

    # Perform notifications
    send_telegram_message("Received a webhook event")

    return {"status": "success"}

# ------------------------------------------------------------------------------
# Run with: uvicorn main:app --reload
# ------------------------------------------------------------------------------
# If you deploy to rendered or other services, follow their instructions.
# ------------------------------------------------------------------------------
