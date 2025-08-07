from adaptive_strategy_config import get_strategy_config

def score_stock(stock_data: dict, market_regime: str) -> dict:
    config = get_strategy_config(market_regime)
    weights = config["weights"]
    filters = config["filters"]
    score = 0.0
    matched = []

    if filters["RSI_min"] <= stock_data.get("RSI", 0) <= filters["RSI_max"]:
        score += weights["RSI"]
        matched.append("RSI")

    if stock_data.get("MACD_Hist", 0) >= filters["MACD_signal_diff_min"]:
        score += weights["MACD"]
        matched.append("MACD")

    if stock_data.get("Volume/20DayAvg", 1) >= filters["Volume_multiplier"]:
        score += weights["Volume"]
        matched.append("Volume")

    if stock_data.get("Close", 0) > stock_data.get("EMA_50", 0):
        score += weights["Price_vs_EMA"]
        matched.append("Price_vs_EMA")

    if stock_data.get("ADX", 0) >= 20:
        score += weights["ADX"]
        matched.append("ADX")

    if stock_data.get("Stoch_K", 0) <= filters["Stoch_K_max"]:
        score += weights["Stoch_K"]
        matched.append("Stoch_K")

    if stock_data.get("WilliamsR", 0) <= filters["WilliamsR_max"]:
        score += weights["WilliamsR"]
        matched.append("WilliamsR")

    if stock_data.get("Candle", "").lower() in ["doji", "hammer", "bullish_engulfing"]:
        score += weights["Candle_Patterns"]
        matched.append("Candle_Patterns")

    return {
        "score": round(score, 2),
        "matched_indicators": matched,
        "strategy": config["strategy"],
        "threshold": config["score_threshold"]
    }
