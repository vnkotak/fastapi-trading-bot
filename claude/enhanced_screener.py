import yfinance as yf
import pandas as pd
import time
from datetime import datetime
from supabase import create_client, Client

# Import our new AI components
from claude.market_regime import MarketRegimeDetector
from claude.adaptive_config import AdaptiveConfig
from claude.multi_timeframe_analyzer import MultiTimeframeAnalyzer
from claude.ml_predictor import MLEnhancedScoring
from claude.execution_engine import ExecutionEngine
from claude.risk_manager import RiskManager

# Import existing components
from indicators import (
    calculate_additional_indicators,
    detect_candle_pattern,
    send_telegram,
    SUPABASE_URL,
    SUPABASE_KEY
)

class EnhancedScreener:
    """
    AI-Enhanced stock screener that combines all advanced components
    """
    def __init__(self):
        # Initialize database
        self.supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        
        # Initialize AI components
        self.regime_detector = MarketRegimeDetector()
        self.adaptive_config = AdaptiveConfig()
        self.multi_tf_analyzer = MultiTimeframeAnalyzer()
        self.ml_enhanced_scoring = MLEnhancedScoring()
        self.execution_engine = ExecutionEngine()
        self.risk_manager = RiskManager()
        
        # Current session data
        self.current_regime = None
        self.current_config = None
        self.session_stats = {
            'total_analyzed': 0,
            'passed_filters': 0,
            'ml_filtered': 0,
            'final_signals': 0,
            'executed_trades': 0
        }
        
    def run_enhanced_screening(self, auto_execute=False):
        """
        Run the complete AI-enhanced screening process
        """
        try:
            print("🚀 Starting AI-Enhanced Stock Screening")
            print("=" * 60)
            
            # Step 1: Detect market regime and adapt configuration
            self._initialize_session()
            
            # Step 2: Check if trading should be allowed
            if not self._check_trading_permissions():
                return
            
            # Step 3: Fetch stock universe
            tickers = self._fetch_stock_universe()
            if not tickers:
                return
            
            # Step 4: Run enhanced screening
            qualified_stocks = self._run_screening_pipeline(tickers)
            
            # Step 5: Execute trades if enabled
            if auto_execute and qualified_stocks:
                self._execute_qualified_trades(qualified_stocks)
            
            # Step 6: Store results and send summary
            self._finalize_session(qualified_stocks)
            
            print("✅ AI-Enhanced Screening Complete!")
            
        except Exception as e:
            print(f"❌ Critical error in enhanced screening: {e}")
            send_telegram(f"🚨 *SCREENING ERROR*\n\nCritical error: {str(e)}")
    
    def _initialize_session(self):
        """
        Initialize the screening session with market regime detection
        """
        print("\n📊 Initializing AI Session...")
        
        # Detect current market regime
        regime, confidence = self.regime_detector.detect_current_regime()
        self.current_regime = regime
        
        # Get adaptive configuration
        self.current_config = self.adaptive_config.get_current_config()
        
        # Get regime characteristics
        characteristics = self.regime_detector.get_regime_characteristics(regime)
        
        print(f"   Market Regime: {regime} (Confidence: {confidence:.2f})")
        print(f"   Trading Style: {characteristics['trading_style']}")
        print(f"   Expected Signals: {characteristics['expected_signals']}")
        print(f"   Score Threshold: {self.current_config['SCORE_THRESHOLD']}")
        print(f"   RSI Range: {self.current_config['RSI_MIN']}-{self.current_config['RSI_MAX']}")
        
        # Send session start notification
        start_message = f"""
🤖 *AI SCREENING SESSION STARTED*

📊 Market Regime: {regime}
🎯 Confidence: {confidence:.1%}
📈 Style: {characteristics['trading_style']}
⚡ Expected: {characteristics['expected_signals']}

🔧 *Adaptive Settings:*
📊 Score Threshold: {self.current_config['SCORE_THRESHOLD']}
📈 RSI Range: {self.current_config['RSI_MIN']}-{self.current_config['RSI_MAX']}
📊 Volume Multiplier: {self.current_config['VOLUME_MULTIPLIER']}x

🕒 Time: {datetime.now().strftime('%H:%M')}
        """
        send_telegram(start_message.strip())
    
    def _check_trading_permissions(self):
        """
        Check if trading should be allowed based on risk management
        """
        print("\n🚦 Checking Trading Permissions...")
        
        # Check market regime trading permission
        should_trade_regime, regime_reason = self.regime_detector.should_trade_today()
        
        # Check risk management permission
        should_trade_risk, risk_reason = self.risk_manager.should_trade_today()
        
        if not should_trade_regime:
            print(f"🚫 Trading suspended due to market regime: {regime_reason}")
            send_telegram(f"🚫 *TRADING SUSPENDED*\n\nReason: {regime_reason}")
            return False
        
        if not should_trade_risk:
            print(f"🚫 Trading suspended due to risk management: {risk_reason}")
            send_telegram(f"🚫 *TRADING SUSPENDED*\n\nReason: {risk_reason}")
            return False
        
        print("✅ Trading permissions granted")
        return True
    
    def _fetch_stock_universe(self):
        """
        Fetch the stock universe for screening
        """
        try:
            print("\n📋 Fetching Stock Universe...")
            
            response = self.supabase.table("master_stocks") \
                .select("ticker") \
                .eq("status", "Active") \
                .eq("exchange", "NSE") \
                .limit(3000) \
                .execute()
            
            tickers = [row["ticker"] for row in response.data]
            print(f"✅ Loaded {len(tickers)} tickers for screening")
            
            return tickers
            
        except Exception as e:
            print(f"❌ Failed to fetch stock universe: {e}")
            return []
    
    def _run_screening_pipeline(self, tickers):
        """
        Run the complete screening pipeline with AI enhancements
        """
        print(f"\n🔍 Running Enhanced Screening Pipeline...")
        print(f"Processing {len(tickers)} stocks...")
        
        qualified_stocks = []
        processed_count = 0
        
        for ticker in tickers:
            try:
                processed_count += 1
                self.session_stats['total_analyzed'] += 1
                
                # Progress reporting
                if processed_count % 100 == 0:
                    progress = (processed_count / len(tickers)) * 100
                    print(f"   Progress: {processed_count}/{len(tickers)} ({progress:.1f}%) - Found: {len(qualified_stocks)}")
                
                # Step 1: Basic data validation and regime-specific pre-filters
                if not self._apply_regime_filters(ticker):
                    continue
                
                self.session_stats['passed_filters'] += 1
                
                # Step 2: Multi-timeframe analysis
                multi_tf_result = self.multi_tf_analyzer.analyze_stock_comprehensive(ticker)
                if not multi_tf_result:
                    continue
                
                # Step 3: ML-enhanced scoring
                ml_enhanced_result = self._apply_ml_enhancement(ticker, multi_tf_result)
                if not ml_enhanced_result:
                    continue
                
                self.session_stats['ml_filtered'] += 1
                
                # Step 4: Final qualification check
                if ml_enhanced_result['final_score'] >= self.current_config['SCORE_THRESHOLD']:
                    qualified_stocks.append(ml_enhanced_result)
                    self.session_stats['final_signals'] += 1
                    
                    print(f"✅ Qualified: {ticker} (Score: {ml_enhanced_result['final_score']:.2f})")
                
                # Rate limiting
                time.sleep(0.1)
                
            except Exception as e:
                print(f"⚠️ Error processing {ticker}: {e}")
                continue
        
        print(f"\n📊 Screening Complete:")
        print(f"   Total Analyzed: {self.session_stats['total_analyzed']}")
        print(f"   Passed Filters: {self.session_stats['passed_filters']}")
        print(f"   ML Filtered: {self.session_stats['ml_filtered']}")
        print(f"   Final Signals: {self.session_stats['final_signals']}")
        
        return qualified_stocks
    
    def _apply_regime_filters(self, ticker):
        """
        Apply regime-specific pre-entry filters
        """
        try:
            # Download basic data
            df = yf.download(ticker, period="3mo", interval="1d", progress=False)
            
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            df.columns.name = None
            
            df = df[['Open', 'High', 'Low', 'Close', 'Volume']].dropna()
            df = df.astype(float)
            
            if df.empty or len(df) < 50:
                return False
            
            df = calculate_additional_indicators(df)
            df.dropna(inplace=True)
            
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
            
            mean_atr = df['ATR'][-21:-1].mean()
            if latest['ATR'] > filters['skip_atr_multiplier'] * mean_atr:
                return False
            
            return True
            
        except Exception as e:
            print(f"⚠️ Filter error for {ticker}: {e}")
            return False
    
    def _apply_ml_enhancement(self, ticker, multi_tf_result):
        """
        Apply ML enhancement to the multi-timeframe result
        """
        try:
            # Get stock data for ML analysis
            df = yf.download(ticker, period="6mo", interval="1d", progress=False)
            
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            
            df = calculate_additional_indicators(df)
            
            # Get Nifty data for relative strength
            nifty_data = yf.download("^NSEI", period="6mo", interval="1d", progress=False)
            if isinstance(nifty_data.columns, pd.MultiIndex):
                nifty_data.columns = nifty_data.columns.get_level_values(0)
            
            latest = df.iloc[-1]
            previous = df.iloc[-2]
            
            # Apply ML-enhanced scoring
            enhanced_score, enhanced_indicators, ml_details = self.ml_enhanced_scoring.enhanced_strategy_score(
                latest, previous, df, nifty_data
            )
            
            # Check ML confidence filter
            ml_confidence_ok, ml_reason = self.ml_enhanced_scoring.should_trade_ml_filter(
                ml_details['ml_probability']
            )
            
            if not ml_confidence_ok:
                return None
            
            # Prepare Candle Pattern
            df['Candle'] = "None"
            df.at[df.index[-1], 'Candle'] = detect_candle_pattern(df)
            
            # Create enhanced result
            enhanced_result = {
                "ticker": ticker,
                "close": round(latest['Close'], 2),
                "ema": round(latest['EMA_50'], 2),
                "rsi": round(latest['RSI'], 2),
                "macd": round(latest['MACD'], 2),
                "signal": round(latest['Signal'], 2),
                "hist": round(latest['MACD_Hist'], 2),
                "volume": int(latest['Volume']),
                "volumeAvg": int(latest['Volume_avg']),
                "willr": round(latest['WilliamsR'], 2),
                "atr": round(latest['ATR'], 2),
                "bb_pos": round(latest['BB_Position'], 2),
                "priceChange1D": round(latest['Price_Change_1D'], 2),
                "priceChange3D": round(latest['Price_Change_3D'], 2),
                "priceChange5D": round(latest['Price_Change_5D'], 2),
                "stochK": round(latest['Stoch_K'], 2),
                "stochD": round(latest['Stoch_D'], 2),
                "pattern": latest['Candle'],
                "score": round(multi_tf_result.get('base_score', enhanced_score), 2),
                "final_score": round(enhanced_score, 2),
                "ml_probability": round(ml_details['ml_probability'], 3),
                "ml_score": round(ml_details['ml_score'], 2),
                "traditional_score": round(ml_details['traditional_score'], 2),
                "matched_indicators": enhanced_indicators,
                "timeframe_bonus": round(multi_tf_result.get('timeframe_bonus', 0), 2),
                "entry_timing": multi_tf_result.get('entry_timing', {}),
                "market_regime": self.current_regime,
                "pattern_type": self._determine_pattern_type(enhanced_indicators)
            }
            
            return enhanced_result
            
        except Exception as e:
            print(f"⚠️ ML enhancement error for {ticker}: {e}")
            return None
    
    def _determine_pattern_type(self, indicators):
        """
        Determine the pattern type based on matched indicators
        """
        if "macd" in indicators and "volume" in indicators:
            return "momentum"
        elif "pattern" in indicators:
            return "reversal"
        elif "price" in indicators:
            return "breakout"
        else:
            return "pullback"
    
    def _execute_qualified_trades(self, qualified_stocks):
        """
        Execute trades for qualified stocks
        """
        print(f"\n⚡ Executing Qualified Trades...")
        
        if not qualified_stocks:
            print("ℹ️ No qualified stocks to execute")
            return
        
        # Sort by score (highest first)
        qualified_stocks.sort(key=lambda x: x['final_score'], reverse=True)
        
        # Limit to top 10 signals per session
        max_trades = min(10, len(qualified_stocks))
        
        for i, stock in enumerate(qualified_stocks[:max_trades]):
            try:
                print(f"🎯 Executing trade {i+1}/{max_trades}: {stock['ticker']}")
                
                execution_result = self.execution_engine.execute_trade_signal(
                    stock, self.current_regime
                )
                
                if execution_result:
                    self.session_stats['executed_trades'] += 1
                    print(f"✅ Trade executed successfully: {stock['ticker']}")
                else:
                    print(f"❌ Trade execution failed: {stock['ticker']}")
                
                # Small delay between executions
                time.sleep(2)
                
            except Exception as e:
                print(f"⚠️ Execution error for {stock['ticker']}: {e}")
    
    def _finalize_session(self, qualified_stocks):
        """
        Finalize the screening session and store results
        """
        print(f"\n📊 Finalizing Session...")
        
        # Store results in database
        if qualified_stocks:
            self._store_screening_results(qualified_stocks)
        
        # Send summary notification
        self._send_session_summary(qualified_stocks)
        
        # Update risk manager capital (if trades were executed)
        if self.session_stats['executed_trades'] > 0:
            self._update_risk_manager_capital()
    
    def _store_screening_results(self, qualified_stocks):
        """
        Store screening results in database
        """
        try:
            # Create screening batch
            batch_data = {
                "num_matches": len(qualified_stocks),
                "source": "ai_enhanced",
                "market_regime": self.current_regime,
                "session_stats": self.session_stats,
                "config_used": self.current_config
            }
            
            batch_res = self.supabase.table("screener_batches").insert(batch_data).execute()
            batch_id = batch_res.data[0]["id"]
            
            # Store individual results
            results_payload = [
                {
                    "batch_id": batch_id,
                    "ticker": stock["ticker"],
                    "score": stock["final_score"],
                    "ml_probability": stock["ml_probability"],
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
        """
        Send session summary via Telegram
        """
        try:
            stats = self.session_stats
            
            if qualified_stocks:
                # Sort by score for display
                top_stocks = sorted(qualified_stocks, key=lambda x: x['final_score'], reverse=True)[:5]
                
                stocks_text = "\n".join([
                    f"📊 *{stock['ticker']}* - Score: {stock['final_score']:.1f} (ML: {stock['ml_probability']:.2f})"
                    for stock in top_stocks
                ])
                
                summary_message = f"""
🤖 *AI SCREENING COMPLETE*

📊 *Session Stats:*
🔍 Analyzed: {stats['total_analyzed']}
✅ Passed Filters: {stats['passed_filters']}
🧠 ML Filtered: {stats['ml_filtered']}
🎯 Final Signals: {stats['final_signals']}
⚡ Executed: {stats['executed_trades']}

🏆 *Top Signals:*
{stocks_text}

📈 Regime: {self.current_regime}
🕒 Completed: {datetime.now().strftime('%H:%M')}
                """
            else:
                summary_message = f"""
🤖 *AI SCREENING COMPLETE*

📊 *Session Stats:*
🔍 Analyzed: {stats['total_analyzed']}
✅ Passed Filters: {stats['passed_filters']}
🧠 ML Filtered: {stats['ml_filtered']}
🚫 *No stocks qualified today*

📈 Regime: {self.current_regime}
🔧 Consider adjusting thresholds for {self.current_regime} market

🕒 Completed: {datetime.now().strftime('%H:%M')}
                """
            
            send_telegram(summary_message.strip())
            
        except Exception as e:
            print(f"⚠️ Error sending summary: {e}")
    
    def _update_risk_manager_capital(self):
        """
        Update risk manager with current capital (would integrate with actual portfolio)
        """
        # This would integrate with actual portfolio tracking
        # For now, just a placeholder
        pass

# Main execution function
def run_ai_enhanced_screening(auto_execute=False):
    """
    Main function to run the AI-enhanced screening
    """
    screener = EnhancedScreener()
    screener.run_enhanced_screening(auto_execute=auto_execute)

# Legacy compatibility function
def run_screener():
    """
    Legacy function for backward compatibility
    """
    run_ai_enhanced_screening(auto_execute=True)

if __name__ == "__main__":
    # Run the enhanced screener
    run_ai_enhanced_screening(auto_execute=True)
