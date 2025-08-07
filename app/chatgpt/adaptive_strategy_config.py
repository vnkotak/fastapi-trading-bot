def get_strategy_config(market_regime: str) -> dict:
    base_config = {
        "weights": {
            "RSI": 1.0,
            "MACD": 1.0,
            "Volume": 1.0,
            "Price_vs_EMA": 1.0,
            "ADX": 1.0,
            "Stoch_K": 1.0,
            "WilliamsR": 1.0,
            "Candle_Patterns": 1.0,
        },
        "filters": {
            "RSI_min": 45,
            "RSI_max": 65,
            "MACD_signal_diff_min": 0.0,
            "Volume_multiplier": 1.5,
            "Stoch_K_max": 80,
            "WilliamsR_max": -20,
        },
        "score_threshold": 5.0,
        "strategy": "momentum_breakout",
    }

    multiplier = {
        "STRONG_BULL": 1.2,
        "BULL": 1.0,
        "SIDEWAYS": 0.8,
        "BEAR": 0.6
    }.get(market_regime, 1.0)

    for key in base_config["weights"]:
        base_config["weights"][key] *= multiplier

    base_config["score_threshold"] *= multiplier
    return base_config
