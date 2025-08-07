# === Strategy Thresholds ===
RSI_THRESHOLD_MIN = 45
RSI_THRESHOLD_MAX = 65
VOLUME_MULTIPLIER = 2.0
MACD_SIGNAL_DIFF = 1.0
STOCH_K_MAX = 80
WILLR_MAX = -20
SCORE_THRESHOLD = 5.9  # Used as final threshold in screener/trading


def advanced_strategy_score(latest, previous):
    score = 0.0
    matched_indicators = []

    # Simplified trend scoring (avoid double counting)
    if latest['Close'] > latest['EMA_20'] > latest['EMA_50']:
        score += 1.0
        matched_indicators.append("price")
    elif latest['EMA_20'] > previous['EMA_20'] and latest['EMA_50'] > previous['EMA_50']:
        score += 0.5
        matched_indicators.append("ema_trend")

    # RSI in range & rising
    if RSI_THRESHOLD_MIN <= latest['RSI'] <= RSI_THRESHOLD_MAX and latest['RSI'] > previous['RSI']:
        score += 1.0
        matched_indicators.append("rsi")

    # Volume surge + price up
    if latest['Volume'] > VOLUME_MULTIPLIER * latest['Volume_avg'] and latest['Close'] > previous['Close']:
        score += 1.0
        matched_indicators.append("volume")

    # MACD bullish momentum
    if latest['MACD'] > latest['Signal'] and latest['MACD_Hist'] > 0 and latest['MACD_Hist'] > previous['MACD_Hist']:
        score += 1.0
        matched_indicators.append("macd")

    # Stoch crossover
    if (latest['Stoch_K'] > latest['Stoch_D'] and
        previous['Stoch_K'] < previous['Stoch_D'] and
        latest['Stoch_K'] < STOCH_K_MAX):
        score += 0.5
        matched_indicators.append("stoch")

    # Williams %R signal
    if latest['WilliamsR'] > previous['WilliamsR'] and latest['WilliamsR'] < WILLR_MAX:
        score += 0.5
        matched_indicators.append("willr")

    # Adjust candle pattern weight conditionally
    pattern = latest.get("Candle", "None")
    price_change_3d = abs(latest.get('Price_Change_3D', 0))
    rsi = latest.get('RSI', 100)

    if ("Hammer" in pattern or "Engulfing" in pattern) and rsi < 60 and price_change_3d < 4:
        score += 0.5
        matched_indicators.append("pattern")
    elif "Doji" in pattern and rsi < 58 and price_change_3d < 4:
        score += 0.25
        matched_indicators.append("pattern")

    return score, matched_indicators
