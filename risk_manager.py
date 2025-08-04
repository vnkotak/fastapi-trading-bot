import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from supabase import create_client
from indicators import SUPABASE_URL, SUPABASE_KEY

class RiskManager:
    """
    Advanced risk management system with dynamic position sizing
    """
    def __init__(self, initial_capital=1000000):  # 10 lakh default
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.max_portfolio_risk = 0.02  # 2% total portfolio risk
        self.max_single_position = 0.05  # 5% max per position
        self.max_correlation_exposure = 0.15  # 15% max in correlated positions
        self.max_sector_exposure = 0.20  # 20% max per sector
        self.supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        
        # Risk thresholds
        self.stop_trading_drawdown = 0.10  # Stop trading at 10% drawdown
        self.reduce_size_drawdown = 0.05   # Reduce size at 5% drawdown
        
    def calculate_position_size(self, entry_price, stop_loss, confidence_score, 
                              market_regime="SIDEWAYS", volatility_factor=1.0):
        """
        Calculate optimal position size based on multiple factors
        """
        try:
            # Base risk per trade (1% of capital)
            base_risk_percent = 0.01
            
            # Adjust base risk based on confidence
            confidence_multiplier = self._get_confidence_multiplier(confidence_score)
            
            # Adjust for market regime
            regime_multiplier = self._get_regime_multiplier(market_regime)
            
            # Adjust for volatility
            volatility_multiplier = self._get_volatility_multiplier(volatility_factor)
            
            # Calculate adjusted risk
            adjusted_risk_percent = (base_risk_percent * confidence_multiplier * 
                                   regime_multiplier * volatility_multiplier)
            
            # Apply drawdown adjustments
            drawdown_multiplier = self._get_drawdown_multiplier()
            adjusted_risk_percent *= drawdown_multiplier
            
            # Calculate risk amount in rupees
            risk_amount = self.current_capital * adjusted_risk_percent
            
            # Calculate position size based on stop loss distance
            price_risk = abs(entry_price - stop_loss)
            if price_risk <= 0:
                return 0, "Invalid stop loss"
            
            position_size = risk_amount / price_risk
            
            # Apply position limits
            max_position_value = self.current_capital * self.max_single_position
            max_shares_by_value = max_position_value / entry_price
            
            position_size = min(position_size, max_shares_by_value)
            
            # Check portfolio heat
            portfolio_risk_check = self._check_portfolio_heat(position_size * price_risk)
            
            if not portfolio_risk_check["allowed"]:
                position_size *= portfolio_risk_check["reduction_factor"]
            
            return int(position_size), f"Risk: {adjusted_risk_percent:.2%}, Regime: {market_regime}"
            
        except Exception as e:
            print(f"❌ Error calculating position size: {e}")
            return 0, "Calculation error"
    
    def _get_confidence_multiplier(self, confidence_score):
        """
        Adjust position size based on signal confidence
        """
        if confidence_score >= 7.0:
            return 1.5  # 50% larger positions for high confidence
        elif confidence_score >= 6.0:
            return 1.2  # 20% larger for good confidence
        elif confidence_score >= 5.0:
            return 1.0  # Normal size
        elif confidence_score >= 4.0:
            return 0.7  # Smaller positions for low confidence
        else:
            return 0.5  # Very small positions for poor signals
    
    def _get_regime_multiplier(self, market_regime):
        """
        Adjust position size based on market regime
        """
        regime_multipliers = {
            "BULL_STRONG": 1.3,    # Larger positions in strong bull market
            "BULL_WEAK": 1.1,      # Slightly larger in weak bull
            "SIDEWAYS": 1.0,       # Normal size in sideways
            "BEAR_WEAK": 0.7,      # Smaller in weak bear
            "BEAR_STRONG": 0.3,    # Very small in strong bear
        }
        return regime_multipliers.get(market_regime, 1.0)
    
    def _get_volatility_multiplier(self, volatility_factor):
        """
        Adjust position size based on stock volatility
        """
        if volatility_factor > 2.0:
            return 0.6  # Much smaller positions for very volatile stocks
        elif volatility_factor > 1.5:
            return 0.8  # Smaller positions for volatile stocks
        elif volatility_factor < 0.7:
            return 1.2  # Larger positions for low volatility stocks
        else:
            return 1.0  # Normal volatility
    
    def _get_drawdown_multiplier(self):
        """
        Adjust position size based on current drawdown
        """
        current_drawdown = (self.initial_capital - self.current_capital) / self.initial_capital
        
        if current_drawdown >= self.stop_trading_drawdown:
            return 0.0  # Stop trading
        elif current_drawdown >= self.reduce_size_drawdown:
            return 0.5  # Half size positions
        else:
            return 1.0  # Normal size
    
    def _check_portfolio_heat(self, new_position_risk):
        """
        Check total portfolio risk and correlation exposure
        """
        try:
            # Get current open positions
            open_positions = self._get_open_positions()
            
            # Calculate current total risk
            current_total_risk = sum(pos.get('current_risk', 0) for pos in open_positions)
            
            # Check if adding new position exceeds total risk
            total_risk_after = current_total_risk + new_position_risk
            max_total_risk = self.current_capital * self.max_portfolio_risk
            
            if total_risk_after > max_total_risk:
                reduction_factor = max_total_risk / total_risk_after
                return {
                    "allowed": False,
                    "reduction_factor": reduction_factor,
                    "reason": f"Portfolio risk limit: {total_risk_after/self.current_capital:.2%}"
                }
            
            return {"allowed": True, "reduction_factor": 1.0}
            
        except Exception as e:
            print(f"⚠️ Error checking portfolio heat: {e}")
            return {"allowed": True, "reduction_factor": 1.0}
    
    def _get_open_positions(self):
        """
        Get current open positions from database
        """
        try:
            response = self.supabase.table("trades").select("*").eq("status", "open").execute()
            return response.data
        except:
            return []
    
    def should_trade_today(self):
        """
        Determine if trading should be allowed based on risk metrics
        """
        current_drawdown = (self.initial_capital - self.current_capital) / self.initial_capital
        
        if current_drawdown >= self.stop_trading_drawdown:
            return False, f"Trading suspended: {current_drawdown:.1%} drawdown"
        
        # Check number of open positions
        open_positions = self._get_open_positions()
        if len(open_positions) >= 10:  # Max 10 concurrent positions
            return False, f"Maximum positions reached: {len(open_positions)}"
        
        return True, "Trading allowed"

class StopLossOptimizer:
    """
    Intelligent stop loss calculation and management
    """
    def __init__(self):
        self.stop_types = ["ATR", "SUPPORT", "PERCENTAGE", "VOLATILITY"]
        
    def calculate_dynamic_stop(self, df, entry_price, pattern_type="momentum", 
                             risk_tolerance="medium"):
        """
        Calculate optimal stop loss based on multiple factors
        """
        try:
            if df.empty or len(df) < 20:
                # Fallback to simple percentage stop
                return entry_price * 0.95, "percentage_fallback"
            
            latest = df.iloc[-1]
            atr = latest.get('ATR', 0)
            
            # Calculate different stop loss methods
            stops = {}
            
            # 1. ATR-based stop
            atr_multiplier = self._get_atr_multiplier(pattern_type, risk_tolerance)
            stops['atr'] = entry_price - (atr_multiplier * atr)
            
            # 2. Support-based stop
            stops['support'] = self._calculate_support_stop(df, entry_price)
            
            # 3. Volatility-based stop
            stops['volatility'] = self._calculate_volatility_stop(df, entry_price)
            
            # 4. Percentage stop (fallback)
            percentage = self._get_percentage_stop(risk_tolerance)
            stops['percentage'] = entry_price * (1 - percentage)
            
            # Select the most conservative (highest) stop that's not too tight
            valid_stops = {k: v for k, v in stops.items() 
                          if v > entry_price * 0.90 and v < entry_price * 0.98}
            
            if not valid_stops:
                # Use percentage stop if all others are invalid
                final_stop = stops['percentage']
                stop_type = "percentage"
            else:
                # Use the highest (most conservative) valid stop
                stop_type = max(valid_stops, key=valid_stops.get)
                final_stop = valid_stops[stop_type]
            
            return final_stop, stop_type
            
        except Exception as e:
            print(f"⚠️ Error calculating dynamic stop: {e}")
            return entry_price * 0.95, "error_fallback"
    
    def _get_atr_multiplier(self, pattern_type, risk_tolerance):
        """
        Get ATR multiplier based on pattern and risk tolerance
        """
        base_multipliers = {
            "momentum": 1.5,    # Tighter stops for momentum
            "reversal": 2.5,    # Wider stops for reversals
            "breakout": 2.0,    # Medium stops for breakouts
            "pullback": 1.8,    # Medium-tight for pullbacks
        }
        
        risk_adjustments = {
            "low": 0.8,         # Tighter stops for low risk tolerance
            "medium": 1.0,      # Normal stops
            "high": 1.3,        # Wider stops for high risk tolerance
        }
        
        base = base_multipliers.get(pattern_type, 2.0)
        adjustment = risk_adjustments.get(risk_tolerance, 1.0)
        
        return base * adjustment
    
    def _calculate_support_stop(self, df, entry_price):
        """
        Calculate stop based on recent support levels
        """
        try:
            # Find recent support levels
            lookback = min(20, len(df))
            recent_lows = df['Low'].tail(lookback)
            
            # Support is the lowest low in recent period
            support_level = recent_lows.min()
            
            # Place stop 1% below support
            support_stop = support_level * 0.99
            
            return support_stop
            
        except:
            return entry_price * 0.95
    
    def _calculate_volatility_stop(self, df, entry_price):
        """
        Calculate stop based on recent volatility
        """
        try:
            # Calculate recent volatility
            returns = df['Close'].pct_change().dropna()
            volatility = returns.rolling(20).std().iloc[-1]
            
            # Stop at 2 standard deviations below entry
            volatility_stop = entry_price * (1 - 2 * volatility)
            
            return volatility_stop
            
        except:
            return entry_price * 0.95
    
    def _get_percentage_stop(self, risk_tolerance):
        """
        Get percentage stop based on risk tolerance
        """
        percentages = {
            "low": 0.03,        # 3% stop
            "medium": 0.05,     # 5% stop
            "high": 0.08,       # 8% stop
        }
        return percentages.get(risk_tolerance, 0.05)
    
    def update_trailing_stop(self, current_price, entry_price, current_stop, 
                           trail_percent=0.02):
        """
        Update trailing stop loss
        """
        try:
            # Only trail if in profit
            if current_price <= entry_price:
                return current_stop, "no_trail_loss"
            
            # Calculate profit percentage
            profit_percent = (current_price - entry_price) / entry_price
            
            # Start trailing after 2% profit
            if profit_percent < 0.02:
                return current_stop, "profit_too_small"
            
            # Calculate new trailing stop
            new_stop = current_price * (1 - trail_percent)
            
            # Only move stop up, never down
            if new_stop > current_stop:
                return new_stop, "stop_trailed"
            else:
                return current_stop, "no_change"
                
        except Exception as e:
            print(f"⚠️ Error updating trailing stop: {e}")
            return current_stop, "error"

class PortfolioRiskMonitor:
    """
    Monitor overall portfolio risk and correlations
    """
    def __init__(self):
        self.supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        
    def calculate_portfolio_metrics(self):
        """
        Calculate comprehensive portfolio risk metrics
        """
        try:
            # Get all open positions
            open_positions = self._get_open_positions()
            
            if not open_positions:
                return self._empty_portfolio_metrics()
            
            metrics = {
                "total_positions": len(open_positions),
                "total_invested": sum(pos.get('position_value', 0) for pos in open_positions),
                "total_risk": sum(pos.get('risk_amount', 0) for pos in open_positions),
                "avg_position_size": 0,
                "largest_position": 0,
                "sector_exposure": {},
                "current_pnl": sum(pos.get('unrealized_pnl', 0) for pos in open_positions),
                "risk_reward_ratio": 0,
            }
            
            if metrics["total_positions"] > 0:
                position_values = [pos.get('position_value', 0) for pos in open_positions]
                metrics["avg_position_size"] = np.mean(position_values)
                metrics["largest_position"] = max(position_values)
            
            return metrics
            
        except Exception as e:
            print(f"❌ Error calculating portfolio metrics: {e}")
            return self._empty_portfolio_metrics()
    
    def _get_open_positions(self):
        """
        Get open positions with calculated values
        """
        try:
            response = self.supabase.table("trades").select("*").eq("status", "open").execute()
            positions = response.data
            
            # Calculate current values for each position
            for pos in positions:
                # These would be calculated from current market prices
                pos['position_value'] = pos.get('quantity', 0) * pos.get('entry_price', 0)
                pos['risk_amount'] = abs(pos.get('entry_price', 0) - pos.get('stop_loss', 0)) * pos.get('quantity', 0)
                pos['unrealized_pnl'] = 0  # Would calculate from current prices
            
            return positions
            
        except:
            return []
    
    def _empty_portfolio_metrics(self):
        """
        Return empty metrics structure
        """
        return {
            "total_positions": 0,
            "total_invested": 0,
            "total_risk": 0,
            "avg_position_size": 0,
            "largest_position": 0,
            "sector_exposure": {},
            "current_pnl": 0,
            "risk_reward_ratio": 0,
        }
    
    def check_risk_limits(self, portfolio_value=1000000):
        """
        Check if portfolio is within risk limits
        """
        metrics = self.calculate_portfolio_metrics()
        warnings = []
        
        # Check position concentration
        if metrics["largest_position"] > portfolio_value * 0.1:
            warnings.append(f"Large position concentration: {metrics['largest_position']/portfolio_value:.1%}")
        
        # Check total risk
        if metrics["total_risk"] > portfolio_value * 0.05:
            warnings.append(f"High portfolio risk: {metrics['total_risk']/portfolio_value:.1%}")
        
        # Check number of positions
        if metrics["total_positions"] > 15:
            warnings.append(f"Too many positions: {metrics['total_positions']}")
        
        return warnings

# Usage and testing
if __name__ == "__main__":
    # Initialize risk management components
    risk_manager = RiskManager(initial_capital=1000000)
    stop_optimizer = StopLossOptimizer()
    portfolio_monitor = PortfolioRiskMonitor()
    
    print("🛡️ Risk Management System Testing")
    
    # Test position sizing
    print("\n💰 Testing Position Sizing...")
    entry_price = 2500
    stop_loss = 2375  # 5% stop
    confidence_score = 6.5
    market_regime = "BULL_WEAK"
    
    position_size, reason = risk_manager.calculate_position_size(
        entry_price, stop_loss, confidence_score, market_regime
    )
    
    print(f"   Entry Price: ₹{entry_price}")
    print(f"   Stop Loss: ₹{stop_loss}")
    print(f"   Confidence: {confidence_score}")
    print(f"   Market Regime: {market_regime}")
    print(f"   Position Size: {position_size} shares")
    print(f"   Reason: {reason}")
    
    # Test stop loss optimization
    print(f"\n🛑 Testing Stop Loss Optimization...")
    
    # Create sample data for testing
    dates = pd.date_range(start='2024-01-01', periods=50, freq='D')
    sample_data = pd.DataFrame({
        'Close': np.random.normal(2500, 50, 50).cumsum() / 50 + 2400,
        'High': np.random.normal(2520, 60, 50).cumsum() / 50 + 2420,
        'Low': np.random.normal(2480, 40, 50).cumsum() / 50 + 2380,
        'Volume': np.random.normal(1000000, 200000, 50),
    }, index=dates)
    
    # Calculate ATR
    sample_data['ATR'] = (sample_data['High'] - sample_data['Low']).rolling(14).mean()
    
    optimal_stop, stop_type = stop_optimizer.calculate_dynamic_stop(
        sample_data, entry_price, "momentum", "medium"
    )
    
    print(f"   Optimal Stop: ₹{optimal_stop:.2f}")
    print(f"   Stop Type: {stop_type}")
    print(f"   Risk: {(
