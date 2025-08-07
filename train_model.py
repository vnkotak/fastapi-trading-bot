import pandas as pd
import numpy as np
import pickle
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score
from supabase import create_client, Client
from indicators import calculate_additional_indicators, SUPABASE_URL, SUPABASE_KEY

# === Initialize Supabase ===
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# === Feature Extraction Function ===
def extract_features_for_model(row):
    return [
        row['RSI'], row['MACD'], row['Signal'], row['MACD_Hist'],
        row['Volume'], row['Volume_avg'], row['EMA_20'], row['EMA_50'],
        row['Stoch_K'], row['Stoch_D'], row['WilliamsR'],
        row['BB_Position'], row['ATR'],
        row['Price_Change_1D'], row['Price_Change_3D'], row['Price_Change_5D']
    ]

# === Load and prepare trade data ===
def load_trade_data():
    response = supabase.table("trades").select("*").execute()
    trades = response.data
    df = pd.DataFrame(trades)

    df = df[df['action'] == 'BUY']
    df = df.dropna(subset=['ticker', 'entry_date'])

    # Label target: profitable trades = 1, others = 0
    df['label'] = df['pnl'].apply(lambda x: 1 if x and x > 0 else 0)
    return df

# === Get enriched features ===
def build_training_dataset(df):
    rows = []
    for _, trade in df.iterrows():
        ticker = trade['ticker']
        try:
            hist = pd.read_csv(f"data/{ticker}.csv")  # assume CSVs downloaded separately
            hist = hist[['Open', 'High', 'Low', 'Close', 'Volume']].astype(float)
            hist = calculate_additional_indicators(hist)
            hist.dropna(inplace=True)
            latest = hist.iloc[-1]
            features = extract_features_for_model(latest)
            rows.append(features + [trade['label']])
        except Exception as e:
            print(f"⚠️ Skipping {ticker}: {e}")

    columns = [
        'RSI', 'MACD', 'Signal', 'MACD_Hist', 'Volume', 'Volume_avg', 'EMA_20', 'EMA_50',
        'Stoch_K', 'Stoch_D', 'WilliamsR', 'BB_Position', 'ATR',
        'Price_Change_1D', 'Price_Change_3D', 'Price_Change_5D', 'label'
    ]
    return pd.DataFrame(rows, columns=columns)

# === Train model ===
def train_and_save_model(df):
    X = df.drop(columns=['label'])
    y = df['label']

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    print("\n📊 Classification Report:")
    print(classification_report(y_test, y_pred))
    print(f"✅ Accuracy: {accuracy_score(y_test, y_pred):.2f}")

    with open("model.pkl", "wb") as f:
        pickle.dump(model, f)
    print("📁 model.pkl saved.")

# === Main ===
if __name__ == "__main__":
    trade_data = load_trade_data()
    dataset = build_training_dataset(trade_data)
    if not dataset.empty:
        train_and_save_model(dataset)
    else:
        print("❌ No training data available.")
