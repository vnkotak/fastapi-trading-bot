import pandas as pd

def detect_market_regime(nifty_data: dict) -> str:
    close = nifty_data.get("Close")
    ema50 = nifty_data.get("EMA_50")
    ema200 = nifty_data.get("EMA_200")
    bb_pos = nifty_data.get("BB_Pos")

    if not all([close, ema50, ema200]):
        return "UNKNOWN"

    if close > ema50 > ema200 and bb_pos > 0.75:
        return "STRONG_BULL"
    elif close > ema50 > ema200:
        return "BULL"
    elif close < ema50 < ema200:
        return "BEAR"
    else:
        return "SIDEWAYS"
