import yfinance as yf
import pandas as pd
import numpy as np
import time
import requests

from indicators import (
    calculate_rsi, calculate_macd, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID,
    RSI_THRESHOLD, VOLUME_MULTIPLIER, MACD_SIGNAL_DIFF, check_strategy_match, send_telegram
)


def fetch_nifty_100():
    try:
        return ["RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS", "ICICIBANK.NS", "TORNTPHARM.NS", "PEL.NS", "GLENMARK.NS", "RAMCOCEM.NS", "MANKIND.NS", "HINDUNILVR.NS"]
    except Exception as e:
        print(f"⚠️ Could not fetch NIFTY 100 from NSE: {e}")
        return ["RELIANCE.NS", "TCS.NS"]


def calculate_additional_indicators(df):
    df['EMA_50'] = df['Close'].ewm(span=50, adjust=False).mean()
    df['RSI'] = calculate_rsi(df['Close'])
    df['MACD'], df['Signal'] = calculate_macd(df['Close'])
    df['MACD_Hist'] = df['MACD'] - df['Signal']
    df['Volume_avg'] = df['Volume'].rolling(window=20).mean()

    high14 = df['High'].rolling(window=14).max()
    low14 = df['Low'].rolling(window=14).min()
    df['Williams_%R'] = -100 * ((high14 - df['Close']) / (high14 - low14))

    df['ATR'] = (df['High'] - df['Low']).rolling(window=14).mean()
    df['Upper_BB'] = df['Close'].rolling(20).mean() + 2 * df['Close'].rolling(20).std()
    df['Lower_BB'] = df['Close'].rolling(20).mean() - 2 * df['Close'].rolling(20).std()
    # df['BB_Position'] = ((df['Close'] - df['Lower_BB']) / (df['Upper_BB'] - df['Lower_BB'])).clip(0, 1)

    df['Price_Change_1D'] = df['Close'].pct_change(1) * 100
    df['Price_Change_3D'] = df['Close'].pct_change(3) * 100
    df['Price_Change_5D'] = df['Close'].pct_change(5) * 100

    df['Stoch_K'] = ((df['Close'] - df['Low'].rolling(14).min()) / (df['High'].rolling(14).max() - df['Low'].rolling(14).min())) * 100
    df['Stoch_D'] = df['Stoch_K'].rolling(3).mean()
    return df


def analyze_stock(ticker):
    print(f"\n📊 Analyzing: {ticker}")
    try:
        df = yf.download(ticker, period="3mo", interval="1d", progress=False)
        if df.empty or any(col not in df.columns for col in ['Close', 'Volume']) or len(df) < 50:
            print("⚠️ Missing data or columns")
            return None

        df = calculate_additional_indicators(df)
        df['Signal_Trigger'] = (
            (df['Close'] > df['EMA_50']) &
            (df['RSI'] > 55) &
            (df['MACD'] > df['Signal']) &
            (df['Volume'] > 1.2 * df['Volume_avg'])
        )
        df.dropna(inplace=True)

        latest = df.iloc[-1]
        match_type = check_strategy_match(latest)
        if match_type is None:
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
            "willr": round(latest['Williams_%R'], 2),
            "atr": round(latest['ATR'], 2),
            "bb_pos": round(latest['BB_Position'], 2),
            "priceChange1D": round(latest['Price_Change_1D'], 2),
            "priceChange3D": round(latest['Price_Change_3D'], 2),
            "priceChange5D": round(latest['Price_Change_5D'], 2),
            "stochK": round(latest['Stoch_K'], 2),
            "stochD": round(latest['Stoch_D'], 2),
            "match_type": match_type
        }

    except Exception as e:
        print(f"❌ Error for {ticker}: {e}")
        return None


def run_screener():
    full_matches = []
    partial_matches = []
    tickers = fetch_nifty_100()

    for ticker in tickers:
        stock = analyze_stock(ticker)
        if not stock:
            continue

        latest = stock
        conditions = [
            latest["close"] > latest["ema"],
            latest["rsi"] > RSI_THRESHOLD,
            latest["macd"] > latest["signal"] + MACD_SIGNAL_DIFF,
            latest["volume"] > VOLUME_MULTIPLIER * latest["volumeAvg"]
        ]
        matched_count = sum(conditions)

        if matched_count == 4:
            full_matches.append(stock)
        elif matched_count == 3:
            partial_matches.append(stock)

        time.sleep(0.2)

    for stock in full_matches:
        msg = (
            f"🎯 *{stock['ticker']}*\n"
            f"Price: ₹{stock['close']}  | EMA50: {stock['ema']}\n"
            f"RSI: {stock['rsi']} | Williams %R: {stock['willr']}\n"
            f"MACD: {stock['macd']} | Signal: {stock['signal']} | Hist: {stock['hist']}\n"
            f"Volume: {stock['volume']} | Avg: {stock['volumeAvg']}\n"
            f"BB Pos: {stock['bb_pos']}%  | ATR: {stock['atr']}\n"
            f"% Change 1D: {stock['priceChange1D']}%, 3D: {stock['priceChange3D']}%, 5D: {stock['priceChange5D']}%\n"
            f"Stoch %K: {stock['stochK']} | %D: {stock['stochD']}\n"
        )
        send_telegram(msg)

    if not full_matches:
        send_telegram("🚫 *No full-match stocks today.*")

    if partial_matches:
        partial_msg = "🟡 *Partial Matches (3/4)*:\n" + \
            "\n".join([f"🔹 `{s['ticker']}`  | 💰 ₹{s['close']}  | RSI: {s['rsi']}" for s in partial_matches])
        send_telegram(partial_msg)


if __name__ == "__main__":
    run_screener()
