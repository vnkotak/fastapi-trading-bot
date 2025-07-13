import pandas as pd
import requests

# === Strategy Thresholds ===
RSI_THRESHOLD_MIN = 45
RSI_THRESHOLD_MAX = 65
VOLUME_MULTIPLIER = 2.0
MACD_SIGNAL_DIFF = 1.0
STOCH_K_MAX = 80
WILLR_MAX = -20
SCORE_THRESHOLD = 3.9  # Minimum score to qualify as Buy

# === Common Keys ===
SUPABASE_URL = "https://lfwgposvyckptsrjkkyx.supabase.co"  # e.g. "https://yourproject.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imxmd2dwb3N2eWNrcHRzcmpra3l4Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc0OTg0MjI3MSwiZXhwIjoyMDY1NDE4MjcxfQ.7Pjsw_HpyE5RHHFshsRT3Ibpn1b6N4CO3F4rIw_GSvc"
TELEGRAM_BOT_TOKEN = "7468828306:AAG6uOChh0SFLZwfhnNMdljQLHTcdPcQTa4"
TELEGRAM_CHAT_ID = "980258123"

# ------------------------------------------------------------------------------
# Telegram Bot - Send Message
# ------------------------------------------------------------------------------
def send_telegram(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "Markdown"
        }
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            print("📬 Telegram alert sent.")
        else:
            print("❌ Telegram failed:", response.text)
    except Exception as e:
        print("⚠️ Telegram error:", e)

# ------------------------------------------------------------------------------
# Indicator Calculations
# ------------------------------------------------------------------------------
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

# ------------------------------------------------------------------------------
# Candle Pattern Detection (Manual)
# ------------------------------------------------------------------------------
def detect_candle_pattern(df):
    try:
        last = df.iloc[-1]
        second_last = df.iloc[-2]

        patterns = []

        # Doji
        if abs(last['Close'] - last['Open']) < 0.1 * (last['High'] - last['Low']):
            patterns.append("Doji")

        # Hammer
        body = abs(last['Close'] - last['Open'])
        lower_wick = last['Open'] - last['Low'] if last['Close'] > last['Open'] else last['Close'] - last['Low']
        upper_wick = last['High'] - max(last['Open'], last['Close'])
        if lower_wick > 2 * body and upper_wick < body:
            patterns.append("Hammer")

        # Bullish Engulfing
        if (
            second_last['Close'] < second_last['Open'] and  # Red candle
            last['Close'] > last['Open'] and               # Green candle
            last['Close'] > second_last['Open'] and
            last['Open'] < second_last['Close']
        ):
            patterns.append("Engulfing")

        return ", ".join(patterns) if patterns else "None"

    except Exception as e:
        print("⚠️ Candle pattern detection failed:", e)
        return "None"

# ------------------------------------------------------------------------------
# Shared Indicator Preparation Logic
# ------------------------------------------------------------------------------
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

# ------------------------------------------------------------------------------
# Scoring-based Strategy Logic
# ------------------------------------------------------------------------------
def advanced_strategy_score(latest, previous):
    score = 0.0

    # 1. Price above EMA_20 and EMA_50
    if latest['Close'] > latest['EMA_20'] > latest['EMA_50']:
        score += 1.0

    # 2. EMA_20 and EMA_50 rising
    if latest['EMA_20'] > previous['EMA_20']:
        score += 0.5
    if latest['EMA_50'] > previous['EMA_50']:
        score += 0.5

    # 3. RSI between 45 and 65 and rising
    if RSI_THRESHOLD_MIN <= latest['RSI'] <= RSI_THRESHOLD_MAX and latest['RSI'] > previous['RSI']:
        score += 1.0

    # 4. Volume spike and up-close day
    if latest['Volume'] > VOLUME_MULTIPLIER * latest['Volume_avg'] and latest['Close'] > previous['Close']:
        score += 1.0

    # 5. MACD bullish crossover and histogram increasing
    if latest['MACD'] > latest['Signal'] and latest['MACD_Hist'] > 0 and latest['MACD_Hist'] > previous['MACD_Hist']:
        score += 1.0

    # 6. Stochastic bullish crossover and not overbought
    if (latest['Stoch_K'] > latest['Stoch_D'] and previous['Stoch_K'] < previous['Stoch_D'] and latest['Stoch_K'] < STOCH_K_MAX):
        score += 0.5

    # 7. Williams %R rising from lower zone
    if (latest['WilliamsR'] > previous['WilliamsR'] and latest['WilliamsR'] < WILLR_MAX):
        score += 0.5

    # 8. Candle Pattern
    pattern = latest.get("Candle", "None")
    if "Hammer" in pattern or "Engulfing" in pattern:
        score += 1.0
    elif "Doji" in pattern:
        score += 0.5

    return score
