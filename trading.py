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
    response = supabase.table("trades").select("*").execute()
    all_trades = response.data

    processed = []
    buy_trades = [t for t in all_trades if t["action"] == "BUY"]

    for trade in buy_trades:
        current_price = None
        sell_price = None

        # Look for matching sell trade
        sell = next(
            (s for s in all_trades if s["action"] == "SELL" and s["ticker"] == trade["ticker"] and s["timestamp"] > trade["timestamp"]),
            None
        )

        if sell:
            sell_price = float(sell["price"])
            trade["status"] = "CLOSED"
        else:
            # Fetch live price if no sell found
            df = yf.download(trade["ticker"], period="1d", interval="1d", progress=False)
            if not df.empty:
                current_price = float(df["Close"].iloc[-1])
            trade["status"] = "OPEN"

        final_price = sell_price or current_price
        if final_price:
            buy_price = float(trade["price"])
            profit = final_price - buy_price
            profit_pct = (profit / buy_price) * 100

            processed.append({
                **trade,
                "sell_or_current_price": round(final_price, 2),
                "profit": round(profit, 2),
                "profit_pct": round(profit_pct, 2),
            })

    # 🔁 Apply status filter
    if status in ["open", "closed"]:
        filtered = [t for t in processed if t["status"].lower() == status.lower()]
    else:
        filtered = processed

    # 📊 Build Summary
    total_invested = sum(float(t["price"]) for t in filtered)
    current_value = sum(float(t["sell_or_current_price"]) for t in filtered)
    total_profit = current_value - total_invested
    profit_pct = round((total_profit / total_invested) * 100, 2) if total_invested > 0 else 0

    closed_trades = [t for t in processed if t["status"] == "CLOSED"]
    open_trades = [t for t in processed if t["status"] == "OPEN"]
    winning_trades = [t for t in processed if t["profit"] > 0]
    total_buy_trades = len(buy_trades)

    summary = {
        "total_invested": round(total_invested, 2),
        "current_value": round(current_value, 2),
        "profit": round(total_profit, 2),
        "profit_pct": profit_pct,
        "total_trades": len(all_trades),
        "total_buy_trades": total_buy_trades,
        "open_trades": len(open_trades),
        "closed_trades": len(closed_trades),
        "winning_trades": len(winning_trades),
        "winning_pct": round((len(winning_trades) / total_buy_trades) * 100, 2) if total_buy_trades else 0,
    }

    return {"summary": summary, "trades": filtered}
