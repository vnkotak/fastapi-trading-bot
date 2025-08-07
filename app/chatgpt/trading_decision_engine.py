from market_regime_detector import detect_market_regime
from strategy_scoring import score_stock
from ml_predictor import predict_success_probability
from database import store_trade

def execute_trade_decision(stock_symbol: str, indicator_data: dict, timestamp: str):
    regime = detect_market_regime(indicator_data.get("NIFTY", {}))
    score_result = score_stock(indicator_data, regime)
    ml_prob = predict_success_probability(indicator_data)

    decision = "BUY" if score_result["score"] >= score_result["threshold"] and ml_prob >= 0.65 else "SKIP"

    if decision == "BUY":
        trade_data = {
            "symbol": stock_symbol,
            "action": "BUY",
            "price": indicator_data.get("Close"),
            "timestamp": timestamp,
            "score": score_result["score"],
            "ml_probability": ml_prob,
            "matched_indicators": score_result["matched_indicators"],
            "strategy": score_result["strategy"],
            "regime": regime,
        }
        store_trade(trade_data)
        return {"status": "TRADE_EXECUTED", "data": trade_data}

    return {
        "status": "SKIPPED",
        "reason": f"Score: {score_result['score']} < {score_result['threshold']} or ML prob too low ({ml_prob})",
        "regime": regime,
        "ml_probability": ml_prob
    }
