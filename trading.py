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
