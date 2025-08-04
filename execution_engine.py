import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from supabase import create_client
from risk_manager import RiskManager, StopLossOptimizer
from multi_timeframe_analyzer import EntryOptimizer
from indicators import send_telegram, SUPABASE_URL, SUPABASE_KEY
import time
import json

class ExecutionEngine:
    """
    Smart order execution with optimal timing and risk management
    """
    def __init__(self):
        self.supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        self.risk_manager = RiskManager()
        self.stop_optimizer = StopLossOptimizer()
        self.entry_optimizer = EntryOptimizer()
        self.pending_orders = {}
        self.position_tracker = {}
        
        # Execution settings
        self.max_slippage = 0.005  # 0.5% max slippage
        self.order_timeout = 300   # 5 minutes timeout
        self.min_liquidity = 100000  # Minimum volume requirement
        
    def execute_trade_signal(self, signal_data, market_regime="SIDEWAYS"):
        """
        Execute a trade based on signal data with intelligent timing
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
            
            # Optimize entry timing and price
            entry_optimization = self.entry_optimizer.find_optimal_entry_price(
                ticker, signal_data
            )
            
            # Calculate optimal stop loss
            stock_df = self._get_stock_data_for_stop(ticker)
            stop_loss, stop_type = self.stop_optimizer.calculate_dynamic_stop(
                stock_df, current_price, signal_data.get('pattern_type', 'momentum')
            )
            
            # Calculate position size
            confidence_score = signal_data.get('final_score', signal_data.get('score', 5.0))
            volatility_factor = current_data.get('atr_ratio', 1.0)
            
            position_size, sizing_reason = self.risk_manager.calculate_position_size(
                current_price, stop_loss, confidence_score, market_regime, volatility_factor
            )
            
            if position_size <= 0:
                print(f"⚠️ Position size too small for {ticker}: {sizing_reason}")
                return None
            
            # Calculate targets
            targets = self._calculate_profit_targets(current_price, stop_loss)
            
            # Create order
            order = self._create_order(
                ticker=ticker,
                signal_data=signal_data,
                entry_price=current_price,
                optimized_entry=entry_optimization,
                position_size=position_size,
                stop_loss=stop_loss,
                targets=targets,
                market_data=current_data,
                reasoning={
                    'sizing_reason': sizing_reason,
                    'stop_type': stop_type,
                    'market_regime': market_regime,
                    'confidence': confidence_score
                }
            )
            
            # Execute the order
            execution_result = self._execute_paper_trade(order)
            
            if execution_result['success']:
                # Send notification
                self._send_execution_notification(order, execution_result)
                
                # Store in database
                self._store_trade_in_db(order, execution_result)
                
                print(f"✅ Trade executed successfully for {ticker}")
                return execution_result
            else:
                print(f"❌ Trade execution failed for {ticker}: {execution_result['reason']}")
                return None
                
        except Exception as e:
            print(f"❌ Error executing trade for {signal_data.get('ticker', 'Unknown')}: {e}")
            return None
    
    def _pre_execution_checks(self, signal_data):
        """
        Perform pre-execution validation checks
        """
        ticker = signal_data['ticker']
        
        # Check if trading is allowed today
        can_trade, reason = self.risk_manager.should_trade_today()
        if not can_trade:
            print(f"🚫 Trading not allowed: {reason}")
            return False
        
        # Check if already have position in this stock
        if self._has_existing_position(ticker):
            print(f"⚠️ Already have position in {ticker}")
            return False
        
        # Check signal strength
        score = signal_data.get('final_score', signal_data.get('score', 0))
        if score < 4.0:
            print(f"⚠️ Signal too weak for {ticker}: {score}")
            return False
        
        return True
    
    def _get_current_market_data(self, ticker):
        """
        Get current market data for execution
        """
        try:
            # Get recent data
            data = yf.download(ticker, period="5d", interval="1d", progress=False)
            
            if data.empty:
                return None
                
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(0)
            
            latest = data.iloc[-1]
            
            # Calculate additional metrics
            atr = (data['High'] - data['Low']).rolling(14).mean().iloc[-1]
            avg_volume = data['Volume'].rolling(20).mean().iloc[-1]
            atr_ratio = atr / data['Close'].rolling(20).mean().iloc[-1]
            
            return {
                'current_price': latest['Close'],
                'volume': latest['Volume'],
                'avg_volume': avg_volume,
                'atr': atr,
                'atr_ratio': atr_ratio,
                'high': latest['High'],
                'low': latest['Low'],
                'timestamp': datetime.now()
            }
            
        except Exception as e:
            print(f"⚠️ Error getting market data for {ticker}: {e}")
            return None
    
    def _get_stock_data_for_stop(self, ticker):
        """
        Get stock data for stop loss calculation
        """
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
        """
        Calculate profit targets based on risk-reward ratios
        """
        risk = entry_price - stop_loss
        
        targets = {
            'target_1': entry_price + (risk * 1.5),  # 1.5:1 R:R
            'target_2': entry_price + (risk * 2.0),  # 2:1 R:R
            'target_3': entry_price + (risk * 3.0),  # 3:1 R:R
        }
        
        return targets
    
    def _create_order(self, **kwargs):
        """
        Create a structured order object
        """
        return {
            'ticker': kwargs['ticker'],
            'signal_data': kwargs['signal_data'],
            'entry_price': kwargs['entry_price'],
            'optimized_entry': kwargs['optimized_entry'],
            'position_size': kwargs['position_size'],
            'stop_loss': kwargs['stop_loss'],
            'targets': kwargs['targets'],
            'market_data': kwargs['market_data'],
            'reasoning': kwargs['reasoning'],
            'order_time': datetime.now(),
            'order_id': f"{kwargs['ticker']}_{int(time.time())}"
        }
    
    def _execute_paper_trade(self, order):
        """
        Execute paper trade with realistic simulation
        """
        try:
            ticker = order['ticker']
            entry_price = order['entry_price']
            position_size = order['position_size']
            
            # Simulate slippage (random between 0 and max_slippage)
            slippage = np.random.uniform(0, self.max_slippage)
            executed_price = entry_price * (1 + slippage)
            
            # Calculate position value
            position_value = executed_price * position_size
            
            # Calculate initial risk
            initial_risk = abs(executed_price - order['stop_loss']) * position_size
            
            execution_result = {
                'success': True,
                'executed_price': executed_price,
                'slippage': slippage,
                'position_value': position_value,
                'initial_risk': initial_risk,
                'execution_time': datetime.now(),
                'order_id': order['order_id']
            }
            
            return execution_result
            
        except Exception as e:
            return {
                'success': False,
                'reason': str(e),
                'execution_time': datetime.now()
            }
    
    def _send_execution_notification(self, order, execution_result):
        """
        Send Telegram notification for trade execution
        """
        try:
            ticker = order['ticker']
            entry_price = execution_result['executed_price']
            position_size = order['position_size']
            stop_loss = order['stop_loss']
            targets = order['targets']
            confidence = order['reasoning']['confidence']
            
            # Calculate risk and reward
            risk_per_share = entry_price - stop_loss
            risk_amount = risk_per_share * position_size
            target1_reward = (targets['target_1'] - entry_price) * position_size
            
            message = f"""
🎯 *TRADE EXECUTED*

📊 *{ticker}*
💰 Entry: ₹{entry_price:.2f}
📈 Quantity: {position_size:,} shares
💸 Investment: ₹{execution_result['position_value']:,.0f}

🛑 Stop Loss: ₹{stop_loss:.2f}
🎯 Target 1: ₹{targets['target_1']:.2f}
🎯 Target 2: ₹{targets['target_2']:.2f}

💀 Risk: ₹{risk_amount:,.0f} ({risk_per_share/entry_price*100:.1f}%)
💎 Reward: ₹{target1_reward:,.0f} (1.5:1 R:R)

🧠 Confidence: {confidence:.1f}/10
📋 Regime: {order['reasoning']['market_regime']}
⚡ Slippage: {execution_result['slippage']*100:.2f}%

🕒 Time: {execution_result['execution_time'].strftime('%H:%M')}
            """
            
            send_telegram(message.strip())
            
        except Exception as e:
            print(f"⚠️ Error sending execution notification: {e}")
    
    def _store_trade_in_db(self, order, execution_result):
        """
        Store trade details in Supabase database
        """
        try:
            trade_data = {
                'ticker': order['ticker'],
                'entry_date': execution_result['execution_time'].isoformat(),
                'entry_price': execution_result['executed_price'],
                'quantity': order['position_size'],
                'stop_loss': order['stop_loss'],
                'target_1': order['targets']['target_1'],
                'target_2': order['targets']['target_2'],
                'target_3': order['targets']['target_3'],
                'initial_risk': execution_result['initial_risk'],
                'position_value': execution_result['position_value'],
                'status': 'open',
                'signal_score': order['signal_data'].get('final_score', order['signal_data'].get('score', 0)),
                'market_regime': order['reasoning']['market_regime'],
                'stop_type': order['reasoning']['stop_type'],
                'slippage': execution_result['slippage'],
                'order_id': order['order_id'],
                'matched_indicators': json.dumps(order['signal_data'].get('matched_indicators', [])),
                'reasoning': json.dumps(order['reasoning'])
            }
            
            response = self.supabase.table("trades").insert(trade_data).execute()
            
            if response.data:
                print(f"📝 Trade stored in database: {order['ticker']}")
                return response.data[0]['id']
            else:
                print(f"⚠️ Failed to store trade in database")
                return None
                
        except Exception as e:
            print(f"❌ Error storing trade in database: {e}")
            return None
    
    def _has_existing_position(self, ticker):
        """
        Check if we already have a position in this stock
        """
        try:
            response = self.supabase.table("trades").select("ticker").eq("ticker", ticker).eq("status", "open").execute()
            return len(response.data) > 0
        except:
            return False

class PositionManager:
    """
    Manages existing positions with trailing stops and profit taking
    """
    def __init__(self):
        self.supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        self.stop_optimizer = StopLossOptimizer()
        
    def update_all_positions(self):
        """
        Update all open positions with current prices and trailing stops
        """
        try:
            print("🔄 Updating all open positions...")
            
            # Get all open positions
            response = self.supabase.table("trades").select("*").eq("status", "open").execute()
            open_positions = response.data
            
            if not open_positions:
                print("ℹ️ No open positions to update")
                return
            
            updated_count = 0
            closed_count = 0
            
            for position in open_positions:
                try:
                    update_result = self._update_single_position(position)
                    
                    if update_result['action'] == 'updated':
                        updated_count += 1
                    elif update_result['action'] == 'closed':
                        closed_count += 1
                        
                except Exception as e:
                    print(f"⚠️ Error updating position {position['ticker']}: {e}")
            
            print(f"✅ Position update complete: {updated_count} updated, {closed_count} closed")
            
        except Exception as e:
            print(f"❌ Error updating positions: {e}")
    
    def _update_single_position(self, position):
        """
        Update a single position with current market data
        """
        ticker = position['ticker']
        
        # Get current price
        current_price = self._get_current_price(ticker)
        if not current_price:
            return {'action': 'error', 'reason': 'Cannot get current price'}
        
        entry_price = position['entry_price']
        current_stop = position['stop_loss']
        quantity = position['quantity']
        
        # Calculate current P&L
        unrealized_pnl = (current_price - entry_price) * quantity
        pnl_percent = (current_price - entry_price) / entry_price * 100
        
        # Check if stop loss is hit
        if current_price <= current_stop:
            return self._close_position(position, current_price, 'stop_loss')
        
        # Check if target is hit
        target_hit = self._check_targets(position, current_price)
        if target_hit:
            return self._close_position(position, current_price, f'target_{target_hit}')
        
        # Update trailing stop
        new_stop, trail_reason = self.stop_optimizer.update_trailing_stop(
            current_price, entry_price, current_stop
        )
        
        # Update position in database
        update_data = {
            'current_price': current_price,
            'unrealized_pnl': unrealized_pnl,
            'pnl_percent': pnl_percent,
            'stop_loss': new_stop,
            'last_updated': datetime.now().isoformat()
        }
        
        self.supabase.table("trades").update(update_data).eq("id", position['id']).execute()
        
        # Send update notification if significant change
        if trail_reason == 'stop_trailed' or abs(pnl_percent) > 5:
            self._send_position_update(position, current_price, unrealized_pnl, new_stop, trail_reason)
        
        return {'action': 'updated', 'new_stop': new_stop, 'pnl': unrealized_pnl}
    
    def _get_current_price(self, ticker):
        """
        Get current market price for a ticker
        """
        try:
            data = yf.download(ticker, period="1d", interval="1m", progress=False)
            if not data.empty:
                if isinstance(data.columns, pd.MultiIndex):
                    data.columns = data.columns.get_level_values(0)
                return data['Close'].iloc[-1]
            return None
        except:
            return None
    
    def _check_targets(self, position, current_price):
        """
        Check if any profit targets are hit
        """
        targets = {
            1: position.get('target_1'),
            2: position.get('target_2'),
            3: position.get('target_3')
        }
        
        for target_num, target_price in targets.items():
            if target_price and current_price >= target_price:
                return target_num
        
        return None
    
    def _close_position(self, position, exit_price, exit_reason):
        """
        Close a position and calculate final P&L
        """
        try:
            ticker = position['ticker']
            entry_price = position['entry_price']
            quantity = position['quantity']
            
            # Calculate final P&L
            final_pnl = (exit_price - entry_price) * quantity
            pnl_percent = (exit_price - entry_price) / entry_price * 100
            
            # Calculate holding period
            entry_date = datetime.fromisoformat(position['entry_date'].replace('Z', '+00:00'))
            exit_date = datetime.now()
            days_held = (exit_date - entry_date).days
            
            # Update position in database
            update_data = {
                'status': 'closed',
                'exit_date': exit_date.isoformat(),
                'exit_price': exit_price,
                'exit_reason': exit_reason,
                'pnl': final_pnl,
                'pnl_percent': pnl_percent,
                'days_held': days_held,
                'last_updated': exit_date.isoformat()
            }
            
            self.supabase.table("trades").update(update_data).eq("id", position['id']).execute()
            
            # Send closure notification
            self._send_closure_notification(position, exit_price, final_pnl, exit_reason, days_held)
            
            print(f"🔒 Position closed: {ticker} | P&L: ₹{final_pnl:,.0f} ({pnl_percent:+.1f}%)")
            
            return {'action': 'closed', 'pnl': final_pnl, 'reason': exit_reason}
            
        except Exception as e:
            print(f"❌ Error closing position {position['ticker']}: {e}")
            return {'action': 'error', 'reason': str(e)}
    
    def _send_position_update(self, position, current_price, pnl, new_stop, trail_reason):
        """
        Send position update notification
        """
        try:
            ticker = position['ticker']
            entry_price = position['entry_price']
            pnl_percent = (current_price - entry_price) / entry_price * 100
            
            if trail_reason == 'stop_trailed':
                icon = "📈"
                status = "STOP TRAILED"
            elif pnl > 0:
                icon = "💚"
                status = "PROFIT UPDATE"
            else:
                icon = "🔴"
                status = "LOSS UPDATE"
            
            message = f"""
{icon} *{status}*

📊 *{ticker}*
💰 Entry: ₹{entry_price:.2f}
📈 Current: ₹{current_price:.2f}
🛑 New Stop: ₹{new_stop:.2f}

💸 P&L: ₹{pnl:,.0f} ({pnl_percent:+.1f}%)
📅 Days: {(datetime.now() - datetime.fromisoformat(position['entry_date'].replace('Z', '+00:00'))).days}
            """
            
            send_telegram(message.strip())
            
        except Exception as e:
            print(f"⚠️ Error sending position update: {e}")
    
    def _send_closure_notification(self, position, exit_price, pnl, exit_reason, days_held):
        """
        Send position closure notification
        """
        try:
            ticker = position['ticker']
            entry_price = position['entry_price']
            pnl_percent = (exit_price - entry_price) / entry_price * 100
            
            if pnl > 0:
                icon = "✅"
                status = "PROFIT"
            else:
                icon = "❌"
                status = "LOSS"
            
            reason_text = {
                'stop_loss': 'Stop Loss Hit',
                'target_1': 'Target 1 Hit',
                'target_2': 'Target 2 Hit',
                'target_3': 'Target 3 Hit',
                'manual': 'Manual Exit'
            }.get(exit_reason, exit_reason)
            
            message = f"""
{icon} *POSITION CLOSED - {status}*

📊 *{ticker}*
💰 Entry: ₹{entry_price:.2f}
🚪 Exit: ₹{exit_price:.2f}
📊 Reason: {reason_text}

💸 Final P&L: ₹{pnl:,.0f} ({pnl_percent:+.1f}%)
📅 Held: {days_held} days
⚡ Daily Return: {pnl_percent/max(days_held, 1):+.2f}%
            """
            
            send_telegram(message.strip())
            
        except Exception as e:
            print(f"⚠️ Error sending closure notification: {e}")

# Usage and testing
if __name__ == "__main__":
    execution_engine = ExecutionEngine()
    position_manager = PositionManager()
    
    print("⚡ Execution Engine Testing")
    
    # Test with sample signal data
    sample_signal = {
        'ticker': 'RELIANCE.NS',
        'score': 6.5,
        'final_score': 6.5,
        'close': 2500,
        'matched_indicators': ['rsi', 'macd', 'volume'],
        'pattern_type': 'momentum'
    }
    
    print(f"\n🧪 Testing Trade Execution...")
    print(f"   Signal: {sample_signal['ticker']} (Score: {sample_signal['score']})")
    
    # Test execution (this would normally be called by your screener)
    # execution_result = execution_engine.execute_trade_signal(sample_signal, "BULL_WEAK")
    
    # Test position management
    print(f"\n📊 Testing Position Management...")
    position_manager.update_all_positions()
    
    print(f"\n✅ Execution Engine testing complete")
