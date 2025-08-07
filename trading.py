import yfinance as yf
import pandas as pd
from datetime import datetime
from dateutil.parser import parse as parse_datetime
from supabase import create_client, Client
import pytz

from indicators import (
    calculate_additional_indicators,
    detect_candle_pattern,
    ai_strategy_score,
    get_dynamic_score_threshold,
    SUPABASE_URL,
    SUPABASE_KEY,
    send_telegram
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

def execute_buy_trade(ticker, price, quantity, total_invested, reason, score, ml_prob, regime, indicators, reasoning, sl, t1, t2, t3):
    trade = {
        "ticker": ticker,
        "action": "BUY",
        "price": round(price, 2),
        "quantity": quantity,
        "total_invested": total_invested,
        "timestamp": datetime.utcnow().isoformat(),
        "status": "OPEN",
        "score": round(score, 2) if score is not None else None,
        "ml_probability": round(ml_prob, 3) if ml_prob else None,
        "market_regime": regime,
        "matched_indicators": indicators,
        "reasoning": reasoning,
        "stop_loss": sl,
        "target_1": t1,
        "target_2": t2,
        "target_3": t3,
        "entry_date": datetime.utcnow().isoformat(),
        "reason": reason
    }
    supabase.table("trades").insert(trade).execute()
    send_telegram(f"🟢 *BUY EXECUTED* for `{ticker}`\n📈 Price: ₹{price:.2f}\n📦 Qty: {quantity}\n💰 Total: ₹{total_invested}\n📝 Reason: {reason}")

def execute_sell_trade(trade_id, ticker, buy_price, current_price, quantity, reason_text, entry_date):
    pnl = (current_price - buy_price) * quantity
    pnl_percent = (pnl / (buy_price * quantity)) * 100
    days_held = (datetime.utcnow() - parse_datetime(entry_date)).days

    update_fields = {
        "status": "CLOSED",
        "exit_price": round(current_price, 2),
        "exit_reason": reason_text,
        "exit_date": datetime.utcnow().isoformat(),
        "days_held": days_held,
        "pnl": round(pnl, 2),
        "pnl_percent": round(pnl_percent, 2),
        "current_price": current_price,
        "unrealized_pnl": round(pnl, 2),
        "position_value": round(current_price * quantity, 2),
        "last_updated": datetime.utcnow().isoformat()
    }

    supabase.table("trades").update(update_fields).eq("id", trade_id).execute()
    send_telegram(f"🔴 *SELL EXECUTED* for `{ticker}`\n📉 Price: ₹{current_price:.2f}\n💰 PnL: ₹{pnl:.2f} ({pnl_percent:.2f}%)\n📅 Days Held: {days_held}\n📝 Reason: {reason_text}")

def analyze_for_trading(ticker, market_regime="NEUTRAL"):
    print(f"\n🤖 Trading Analysis: {ticker}")
    if is_market_closed():
        print("⏰ Market closed — skipping trade for", ticker)
        return

    try:
        df = yf.download(ticker, period="3mo", interval="1d", progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df.columns.name = None
        df = df[['Open', 'High', 'Low', 'Close', 'Volume']].dropna().astype(float)
        if df.empty or len(df) < 50:
            print("⚠️ Missing data or not enough candles.")
            return

        df = calculate_additional_indicators(df)
        df.dropna(inplace=True)
        df['Candle'] = "None"
        df.at[df.index[-1], 'Candle'] = detect_candle_pattern(df)

        latest = df.iloc[-1]
        previous = df.iloc[-2]

        df_weekly = yf.download(ticker, interval="1wk", period="6mo", progress=False)
        if not df_weekly.empty:
            df_weekly = calculate_additional_indicators(df_weekly)

        score, matched_indicators, reasoning = ai_strategy_score(
            latest, previous, df_weekly=df_weekly, df_full=df, ticker=ticker, market_regime=market_regime
        )
        dynamic_threshold = get_dynamic_score_threshold(market_regime)
        print(f"🧠 {ticker} Score: {score:.2f} | Threshold: {dynamic_threshold}")

        last_trade = get_last_trade(ticker)

        if not last_trade or last_trade['status'].lower() == "closed":
            if score >= dynamic_threshold:
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
                reason = f"Score {score} ≥ {dynamic_threshold} | Pattern: {latest['Candle']}"
                atr = latest['ATR']
                stop_loss = round(current_price - 1.2 * atr, 2)
                target_1 = round(current_price + 1.5 * atr, 2)
                target_2 = round(current_price + 2.0 * atr, 2)
                target_3 = round(current_price + 3.0 * atr, 2)

                print(f"➡️ Executing BUY: {ticker} at ₹{current_price} | Qty: {quantity}")
                execute_buy_trade(
                    ticker, current_price, quantity, total_invested,
                    reason, score, latest.get("ML_Prob"), market_regime,
                    matched_indicators, reasoning, stop_loss, target_1, target_2, target_3
                )

        elif last_trade['status'].lower() == "open":
            buy_price = float(last_trade['price'])
            current_price = get_current_price(ticker)
            if not current_price:
                print("❌ Could not fetch fresh price for SELL.")
                return

            price_variation_pct = abs(current_price - buy_price) / buy_price * 100
            if price_variation_pct > 50:
                print(f"❌ SELL price variation > 50%: {price_variation_pct:.2f}% — skipping")
                return

            stop_loss = last_trade.get("stop_loss", buy_price * 0.97)
            target_1 = last_trade.get("target_1")
            target_2 = last_trade.get("target_2")
            target_3 = last_trade.get("target_3")
            atr = latest.get("ATR", 0)
            entry_date = last_trade.get("entry_date") or last_trade.get("timestamp")

            sell_reasons = []
            if current_price <= stop_loss:
                sell_reasons.append("Hit Stop Loss")

            if target_3 and current_price >= target_3:
                if latest['RSI'] < 55 or latest['MACD'] < latest['Signal'] or latest['Close'] < latest['EMA_20']:
                    sell_reasons.append("Exiting after Target 3")
                else:
                    new_target_4 = round(current_price + 1.5 * atr, 2)
                    new_target_5 = round(current_price + 2.5 * atr, 2)
                    supabase.table("trades").update({"target_2": target_3, "target_3": new_target_4}).eq("id", last_trade["id"]).execute()
                    print(f"📈 Extending targets for {ticker} → T3: ₹{new_target_4}, T4: ₹{new_target_5}")
                    return

            elif target_2 and current_price >= target_2:
                if latest['RSI'] < 55 or latest['MACD'] < latest['Signal']:
                    sell_reasons.append("Exiting at Target 2 due to weakening")
                else:
                    return

            elif target_1 and current_price >= target_1:
                if latest['RSI'] < 50 or latest['MACD'] < latest['Signal'] or latest['Close'] < latest['EMA_50']:
                    sell_reasons.append("Weakness at Target 1")
                else:
                    return

            if not sell_reasons:
                print("🟡 Holding — No exit conditions met.")
                return

            reason_text = ", ".join(sell_reasons)
            quantity = int(last_trade.get("quantity", 1))
            print(f"➡️ Executing SELL: {ticker} at ₹{current_price} | Qty: {quantity} | Reason: {reason_text}")
            execute_sell_trade(last_trade["id"], ticker, buy_price, current_price, quantity, reason_text, entry_date)

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

