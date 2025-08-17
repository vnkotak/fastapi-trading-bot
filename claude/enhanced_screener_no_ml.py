import yfinance as yf
import pandas as pd
import time
from datetime import datetime
from supabase import create_client, Client
import sys
import os

# Add the claude folder to path
claude_path = os.path.join(os.path.dirname(__file__), '..', 'claude')
if claude_path not in sys.path:
    sys.path.append(claude_path)

# Import working AI components (excluding ML)
try:
    from market_regime import MarketRegimeDetector
    from adaptive_config import AdaptiveConfig
    # from multi_timeframe_analyzer import MultiTimeframeAnalyzer  # Comment out for now
    # from ml_predictor import MLEnhancedScoring  # Comment out ML
    from execution_engine import ExecutionEngine  # Use the updated original
    from risk_manager import RiskManager
    AI_IMPORTS_OK = True
    print("✅ AI modules imported successfully (ML disabled)")
except ImportError as e:
    print(f"⚠️ Could not import AI modules: {e}")
    AI_IMPORTS_OK = False

from claude_indicators import advanced_strategy_score

# Import existing components
from indicators import (
    calculate_additional_indicators,
    detect_candle_pattern,
    SUPABASE_URL,
    SUPABASE_KEY
)

# Import fixed telegram function
try:
    from telegram_fix import send_telegram
    print("✅ Using fixed Telegram function")
except ImportError:
    from indicators import send_telegram
    print("⚠️ Using original Telegram function")

class EnhancedScreenerNoML:
    """
    AI-Enhanced stock screener WITHOUT ML components
    """
    def __init__(self):
        if not AI_IMPORTS_OK:
            raise ImportError("AI modules not available")
            
        # Initialize database
        self.supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        
        # Initialize AI components (excluding ML)
        try:
            self.regime_detector = MarketRegimeDetector()
            self.adaptive_config = AdaptiveConfig()
            # self.multi_tf_analyzer = MultiTimeframeAnalyzer()  # Commented out
            # self.ml_enhanced_scoring = MLEnhancedScoring()     # Commented out
            self.execution_engine = ExecutionEngine()  # Use the updated original
            self.risk_manager = RiskManager()
            print("✅ AI components initialized (ML disabled)")
        except Exception as e:
            print(f"⚠️ Error initializing AI components: {e}")
            raise
        
        # Current session data
        self.current_regime = None
        self.current_config = None
        self.processed_tickers = set()  # Track processed tickers in this session
        self.session_stats = {
            'total_analyzed': 0,
            'passed_filters': 0,
            'traditional_filtered': 0,  # Instead of ml_filtered
            'final_signals': 0,
            'executed_trades': 0,
            'duplicate_skips': 0  # Track duplicate skips
        }
    
    def run_enhanced_screening(self, auto_execute=False):
        """
        Run the enhanced screening process without ML
        """
        try:
            print("🚀 Starting AI-Enhanced Stock Screening (No ML)")
            print("=" * 60)
            
            # Step 1: Initialize session
            self._initialize_session()
            
            # Step 2: Check trading permissions
            if not self._check_trading_permissions():
                return
            
            # Step 3: Fetch stocks
            tickers = self._fetch_stock_universe()
            if not tickers:
                return
            
            # Step 4: Run screening without ML
            qualified_stocks = self._run_screening_pipeline_no_ml(tickers)
            
            # Step 5: Execute trades if enabled
            if auto_execute and qualified_stocks:
                self._execute_qualified_trades(qualified_stocks)
            
            # Step 6: Finalize
            self._finalize_session(qualified_stocks)
            
            print("✅ AI-Enhanced Screening Complete!")
            
        except Exception as e:
            print(f"❌ Critical error in enhanced screening: {e}")
            send_telegram(f"🚨 SCREENING ERROR - {str(e)}")
    
    def _initialize_session(self):
        """Initialize session with proper Telegram messaging"""
        try:
            print("\n📊 Initializing AI Session...")
            
            regime, confidence = self.regime_detector.detect_current_regime()
            self.current_regime = regime
            self.current_config = self.adaptive_config.get_current_config()
            
            characteristics = self.regime_detector.get_regime_characteristics(regime)
            
            print(f"   Market Regime: {regime} (Confidence: {confidence:.2f})")
            print(f"   Trading Style: {characteristics['trading_style']}")
            print(f"   Expected Signals: {characteristics['expected_signals']}")
            
            # Send start notification with safe formatting
            start_message = f"""🤖 AI SCREENING STARTED

                                📊 Market Regime: {regime}
                                🎯 Confidence: {confidence:.1%}
                                📈 Style: {characteristics['trading_style']}
                                ⚡ Expected: {characteristics['expected_signals']}

                                🔧 Adaptive Settings:
                                📊 Score Threshold: {self.current_config['SCORE_THRESHOLD']}
                                📈 RSI Range: {self.current_config['RSI_MIN']}-{self.current_config['RSI_MAX']}
                                📊 Volume Multiplier: {self.current_config['VOLUME_MULTIPLIER']}x

                                🕒 Time: {datetime.now().strftime('%H:%M')}
                                Note: ML components disabled for testing"""
            
            send_telegram(start_message)
            
        except Exception as e:
            print(f"⚠️ Session initialization error: {e}")
            # Set safe defaults
            self.current_regime = "SIDEWAYS"
            self.current_config = {
                'SCORE_THRESHOLD': 5.9,
                'RSI_MIN': 45,
                'RSI_MAX': 65,
                'VOLUME_MULTIPLIER': 2.0
            }
    
    def _check_trading_permissions(self):
        """Check trading permissions"""
        try:
            should_trade_regime, regime_reason = self.regime_detector.should_trade_today()
            should_trade_risk, risk_reason = self.risk_manager.should_trade_today()
            
            if not should_trade_regime:
                print(f"🚫 Trading suspended due to regime: {regime_reason}")
                send_telegram(f"🚫 TRADING SUSPENDED - {regime_reason}")
                return False
            
            if not should_trade_risk:
                print(f"🚫 Trading suspended due to risk: {risk_reason}")
                send_telegram(f"🚫 TRADING SUSPENDED - {risk_reason}")
                return False
            
            print("✅ Trading permissions granted")
            return True
            
        except Exception as e:
            print(f"⚠️ Permission check error: {e}")
            return True  # Default to allow trading
    
    def _fetch_stock_universe(self):
        """Fetch stocks"""
        try:
            response = self.supabase.table("master_stocks") \
                .select("ticker") \
                .eq("status", "Active") \
                .eq("exchange", "NSE") \
                .limit(3000) \
                .execute()
            
            tickers = [row["ticker"] for row in response.data]
            print(f"✅ Loaded {len(tickers)} tickers")
            return tickers
            
        except Exception as e:
            print(f"❌ Failed to fetch stocks: {e}")
            return []
    
    def _run_screening_pipeline_no_ml(self, tickers):
        """Run screening without ML components"""
        print(f"\n🔍 Running Enhanced Screening Pipeline (No ML)...")
        
        qualified_stocks = []
        processed_count = 0
        
        # Limit for testing
        tickers_to_process = tickers[:1800] if len(tickers) > 1800 else tickers
        
        for ticker in tickers_to_process:
            try:
                processed_count += 1
                self.session_stats['total_analyzed'] += 1
                print(processed_count)
                
                # Check for duplicates in this session
                if ticker in self.processed_tickers:
                    print(f"⚠️ Skipping duplicate ticker in this session: {ticker}")
                    self.session_stats['duplicate_skips'] += 1
                    continue
                
                self.processed_tickers.add(ticker)
                
                # Progress reporting
                if processed_count % 50 == 0:
                    progress = (processed_count / len(tickers_to_process)) * 100
                    print(f"   Progress: {processed_count}/{len(tickers_to_process)} ({progress:.1f}%) - Found: {len(qualified_stocks)}")
                
                # Apply regime-specific filters
                if not self._apply_regime_filters(ticker):
                    continue
                
                self.session_stats['passed_filters'] += 1
                
                # Traditional analysis (no ML)
                stock_result = self._analyze_stock_traditional(ticker)
                if not stock_result:
                    continue
                
                self.session_stats['traditional_filtered'] += 1
                    
                # Check if qualifies
                # if stock_result['score'] >= self.current_config['SCORE_THRESHOLD']:
                if stock_result['score'] >= 2.0:
                    qualified_stocks.append(stock_result)
                    self.session_stats['final_signals'] += 1
                    print(f"✅ Qualified: {ticker} (Score: {stock_result['score']:.2f})")
                
                # Rate limiting
                time.sleep(0.05)
                
            except Exception as e:
                print(f"⚠️ Error processing {ticker}: {e}")
                continue
        
        print(f"\n📊 Screening Complete:")
        print(f"   Total Analyzed: {self.session_stats['total_analyzed']}")
        print(f"   Duplicate Skips: {self.session_stats['duplicate_skips']}")
        print(f"   Passed Filters: {self.session_stats['passed_filters']}")
        print(f"   Traditional Filtered: {self.session_stats['traditional_filtered']}")
        print(f"   Final Signals: {self.session_stats['final_signals']}")
        
        return qualified_stocks
    
    def _apply_regime_filters(self, ticker):
        """Apply regime-specific pre-entry filters"""
        try:
            df = yf.download(ticker, period="3mo", interval="1d", progress=False)
            
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            df.columns.name = None
            
            df = df[['Open', 'High', 'Low', 'Close', 'Volume']].dropna()
            
            if df.empty or len(df) < 50:
                return False
            
            df = df.astype(float)
            df = calculate_additional_indicators(df)
            df.dropna(inplace=True)
            
            if df.empty:
                return False
            
            latest = df.iloc[-1]
            
            # Get regime-specific filters
            filters = self.adaptive_config.get_regime_specific_filters(self.current_regime)
            
            # Apply filters
            if latest['RSI'] > filters['skip_rsi_above']:
                return False
            
            if latest['Price_Change_3D'] > filters['skip_price_change_3d_above']:
                return False
            
            if latest['Price_Change_5D'] > filters['skip_price_change_5d_above']:
                return False
            
            if (latest['Volume'] > filters['skip_volume_spike_threshold'] * latest['Volume_avg'] and 
                latest['Price_Change_1D'] > 7):
                return False
            
            if len(df) >= 21:
                mean_atr = df['ATR'][-21:-1].mean()
                if pd.notna(mean_atr) and latest['ATR'] > filters['skip_atr_multiplier'] * mean_atr:
                    return False
            
            return True
            
        except Exception as e:
            print(f"⚠️ Filter error for {ticker}: {e}")
            return False
    
    def _analyze_stock_traditional(self, ticker):
        """Traditional stock analysis without ML"""
        try:
            df = yf.download(ticker, period="3mo", interval="1d", progress=False)
            
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            df.columns.name = None
            
            df = df[['Open', 'High', 'Low', 'Close', 'Volume']].dropna()
            df = df.astype(float)
            
            if df.empty or len(df) < 50:
                return None
            
            df = calculate_additional_indicators(df)
            df.dropna(inplace=True)
            
            if df.empty:
                return None
            
            # Detect candle pattern
            df['Candle'] = "None"
            df.at[df.index[-1], 'Candle'] = detect_candle_pattern(df)
            
            latest = df.iloc[-1]
            previous = df.iloc[-2] if len(df) > 1 else latest
            
            # Get traditional strategy score
            score, matched_indicators = advanced_strategy_score(latest, previous)
            
            # Apply regime-specific scoring weights
            weights = self.adaptive_config.get_scoring_weights(self.current_regime)
            
            # Adjust score based on regime weights (simplified)
            regime_multiplier = weights.get('price_trend', 1.0)  # Use trend weight as overall multiplier
            adjusted_score = score * regime_multiplier
            
            # Create result
            result = {
                "ticker": ticker,
                "close": round(float(latest['Close']), 2),
                "ema": round(float(latest['EMA_50']), 2),
                "rsi": round(float(latest['RSI']), 2),
                "macd": round(float(latest['MACD']), 2),
                "signal": round(float(latest['Signal']), 2),
                "hist": round(float(latest['MACD_Hist']), 2),
                "volume": int(latest['Volume']),
                "volumeAvg": int(latest['Volume_avg']),
                "willr": round(float(latest['WilliamsR']), 2),
                "atr": round(float(latest['ATR']), 2),
                "bb_pos": round(float(latest['BB_Position']), 2),
                "priceChange1D": round(float(latest['Price_Change_1D']), 2),
                "priceChange3D": round(float(latest['Price_Change_3D']), 2),
                "priceChange5D": round(float(latest['Price_Change_5D']), 2),
                "stochK": round(float(latest['Stoch_K']), 2),
                "stochD": round(float(latest['Stoch_D']), 2),
                "pattern": latest['Candle'],
                "score": round(adjusted_score, 2),
                "base_score": round(score, 2),
                "matched_indicators": matched_indicators,
                "market_regime": self.current_regime,
                "regime_multiplier": round(regime_multiplier, 2),
                "analysis_type": "traditional_enhanced"
            }
            
            return result
            
        except Exception as e:
            print(f"⚠️ Analysis error for {ticker}: {e}")
            return None
    
    def _execute_qualified_trades(self, qualified_stocks):
        """Execute trades for qualified stocks"""
        print(f"\n⚡ Executing Qualified Trades...")
        
        if not qualified_stocks:
            print("ℹ️ No qualified stocks to execute")
            return
        
        # Sort by score
        qualified_stocks.sort(key=lambda x: x['score'], reverse=True)
        
        # Limit trades
        max_trades = min(5, len(qualified_stocks))
        
        for i, stock in enumerate(qualified_stocks[:max_trades]):
            try:
                print(f"🎯 Executing trade {i+1}/{max_trades}: {stock['ticker']}")
                
                execution_result = self.execution_engine.execute_trade_signal(
                    stock, self.current_regime
                )
                
                if execution_result:
                    self.session_stats['executed_trades'] += 1
                    print(f"✅ Trade executed: {stock['ticker']}")
                else:
                    print(f"❌ Trade failed: {stock['ticker']}")
                
                time.sleep(2)
                
            except Exception as e:
                print(f"⚠️ Execution error for {stock['ticker']}: {e}")
    
    def _finalize_session(self, qualified_stocks):
        """Finalize session"""
        try:
            # Store results
            if qualified_stocks:
                self._store_screening_results(qualified_stocks)
            
            # Send summary
            self._send_session_summary(qualified_stocks)
            
        except Exception as e:
            print(f"⚠️ Finalization error: {e}")
    
    def _store_screening_results(self, qualified_stocks):
        """Store results in database"""
        try:
            batch_data = {
                "num_matches": len(qualified_stocks),
                "source": "ai_enhanced_no_ml",
                "market_regime": self.current_regime,
                "session_stats": self.session_stats
            }
            
            batch_res = self.supabase.table("screener_batches").insert(batch_data).execute()
            batch_id = batch_res.data[0]["id"]
            
            results_payload = [
                {
                    "batch_id": batch_id,
                    "ticker": stock["ticker"],
                    "score": stock["score"],
                    "indicators": stock["matched_indicators"],
                    "market_regime": self.current_regime
                }
                for stock in qualified_stocks
            ]
            
            self.supabase.table("screener_results").insert(results_payload).execute()
            print(f"✅ Results stored: Batch ID {batch_id}")
            
        except Exception as e:
            print(f"⚠️ Error storing results: {e}")
    
    def _send_session_summary(self, qualified_stocks):
        """Send session summary"""
        try:
            stats = self.session_stats
            
            if qualified_stocks:
                top_stocks = sorted(qualified_stocks, key=lambda x: x['score'], reverse=True)[:5]
                
                stocks_text = "\\n".join([
                    f"📊 {stock['ticker']} - Score: {stock['score']:.1f}"
                    for stock in top_stocks
                ])
                
                summary_message = f"""🤖 AI SCREENING COMPLETE

                                    📊 Session Stats:
                                    🔍 Analyzed: {stats['total_analyzed']}
                                    ✅ Passed Filters: {stats['passed_filters']}
                                    🧠 Traditional Filtered: {stats['traditional_filtered']}
                                    🎯 Final Signals: {stats['final_signals']}
                                    ⚡ Executed: {stats['executed_trades']}

                                    🏆 Top Signals:
                                    {stocks_text}

                                    📈 Regime: {self.current_regime}
                                    🕒 Completed: {datetime.now().strftime('%H:%M')}
                                    Note: ML disabled for testing"""
            else:
                summary_message = f"""🤖 AI SCREENING COMPLETE

                📊 Session Stats:
                🔍 Analyzed: {stats['total_analyzed']}
                ✅ Passed Filters: {stats['passed_filters']}
                🚫 No stocks qualified today

                📈 Regime: {self.current_regime}
                🔧 Consider adjusting thresholds

                🕒 Completed: {datetime.now().strftime('%H:%M')}"""
            
            send_telegram(summary_message)
            
        except Exception as e:
            print(f"⚠️ Error sending summary: {e}")

# Main functions
def run_ai_enhanced_screening(auto_execute=False):
    """Main function without ML"""
    #if not AI_IMPORTS_OK:
    #    print("❌ AI components not available")
    #    return
        
    try:
        screener = EnhancedScreenerNoML()
        screener.run_enhanced_screening(auto_execute=auto_execute)
    except Exception as e:
        print(f"❌ Screener failed: {e}")

def run_screener():
    """Legacy compatibility"""
    run_ai_enhanced_screening_no_ml(auto_execute=True)

if __name__ == "__main__":
    run_ai_enhanced_screening_no_ml(auto_execute=True)
