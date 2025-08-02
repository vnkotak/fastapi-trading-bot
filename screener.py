import yfinance as yf
import pandas as pd
import time
from supabase import create_client, Client
import os
from indicators import (
    calculate_additional_indicators,
    advanced_strategy_score,
    send_telegram,
    detect_candle_pattern,
    SCORE_THRESHOLD,
    SUPABASE_URL,
    SUPABASE_KEY
)

# Initialize Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def fetch_nifty_stocks():
    try:
        response = supabase.table("master_stocks") \
            .select("ticker") \
            .eq("status", "Active") \
            .eq("exchange", "NSE") \
            .limit(2999) \
            .execute()

        tickers = [row["ticker"] for row in response.data]
        print(f"✅ Loaded {len(tickers)} tickers from Supabase")
        return tickers
    except Exception as e:
        print(f"❌ Failed to fetch tickers: {e}")
        return []

def analyze_stock(ticker):
    print(f"\n📊 Analyzing: {ticker}")
    try:
        df = yf.download(ticker, period="3mo", interval="1d", progress=False)

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df.columns.name = None

        df = df[['Open', 'High', 'Low', 'Close', 'Volume']].dropna()
        df = df.astype(float)

        if df.empty or len(df) < 50:
            print("⚠️ Not enough data.")
            return None

        df = calculate_additional_indicators(df)
        df.dropna(inplace=True)

        # Prepare Candle Pattern
        df['Candle'] = "None"
        df.at[df.index[-1], 'Candle'] = detect_candle_pattern(df)

        latest = df.iloc[-1]
        previous = df.iloc[-2]

        # --- Pre-Entry Filters ---

        price_change_1d = latest['Price_Change_1D']
        price_change_3d = latest['Price_Change_3D']
        price_change_5d = latest['Price_Change_5D']
        rsi = latest['RSI']
        volume = latest['Volume']
        volume_avg = latest['Volume_avg']
        atr = latest['ATR']

        mean_atr = df['ATR'][-21:-1].mean()  # 20-day ATR average (excluding today)

        # Skip if recent run-up too strong
        if price_change_3d > 5 or price_change_5d > 8:
            print(f"⏳ Skipping {ticker}: recent run too strong (3D={price_change_3d:.2f}%, 5D={price_change_5d:.2f}%)")
            return None

        # Skip if RSI too high
        if rsi > 62:
            print(f"⏳ Skipping {ticker}: RSI too high ({rsi:.2f})")
            return None

        # Skip if volume spike and price spike (possible fakeout)
        if volume > 2.5 * volume_avg and price_change_1d > 7:
            print(f"⏳ Skipping {ticker}: volume and price spike (Vol={volume}, Avg={volume_avg}, PriceChg1D={price_change_1d:.2f}%)")
            return None

        # Skip if ATR today > 1.4 * mean ATR (high volatility day)
        if atr > 1.4 * mean_atr:
            print(f"⏳ Skipping {ticker}: ATR too high today ({atr:.2f} vs avg {mean_atr:.2f})")
            return None

        # Calculate strategy score
        score, matched_indicators = advanced_strategy_score(latest, previous)
        print(f"🧠 {ticker} Strategy Score: {score:.2f}")

        if score < SCORE_THRESHOLD:
            print(f"⏳ Skipping {ticker}: Score below threshold ({score:.2f} < {SCORE_THRESHOLD})")
            return None

        print(f"\n✅ Matched : {ticker}")

        history = df.tail(30).copy()
        history_json = [
            {
                "date": str(idx.date()),
                "close": round(row.Close, 2),
                "ema": round(row.EMA_50, 2),
                "rsi": round(row.RSI, 2),
                "macd": round(row.MACD, 2),
                "signal": round(row.Signal, 2),
                "hist": round(row.MACD_Hist, 2),
                "volume": int(row.Volume),
                "volumeAvg": int(row.Volume_avg),
                "willr": round(row.WilliamsR, 2),
                "atr": round(row.ATR, 2),
                "bb_pos": round(row.BB_Position, 2),
                "priceChange1D": round(row.Price_Change_1D, 2),
                "priceChange3D": round(row.Price_Change_3D, 2),
                "priceChange5D": round(row.Price_Change_5D, 2),
                "stochK": round(row.Stoch_K, 2),
                "stochD": round(row.Stoch_D, 2),
                "signal_trigger": bool(row.get("Signal_Trigger", False)),
                "sell_trigger": bool(row.get("Sell_Trigger", False)),
            }
            for idx, row in history.iterrows()
        ]

        return {
            "ticker": ticker,
            "close": round(latest['Close'], 2),
            "ema": round(latest['EMA_50'], 2),
            "rsi": round(latest['RSI'], 2),
            "macd": round(latest['MACD'], 2),
            "signal": round(latest['Signal'], 2),
            "hist": round(latest['MACD_Hist'], 2),
            "volume": int(latest['Volume']),
            "volumeAvg": int(latest['Volume_avg']),
            "willr": round(latest['WilliamsR'], 2),
            "atr": round(latest['ATR'], 2),
            "bb_pos": round(latest['BB_Position'], 2),
            "priceChange1D": round(latest['Price_Change_1D'], 2),
            "priceChange3D": round(latest['Price_Change_3D'], 2),
            "priceChange5D": round(latest['Price_Change_5D'], 2),
            "stochK": round(latest['Stoch_K'], 2),
            "stochD": round(latest['Stoch_D'], 2),
            "pattern": latest['Candle'],
            "score": round(score, 2),
            "matched_indicators": matched_indicators,
            "history": history_json
        }

    except Exception as e:
        print(f"❌ Error analyzing {ticker}: {e}")
        return None

def run_screener():
    matches = []
    tickers = fetch_nifty_stocks()

    for ticker in tickers:
        stock = analyze_stock(ticker)
        if stock:
            matches.append(stock)
        time.sleep(0.2)

    if matches:
        batch_res = supabase.table("screener_batches").insert({
            "num_matches":len(matches),
            "source":"auto"
        }).execute()
        batch_id = batch_res.data[0]["id"]
        print(f"📦 Created Screener Batch ID: {batch_id}")

        results_payload = [
            {
                "batch_id": batch_id,
                "ticker": stock["ticker"],
                "score": stock["score"],
                "indicators": stock["matched_indicators"]
            }
            for stock in matches
        ]

        supabase.table("screener_results").insert(results_payload).execute()
        print(f"✅ Stored {len(results_payload)} screener results.")

        for stock in matches:
            msg = (
                f"🎯 *{stock['ticker']}*\n"
                f"Price: ₹{stock['close']} | EMA50: {stock['ema']}\n"
                f"RSI: {stock['rsi']} | Williams %R: {stock['willr']}\n"
                f"MACD: {stock['macd']} | Signal: {stock['signal']} | Hist: {stock['hist']}\n"
                f"Volume: {stock['volume']} | Avg: {stock['volumeAvg']}\n"
                f"BB Pos: {stock['bb_pos']} | ATR: {stock['atr']}\n"
                f"% Change: 1D {stock['priceChange1D']}%, 3D {stock['priceChange3D']}%, 5D {stock['priceChange5D']}%\n"
                f"Stoch %K: {stock['stochK']} | %D: {stock['stochD']}\n"
                f"Candle: {stock['pattern']} | Score: {stock['score']}\n"
            )
            send_telegram(msg)
    else:
        send_telegram("🚫 *No stocks matched advanced criteria today.*")

def get_latest_screener_batch():
    try:
        batch_res = supabase.table("screener_batches") \
            .select("id, timestamp") \
            .order("timestamp", desc=True) \
            .limit(1) \
            .execute()

        if not batch_res.data:
            return {"refreshed_at": None, "tickers": []}

        batch = batch_res.data[0]
        batch_id = batch["id"]
        refreshed_at = batch["timestamp"]
        print(f"📦 Latest Screener Batch ID: {batch_id} @ {refreshed_at}")

        result_res = supabase.table("screener_results") \
            .select("ticker") \
            .eq("batch_id", batch_id) \
            .limit(2999) \
            .execute()

        tickers = [row["ticker"] for row in result_res.data]
        return {"refreshed_at": refreshed_at, "tickers": tickers}
    except Exception as e:
        print(f"❌ Failed to fetch latest screener batch: {e}")
        return {"refreshed_at": None, "tickers": []}

if __name__ == "__main__":
    run_screener()
