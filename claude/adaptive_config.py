from market_regime import MarketRegimeDetector
from datetime import datetime
import json

class AdaptiveConfig:
    """
    Dynamically adjusts strategy parameters based on market regime
    """
    def __init__(self):
        self.regime_detector = MarketRegimeDetector()
        self.base_config = {
            # RSI thresholds
            "RSI_MIN": 45,
            "RSI_MAX": 65,
            
            # Volume and momentum
            "VOLUME_MULTIPLIER": 2.0,
            "MACD_SIGNAL_DIFF": 1.0,
            
            # Risk management
            "ATR_MULTIPLIER": 1.4,
            "SCORE_THRESHOLD": 5.9,
            
            # Price change limits
            "PRICE_CHANGE_3D_LIMIT": 5,
            "PRICE_CHANGE_5D_LIMIT": 8,
            
            # Other indicators
            "STOCH_K_MAX": 80,
            "WILLR_MAX": -20,
            
            # Position sizing
            "MAX_POSITION_RISK": 0.02,
            "BASE_POSITION_SIZE": 0.01,
        }
        
        # Regime-specific adjustments
        self.regime_adjustments = {
            "BULL_STRONG": {
                "RSI_MAX": 75,                    # Allow higher RSI in strong markets
                "SCORE_THRESHOLD": 5.2,           # Easier to qualify
                "VOLUME_MULTIPLIER": 1.6,         # Accept lower volume surges
                "PRICE_CHANGE_3D_LIMIT": 8,       # Allow stronger recent moves
                "PRICE_CHANGE_5D_LIMIT": 12,      
                "ATR_MULTIPLIER": 1.2,            # Less strict on volatility
                "BASE_POSITION_SIZE": 0.015,      # Larger positions in bull market
                "STOCH_K_MAX": 85,                # Allow higher stochastic
            },
            
            "BULL_WEAK": {
                "RSI_MAX": 70,                    # Moderate RSI allowance
                "SCORE_THRESHOLD": 5.5,           # Slightly easier
                "VOLUME_MULTIPLIER": 1.8,         
                "PRICE_CHANGE_3D_LIMIT": 6,       
                "PRICE_CHANGE_5D_LIMIT": 10,      
                "BASE_POSITION_SIZE": 0.012,      # Moderate position size
            },
            
            "SIDEWAYS": {
                "RSI_MIN": 35,                    # Look for oversold bounces
                "RSI_MAX": 55,                    # Avoid overbought in range
                "SCORE_THRESHOLD": 6.2,           # Be more selective
                "VOLUME_MULTIPLIER": 2.5,         # Require stronger volume
                "PRICE_CHANGE_3D_LIMIT": 3,       # Minimal recent moves
                "PRICE_CHANGE_5D_LIMIT": 5,       
                "ATR_MULTIPLIER": 1.6,            # More strict on volatility
                "BASE_POSITION_SIZE": 0.008,      # Smaller positions
                "WILLR_MAX": -30,                 # More oversold requirement
            },
            
            "BEAR_WEAK": {
                "RSI_MIN": 30,                    # Very oversold only
                "RSI_MAX": 50,                    # Conservative upper limit
                "SCORE_THRESHOLD": 6.8,           # Very selective
                "VOLUME_MULTIPLIER": 3.0,         # Require very strong volume
                "PRICE_CHANGE_3D_LIMIT": 2,       # Very minimal moves
                "PRICE_CHANGE_5D_LIMIT": 3,       
                "ATR_MULTIPLIER": 2.0,            # Very strict on volatility
                "BASE_POSITION_SIZE": 0.005,      # Very small positions
                "WILLR_MAX": -40,                 # Very oversold
            },
            
            "BEAR_STRONG": {
                "SCORE_THRESHOLD": 10.0,          # Essentially disabled
                "BASE_POSITION_SIZE": 0.0,        # No positions
            }
        }
    
    def get_current_config(self):
        """
        Get configuration adapted to current market regime
        """
        # Detect current regime
        regime, confidence = self.regime_detector.detect_current_regime()
        
        # Start with base configuration
        config = self.base_config.copy()
        
        # Apply regime-specific adjustments
        if regime in self.regime_adjustments:
            adjustments = self.regime_adjustments[regime]
            config.update(adjustments)
        
        # Confidence adjustments (if regime detection is uncertain)
        if confidence < 0.6:
            # Be more conservative when uncertain
            config["SCORE_THRESHOLD"] = config["SCORE_THRESHOLD"] + 0.3
            config["BASE_POSITION_SIZE"] = config["BASE_POSITION_SIZE"] * 0.8
        
        # Add metadata
        config["_regime"] = regime
        config["_confidence"] = confidence
        config["_updated_at"] = datetime.now().isoformat()
        
        return config
    
    def get_regime_specific_filters(self, regime):
        """
        Get regime-specific pre-entry filters for screener
        """
        filters = {
            "BULL_STRONG": {
                "skip_rsi_above": 75,
                "skip_price_change_3d_above": 8,
                "skip_price_change_5d_above": 12,
                "skip_volume_spike_threshold": 3.5,
                "skip_atr_multiplier": 1.2,
            },
            
            "BULL_WEAK": {
                "skip_rsi_above": 70,
                "skip_price_change_3d_above": 6,
                "skip_price_change_5d_above": 10,
                "skip_volume_spike_threshold": 2.8,
                "skip_atr_multiplier": 1.3,
            },
            
            "SIDEWAYS": {
                "skip_rsi_above": 58,
                "skip_price_change_3d_above": 4,
                "skip_price_change_5d_above": 6,
                "skip_volume_spike_threshold": 2.2,
                "skip_atr_multiplier": 1.5,
            },
            
            "BEAR_WEAK": {
                "skip_rsi_above": 55,
                "skip_price_change_3d_above": 3,
                "skip_price_change_5d_above": 4,
                "skip_volume_spike_threshold": 2.0,
                "skip_atr_multiplier": 1.8,
            },
            
            "BEAR_STRONG": {
                "skip_rsi_above": 45,  # Very restrictive
                "skip_price_change_3d_above": 1,
                "skip_price_change_5d_above": 2,
                "skip_volume_spike_threshold": 1.5,
                "skip_atr_multiplier": 2.5,
            }
        }
        
        return filters.get(regime, filters["SIDEWAYS"])
    
    def get_scoring_weights(self, regime):
        """
        Get regime-specific scoring weights for indicators
        """
        weights = {
            "BULL_STRONG": {
                "price_trend": 1.2,      # Higher weight on trend following
                "rsi": 1.0,
                "volume": 1.1,           # Volume confirmation important
                "macd": 1.0,
                "stoch": 0.6,            # Less weight on mean reversion
                "willr": 0.5,
                "pattern": 0.4,          # Patterns less important in momentum
            },
            
            "BULL_WEAK": {
                "price_trend": 1.0,
                "rsi": 1.0,
                "volume": 1.0,
                "macd": 1.0,
                "stoch": 0.7,
                "willr": 0.6,
                "pattern": 0.6,
            },
            
            "SIDEWAYS": {
                "price_trend": 0.8,      # Less weight on trend
                "rsi": 1.2,              # Higher weight on mean reversion
                "volume": 0.9,
                "macd": 0.8,
                "stoch": 1.1,            # Stochastic important for reversals
                "willr": 1.0,
                "pattern": 1.0,          # Patterns more important
            },
            
            "BEAR_WEAK": {
                "price_trend": 0.6,
                "rsi": 1.5,              # Very high weight on oversold
                "volume": 1.2,           # Need strong volume for bounces
                "macd": 0.7,
                "stoch": 1.2,
                "willr": 1.3,
                "pattern": 1.2,          # Reversal patterns critical
            },
            
            "BEAR_STRONG": {
                "price_trend": 0.1,      # Trend following dangerous
                "rsi": 2.0,              # Only extremely oversold
                "volume": 1.5,
                "macd": 0.3,
                "stoch": 1.5,
                "willr": 1.5,
                "pattern": 1.5,
            }
        }
        
        return weights.get(regime, weights["SIDEWAYS"])
    
    def should_increase_position_size(self, regime, confidence):
        """
        Determine if position sizes should be increased based on regime
        """
        favorable_regimes = ["BULL_STRONG", "BULL_WEAK"]
        
        if regime in favorable_regimes and confidence > 0.7:
            return True, 1.2  # 20% increase
        elif regime == "SIDEWAYS" and confidence > 0.8:
            return True, 1.1  # 10% increase only if very confident
        else:
            return False, 1.0
    
    def get_regime_summary(self):
        """
        Get current regime summary for display
        """
        config = self.get_current_config()
        regime = config["_regime"]
        confidence = config["_confidence"]
        
        characteristics = self.regime_detector.get_regime_characteristics(regime)
        
        return {
            "regime": regime,
            "confidence": round(confidence, 2),
            "description": characteristics["description"],
            "trading_style": characteristics["trading_style"],
            "expected_signals": characteristics["expected_signals"],
            "score_threshold": config["SCORE_THRESHOLD"],
            "rsi_range": f"{config['RSI_MIN']}-{config['RSI_MAX']}",
            "position_size": config["BASE_POSITION_SIZE"]
        }

# Usage and testing
if __name__ == "__main__":
    adaptive_config = AdaptiveConfig()
    
    # Get current configuration
    config = adaptive_config.get_current_config()
    print("📊 Current Adaptive Configuration:")
    print(json.dumps(config, indent=2, default=str))
    
    # Get regime summary
    summary = adaptive_config.get_regime_summary()
    print(f"\n📋 Regime Summary:")
    for key, value in summary.items():
        print(f"   {key}: {value}")
    
    # Test different regimes
    print(f"\n🧪 Testing Different Regime Configurations:")
    for regime in ["BULL_STRONG", "SIDEWAYS", "BEAR_WEAK"]:
        filters = adaptive_config.get_regime_specific_filters(regime)
        weights = adaptive_config.get_scoring_weights(regime)
        print(f"\n{regime}:")
        print(f"   Filters: {filters}")
        print(f"   Weights: {weights}")
