"""
Configuration for Prop Firm Challenge Algorithm
================================================
Topstep-style funded account challenge settings
"""

# ==================== API Configuration ====================
API_CONFIG = {
    # Tradovate API settings
    "TRADOVATE": {
        "username": "",           # Your Tradovate username
        "password": "",           # Your password
        "api_key": "",            # Your API key
        "organization": "",       # Organization ID
        "sandbox": True,          # True = paper trading, False = live
    },
    # CME Data WebSocket (for historical data)
    "CME_DATA": {
        "api_key": "",            # CME Group API key
        "api_secret": "",         # CME Group API secret
    },
    # Alternative: Use Yahoo Finance via yfinance (no auth needed)
    "USE_YAHOO": True,           # Set to True to use yfinance data
}

# ==================== Trading Configuration ====================
SYMBOLS = {
    "MES": {                      # Micro E-Mini S&P 500
        "contract_size": 5,       # $5 per point
        "tick_value": 1.25,       # $1.25 per tick
        "min_move": 0.25,         # Min price move
        "exchange": "CMES6!",     # Tradovate symbol
    },
    "NQ": {                      # E-Mini Nasdaq
        "contract_size": 20,      # $20 per point
        "tick_value": 2.5,        # $2.5 per tick
        "min_move": 0.25,
        "exchange": "NQS6!",
    },
    "ES": {                      # E-Mini S&P 500
        "contract_size": 50,      # $50 per point
        "tick_value": 12.50,      # $12.50 per tick
        "min_move": 0.25,
        "exchange": "ES6!",
    },
}

SYMBOL = "MES"  # Start with MES (lower capital req)

# ==================== Challenge Phase Settings ====================
CHALLENGE_PHASE = {
    "daily_loss_limit": 1000,      # $1,000 daily loss limit
    "max_drawdown": 2000,          # $2,000 max trailing drawdown
    "profit_target": 3000,         # $3,000 profit target
    "session_start": "9:30",       # RTH opening
    "session_end": "16:00",        # EST close
    "trading_days_per_month": 22,  # Approximate trading days
}

# ==================== Risk Management ====================
RISK = {
    "risk_per_trade": 0.20,        # 20% of daily loss limit per trade
    "max_concurrent_trades": 1,    # One trade per day max
    "position_sizing": "volatility",  # "fixed" or "volatility"
}

# ==================== ORB Strategy Parameters ====================
ORB = {
    "opening_range_minutes": 30,   # 30-min opening range
    "breakout_threshold": 1.05,    # Breakout threshold (105% of range)
    "tp_multiplier": 0.75,         # TP = 0.75x opening range size
    "sl_multiplier": 1.75,         # SL = 1.75x opening range size
    "max_trades_per_day": 1,       # One trade max per day
    "require_volatility_filter": True,  # Only trade if range is > $X
}

# ==================== Funded Phase Settings ====================
FUNDED_PHASE = {
    "tp_multiplier": 1.0,          # Slightly wider RR: 1:1
    "sl_multiplier": 1.5,          # 1.5x range
    "max_daily_loss": 0.40,        # Cap at 40% of daily limit
    "protect_dd": True,            # Always respect max drawdown
}

# ==================== Backtest Settings ====================
BACKTEST = {
    "start_date": "2025-10-01",
    "end_date": "2026-03-31",      # 6 months of data
    "data_interval": "1m",         # 1-minute OHLCV
    "initial_capital": 50000,      # Starting balance
}

# ==================== Monte Carlo Settings ====================
MONTEN_CARLO = {
    "n_simulations": 1000,         # Number of simulations
    "trade_correlation": 0.3,      # Simulated correlation between trades
    "dd_factor": 1.0,              # Use actual DD or scaled
}

# ==================== Logging ====================
LOG = {
    "level": "INFO",
    "file": "logs/trading.log",
    "format": "%(asctime)s - %(levelname)s - %(message)s",
}
