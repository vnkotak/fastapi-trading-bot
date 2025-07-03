import yfinance as yf
import pandas as pd
from datetime import datetime
from supabase import create_client, Client
import os
from indicators import calculate_rsi, calculate_macd


# Initialize Supabase
SUPABASE_URL = "https://lfwgposvyckptsrjkkyx.supabase.co"  # e.g. "https://yourproject.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imxmd2dwb3N2eWNrcHRzcmpra3l4Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc0OTg0MjI3MSwiZXhwIjoyMDY1NDE4MjcxfQ.7Pjsw_HpyE5RHHFshsRT3Ibpn1b6N4CO3F4rIw_GSvc"
#SUPABASE_URL = os.environ.get("SUPABASE_URL")
#SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_last_trade(ticker):
    response = supabase.table("trades").select("*").eq("ticker", ticker).order("timestamp", desc=True).limit(1).execute()
    if response.data:
        return response.data[0]
    return None

def execute_trade(ticker, action, price):
    trade = {
        "ticker": ticker,
        "action": action,
        "price": price,
        "timestamp": datetime.utcnow().isoformat(),
        "status": "OPEN" if action == "BUY" else "CLOSED"
    }
    supabase.table("trades").insert(trade).execute()
    print(f"✅ {action} EXECUTED for {ticker} at {price}")

def analyze_for_trading(ticker):
    print(f"\n🤖 Trading Analysis: {ticker}")
    try:
        df = yf.download(ticker, period="3mo", interval="1d", progress=False)

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df.columns.name = None

        if df.empty or any(col not in df.columns for col in ['Close', 'Volume']) or len(df) < 50:
            print("⚠️ Missing data or columns")
            return

        df['EMA_50'] = df['Close'].ewm(span=50, adjust=False).mean()
        df['RSI'] = calculate_rsi(df['Close'])
        df['MACD'], df['Signal'] = calculate_macd(df['Close'])
        df['Volume_avg'] = df['Volume'].rolling(window=20).mean()

        df.dropna(inplace=True)
        latest = df.iloc[-1]
        last_trade = get_last_trade(ticker)

        if not last_trade:
            # No previous trade, check for Buy
            if (
                latest['Close'] > latest['EMA_50'] and
                latest['RSI'] > 55 and
                latest['MACD'] > latest['Signal']
            ):
                execute_trade(ticker, "BUY", float(latest['Close']))

        elif last_trade['status'] == "OPEN":
            buy_price = float(last_trade['price'])
            profit_pct = ((latest['Close'] - buy_price) / buy_price) * 100

            reason = []
            if latest['RSI'] < 45:
                reason.append("RSI<45")
            if latest['MACD'] < latest['Signal']:
                reason.append("MACD Bearish")
            if latest['Close'] < latest['EMA_50']:
                reason.append("Price<EMA50")
            if profit_pct >= 10:
                reason.append("Profit>10%")

            if reason:
                print(f"🔻 SELL {ticker} triggered due to: {', '.join(reason)}")
                execute_trade(ticker, "SELL", float(latest['Close']))

    except Exception as e:
        print(f"❌ Error in trading analysis for {ticker}: {e}")
