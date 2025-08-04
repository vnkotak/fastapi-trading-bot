import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.model_selection import TimeSeriesSplit, cross_val_score
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import classification_report, confusion_matrix
import joblib
import yfinance as yf
from datetime import datetime, timedelta
import os
from supabase import create_client
from indicators import calculate_additional_indicators, SUPABASE_URL, SUPABASE_KEY

class FeatureEngineer:
    """
    Creates advanced features for ML model training
    """
    def __init__(self):
        self.feature_names = []
        self.scaler = StandardScaler()
        
    def create_features(self, df, nifty_data=None):
        """
        Create comprehensive feature set from stock data
        """
        if df.empty or len(df) < 50:
            return {}
        
        features = {}
        
        # Technical indicators (already calculated)
        features.update(self._technical_features(df))
        
        # Market microstructure features
        features.update(self._microstructure_features(df))
        
        # Relative strength vs market
        if nifty_data is not None:
            features.update(self._relative_strength_features(df, nifty_data))
        
        # Price action features
        features.update(self._price_action_features(df))
        
        # Volume analysis features
        features.update(self._volume_features(df))
        
        # Volatility features
        features.update(self._volatility_features(df))
        
        return features
    
    def _technical_features(self, df):
        """
        Standard technical indicator features
        """
        latest = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else latest
        
        return {
            "rsi": latest['RSI'],
            "rsi_change": latest['RSI'] - prev['RSI'],
            "rsi_oversold": 1 if latest['RSI'] < 30 else 0,
            "rsi_overbought": 1 if latest['RSI'] > 70 else 0,
            
            "macd": latest['MACD'],
            "macd_signal": latest['Signal'],
            "macd_histogram": latest['MACD_Hist'],
            "macd_bullish": 1 if latest['MACD'] > latest['Signal'] else 0,
            
            "ema20_slope": (latest['EMA_20'] - df['EMA_20'].iloc[-5]) / 5,
            "ema50_slope": (latest['EMA_50'] - df['EMA_50'].iloc[-10]) / 10,
            "price_above_ema20": 1 if latest['Close'] > latest['EMA_20'] else 0,
            "price_above_ema50": 1 if latest['Close'] > latest['EMA_50'] else 0,
            
            "bb_position": latest['BB_Position'],
            "bb_squeeze": 1 if (latest['Upper_BB'] - latest['Lower_BB']) / latest['Close'] < 0.1 else 0,
            
            "stoch_k": latest['Stoch_K'],
            "stoch_d": latest['Stoch_D'],
            "stoch_bullish": 1 if latest['Stoch_K'] > latest['Stoch_D'] else 0,
            
            "williams_r": latest['WilliamsR'],
            "williams_oversold": 1 if latest['WilliamsR'] > -20 else 0,
        }
    
    def _microstructure_features(self, df):
        """
        Market microstructure and price action features
        """
        # Price-volume relationship
        pv_correlation = df['Close'].pct_change().rolling(10).corr(df['Volume'].pct_change()).iloc[-1]
        
        # Intraday strength
        intraday_strength = ((df['Close'] - df['Low']) / (df['High'] - df['Low'])).rolling(5).mean().iloc[-1]
        
        # Gap behavior
        gaps = (df['Open'] - df['Close'].shift(1)).abs()
        avg_gap = gaps.rolling(10).mean().iloc[-1] / df['Close'].iloc[-1]
        
        # Price momentum at different timeframes
        momentum_1d = df['Close'].pct_change(1).iloc[-1]
        momentum_3d = df['Close'].pct_change(3).iloc[-1]
        momentum_5d = df['Close'].pct_change(5).iloc[-1]
        momentum_10d = df['Close'].pct_change(10).iloc[-1]
        
        return {
            "price_volume_corr": pv_correlation if not np.isnan(pv_correlation) else 0,
            "intraday_strength": intraday_strength if not np.isnan(intraday_strength) else 0.5,
            "avg_gap_ratio": avg_gap if not np.isnan(avg_gap) else 0,
            "momentum_1d": momentum_1d if not np.isnan(momentum_1d) else 0,
            "momentum_3d": momentum_3d if not np.isnan(momentum_3d) else 0,
            "momentum_5d": momentum_5d if not np.isnan(momentum_5d) else 0,
            "momentum_10d": momentum_10d if not np.isnan(momentum_10d) else 0,
            "momentum_consistency": 1 if all([momentum_1d > 0, momentum_3d > 0, momentum_5d > 0]) else 0,
        }
    
    def _relative_strength_features(self, df, nifty_data):
        """
        Relative strength vs benchmark (Nifty)
        """
        try:
            # Align data
            common_dates = df.index.intersection(nifty_data.index)
            if len(common_dates) < 20:
                return {"beta": 0, "relative_strength": 0, "correlation": 0}
            
            stock_aligned = df.loc[common_dates]['Close']
            nifty_aligned = nifty_data.loc[common_dates]['Close']
            
            # Calculate returns
            stock_returns = stock_aligned.pct_change().dropna()
            nifty_returns = nifty_aligned.pct_change().dropna()
            
            # Beta calculation
            covariance = stock_returns.cov(nifty_returns)
            nifty_variance = nifty_returns.var()
            beta = covariance / nifty_variance if nifty_variance != 0 else 1
            
            # Relative strength
            relative_strength = (stock_returns.rolling(20).mean().iloc[-1] - 
                               nifty_returns.rolling(20).mean().iloc[-1])
            
            # Correlation
            correlation = stock_returns.rolling(20).corr(nifty_returns).iloc[-1]
            
            return {
                "beta": beta if not np.isnan(beta) else 1,
                "relative_strength": relative_strength if not np.isnan(relative_strength) else 0,
                "correlation": correlation if not np.isnan(correlation) else 0.5,
                "outperforming_market": 1 if relative_strength > 0 else 0,
            }
        except:
            return {"beta": 1, "relative_strength": 0, "correlation": 0.5, "outperforming_market": 0}
    
    def _price_action_features(self, df):
        """
        Price action and candlestick features
        """
        latest = df.iloc[-1]
        
        # Candle body and shadows
        body_size = abs(latest['Close'] - latest['Open']) / latest['Close']
        upper_shadow = (latest['High'] - max(latest['Open'], latest['Close'])) / latest['Close']
        lower_shadow = (min(latest['Open'], latest['Close']) - latest['Low']) / latest['Close']
        
        # Price position in range
        price_in_range = (latest['Close'] - df['Low'].rolling(20).min().iloc[-1]) / \
                        (df['High'].rolling(20).max().iloc[-1] - df['Low'].rolling(20).min().iloc[-1])
        
        # Higher highs and higher lows
        recent_highs = df['High'].tail(5)
        recent_lows = df['Low'].tail(5)
        higher_highs = 1 if recent_highs.iloc[-1] > recent_highs.iloc[-3] else 0
        higher_lows = 1 if recent_lows.iloc[-1] > recent_lows.iloc[-3] else 0
        
        return {
            "body_size": body_size,
            "upper_shadow": upper_shadow,
            "lower_shadow": lower_shadow,
            "price_in_range": price_in_range if not np.isnan(price_in_range) else 0.5,
            "higher_highs": higher_highs,
            "higher_lows": higher_lows,
            "bullish_structure": 1 if higher_highs and higher_lows else 0,
            "doji": 1 if body_size < 0.005 else 0,
            "hammer": 1 if lower_shadow > 2 * body_size and upper_shadow < body_size else 0,
        }
    
    def _volume_features(self, df):
        """
        Volume analysis features
        """
        latest = df.iloc[-1]
        
        # Volume ratios
        volume_ratio = latest['Volume'] / latest['Volume_avg']
        volume_trend = df['Volume'].rolling(5).mean().iloc[-1] / df['Volume'].rolling(20).mean().iloc[-1]
        
        # Volume-price divergence
        price_change_5d = df['Close'].pct_change(5).iloc[-1]
        volume_change_5d = (df['Volume'].rolling(5).mean().iloc[-1] / 
                           df['Volume'].rolling(5).mean().iloc[-6]) - 1
        
        # On-balance volume approximation
        obv_signal = np.sign(df['Close'].diff()) * df['Volume']
        obv_trend = obv_signal.rolling(10).sum().iloc[-1] / obv_signal.rolling(20).sum().iloc[-1]
        
        return {
            "volume_ratio": volume_ratio,
            "volume_trend": volume_trend if not np.isnan(volume_trend) else 1,
            "volume_surge": 1 if volume_ratio > 2 else 0,
            "volume_dry_up": 1 if volume_ratio < 0.5 else 0,
            "price_volume_divergence": abs(price_change_5d) - abs(volume_change_5d),
            "obv_trend": obv_trend if not np.isnan(obv_trend) else 1,
        }
    
    def _volatility_features(self, df):
        """
        Volatility and risk features
        """
        latest = df.iloc[-1]
        
        # ATR features
        atr_ratio = latest['ATR'] / df['ATR'].rolling(20).mean().iloc[-1]
        volatility_rank = (df['ATR'].rolling(50).rank().iloc[-1]) / 50
        
        # Realized volatility
        returns = df['Close'].pct_change()
        realized_vol = returns.rolling(20).std().iloc[-1] * np.sqrt(252)
        
        # Volatility regime
        vol_ma = df['ATR'].rolling(20).mean()
        vol_expanding = 1 if vol_ma.iloc[-1] > vol_ma.iloc[-5] else 0
        
        return {
            "atr_ratio": atr_ratio if not np.isnan(atr_ratio) else 1,
            "volatility_rank": volatility_rank if not np.isnan(volatility_rank) else 0.5,
            "realized_volatility": realized_vol if not np.isnan(realized_vol) else 0.2,
            "volatility_expanding": vol_expanding,
            "low_volatility": 1 if atr_ratio < 0.8 else 0,
            "high_volatility": 1 if atr_ratio > 1.5 else 0,
        }

class MLPredictor:
    """
    Machine Learning predictor for trade success probability
    """
    def __init__(self):
        self.models = {
            "rf": RandomForestClassifier(n_estimators=100, max_depth=10, random_state=42),
            "gb": GradientBoostingClassifier(n_estimators=100, max_depth=6, random_state=42),
        }
        self.feature_engineer = FeatureEngineer()
        self.scaler = StandardScaler()
        self.feature_importance = {}
        self.is_trained = False
        self.supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        
    def prepare_training_data(self, min_trades=50):
        """
        Prepare training data from historical trades
        """
        try:
            print("📚 Preparing ML training data...")
            
            # Get historical trades
            trades_response = self.supabase.table("trades").select("*").execute()
            trades = trades_response.data
            
            if len(trades) < min_trades:
                print(f"⚠️ Insufficient trades for training: {len(trades)} < {min_trades}")
                return None, None
            
            # Get Nifty data for relative strength calculation
            nifty_data = yf.download("^NSEI", period="1y", interval="1d", progress=False)
            if isinstance(nifty_data.columns, pd.MultiIndex):
                nifty_data.columns = nifty_data.columns.get_level_values(0)
            
            features_list = []
            labels_list = []
            
            print(f"📊 Processing {len(trades)} historical trades...")
            
            for i, trade in enumerate(trades):
                try:
                    # Get historical data for the trade date
                    entry_date = datetime.fromisoformat(trade['entry_date'].replace('Z', '+00:00'))
                    start_date = entry_date - timedelta(days=100)  # Get enough history
                    
                    # Download stock data
                    stock_data = yf.download(
                        trade['ticker'], 
                        start=start_date.strftime('%Y-%m-%d'),
                        end=(entry_date + timedelta(days=1)).strftime('%Y-%m-%d'),
                        interval="1d",
                        progress=False
                    )
                    
                    if stock_data.empty or len(stock_data) < 50:
                        continue
                    
                    # Clean data
                    if isinstance(stock_data.columns, pd.MultiIndex):
                        stock_data.columns = stock_data.columns.get_level_values(0)
                    
                    # Calculate indicators
                    stock_data = calculate_additional_indicators(stock_data)
                    
                    # Get features at entry date
                    features = self.feature_engineer.create_features(stock_data, nifty_data)
                    
                    if not features:
                        continue
                    
                    # Create label (1 for profitable trade, 0 for loss)
                    pnl = trade.get('pnl', 0)
                    label = 1 if pnl > 0 else 0
                    
                    features_list.append(features)
                    labels_list.append(label)
                    
                    if (i + 1) % 10 == 0:
                        print(f"   Processed {i + 1}/{len(trades)} trades...")
                    
                except Exception as e:
                    print(f"⚠️ Error processing trade {trade.get('ticker', 'Unknown')}: {e}")
                    continue
            
            if len(features_list) < min_trades:
                print(f"❌ Insufficient valid training samples: {len(features_list)}")
                return None, None
            
            # Convert to DataFrame and arrays
            features_df = pd.DataFrame(features_list)
            features_df = features_df.fillna(0)  # Handle any NaN values
            
            X = features_df.values
            y = np.array(labels_list)
            
            # Store feature names
            self.feature_names = features_df.columns.tolist()
            
            print(f"✅ Training data prepared: {len(X)} samples, {len(self.feature_names)} features")
            print(f"📈 Positive samples: {sum(y)} ({sum(y)/len(y)*100:.1f}%)")
            
            return X, y
            
        except Exception as e:
            print(f"❌ Error preparing training data: {e}")
            return None, None
    
    def train_models(self, X=None, y=None):
        """
        Train ML models on historical data
        """
        try:
            if X is None or y is None:
                X, y = self.prepare_training_data()
                
            if X is None:
                print("❌ Cannot train models: no training data available")
                return False
            
            print("🤖 Training ML models...")
            
            # Scale features
            X_scaled = self.scaler.fit_transform(X)
            
            # Time series cross-validation
            tscv = TimeSeriesSplit(n_splits=5)
            
            best_model = None
            best_score = 0
            
            for name, model in self.models.items():
                print(f"   Training {name}...")
                
                # Cross-validation
                cv_scores = cross_val_score(model, X_scaled, y, cv=tscv, scoring='accuracy')
                mean_score = cv_scores.mean()
                
                print(f"   {name} CV Score: {mean_score:.3f} (+/- {cv_scores.std() * 2:.3f})")
                
                # Train on full dataset
                model.fit(X_scaled, y)
                
                # Feature importance (for tree-based models)
                if hasattr(model, 'feature_importances_'):
                    importance_dict = dict(zip(self.feature_names, model.feature_importances_))
                    self.feature_importance[name] = importance_dict
                    
                    # Print top features
                    top_features = sorted(importance_dict.items(), key=lambda x: x[1], reverse=True)[:10]
                    print(f"   Top features for {name}:")
                    for feature, importance in top_features:
                        print(f"     {feature}: {importance:.3f}")
                
                # Save best model
                if mean_score > best_score:
                    best_score = mean_score
                    best_model = name
                
                # Save model
                os.makedirs("models", exist_ok=True)
                joblib.dump(model, f"models/{name}_model.pkl")
                
            # Save scaler
            joblib.dump(self.scaler, "models/scaler.pkl")
            
            print(f"✅ Models trained successfully!")
            print(f"🏆 Best model: {best_model} (Score: {best_score:.3f})")
            
            self.is_trained = True
            return True
            
        except Exception as e:
            print(f"❌ Error training models: {e}")
            return False
    
    def predict_trade_success(self, stock_data, nifty_data=None, model_name="rf"):
        """
        Predict probability of trade success
        """
        try:
            if not self.is_trained:
                # Try to load trained model
                if not self.load_models():
                    print("⚠️ No trained model available. Using default probability.")
                    return 0.5
            
            # Generate features
            features = self.feature_engineer.create_features(stock_data, nifty_data)
            
            if not features:
                return 0.5
            
            # Convert to array
            feature_array = np.array([list(features.values())])
            
            # Handle missing features (pad with zeros)
            if len(features) < len(self.feature_names):
                missing_features = len(self.feature_names) - len(features)
                feature_array = np.pad(feature_array, ((0, 0), (0, missing_features)), mode='constant')
            elif len(features) > len(self.feature_names):
                feature_array = feature_array[:, :len(self.feature_names)]
            
            # Scale features
            feature_array_scaled = self.scaler.transform(feature_array)
            
            # Load and predict
            model = joblib.load(f"models/{model_name}_model.pkl")
            probability = model.predict_proba(feature_array_scaled)[0][1]  # Probability of success
            
            return probability
            
        except Exception as e:
            print(f"⚠️ ML prediction error: {e}")
            return 0.5
    
    def load_models(self):
        """
        Load pre-trained models
        """
        try:
            if os.path.exists("models/rf_model.pkl") and os.path.exists("models/scaler.pkl"):
                self.scaler = joblib.load("models/scaler.pkl")
                # Load feature names (you might want to save this
