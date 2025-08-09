import pandas as pd
import requests
import joblib
import os
import yfinance as yf

# === Strategy Thresholds ===
RSI_THRESHOLD_MIN = 45
RSI_THRESHOLD_MAX = 65
VOLUME_MULTIPLIER = 2.0
MACD_SIGNAL_DIFF = 1.0
STOCH_K_MAX = 80
WILLR_MAX = -20
SCORE_THRESHOLD = 5.9

SUPABASE_URL = "https://lfwgposvyckptsrjkkyx.supabase.co"  # e.g. "https://yourproject.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imxmd2dwb3N2eWNrcHRzcmpra3l4Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc0OTg0MjI3MSwiZXhwIjoyMDY1NDE4MjcxfQ.7Pjsw_HpyE5RHHFshsRT3Ibpn1b6N4CO3F4rIw_GSvc"
TELEGRAM_BOT_TOKEN = "7468828306:AAG6uOChh0SFLZwfhnNMdljQLHTcdPcQTa4"
TELEGRAM_CHAT_ID = "980258123"

from io import BytesIO
import pickle

def load_ai_model():
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        res = supabase.storage.from_("models").download("model.pkl")
        model_file = BytesIO(res)
        model = pickle.load(model_file)
        return model
    except Exception as e:
        print("⚠️ Failed to load model:", e)
        return None


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
        print("4.1")

        if abs(last['Close'] - last['Open']) < 0.1 * (last['High'] - last['Low']):
            patterns.append("Doji")

        print("4.2")
        body = abs(last['Close'] - last['Open'])
        lower_wick = last['Open'] - last['Low'] if last['Close'] > last['Open'] else last['Close'] - last['Low']
        upper_wick = last['High'] - max(last['Open'], last['Close'])
        if lower_wick > 2 * body and upper_wick < body:
            patterns.append("Hammer")

        print("4.3")
        if (
            second_last['Close'] < second_last['Open'] and
            last['Close'] > last['Open'] and
            last['Close'] > second_last['Open'] and
            last['Open'] < second_last['Close']
        ):
            patterns.append("Engulfing")

        print("4.4")
        return ", ".join(patterns) if patterns else "None"

    except Exception as e:
        print("⚠️ Candle pattern detection failed:", e)
        return "None"


def calculate_additional_indicators(df: pd.DataFrame) -> pd.DataFrame:
    from ta.trend import EMAIndicator, MACD, ADXIndicator
    from ta.momentum import RSIIndicator, StochasticOscillator
    from ta.volatility import BollingerBands, AverageTrueRange

    print("3.1")
    df = df.copy()

    # EMA
    df['EMA_20'] = EMAIndicator(close=df['Close'], window=20).ema_indicator()
    df['EMA_50'] = EMAIndicator(close=df['Close'], window=50).ema_indicator()

    print("3.2")
    # RSI
    df['RSI'] = RSIIndicator(close=df['Close'], window=14).rsi()

    print("3.3")
    # MACD
    macd = MACD(close=df['Close'], window_slow=26, window_fast=12, window_sign=9)
    df['MACD'] = macd.macd()
    df['Signal'] = macd.macd_signal()
    df['MACD_Hist'] = macd.macd_diff()

    print("3.4")
    # Volume average (20-day)
    df['Volume_avg'] = df['Volume'].rolling(window=20).mean()

    print("3.5")
    # Bollinger Bands
    bb = BollingerBands(close=df['Close'], window=20, window_dev=2)
    df['BB_Middle'] = bb.bollinger_mavg()
    df['BB_Upper'] = bb.bollinger_hband()
    df['BB_Lower'] = bb.bollinger_lband()
    df['BB_Width'] = df['BB_Upper'] - df['BB_Lower']

    print("3.6")
    # Prevent division by zero in BB_Position
    bb_range = (df['BB_Upper'] - df['BB_Lower']).replace(0, 1e-9)
    df['BB_Position'] = ((df['Close'] - df['BB_Lower']) / bb_range).clip(0, 1)

    print("3.7")
    # Price Change %
    df['Price_Change_1D'] = df['Close'].pct_change(periods=1) * 100
    df['Price_Change_3D'] = df['Close'].pct_change(periods=3) * 100
    df['Price_Change_5D'] = df['Close'].pct_change(periods=5) * 100

    print("3.8")
    # ATR
    atr = AverageTrueRange(high=df['High'], low=df['Low'], close=df['Close'], window=14)
    df['ATR'] = atr.average_true_range()

    # Stochastic Oscillator
    stoch = StochasticOscillator(high=df['High'], low=df['Low'], close=df['Close'], window=14, smooth_window=3)
    df['Stoch_K'] = stoch.stoch()
    df['Stoch_D'] = stoch.stoch_signal()

    print("3.9")
    # Williams %R
    highest_high = df['High'].rolling(14).max()
    lowest_low = df['Low'].rolling(14).min()
    df['WilliamsR'] = ((highest_high - df['Close']) /
                       (highest_high - lowest_low + 1e-9)) * -100

    print("3.10")
    # ADX
    adx = ADXIndicator(high=df['High'], low=df['Low'], close=df['Close'], window=14)
    df['ADX'] = adx.adx()
    print("3.11")

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

def get_dynamic_score_threshold(market_regime: str) -> float:
    """
    Returns a dynamic threshold for entry score based on current market regime.
    Higher thresholds in bearish markets to reduce risk.
    """
    base = 5.9  # neutral base threshold

    adjustments = {
        "BULL_STRONG": -0.5,
        "BULL_WEAK": -0.2,
        "NEUTRAL": 0.0,
        "BEAR_WEAK": 0.4,
        "BEAR_STRONG": 0.8
    }

    return round(base + adjustments.get(market_regime.upper(), 0.0), 2)
