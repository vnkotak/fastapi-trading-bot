import pandas as pd
import pickle
from sklearn.ensemble import RandomForestClassifier
from supabase import create_client
import os
from io import BytesIO
from indicators import SUPABASE_URL, SUPABASE_KEY

# Supabase config
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
BUCKET_NAME = "models"
MODEL_PATH = "model.pkl"

def fetch_trade_data():
    response = supabase.table("trades").select("*").execute()
    return pd.DataFrame(response.data)

def extract_features(df):
    df = df.copy()
    df['pnl'] = df['pnl'].fillna(0)
    df['pnl_percent'] = df['pnl_percent'].fillna(0)

    features = pd.DataFrame({
        'score': df['score'].fillna(0),
        'ml_probability': df['ml_probability'].fillna(0),
        'rsi': df['matched_indicators'].apply(lambda x: 1 if 'rsi' in str(x) else 0),
        'macd': df['matched_indicators'].apply(lambda x: 1 if 'macd' in str(x) else 0),
        'pattern': df['matched_indicators'].apply(lambda x: 1 if 'pattern' in str(x) else 0),
        'volume': df['matched_indicators'].apply(lambda x: 1 if 'volume' in str(x) else 0),
        'profit': df['pnl_percent'] > 0
    })
    return features.dropna()

def train_and_upload_model():
    df = fetch_trade_data()
    features = extract_features(df)

    X = features.drop("profit", axis=1)
    y = features["profit"].astype(int)

    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X, y)

    # Serialize
    buffer = BytesIO()
    pickle.dump(model, buffer)
    buffer.seek(0)

    # Upload to Supabase Storage
    supabase.storage.from_(BUCKET_NAME).upload(MODEL_PATH, buffer, file_options={"content-type": "application/octet-stream"})
    print("✅ Model trained and uploaded to Supabase Storage.")

if __name__ == "__main__":
    train_and_upload_model()
