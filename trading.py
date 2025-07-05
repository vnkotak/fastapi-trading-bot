import yfinance as yf
import pandas as pd
from datetime import datetime
from supabase import create_client, Client
import os
from indicators import calculate_rsi, calculate_macd, send_telegram
# === Strategy Thresholds (Moved to indicators.py) ===
from indicators import RSI_THRESHOLD, VOLUME_MULTIPLIER, MACD_SIGNAL_DIFF, SUPABASE_URL, SUPABASE_KEY
from indicators import check_strategy_match

# Initialize Supabase
#SUPABASE_URL = "https://lfwgposvyckptsrjkkyx.supabase.co"  # e.g. "https://yourproject.supabase.co"
#SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imxmd2dwb3N2eWNrcHRzcmpra3l4Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc0OTg0MjI3MSwiZXhwIjoyMDY1NDE4MjcxfQ.7Pjsw_HpyE5RHHFshsRT3Ibpn1b6N4CO3F4rIw_GSvc"
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

from indicators import check_strategy_match

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
        
        match_type = check_strategy_match(latest)
        is_full_match = match_type == "full"

        if not last_trade or last_trade['status'] == "CLOSED":
            if is_full_match:
                execute_trade(ticker, "BUY", float(latest['Close']))

        elif last_trade['status'] == "OPEN":
            buy_price = float(last_trade['price'])
            stop_loss_hit = latest['Close'] < buy_price * 0.97
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
            if stop_loss_hit:
                reason.append("StopLoss>3%")

            if reason:
                print(f"🔻 SELL {ticker} triggered due to: {', '.join(reason)}")
                execute_trade(ticker, "SELL", float(latest['Close']))

    except Exception as e:
        print(f"❌ Error in trading analysis for {ticker}: {e}")
        
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
    
    # ✅ Telegram alert
    emoji = "🟢" if action == "BUY" else "🔴"
    msg = f"{emoji} *{action} EXECUTED* for `{ticker}` at ₹{round(price, 2)}"
    send_telegram(msg)

def get_trades_with_summary(status="open"):
    response = supabase.table("trades").select("*").order("timestamp").execute()
    all_trades = response.data

    # Separate BUY and SELL trades
    buys = [t for t in all_trades if t["action"] == "BUY"]
    sells = [t for t in all_trades if t["action"] == "SELL"]

    matched_sells = set()
    summary = {"total_invested": 0, "current_value": 0, "profit": 0, "profit_pct": 0}
    processed = []

    for buy in buys:
        if status != "all" and buy["status"].lower() != status.lower():
            continue

        buy_price = float(buy["price"])
        final_price = None
        ticker = buy["ticker"]
        profit = 0

        if buy["status"] == "OPEN":
            df = yf.download(ticker, period="1d", interval="1d", progress=False)
            if not df.empty:
                final_price = float(df["Close"].iloc[-1])
        else:
            # Find the first unmatched SELL for this ticker after the BUY
            for sell in sells:
                if (
                    sell["ticker"] == ticker and
                    sell["timestamp"] > buy["timestamp"] and
                    sell["id"] not in matched_sells
                ):
                    final_price = float(sell["price"])
                    matched_sells.add(sell["id"])
                    break

        if final_price is not None:
            profit = final_price - buy_price
            profit_pct = (profit / buy_price) * 100

            summary["total_invested"] += buy_price
            summary["current_value"] += final_price
            summary["profit"] += profit

            processed.append({
                **buy,
                "sell_or_current_price": round(final_price, 2),
                "profit": round(profit, 2),
                "profit_pct": round(profit_pct, 2),
            })

    if summary["total_invested"] > 0:
        summary["profit_pct"] = round((summary["profit"] / summary["total_invested"]) * 100, 2)

    return {"summary": summary, "trades": processed}
