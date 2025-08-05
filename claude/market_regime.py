import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from indicators import calculate_rsi

class MarketRegimeDetector:
    """
    Detects current market regime to adapt trading strategy
    """
    def __init__(self):
        self.regimes = ["BULL_STRONG", "BULL_WEAK", "SIDEWAYS", "BEAR_WEAK", "BEAR_STRONG"]
        self.current_regime = None
        self.regime_confidence = 0.0
        
    def detect_current_regime(self):
        """
        Analyze Nifty 50 to determine current market regime
        Returns: (regime, confidence_score)
        """
        try:
            # Fetch Nifty 50 data
            nifty_data = yf.download("^NSEI", period="3mo", interval="1d", progress=False)
            
            if nifty_data.empty or len(nifty_data) < 20:
                print("⚠️ Insufficient Nifty data, using SIDEWAYS regime")
                return "SIDEWAYS", 0.5
            
            # Clean column names if MultiIndex
            if isinstance(nifty_data.columns, pd.MultiIndex):
                nifty_data.columns = nifty_data.columns.get_level_values(0)
            nifty_data.columns.name = None
            
            # Calculate indicators with error handling
            try:
                nifty_data['EMA_20'] = nifty_data['Close'].ewm(span=20, adjust=False).mean()
                nifty_data['EMA_50'] = nifty_data['Close'].ewm(span=50, adjust=False).mean()
                nifty_data['RSI'] = calculate_rsi(nifty_data['Close'])
                
                # Calculate volatility (VIX proxy)
                nifty_data['Daily_Range'] = (nifty_data['High'] - nifty_data['Low']) / nifty_data['Close']
                nifty_data['Volatility'] = nifty_data['Daily_Range'].rolling(20).mean()
                
                # Drop any NaN rows
                nifty_data = nifty_data.dropna()
                
                if nifty_data.empty or len(nifty_data) < 10:
                    print("⚠️ Insufficient clean data after calculations")
                    return "SIDEWAYS", 0.5
                    
            except Exception as calc_error:
                print(f"⚠️ Error calculating indicators: {calc_error}")
                return "SIDEWAYS", 0.5
            
            # Get latest values (extract scalar values to avoid Series comparison issues)
            latest = nifty_data.iloc[-1]
            
            # Extract scalar values with validation
            try:
                price = float(latest['Close'])
                ema_20 = float(latest['EMA_20'])
                ema_50 = float(latest['EMA_50'])
                rsi = float(latest['RSI'])
                volatility = float(latest['Volatility'])
                
                # Validate extracted values
                if any(pd.isna([price, ema_20, ema_50, rsi, volatility])):
                    print("⚠️ NaN values in latest data")
                    return "SIDEWAYS", 0.5
                    
            except (KeyError, ValueError, TypeError) as extract_error:
                print(f"⚠️ Error extracting latest values: {extract_error}")
                return "SIDEWAYS", 0.5
            
            # Price change metrics (ensure we have enough data)
            try:
                if len(nifty_data) >= 6:
                    prev_close_1d = float(nifty_data['Close'].iloc[-2])
                    prev_close_5d = float(nifty_data['Close'].iloc[-6])  # 6 days ago to get 5-day change
                    
                    change_1d = ((price - prev_close_1d) / prev_close_1d) * 100 if prev_close_1d != 0 else 0
                    change_5d = ((price - prev_close_5d) / prev_close_5d) * 100 if prev_close_5d != 0 else 0
                else:
                    change_1d = 0
                    change_5d = 0
            except (IndexError, ValueError, ZeroDivisionError):
                change_1d = 0
                change_5d = 0
            
            # Trend strength
            try:
                trend_strength = abs(ema_20 - ema_50) / ema_50 * 100 if ema_50 != 0 else 0
            except (ValueError, ZeroDivisionError):
                trend_strength = 0
            
            # Regime classification logic
            regime, confidence = self._classify_regime(
                price, ema_20, ema_50, rsi, volatility, change_1d, change_5d, trend_strength
            )
            
            self.current_regime = regime
            self.regime_confidence = confidence
            
            print(f"📊 Market Regime: {regime} (Confidence: {confidence:.2f})")
            print(f"📈 Nifty: {price:.1f} | RSI: {rsi:.1f} | 5D Change: {change_5d:.1f}%")
            
            return regime, confidence
            
        except Exception as e:
            print(f"❌ Error detecting market regime: {e}")
            print(f"🔧 Using default SIDEWAYS regime")
            return "SIDEWAYS", 0.5
    
    def _classify_regime(self, price, ema_20, ema_50, rsi, volatility, change_1d, change_5d, trend_strength):
        """
        Classify market regime based on multiple factors
        All inputs should be scalar values (float/int)
        """
        confidence = 0.7  # Base confidence
        
        # Ensure all inputs are scalar (convert from numpy/pandas types if needed)
        price = float(price)
        ema_20 = float(ema_20)
        ema_50 = float(ema_50)
        rsi = float(rsi)
        volatility = float(volatility)
        change_1d = float(change_1d)
        change_5d = float(change_5d)
        trend_strength = float(trend_strength)
        
        # Strong uptrend conditions
        if (price > ema_20 > ema_50 and 
            rsi > 55 and 
            change_5d > 2 and 
            trend_strength > 1.5):
            
            if rsi > 65 and change_5d > 5:
                return "BULL_STRONG", min(confidence + 0.2, 0.95)
            else:
                return "BULL_WEAK", confidence
        
        # Strong downtrend conditions  
        elif (price < ema_20 < ema_50 and 
              rsi < 45 and 
              change_5d < -2 and 
              trend_strength > 1.5):
            
            if rsi < 35 and change_5d < -5:
                return "BEAR_STRONG", min(confidence + 0.2, 0.95)
            else:
                return "BEAR_WEAK", confidence
        
        # Sideways market
        elif (abs(change_5d) < 2 and 
              trend_strength < 1 and 
              40 < rsi < 60):
            
            return "SIDEWAYS", confidence
        
        # Weak trends or transitional periods
        elif price > ema_20 and rsi > 50:
            return "BULL_WEAK", max(confidence - 0.1, 0.4)
        elif price < ema_20 and rsi < 50:
            return "BEAR_WEAK", max(confidence - 0.1, 0.4)
        else:
            return "SIDEWAYS", max(confidence - 0.2, 0.3)
    
    def get_regime_characteristics(self, regime):
        """
        Get trading characteristics for each regime
        """
        characteristics = {
            "BULL_STRONG": {
                "description": "Strong uptrend with momentum",
                "trading_style": "Momentum following",
                "risk_level": "Medium",
                "expected_signals": "15-25 per day"
            },
            "BULL_WEAK": {
                "description": "Weak uptrend, choppy action",
                "trading_style": "Selective momentum",
                "risk_level": "Medium-High",
                "expected_signals": "8-15 per day"
            },
            "SIDEWAYS": {
                "description": "Range-bound, mean reverting",
                "trading_style": "Mean reversion",
                "risk_level": "High",
                "expected_signals": "5-12 per day"
            },
            "BEAR_WEAK": {
                "description": "Weak downtrend, bounces likely",
                "trading_style": "Counter-trend bounces",
                "risk_level": "Very High",
                "expected_signals": "3-8 per day"
            },
            "BEAR_STRONG": {
                "description": "Strong downtrend, avoid longs",
                "trading_style": "Minimal trading",
                "risk_level": "Extreme",
                "expected_signals": "0-2 per day"
            }
        }
        
        return characteristics.get(regime, characteristics["SIDEWAYS"])
    
    def should_trade_today(self):
        """
        Determine if we should trade based on current regime
        """
        if not self.current_regime:
            self.detect_current_regime()
        
        no_trade_regimes = ["BEAR_STRONG"]
        
        if self.current_regime in no_trade_regimes:
            return False, f"Market regime {self.current_regime} - trading suspended"
        
        return True, f"Trading allowed in {self.current_regime} regime"

# Usage example and testing
if __name__ == "__main__":
    detector = MarketRegimeDetector()
    regime, confidence = detector.detect_current_regime()
    
    characteristics = detector.get_regime_characteristics(regime)
    print(f"\n📋 Regime Characteristics:")
    for key, value in characteristics.items():
        print(f"   {key}: {value}")
    
    should_trade, reason = detector.should_trade_today()
    print(f"\n🎯 Trading Decision: {should_trade}")
    print(f"   Reason: {reason}")
