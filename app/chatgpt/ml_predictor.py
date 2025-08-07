import pandas as pd
import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score

MODEL_PATH = "ml_model.joblib"

FEATURES = [
    "RSI", "MACD_Hist", "Volume/20DayAvg", "Close", "EMA_50",
    "ADX", "Stoch_K", "WilliamsR", "BB_Pos", "ATR"
]

def train_ml_model(trades_df: pd.DataFrame):
    trades_df = trades_df.dropna()
    trades_df["target"] = trades_df["pnl"] > 0
    X = trades_df[FEATURES]
    y = trades_df["target"]

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)

    joblib.dump(model, MODEL_PATH)
    preds = model.predict(X_test)
    print("ML Accuracy:", accuracy_score(y_test, preds))


def predict_success_probability(indicator_data: dict) -> float:
    model = joblib.load(MODEL_PATH)
    X = pd.DataFrame([{k: indicator_data.get(k, 0) for k in FEATURES}])
    prob = model.predict_proba(X)[0][1]  # Probability of success (class 1)
    return round(prob, 4)
