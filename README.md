# Prop Firm Challenge Algorithm

Algorithm optimized for Topstep-style funded account challenges that exploits the convex payoff structure: **losses are capped at challenge fees, but gains are unlimited**.

## Strategy Overview

### Opening Range Breakout (ORB)
- **Opening Range**: First 30 minutes of RTH session
- **Long Signal**: Breakout above range high
- **Short Signal**: Breakout below range low
- **Take Profit**: 0.75x - 1.0x opening range size
- **Stop Loss**: 1.75x - 2.0x opening range size

### Why This Works
- **High win rate** (60-75%) due to tight TP / wide SL geometry
- **Low volatility** = faster barrier completion
- **Capped downside** + unlimited upside = positive net EV

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Main Modules                           │
├─────────────────────────────────────────────────────────────┤
│  data_loader.py       │  Fetch historical futures OHLCV      │
│  orb_strategy.py      │  ORB signals & TP/SL calculation     │
│  backtester.py        │  Backtest with equity curve           │
│  monte_carlo.py       │  Pass rate simulation                 │
│  api_connector.py     │  Tradovate/Topstep API wrapper        │
│  trader.py            │  Live trading (paper/live mode)       │
└─────────────────────────────────────────────────────────────┘
```

## Quick Start

### 1. Install Dependencies

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure API Keys

Edit `config.py`:

```python
API_CONFIG = {
    "TRADOVATE": {
        "username": "your_username",
        "password": "your_password",
        "api_key": "your_api_key",
        "organization": "your_org_id",
        "sandbox": True,  # True = paper trading
    },
    "CME_DATA": {
        "api_key": "your_cme_api_key",
        "api_secret": "your_cme_api_secret",
    },
    "USE_YAHOO": True,  # Use yfinance instead of CME API
}
```

### 3. Run Backtest

```bash
python backtester.py
```

### 4. Run Monte Carlo Simulation

```bash
python monte_carlo.py
```

### 5. Run Live/Paper Trading

```bash
python trader.py
```

## Output

### Backtest Results
- Equity curve visualization (`equity_curve.png`)
- Trade log with win/loss stats
- Win rate, RR, profit factor

### Monte Carlo Results
- Pass rate percentage
- Average payout per challenge
- Net EV per attempt
- Distribution plots (`monte_carlo_results.png`)

## Challenge Rules (Topstep 50K)

| Parameter | Value |
|-----------|-------|
| Daily loss limit | $1,000 |
| Max trailing drawdown | $2,000 |
| Profit target | $3,000 |
| Typical challenge duration | 2-3 months |

## Performance Targets

| Metric | Target |
|--------|--------|
| Win rate | 60-75% |
| Risk/Reward | 1:0.5 - 1:0.75 |
| Pass rate (2 months) | 40-60% |
| Average payout | $3,000+ per passed challenge |
| Net EV per attempt | $500+ |

## File Structure

```
quntalgo1.0/
├── config.py              # Configuration parameters
├── data_loader.py         # Data fetching
├── orb_strategy.py        # ORB strategy logic
├── backtester.py          # Backtesting engine
├── monte_carlo.py         # Pass rate simulator
├── api_connector.py       # Tradovate API wrapper
├── trader.py              # Live trading script
├── requirements.txt       # Dependencies
└── README.md              # This file
```

## Disclaimer

This software is for educational purposes only. Trading futures involves substantial risk of loss. Test thoroughly in paper mode before using real capital.

## License

MIT License
