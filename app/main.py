# main.py

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import requests
import subprocess

app = FastAPI()

# Allow all origins (optional, useful if using frontend later)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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


@app.post("/webhook")
def webhook(data: dict):
    print("Received webhook!", data)
    send_telegram_message("📩 Received a webhook event from TradingView.")
    return {"status": "success"}


@app.get("/run-screener")
def run_screener():
    try:
        result = subprocess.run(["python", "app/screener.py"], capture_output=True, text=True)
        print(result.stdout)
        return {"status": "success", "output": result.stdout}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ------------------------------------------------------------------------------
# Notify via Telegram on App Startup
# ------------------------------------------------------------------------------

@app.on_event("startup")
async def notify_on_startup():
    message = "🚀 Your FastAPI trading bot has *started successfully* and is *live!*"
    send_telegram_message(message)
