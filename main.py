from fastapi import FastAPI, Request
import httpx
import os

app = FastAPI()

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()
    symbol = data.get("symbol", "UNKNOWN")
    signal = data.get("signal", "UNKNOWN")
    price = data.get("price", "N/A")

    msg = f"📈 Symbol: {symbol}\n📉 Signal: {signal}\n💰 Price: {price}"
    await send_telegram_message(msg)
    return {"status": "received"}

async def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    async with httpx.AsyncClient() as client:
        await client.post(url, data=payload)