# execution_engine_fixed.py - Fixed to work with your existing database schema
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from supabase import create_client
import time
import json

# Import your fixed components
from risk_manager import RiskManager, StopLossOptimizer
from multi_timeframe_analyzer import EntryOptimizer
from indicators import SUPABASE_URL, SUPABASE_KEY

# Import the column mapping
from column_mapping import get_insert_data_mapped, get_update_data_mapped

# Import fixed telegram
try:
    from telegram_fix import send_telegram
except ImportError:
    from indicators import send_telegram

class ExecutionEngineFixed:
    """
    Smart order execution adapted for your existing database schema
    """
    def __init__(self):
        self.supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        self.risk_manager = RiskManager()
        self.stop_optimizer = StopLossOptimizer()
        # self.entry_optimizer = EntryOptimizer()  # Comment out if causing issues
        
        # Execution settings
        self.max_slippage = 0.005
        self.order_timeout = 300
        self.min_liquidity = 100000
        
    def execute_trade_signal(self, signal_data, market_regime="SIDEWAYS"):
        """
        Execute trade using your existing database schema
        """
        try:
            ticker = signal_data['ticker']
            print(f"🎯 Executing trade signal for {ticker}")
            
            # Pre-execution checks
            if not self._pre_execution_checks(signal_data):
                return None
            
            # Get current market data
            current_data = self._get_current_market_data(ticker)
            if not current_data:
                print(f"❌ Cannot get current market data for {ticker}")
                return None
            
            current_price = current_data['current_price']
            
            # Calculate optimal stop loss
            stock_df = self._get_stock_data_for_stop(ticker)
            stop_loss, stop_type = self.stop_optimizer.calculate_dynamic_stop(
                stock_df, current_price, 'momentum'  # Default pattern type
            )
            
            # Calculate position size
            confidence_score = signal_data.get('score', signal_data.get('final_score', 5.0))
            volatility_factor = current_data.get('atr_ratio', 1.0)
            
            position_size, sizing_reason = self.risk_manager.calculate_position_size(
                current_price, stop_loss, confidence_score, market_regime, volatility_factor
            )
            
            if position_size <= 0:
                print(f"⚠️ Position size too small for {ticker}: {sizing_reason}")
                return None
            
            # Calculate targets
            targets = self._calculate_profit_targets(current_price, stop_loss)
            
            # Execute the trade
            execution_result = self._execute_paper_trade_fixed(
                ticker, signal_data, current_price, position_size, 
                stop_loss, targets, market_regime, confidence_score, stop_type
            )
            
            if execution_result['success']:
                self._send_execution_notification_fixed(execution_result)
                print(f"✅ Trade executed successfully for {ticker}")
                return execution_result
            else:
                print(f"❌ Trade execution failed for {ticker}: {execution_result['reason']}")
                return None
                
        except Exception as e:
            print(f"❌ Error executing trade for {signal_data.get('ticker', 'Unknown')}: {e}")
            return None
    
    def _pre_execution_checks(self, signal_data):
        """Pre-execution validation checks"""
        ticker = signal_data['ticker']
        
        # Check if trading is allowed
        can_trade, reason = self.risk_manager.should_trade_today()
        if not can_trade:
            print(f"🚫 Trading not allowed: {reason}")
            return False
        
        # Check existing position using your table structure
        if self._has_existing_position(ticker):
            print(f"⚠️ Already have position in {ticker}")
            return False
        
        # Check signal strength
        score = signal_data.get('score', signal_data.get('final_score', 0))
        if score < 4.0:
            print(f"⚠️ Signal too weak for {ticker}: {score}")
            return False
        
        return True
    
    def _get_current_market_data(self, ticker):
        """Get current market data"""
        try:
            data = yf.download(ticker, period="5d", interval="1d", progress=False)
            
            if data.empty:
                return None
                
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(0)
            
            latest = data.iloc[-1]
            
            # Calculate metrics
            atr = (data['High'] - data['Low']).rolling(14).mean().iloc[-1]
            avg_volume = data['Volume'].rolling(20).mean().iloc[-1]
            atr_ratio = atr / data['Close'].rolling(20).mean().iloc[-1]
            
            return {
                'current_price': float(latest['Close']),
                'volume': float(latest['Volume']),
                'avg_volume': float(avg_volume) if pd.notna(avg_volume) else float(latest['Volume']),
                'atr': float(atr) if pd.notna(atr) else 50.0,
                'atr_ratio': float(atr_ratio) if pd.notna(atr_ratio) else 1.0,
                'timestamp': datetime.now()
            }
            
        except Exception as e:
            print(f"⚠️ Error getting market data for {ticker}: {e}")
            return None
    
    def _get_stock_data_for_stop(self, ticker):
        """Get stock data for stop loss calculation"""
        try:
            data = yf.download(ticker, period="3mo", interval="1d", progress=False)
            
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(0)
            
            # Calculate ATR
            data['ATR'] = (data['High'] - data['Low']).rolling(14).mean()
            
            return data
            
        except:
            return pd.DataFrame()
    
    def _calculate_profit_targets(self, entry_price, stop_loss):
        """Calculate profit targets"""
        risk = entry_price - stop_loss
        
        return {
            'target_1': entry_price + (risk * 1.5),  # 1.5:1 R:R
            'target_2': entry_price + (risk * 2.0),  # 2:1 R:R  
            'target_3': entry_price + (risk * 3.0),  # 3:1 R:R
        }
    
    def _execute_paper_trade_fixed(self, ticker, signal_data, entry_price, position_size, 
                                  stop_loss, targets, market_regime, confidence_score, stop_type):
        """Execute paper trade using your database schema"""
        try:
            # Simulate slippage
            slippage = np.random.uniform(0, self.max_slippage)
            executed_price = entry_price * (1 + slippage)
            
            # Calculate values
            position_value = executed_price * position_size
            initial_risk = abs(executed_price - stop_loss) * position_size
            
            # Prepare data for your database schema
            trade_data = {
                'ticker': ticker,
                'price': executed_price,                    # Your column name
                'timestamp': datetime.now(),                # Your column name  
                'action': 'BUY',
                'status': 'OPEN',
                'quantity': int(position_size),
                'total_invested': position_value,           # Your column name
                'reason': f"AI Signal Score: {confidence_score:.1f}",
                'score': confidence_score,                  # Your column name
                'ml_probability': signal_data.get('ml_probability', 0.7),
                'market_regime': market_regime,
                'stop_type': stop_type,
                'reasoning': json.dumps({                   # Your column name (but misspelled as 'easoning')
                    'signal_indicators': signal_data.get('matched_indicators', []),
                    'market_regime': market_regime,
                    'stop_type': stop_type,
                    'entry_strategy': 'ai_enhanced'
                })
            }
            
            # Add new columns if they were added to your table
            try:
                trade_data.update({
                    'stop_loss': stop_loss,
                    'target_1': targets['target_1'],
                    'target_2': targets['target_2'], 
                    'target_3': targets['target_3'],
                    'initial_risk': initial_risk,
                    'slippage': slippage,
                    'order_id': f"{ticker}_{int(time.time())}",
                    'matched_indicators': json.dumps(signal_data.get('matched_indicators', [])),
                    'entry_date': datetime.now(),
                    'position_value': position_value,
                    'signal_score': confidence_score
                })
            except Exception as col_error:
                print(f"⚠️ Some new columns not available: {col_error}")
            
            # Insert into database
            response = self.supabase.table("trades").insert(trade_data).execute()
            
            if response.data:
                trade_id = response.data[0]['id']
                
                execution_result = {
                    'success': True,
                    'trade_id': trade_id,
                    'ticker': ticker,
                    'executed_price': executed_price,
                    'slippage': slippage,
                    'position_size': position_size,
                    'position_value': position_value,
                    'initial_risk': initial_risk,
                    'stop_loss': stop_loss,
                    'targets': targets,
                    'execution_time': datetime.now(),
                    'confidence_score': confidence_score,
                    'market_regime': market_regime
                }
                
                return execution_result
            else:
                return {'success': False, 'reason': 'Database insert failed'}
                
        except Exception as e:
            print(f"❌ Execution error: {e}")
            return {'success': False, 'reason': str(e)}
    
    def _send_execution_notification_fixed(self, execution_result):
        """Send execution notification with safe formatting"""
        try:
            ticker = execution_result['ticker']
            entry_price = execution_result['executed_price']
            position_size = execution_result['position_size']
            stop_loss = execution_result['stop_loss']
            targets = execution_result['targets']
            confidence = execution_result['confidence_score']
            
            risk_amount = execution_result['initial_risk']
            target1_reward = (targets['target_1'] - entry_price) * position_size
            
            # Simple message without complex markdown
            message = f"""TRADE EXECUTED

Ticker: {ticker}
Entry: Rs{entry_price:.2f}
Quantity: {position_size:,} shares
Investment: Rs{execution_result['position_value']:,.0f}

Stop Loss: Rs{stop_loss:.2f}
Target 1: Rs{targets['target_1']:.2f}
Target 2: Rs{targets['target_2']:.2f}

Risk: Rs{risk_amount:,.0f}
Reward: Rs{target1_reward:,.0f} (1.5:1 R:R)

Confidence: {confidence:.1f}/10
Regime: {execution_result['market_regime']}
Slippage: {execution_result['slippage']*100:.2f}%

Time: {execution_result['execution_time'].strftime('%H:%M')}"""
            
            send_telegram(message)
            
        except Exception as e:
            print(f"⚠️ Error sending notification: {e}")
    
    def _has_existing_position(self, ticker):
        """Check existing position using your table structure"""
        try:
            response = self.supabase.table("trades").select("ticker").eq("ticker", ticker).eq("status", "OPEN").execute()
            return len(response.data) > 0
        except:
            return False

# Position manager adapted for your schema
class PositionManagerFixed:
    """Position manager adapted for your database schema"""
    def __init__(self):
        self.supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        self.stop_optimizer = StopLossOptimizer()
        
    def update_all_positions(self):
        """Update all open positions"""
        try:
            print("🔄 Updating all open positions...")
            
            # Get open positions using your schema
            response = self.supabase.table("trades").select("*").eq("status", "OPEN").execute()
            open_positions = response.data
            
            if not open_positions:
                print("ℹ️ No open positions to update")
                return
            
            updated_count = 0
            closed_count = 0
            
            for position in open_positions:
                try:
                    result = self._update_single_position_fixed(position)
                    
                    if result['action'] == 'updated':
                        updated_count += 1
                    elif result['action'] == 'closed':
                        closed_count += 1
                        
                except Exception as e:
                    print(f"⚠️ Error updating {position['ticker']}: {e}")
            
            print(f"✅ Update complete: {updated_count} updated, {closed_count} closed")
            
        except Exception as e:
            print(f"❌ Error updating positions: {e}")
    
    def _update_single_position_fixed(self, position):
        """Update single position using your schema"""
        ticker = position['ticker']
        
        # Get current price
        current_price = self._get_current_price(ticker)
        if not current_price:
            return {'action': 'error', 'reason': 'Cannot get current price'}
        
        entry_price = float(position['price'])  # Your column name
        current_stop = float(position.get('stop_loss', entry_price * 0.95))
        quantity = int(position['quantity'])
        
        # Calculate P&L
        unrealized_pnl = (current_price - entry_price) * quantity
        pnl_percent = (current_price - entry_price) / entry_price * 100
        
        # Check stop loss
        if current_price <= current_stop:
            return self._close_position_fixed(position, current_price, 'stop_loss')
        
        # Check targets (if available)
        target_hit = self._check_targets_fixed(position, current_price)
        if target_hit:
            return self._close_position_fixed(position, current_price, f'target_{target_hit}')
        
        # Update trailing stop
        new_stop, trail_reason = self.stop_optimizer.update_trailing_stop(
            current_price, entry_price, current_stop
        )
        
        # Update in database using your column names
        update_data = {
            'last_updated': datetime.now().isoformat()
        }
        
        # Add new columns if available
        try:
            update_data.update({
                'current_price': current_price,
                'unrealized_pnl': unrealized_pnl,
                'pnl_percent': pnl_percent,
                'stop_loss': new_stop
            })
        except:
            pass  # New columns not available yet
        
        self.supabase.table("trades").update(update_data).eq("id", position['id']).execute()
        
        return {'action': 'updated', 'new_stop': new_stop, 'pnl': unrealized_pnl}
    
    def _get_current_price(self, ticker):
        """Get current price"""
        try:
            data = yf.download(ticker, period="1d", interval="1m", progress=False)
            if not data.empty:
                if isinstance(data.columns, pd.MultiIndex):
                    data.columns = data.columns.get_level_values(0)
                return float(data['Close'].iloc[-1])
            return None
        except:
            return None
    
    def _check_targets_fixed(self, position, current_price):
        """Check targets using your schema"""
        targets = {
            1: position.get('target_1'),
            2: position.get('target_2'),
            3: position.get('target_3')
        }
        
        for target_num, target_price in targets.items():
            if target_price and float(current_price) >= float(target_price):
                return target_num
        
        return None
    
    def _close_position_fixed(self, position, exit_price, exit_reason):
        """Close position using your schema"""
        try:
            ticker = position['ticker']
            entry_price = float(position['price'])  # Your column name
            quantity = int(position['quantity'])
            
            # Calculate final P&L
            final_pnl = (exit_price - entry_price) * quantity
            pnl_percent = (exit_price - entry_price) / entry_price * 100
            
            # Calculate holding period
            entry_date = datetime.fromisoformat(position['timestamp'].replace('Z', '+00:00'))
            exit_date = datetime.now()
            days_held = (exit_date - entry_date).days
            
            # Update using your column names
            update_data = {
                'status': 'CLOSED',
                'reason': f"Closed: {exit_reason}",  # Update your reason field
                'last_updated': exit_date.isoformat()
            }
            
            # Add new columns if available
            try:
                update_data.update({
                    'exit_date': exit_date.isoformat(),
                    'exit_price': exit_price,
                    'exit_reason': exit_reason,
                    'pnl': final_pnl,
                    'pnl_percent': pnl_percent,
                    'days_held': days_held
                })
            except:
                pass  # New columns not available
            
            self.supabase.table("trades").update(update_data).eq("id", position['id']).execute()
            
            # Send notification
            self._send_closure_notification_fixed(position, exit_price, final_pnl, exit_reason, days_held)
            
            print(f"🔒 Position closed: {ticker} | P&L: Rs{final_pnl:,.0f} ({pnl_percent:+.1f}%)")
            
            return {'action': 'closed', 'pnl': final_pnl, 'reason': exit_reason}
            
        except Exception as e:
            print(f"❌ Error closing position {position['ticker']}: {e}")
            return {'action': 'error', 'reason': str(e)}
    
    def _send_closure_notification_fixed(self, position, exit_price, pnl, exit_reason, days_held):
        """Send closure notification with safe formatting"""
        try:
            ticker = position['ticker']
            entry_price = float(position['price'])  # Your column name
            pnl_percent = (exit_price - entry_price) / entry_price * 100
            
            status = "PROFIT" if pnl > 0 else "LOSS"
            icon = "✅" if pnl > 0 else "❌"
            
            reason_text = {
                'stop_loss': 'Stop Loss Hit',
                'target_1': 'Target 1 Hit',
                'target_2': 'Target 2 Hit', 
                'target_3': 'Target 3 Hit',
                'manual': 'Manual Exit'
            }.get(exit_reason, exit_reason)
            
            message = f"""{icon} POSITION CLOSED - {status}

Ticker: {ticker}
Entry: Rs{entry_price:.2f}
Exit: Rs{exit_price:.2f}
Reason: {reason_text}

Final P&L: Rs{pnl:,.0f} ({pnl_percent:+.1f}%)
Held: {days_held} days
Daily Return: {pnl_percent/max(days_held, 1):+.2f}%"""
            
            send_telegram(message)
            
        except Exception as e:
            print(f"⚠️ Error sending closure notification: {e}")

# Export the fixed classes
def get_execution_engine():
    """Get the fixed execution engine"""
    return ExecutionEngineFixed()

def get_position_manager():
    """Get the fixed position manager"""
    return PositionManagerFixed()

# Usage and testing
if __name__ == "__main__":
    print("🧪 Testing Fixed Execution Engine...")
    
    # Test execution engine
    execution_engine = ExecutionEngineFixed()
    position_manager = PositionManagerFixed()
    
    # Test with sample signal
    sample_signal = {
        'ticker': 'RELIANCE.NS',
        'score': 6.5,
        'close': 2500,
        'matched_indicators': ['rsi', 'macd', 'volume'],
        'analysis_type': 'traditional_enhanced'
    }
    
    print(f"\n🎯 Testing Trade Execution...")
    print(f"   Signal: {sample_signal['ticker']} (Score: {sample_signal['score']})")
    
    # Uncomment to test actual execution
    # execution_result = execution_engine.execute_trade_signal(sample_signal, "BULL_WEAK")
    # if execution_result:
    #     print(f"   ✅ Execution successful: {execution_result['trade_id']}")
    # else:
    #     print(f"   ❌ Execution failed")
    
    # Test position management
    print(f"\n📊 Testing Position Management...")
    position_manager.update_all_positions()
    
    print(f"\n✅ Fixed Execution Engine testing complete")
