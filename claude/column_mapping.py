# column_mapping.py - Maps AI system columns to your existing database schema

# Column mapping from AI system to your database
COLUMN_MAPPING = {
    # Existing columns (reuse these)
    'entry_price': 'price',           # Your 'price' column = our 'entry_price'
    'entry_date': 'timestamp',        # Your 'timestamp' column = our 'entry_date'  
    'quantity': 'quantity',           # Already exists
    'position_value': 'total_invested', # Your 'total_invested' = our 'position_value'
    'signal_score': 'score',          # Your 'score' column = our 'signal_score'
    'ml_probability': 'ml_probability', # Already exists
    'market_regime': 'market_regime',   # Already exists
    'stop_type': 'stop_type',          # Already exists
    'reasoning': 'reasoning',          # Already exists (but has typo 'easoning')
    'status': 'status',               # Already exists
    'ticker': 'ticker',               # Already exists
    'action': 'action',               # Already exists
    
    # New columns (will be added by ALTER TABLE)
    'exit_date': 'exit_date',
    'exit_price': 'exit_price', 
    'exit_reason': 'exit_reason',
    'stop_loss': 'stop_loss',
    'target_1': 'target_1',
    'target_2': 'target_2',
    'target_3': 'target_3',
    'initial_risk': 'initial_risk',
    'current_price': 'current_price',
    'unrealized_pnl': 'unrealized_pnl',
    'pnl': 'pnl',
    'pnl_percent': 'pnl_percent',
    'days_held': 'days_held',
    'slippage': 'slippage',
    'order_id': 'order_id',
    'matched_indicators': 'matched_indicators',
    'last_updated': 'last_updated'
}

def get_insert_data_mapped(ai_trade_data):
    """
    Map AI system trade data to your database column names
    """
    mapped_data = {}
    
    # Map existing columns
    if 'executed_price' in ai_trade_data:
        mapped_data['price'] = ai_trade_data['executed_price']  # entry_price -> price
    
    if 'execution_time' in ai_trade_data:
        mapped_data['timestamp'] = ai_trade_data['execution_time'].isoformat()  # entry_date -> timestamp
    
    if 'position_value' in ai_trade_data:
        mapped_data['total_invested'] = ai_trade_data['position_value']
    
    if 'signal_score' in ai_trade_data:
        mapped_data['score'] = ai_trade_data['signal_score']
    
    # Always set action to BUY for new trades
    mapped_data['action'] = 'BUY'
    mapped_data['status'] = 'OPEN'
    mapped_data['quantity'] = ai_trade_data.get('quantity', 1)
    
    # Add new columns if they exist
    for ai_key, db_key in COLUMN_MAPPING.items():
        if ai_key in ai_trade_data and db_key not in mapped_data:
            mapped_data[db_key] = ai_trade_data[ai_key]
    
    return mapped_data

def get_update_data_mapped(ai_update_data):
    """  
    Map AI system update data to your database column names
    """
    mapped_data = {}
    
    # Map common update fields
    for ai_key, db_key in COLUMN_MAPPING.items():
        if ai_key in ai_update_data:
            mapped_data[db_key] = ai_update_data[ai_key]
    
    return mapped_data

# Usage example and testing
if __name__ == "__main__":
    # Test the mapping
    sample_ai_data = {
        'ticker': 'RELIANCE.NS',
        'executed_price': 2500.50,
        'execution_time': '2024-01-15T10:30:00',
        'position_value': 250050.0,
        'quantity': 100,
        'signal_score': 6.5,
        'ml_probability': 0.75,
        'market_regime': 'BULL_WEAK',
        'stop_loss': 2375.0,
        'target_1': 2625.0,
        'initial_risk': 12525.0,
        'slippage': 0.002,
        'order_id': 'RELIANCE_1705305000'
    }
    
    mapped_data = get_insert_data_mapped(sample_ai_data)
    print("Mapped data for database insert:")
    for key, value in mapped_data.items():
        print(f"  {key}: {value}")
