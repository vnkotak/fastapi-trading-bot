import pandas as pd
import requests
import joblib
import os\import yfinance as yf

# === Strategy Thresholds ===
RSI_THRESHOLD_MIN = 45
RSI_THRESHOLD_MAX = 65
VOLUME_MULTIPLIER = 2.0
MACD_SIGNAL_DIFF = 1.0
STOCH_K_MAX = 80
WILLR_MAX = -20
SCORE_THRESHOLD = 5.9

SUPABASE_URL = "https://lfwgposvyckptsrjkkyx.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
TELEGRAM_BOT_TOKEN = "7468828306:AAG6uOChh0SFLZwfhnNMdljQLHTcdPcQTa4"
TELEGRAM_CHAT_ID = "980258123"

MODEL_PATH = "models/ai_trade_model.pkl"
_ai_model = None

def load_ai_model():
    global _ai_model
    if _ai_model is None:
        if os.path.exists(MODEL_PATH):
            _ai_model = joblib.load(MODEL_PATH)
        else:
            print("⚠️ ML model not found. Skipping prediction step.")
            _ai_model = None
    return _ai_model

def extract_features_for_model(latest):
    return [
        latest['Close'], latest['EMA_20'], latest['EMA_50'],
        latest['RSI'], latest['MACD'], latest['Signal'],
        latest['MACD_Hist'], latest['Volume'], latest['Volume_avg'],
        latest['ATR'], latest['BB_Position'],
        latest['Price_Change_1D'], latest['Price_Change_3D'], latest['Price_Change_5D'],
        latest['Stoch_K'], latest['Stoch_D'], latest['WilliamsR']
    ]

def send_telegram(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message.replace("_", ""),
            "parse_mode": "Markdown"
        }
        response = requests.post(url, json=payload)
        print("📬 Telegram alert sent." if response.status_code == 200 else "❌ Telegram failed:", response.text)
    except Exception as e:
        print("⚠️ Telegram error:", e)

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = delta.where(delta > 0, 0).rolling(window=period).mean()
    loss = -delta.where(delta < 0, 0).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def calculate_macd(series, fast=12, slow=26, signal=9):
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd = ema_fast - ema_slow
    signal_line = macd.ewm(span=signal, adjust=False).mean()
    return macd, signal_line

def detect_candle_pattern(df):
    try:
        last = df.iloc[-1]
        second_last = df.iloc[-2]
        patterns = []

        if abs(last['Close'] - last['Open']) < 0.1 * (last['High'] - last['Low']):
            patterns.append("Doji")

        body = abs(last['Close'] - last['Open'])
        lower_wick = last['Open'] - last['Low'] if last['Close'] > last['Open'] else last['Close'] - last['Low']
        upper_wick = last['High'] - max(last['Open'], last['Close'])
        if lower_wick > 2 * body and upper_wick < body:
            patterns.append("Hammer")

        if (
            second_last['Close'] < second_last['Open'] and
            last['Close'] > last['Open'] and
            last['Close'] > second_last['Open'] and
            last['Open'] < second_last['Close']
        ):
            patterns.append("Engulfing")

        return ", ".join(patterns) if patterns else "None"

    except Exception as e:
        print("⚠️ Candle pattern detection failed:", e)
        return "None"

def calculate_additional_indicators(df):
    rolling_mean = df['Close'].rolling(window=20).mean()
    rolling_std = df['Close'].rolling(window=20).std()

    df['EMA_20'] = df['Close'].ewm(span=20, adjust=False).mean()
    df['EMA_50'] = df['Close'].ewm(span=50, adjust=False).mean()
    df['RSI'] = calculate_rsi(df['Close'])
    df['MACD'], df['Signal'] = calculate_macd(df['Close'])
    df['MACD_Hist'] = df['MACD'] - df['Signal']
    df['Volume_avg'] = df['Volume'].rolling(window=20).mean()
    df['ATR'] = (df['High'] - df['Low']).rolling(window=14).mean()
    df['Upper_BB'] = rolling_mean + 2 * rolling_std
    df['Lower_BB'] = rolling_mean - 2 * rolling_std
    df['BB_Position'] = ((df['Close'] - df['Lower_BB']) / (df['Upper_BB'] - df['Lower_BB'])).clip(0, 1)
    df['Price_Change_1D'] = df['Close'].pct_change(1) * 100
    df['Price_Change_3D'] = df['Close'].pct_change(3) * 100
    df['Price_Change_5D'] = df['Close'].pct_change(5) * 100
    df['Stoch_K'] = ((df['Close'] - df['Low'].rolling(14).min()) /
                     (df['High'].rolling(14).max() - df['Low'].rolling(14).min())) * 100
    df['Stoch_D'] = df['Stoch_K'].rolling(3).mean()
    df['WilliamsR'] = -100 * ((df['High'].rolling(14).max() - df['Close']) /
                              (df['High'].rolling(14).max() - df['Low'].rolling(14).min()))

    return df

def detect_intraday_spike(ticker):
    try:
        df_5min = yf.download(ticker, interval="5m", period="1d", progress=False)
        df_5min = df_5min[['Close']].dropna()
        df_5min['change'] = df_5min['Close'].pct_change() * 100
        recent_spike = df_5min['change'].tail(6).sum() > 3  # 6x5min = 30min
        return recent_spike
    except:
        return False

def ai_strategy_score(latest, previous, df_weekly=None, df_full=None, ticker=None, market_regime="NEUTRAL"):
    regime_multipliers = {
        "BULL_STRONG": 1.2,
        "BULL_WEAK": 1.1,
        "NEUTRAL": 1.0,
        "BEAR_WEAK": 0.8,
        "BEAR_STRONG": 0.6
    }

    regime_multiplier = regime_multipliers.get(market_regime, 1.0)
    score = 0.0
    matched = []
    reasoning = []

    weights = {
        "price_trend": 1.0,
        "ema_trend": 0.6,
        "rsi": 0.9,
        "macd": 1.0,
        "volume": 0.7,
        "stoch": 0.5,
        "willr": 0.5,
        "pattern": 0.4,
        "bb_position": 0.3,
        "price_momentum": 0.5,
        "weekly_confirmation": 1.2,
        "ml_prediction": 1.5
    }

    if latest['Close'] > latest['EMA_20'] > latest['EMA_50']:
        score += weights["price_trend"]
        matched.append("price")
        reasoning.append("Price is above EMA20 and EMA50.")
    elif latest['EMA_20'] > previous['EMA_20'] and latest['EMA_50'] > previous['EMA_50']:
        score += weights["ema_trend"]
        matched.append("ema_trend")
        reasoning.append("EMAs are rising.")

    if RSI_THRESHOLD_MIN <= latest['RSI'] <= RSI_THRESHOLD_MAX:
        score += weights["rsi"]
        matched.append("rsi")
        reasoning.append(f"RSI is healthy: {latest['RSI']:.2f}")

    if latest['MACD'] > latest['Signal'] and latest['MACD_Hist'] > 0:
        score += weights["macd"]
        matched.append("macd")
        reasoning.append("MACD bullish crossover.")

    if latest['Volume'] > 1.5 * latest['Volume_avg']:
        score += weights["volume"]
        matched.append("volume")
        reasoning.append("Volume spike detected.")

    if latest['Stoch_K'] > latest['Stoch_D'] and latest['Stoch_K'] < STOCH_K_MAX:
        score += weights["stoch"]
        matched.append("stoch")
        reasoning.append("Stoch bullish crossover.")

    if latest['WilliamsR'] > -80 and latest['WilliamsR'] < WILLR_MAX:
        score += weights["willr"]
        matched.append("willr")
        reasoning.append("Williams %R recovering.")

    pattern = latest.get("Candle", "None")
    if any(p in pattern for p in ["Hammer", "Engulfing"]):
        score += weights["pattern"]
        matched.append("pattern")
        reasoning.append(f"Candle pattern: {pattern}.")

    if latest['BB_Position'] < 0.85:
        score += weights["bb_position"]
        matched.append("bb_pos")
        reasoning.append("Price has room inside Bollinger Band.")

    if latest['Price_Change_3D'] > 0:
        score += weights["price_momentum"]
        matched.append("momentum")
        reasoning.append("Positive 3-day momentum.")

    if df_weekly is not None and len(df_weekly) > 3:
        latest_w = df_weekly.iloc[-1]
        prev_w = df_weekly.iloc[-2]
        if latest_w['Close'] > latest_w['EMA_20'] > latest_w['EMA_50'] and latest_w['Close'] > prev_w['Close']:
            score += weights["weekly_confirmation"]
            matched.append("weekly")
            reasoning.append("Weekly confirms uptrend.")

    if df_full is not None and latest['ATR'] > 1.5 * df_full['ATR'].iloc[-21:-1].mean():
        score -= 0.5
        reasoning.append("⚠️ ATR spike: high volatility warning.")

    if ticker and detect_intraday_spike(ticker):
        score -= 0.5
        reasoning.append("⚠️ Intraday spike detected in last 30m.")

    model = load_ai_model()
    if model:
        try:
            X = [extract_features_for_model(latest)]
            y_pred = model.predict(X)[0]
            y_prob = model.predict_proba(X)[0][1]
            if y_pred == 1 and y_prob > 0.6:
                score += weights["ml_prediction"]
                matched.append("ml")
                reasoning.append(f"ML model suggests BUY ({y_prob:.2%})")
            else:
                reasoning.append(f"ML model not confident ({y_prob:.2%})")
        except Exception as e:
            reasoning.append(f"⚠️ ML failed: {e}")

    final_score = round(score * regime_multiplier, 2)
    return final_score, matched, "; ".join(reasoning)
