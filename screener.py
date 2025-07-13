import yfinance as yf
import pandas as pd
import time
from indicators import (
    calculate_additional_indicators,
    advanced_strategy_score,
    send_telegram,
    detect_candle_pattern,
    SCORE_THRESHOLD
)

# ------------------------------------------------------------------
# List of stocks (can later be dynamic from NSE CSV)
# ------------------------------------------------------------------
def fetch_nifty_100():
    try:
        return [
            "RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS", "ICICIBANK.NS",
            "TORNTPHARM.NS", "PEL.NS", "GLENMARK.NS", "RAMCOCEM.NS", "MANKIND.NS", "HINDUNILVR.NS"
        ]
    except Exception as e:
        print(f"⚠️ Could not fetch NIFTY 100: {e}")
        return ["RELIANCE.NS", "TCS.NS"]

# ------------------------------------------------------------------
# Analyze a single stock
# ------------------------------------------------------------------
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

        # Attach candle pattern
        df['Candle'] = "None"
        df.at[df.index[-1], 'Candle'] = detect_candle_pattern(df)

        latest = df.iloc[-1]
        previous = df.iloc[-2]

        score = advanced_strategy_score(latest, previous)
        print(f"🧠 {ticker} Strategy Score: {score:.2f}")

        if score < SCORE_THRESHOLD:
            return None

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
            "score": round(score, 2)
        }

    except Exception as e:
        print(f"❌ Error analyzing {ticker}: {e}")
        return None

# ------------------------------------------------------------------
# Run Screener
# ------------------------------------------------------------------
def run_screener():
    matches = []
    tickers = fetch_nifty_100()

    for ticker in tickers:
        stock = analyze_stock(ticker)
        if stock:
            matches.append(stock)
        time.sleep(0.2)

    if matches:
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

if __name__ == "__main__":
    run_screener()
