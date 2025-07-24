import yfinance as yf
import pandas as pd
from datetime import datetime
from dateutil.parser import parse as parse_datetime
from supabase import create_client, Client
import os
import pytz

from indicators import (
    calculate_additional_indicators,
    advanced_strategy_score,
    detect_candle_pattern,
    send_telegram,
    SCORE_THRESHOLD,
    SUPABASE_URL,
    SUPABASE_KEY
)

# Initialize Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_last_trade(ticker):
    response = supabase.table("trades").select("*").eq("ticker", ticker).order("timestamp", desc=True).limit(1).execute()
    if response.data:
        return response.data[0]
    return None

def get_current_price(ticker):
    df = yf.download(ticker, period="1d", interval="1d", progress=False)
    if df.empty:
        return None
    return float(df["Close"].iloc[-1])

def is_market_closed():
    india_tz = pytz.timezone("Asia/Kolkata")
    now_ist = datetime.now(india_tz)
    return now_ist.hour > 15 or (now_ist.hour == 15 and now_ist.minute > 15)

def execute_trade(ticker, action, price, quantity=1, total_invested=None, reason=None, score=None):
    if total_invested is None:
        total_invested = round(price * quantity, 2)

    trade = {
        "ticker": ticker,
        "action": action,
        "price": round(price, 2),
        "quantity": quantity,
        "total_invested": total_invested,
        "timestamp": datetime.utcnow().isoformat(),
        "status": "OPEN" if action == "BUY" else "CLOSED",
    }

    if reason:
        trade["reason"] = reason
    if score and action == "BUY":
        trade["score"] = round(score, 2)

    supabase.table("trades").insert(trade).execute()
    print(f"✅ {action} EXECUTED for {ticker} at ₹{price:.2f} x {quantity} units (₹{total_invested})")

    emoji = "🟢" if action == "BUY" else "🔴"
    msg = (
        f"{emoji} *{action} EXECUTED* for `{ticker}`\n"
        f"📈 Price: ₹{round(price, 2)}\n"
        f"📦 Qty: {quantity}\n"
        f"💰 Total: ₹{total_invested}"
    )
    if reason:
        msg += f"\n📝 Reason: {reason}"
    send_telegram(msg)

def analyze_for_trading(ticker):
    print(f"\n🤖 Trading Analysis: {ticker}")

    if is_market_closed():
        print("⏰ Market closed — skipping trade for", ticker)
        return

    try:
        df = yf.download(ticker, period="3mo", interval="1d", progress=False)

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df.columns.name = None

        df = df[['Open', 'High', 'Low', 'Close', 'Volume']].dropna()
        df = df.astype(float)

        if df.empty or len(df) < 50:
            print("⚠️ Missing data or not enough candles.")
            return

        df = calculate_additional_indicators(df)
        df.dropna(inplace=True)

        df['Candle'] = "None"
        df.at[df.index[-1], 'Candle'] = detect_candle_pattern(df)

        latest = df.iloc[-1]
        previous = df.iloc[-2]
        score, matched_indicators = advanced_strategy_score(latest, previous)

        print(f"🧠 {ticker} Score: {score:.2f}")
        last_trade = get_last_trade(ticker)

        if not last_trade or last_trade['status'] == "CLOSED":
            if score >= SCORE_THRESHOLD:
                latest_price = float(latest['Close'])
                current_price = get_current_price(ticker)
                if not current_price:
                    print("❌ Could not fetch fresh price.")
                    return

                price_diff_pct = abs(latest_price - current_price) / latest_price * 100
                if price_diff_pct > 5:
                    print(f"❌ BUY price deviation too high: {price_diff_pct:.2f}% — skipping {ticker}")
                    return

                MAX_INVEST_PER_TRADE = 5000
                quantity = max(1, int(MAX_INVEST_PER_TRADE // current_price))
                total_invested = round(quantity * current_price, 2)
                reason = f"Score {score} ≥ {SCORE_THRESHOLD} | Pattern: {latest['Candle']}"

                print(f"➡️ Executing BUY: {ticker} at ₹{current_price} | Qty: {quantity}")
                execute_trade(ticker, "BUY", current_price, quantity, total_invested, reason, score)

        elif last_trade['status'] == "OPEN":
            buy_price = float(last_trade['price'])
            current_price = get_current_price(ticker)
            if not current_price:
                print("❌ Could not fetch fresh price for SELL.")
                return

            price_variation_pct = abs(current_price - buy_price) / buy_price * 100
            if price_variation_pct > 25:
                print(f"❌ SELL price variation > 50%: {price_variation_pct:.2f}% — skipping")
                return

            stop_loss_hit = current_price < buy_price * 0.97
            profit_pct = ((current_price - buy_price) / buy_price) * 100

            sell_reasons = []
            indicator_triggers = []

            if latest['RSI'] < 45:
                indicator_triggers.append("RSI<45")
            if latest['MACD'] < latest['Signal']:
                indicator_triggers.append("MACD Bearish")
            if latest['Close'] < latest['EMA_50']:
                indicator_triggers.append("Price<EMA50")

            if len(indicator_triggers) >= 2:
                sell_reasons.extend(indicator_triggers)
            if profit_pct >= 5:
                sell_reasons.append("Profit>5%")
            if stop_loss_hit:
                sell_reasons.append("StopLoss>3%")

            if sell_reasons:
                reason_text = ", ".join(sell_reasons)
                quantity = int(last_trade.get("quantity", 1))
                print(f"➡️ Executing SELL: {ticker} at ₹{current_price} | Qty: {quantity} | Reason: {reason_text}")
                execute_trade(ticker, "SELL", current_price, quantity=quantity, reason=reason_text)

    except Exception as e:
        print(f"❌ Error in trading analysis for {ticker}: {e}")

def get_trades_with_summary(status="open"):
    response = supabase.table("trades").select("*").execute()
    all_trades = response.data

    processed = []
    buy_trades = [t for t in all_trades if t["action"] == "BUY"]

    for trade in buy_trades:
        current_price = None
        sell_price = None
        sell_reason = None
        sell_timestamp = None
        days_held = None

        sell = next(
            (s for s in all_trades if s["action"] == "SELL" and s["ticker"] == trade["ticker"] and s["timestamp"] > trade["timestamp"]),
            None
        )

        if sell:
            sell_price = float(sell["price"])
            sell_reason = sell.get("reason")
            sell_timestamp = sell.get("timestamp")
            try:
                buy_date = parse_datetime(trade["timestamp"])
                sell_date = parse_datetime(sell_timestamp)
            except Exception as e:
                print(f"Invalid timestamp in {trade['ticker']}")
                raise e

            days_held = (sell_date - buy_date).days
            trade["status"] = "CLOSED"
        else:
            current_price = get_current_price(trade["ticker"])
            trade["status"] = "OPEN"

        final_price = sell_price or current_price
        if final_price:
            quantity = trade.get("quantity", 1)
            total_invested = trade.get("total_invested", float(trade["price"]) * quantity)
            current_value = final_price * quantity
            profit = current_value - total_invested
            profit_pct = (profit / total_invested) * 100

            processed.append({
                **trade,
                "sell_or_current_price": round(final_price, 2),
                "current_value": round(current_value, 2),
                "profit": round(profit, 2),
                "profit_pct": round(profit_pct, 2),
                "reason": sell_reason if trade["status"] == "CLOSED" else trade.get("reason"),
                "sell_timestamp": sell_timestamp,
                "days_held": days_held
            })

    if status in ["open", "closed"]:
        filtered = [t for t in processed if t["status"].lower() == status.lower()]
    else:
        filtered = processed

    filtered.sort(key=lambda x: x["sell_timestamp"] if status == "closed" else x["timestamp"], reverse=True)

    summary = {
        "total_invested": 0,
        "current_value": 0,
        "profit": 0,
        "profit_pct": 0,
        "total_buy_trades": len(buy_trades),
        "open_trades": len([t for t in processed if t["status"] == "OPEN"]),
        "closed_trades": len([t for t in processed if t["status"] == "CLOSED"]),
        "winning_trades": 0,
        "winning_pct": 0
    }

    for t in filtered:
        summary["total_invested"] += t.get("total_invested", float(t["price"]) * t.get("quantity", 1))
        summary["current_value"] += t.get("current_value", t["sell_or_current_price"] * t.get("quantity", 1))
        summary["profit"] += t["profit"]

    filtered_winning_trades = [t for t in filtered if t["profit"] > 0]
    summary["winning_trades"] = len(filtered_winning_trades)

    total_considered = (
        summary["open_trades"] if status == "open" else
        summary["closed_trades"] if status == "closed" else
        summary["open_trades"] + summary["closed_trades"]
    )

    summary["winning_pct"] = round((summary["winning_trades"] / total_considered) * 100, 2) if total_considered > 0 else 0

    if summary["total_invested"] > 0:
        summary["profit_pct"] = round((summary["profit"] / summary["total_invested"]) * 100, 2)

    return {"summary": summary, "trades": filtered}
