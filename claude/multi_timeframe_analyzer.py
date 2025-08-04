import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from indicators import calculate_additional_indicators, detect_candle_pattern, advanced_strategy_score
import warnings
warnings.filterwarnings('ignore')

class MultiTimeframeAnalyzer:
    """
    Analyzes stocks across multiple timeframes for better entry timing
    """
    def __init__(self):
        self.timeframes = {
            "daily": {"period": "6mo", "interval": "1d"},
            "hourly": {"period": "1mo", "interval": "1h"},
            "15min": {"period": "5d", "interval": "15m"}
        }
        
    def analyze_stock_comprehensive(self, ticker):
        """
        Comprehensive multi-timeframe analysis of a stock
        Returns enhanced scoring with timeframe confirmations
        """
        try:
            print(f"🔍 Multi-timeframe analysis: {ticker}")
            
            # Get data for all timeframes
            data = {}
            for tf_name, tf_config in self.timeframes.items():
                try:
                    df = yf.download(ticker, 
                                   period=tf_config["period"], 
                                   interval=tf_config["interval"], 
                                   progress=False)
                    
                    if not df.empty and len(df) > 20:
                        # Clean column names if MultiIndex
                        if isinstance(df.columns, pd.MultiIndex):
                            df.columns = df.columns.get_level_values(0)
                        df.columns.name = None
                        
                        # Calculate indicators
                        df = calculate_additional_indicators(df)
                        data[tf_name] = df
                    else:
                        print(f"⚠️ Insufficient {tf_name} data for {ticker}")
                        
                except Exception as e:
                    print(f"⚠️ Failed to fetch {tf_name} data for {ticker}: {e}")
            
            if "daily" not in data:
                return None
            
            # Analyze each timeframe
            analysis = {}
            for tf_name, df in data.items():
                analysis[tf_name] = self._analyze_timeframe(df, tf_name)
            
            # Combine timeframe signals
            combined_score = self._combine_timeframe_signals(analysis, ticker)
            
            return combined_score
            
        except Exception as e:
            print(f"❌ Error in multi-timeframe analysis for {ticker}: {e}")
            return None
    
    def _analyze_timeframe(self, df, timeframe):
        """
        Analyze individual timeframe
        """
        if df.empty or len(df) < 10:
            return None
            
        latest = df.iloc[-1]
        previous = df.iloc[-2] if len(df) > 1 else latest
        
        # Basic trend analysis
        trend_signals = {
            "price_above_ema20": latest['Close'] > latest['EMA_20'],
            "price_above_ema50": latest['Close'] > latest['EMA_50'],
            "ema20_above_ema50": latest['EMA_20'] > latest['EMA_50'],
            "ema20_rising": latest['EMA_20'] > previous['EMA_20'],
            "ema50_rising": latest['EMA_50'] > previous['EMA_50'],
        }
        
        # Momentum signals
        momentum_signals = {
            "rsi_rising": latest['RSI'] > previous['RSI'],
            "rsi_in_range": 35 < latest['RSI'] < 75,
            "macd_bullish": latest['MACD'] > latest['Signal'],
            "macd_histogram_rising": latest['MACD_Hist'] > previous['MACD_Hist'],
            "stoch_bullish": latest['Stoch_K'] > latest['Stoch_D'],
        }
        
        # Volume signals
        volume_signals = {
            "volume_above_average": latest['Volume'] > latest['Volume_avg'],
            "volume_surge": latest['Volume'] > 1.5 * latest['Volume_avg'],
            "price_volume_confirmation": (latest['Close'] > previous['Close'] and 
                                        latest['Volume'] > previous['Volume']),
        }
        
        # Support/Resistance levels
        support_resistance = self._calculate_support_resistance(df)
        
        # Price action signals
        price_action = {
            "near_support": self._is_near_level(latest['Close'], support_resistance['support'], 0.02),
            "above_resistance": latest['Close'] > support_resistance['resistance'],
            "bullish_pattern": "Engulfing" in detect_candle_pattern(df) or "Hammer" in detect_candle_pattern(df),
        }
        
        # Calculate timeframe score
        tf_score = self._calculate_timeframe_score(trend_signals, momentum_signals, 
                                                 volume_signals, price_action, timeframe)
        
        return {
            "timeframe": timeframe,
            "score": tf_score,
            "trend_signals": trend_signals,
            "momentum_signals": momentum_signals,
            "volume_signals": volume_signals,
            "price_action": price_action,
            "support_resistance": support_resistance,
            "latest_data": {
                "close": latest['Close'],
                "rsi": latest['RSI'],
                "volume": latest['Volume'],
                "atr": latest['ATR'],
            }
        }
    
    def _calculate_support_resistance(self, df, window=20):
        """
        Calculate key support and resistance levels
        """
        try:
            recent_data = df.tail(window)
            
            # Support: Recent low areas
            support_candidates = recent_data['Low'].rolling(5).min()
            support = support_candidates.min()
            
            # Resistance: Recent high areas  
            resistance_candidates = recent_data['High'].rolling(5).max()
            resistance = resistance_candidates.max()
            
            # Pivot points
            pivot = (recent_data['High'].iloc[-1] + recent_data['Low'].iloc[-1] + recent_data['Close'].iloc[-1]) / 3
            
            return {
                "support": support,
                "resistance": resistance,
                "pivot": pivot,
                "current_price": df['Close'].iloc[-1]
            }
        except:
            return {
                "support": df['Low'].iloc[-1],
                "resistance": df['High'].iloc[-1], 
                "pivot": df['Close'].iloc[-1],
                "current_price": df['Close'].iloc[-1]
            }
    
    def _is_near_level(self, price, level, tolerance=0.02):
        """
        Check if price is near a support/resistance level
        """
        return abs(price - level) / level <= tolerance
    
    def _calculate_timeframe_score(self, trend, momentum, volume, price_action, timeframe):
        """
        Calculate weighted score for each timeframe
        """
        # Timeframe weights (daily is most important)
        weights = {
            "daily": 1.0,
            "hourly": 0.7, 
            "15min": 0.4
        }
        
        weight = weights.get(timeframe, 0.5)
        
        # Count positive signals
        trend_score = sum(trend.values()) / len(trend)
        momentum_score = sum(momentum.values()) / len(momentum)
        volume_score = sum(volume.values()) / len(volume)
        price_action_score = sum(price_action.values()) / len(price_action)
        
        # Weighted combination
        raw_score = (trend_score * 0.3 + 
                    momentum_score * 0.3 + 
                    volume_score * 0.2 + 
                    price_action_score * 0.2)
        
        return raw_score * weight * 10  # Scale to 0-10
    
    def _combine_timeframe_signals(self, analysis, ticker):
        """
        Combine signals from all timeframes into final score
        """
        if "daily" not in analysis or analysis["daily"] is None:
            return None
        
        daily_analysis = analysis["daily"]
        
        # Start with daily analysis base score
        daily_df = yf.download(ticker, period="3mo", interval="1d", progress=False)
        if isinstance(daily_df.columns, pd.MultiIndex):
            daily_df.columns = daily_df.columns.get_level_values(0)
        daily_df.columns.name = None
        daily_df = calculate_additional_indicators(daily_df)
        
        # Detect candle pattern
        daily_df['Candle'] = "None"
        daily_df.at[daily_df.index[-1], 'Candle'] = detect_candle_pattern(daily_df)
        
        latest = daily_df.iloc[-1]
        previous = daily_df.iloc[-2]
        
        # Get base score from existing strategy
        base_score, matched_indicators = advanced_strategy_score(latest, previous)
        
        # Multi-timeframe adjustments
        timeframe_bonus = 0.0
        confirmations = []
        
        # Daily timeframe (base)
        daily_score = analysis["daily"]["score"]
        
        # Hourly confirmation
        if "hourly" in analysis and analysis["hourly"]:
            hourly = analysis["hourly"]
            
            # Strong hourly trend confirmation
            if (hourly["trend_signals"]["price_above_ema20"] and 
                hourly["trend_signals"]["ema20_rising"] and
                hourly["volume_signals"]["volume_above_average"]):
                timeframe_bonus += 0.5
                confirmations.append("hourly_trend")
            
            # Hourly momentum building
            if (hourly["momentum_signals"]["rsi_rising"] and 
                hourly["momentum_signals"]["macd_histogram_rising"]):
                timeframe_bonus += 0.3
                confirmations.append("hourly_momentum")
        
        # 15-minute confirmation (for entry timing)
        if "15min" in analysis and analysis["15min"]:
            min15 = analysis["15min"]
            
            # Recent price action positive
            if (min15["price_action"]["bullish_pattern"] or
                min15["volume_signals"]["price_volume_confirmation"]):
                timeframe_bonus += 0.2
                confirmations.append("15min_entry")
        
        # Multi-timeframe alignment bonus
        if len(confirmations) >= 2:
            timeframe_bonus += 0.3
            confirmations.append("multi_tf_alignment")
        
        # Entry timing optimization
        entry_timing = self._optimize_entry_timing(analysis)
        
        # Final combined score
        final_score = base_score + timeframe_bonus
        
        # Enhanced matched indicators
        enhanced_indicators = matched_indicators + confirmations
        
        return {
            "ticker": ticker,
            "base_score": round(base_score, 2),
            "timeframe_bonus": round(timeframe_bonus, 2),
            "final_score": round(final_score, 2),
            "matched_indicators": enhanced_indicators,
            "timeframe_analysis": analysis,
            "entry_timing": entry_timing,
            "multi_timeframe_signals": {
                "daily_score": round(daily_score, 2),
                "confirmations": confirmations,
                "alignment_strength": len(confirmations)
            }
        }
    
    def _optimize_entry_timing(self, analysis):
        """
        Determine optimal entry timing based on timeframe analysis
        """
        timing_recommendation = {
            "strategy": "immediate",
            "confidence": 0.5,
            "wait_for": [],
            "risk_level": "medium"
        }
        
        # Check if we should wait for pullback
        if "hourly" in analysis and analysis["hourly"]:
            hourly = analysis["hourly"]
            
            # If hourly RSI is high, wait for pullback
            if hourly["latest_data"]["rsi"] > 70:
                timing_recommendation.update({
                    "strategy": "wait_pullback",
                    "wait_for": ["RSI pullback to 60"],
                    "confidence": 0.7
                })
            
            # If near resistance, wait for breakout
            elif hourly["price_action"]["near_support"]:
                timing_recommendation.update({
                    "strategy": "immediate",
                    "confidence": 0.8,
                    "risk_level": "low"
                })
        
        # Check 15-minute for immediate entry signals
        if "15min" in analysis and analysis["15min"]:
            min15 = analysis["15min"]
            
            if min15["volume_signals"]["volume_surge"]:
                timing_recommendation.update({
                    "strategy": "immediate",
                    "confidence": 0.9,
                    "wait_for": [],
                    "risk_level": "low"
                })
        
        return timing_recommendation

class EntryOptimizer:
    """
    Optimizes entry timing based on intraday patterns
    """
    def __init__(self):
        self.optimal_entry_times = ["09:45", "10:15", "14:00", "15:00"]
        
    def find_optimal_entry_price(self, ticker, signal_data):
        """
        Find optimal entry price and timing
        """
        try:
            # Get recent intraday data
            intraday_data = yf.download(ticker, period="2d", interval="5m", progress=False)
            
            if intraday_data.empty:
                return {
                    "entry_price": signal_data.get("close", 0),
                    "entry_strategy": "market_price",
                    "confidence": 0.5
                }
            
            # Clean data
            if isinstance(intraday_data.columns, pd.MultiIndex):
                intraday_data.columns = intraday_data.columns.get_level_values(0)
            
            current_price = intraday_data['Close'].iloc[-1]
            
            # Calculate entry strategies
            entry_strategies = self._calculate_entry_strategies(intraday_data, current_price)
            
            # Select best strategy based on market conditions
            best_strategy = self._select_best_entry_strategy(entry_strategies, signal_data)
            
            return best_strategy
            
        except Exception as e:
            print(f"⚠️ Entry optimization failed for {ticker}: {e}")
            return {
                "entry_price": signal_data.get("close", 0),
                "entry_strategy": "market_price",
                "confidence": 0.5
            }
    
    def _calculate_entry_strategies(self, df, current_price):
        """
        Calculate different entry price strategies
        """
        # Support/resistance levels
        recent_high = df['High'].tail(20).max()
        recent_low = df['Low'].tail(20).min()
        vwap = (df['Close'] * df['Volume']).sum() / df['Volume'].sum()
        
        strategies = {
            "market_price": {
                "price": current_price,
                "description": "Enter at current market price",
                "risk": "medium",
                "confidence": 0.6
            },
            
            "pullback_to_vwap": {
                "price": vwap,
                "description": "Wait for pullback to VWAP",
                "risk": "low",
                "confidence": 0.8 if current_price > vwap * 1.01 else 0.3
            },
            
            "breakout_entry": {
                "price": recent_high * 1.002,
                "description": "Enter on breakout above recent high",
                "risk": "high",
                "confidence": 0.7 if current_price > recent_high * 0.99 else 0.2
            },
            
            "support_bounce": {
                "price": recent_low * 1.01,
                "description": "Enter on bounce from support",
                "risk": "medium",
                "confidence": 0.6 if current_price < recent_low * 1.05 else 0.1
            }
        }
        
        return strategies
    
    def _select_best_entry_strategy(self, strategies, signal_data):
        """
        Select the best entry strategy based on signal characteristics
        """
        # Default to market price
        best_strategy = strategies["market_price"]
        
        # If signal has high momentum, use breakout strategy
        if signal_data.get("timeframe_bonus", 0) > 0.5:
            if strategies["breakout_entry"]["confidence"] > 0.5:
                best_strategy = strategies["breakout_entry"]
        
        # If signal is near support, use support bounce
        elif "pattern" in signal_data.get("matched_indicators", []):
            if strategies["support_bounce"]["confidence"] > 0.4:
                best_strategy = strategies["support_bounce"]
        
        # If overbought, wait for pullback
        elif signal_data.get("final_score", 0) > 6.5:
            if strategies["pullback_to_vwap"]["confidence"] > 0.6:
                best_strategy = strategies["pullback_to_vwap"]
        
        return {
            "entry_price": best_strategy["price"],
            "entry_strategy": best_strategy["description"],
            "risk_level": best_strategy["risk"],
            "confidence": best_strategy["confidence"]
        }

# Usage and testing
if __name__ == "__main__":
    analyzer = MultiTimeframeAnalyzer()
    entry_optimizer = EntryOptimizer()
    
    # Test with a sample stock
    test_ticker = "RELIANCE.NS"
    
    print(f"🧪 Testing Multi-Timeframe Analysis for {test_ticker}")
    
    # Run comprehensive analysis
    result = analyzer.analyze_stock_comprehensive(test_ticker)
    
    if result:
        print(f"\n📊 Analysis Results:")
        print(f"   Base Score: {result['base_score']}")
        print(f"   Timeframe Bonus: {result['timeframe_bonus']}")
        print(f"   Final Score: {result['final_score']}")
        print(f"   Confirmations: {result['multi_timeframe_signals']['confirmations']}")
        
        print(f"\n⏰ Entry Timing:")
        timing = result['entry_timing']
        print(f"   Strategy: {timing['strategy']}")
        print(f"   Confidence: {timing['confidence']}")
        if timing['wait_for']:
            print(f"   Wait for: {timing['wait_for']}")
        
        # Test entry optimization
        entry_info = entry_optimizer.find_optimal_entry_price(test_ticker, result)
        print(f"\n🎯 Entry Optimization:")
        print(f"   Entry Price: ₹{entry_info['entry_price']:.2f}")
        print(f"   Strategy: {entry_info['entry_strategy']}")
        print(f"   Confidence: {entry_info['confidence']:.2f}")
    
    else:
        print(f"❌ Analysis failed for {test_ticker}")
