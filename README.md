<div align="center">

# QuantAlgo PropFirms

**An Opening-Range-Breakout (ORB) trading engine engineered for prop-firm funded-account challenges.**

[![CI](https://github.com/tylrcc/quantalgo-propfirms/actions/workflows/ci.yml/badge.svg)](https://github.com/tylrcc/quantalgo-propfirms/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue.svg)](https://www.python.org)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-261230.svg)](https://github.com/astral-sh/ruff)

</div>

---

## Why this exists

Prop-firm challenges (Topstep, Apex, etc.) have a **convex payoff**: your downside is
capped at the challenge fee, but a pass unlocks a funded account with uncapped upside.
That structure rewards a strategy with a **high win-rate and bounded daily risk**, exactly
what a disciplined Opening Range Breakout delivers. This project turns that idea into a
tested, reproducible engine you can **backtest**, **stress-test with Monte-Carlo**, and
**run on a paper account**.

> ⚠️ **Disclaimer.** This is research and educational software, not financial advice.
> Trading futures involves substantial risk of loss. Past or simulated performance does
> not guarantee future results. Use the paper/sandbox mode until you understand the risks.

## Features

- 📈 **ORB strategy engine**, opening-range detection, breakout entries, fixed-multiple
  TP/SL, and a volatility filter (`quantalgo.strategy`).
- 🧪 **Event-driven backtester**, correct position sizing with Topstep-style **daily loss
  limit**, **trailing drawdown**, and **profit target** enforcement (`quantalgo.backtest`).
- 🎲 **Monte-Carlo pass-rate simulator**, bootstrap thousands of challenge attempts to
  estimate pass rate, expected value, and P&L percentiles (`quantalgo.montecarlo`).
- 🔌 **Pluggable execution**, in-memory `PaperBroker` for testing plus an async
  `TradovateBroker` wrapper for Topstep's venue (`quantalgo.execution`).
- 🛰️ **Offline-first data**, Yahoo Finance loader with Parquet caching and a deterministic
  **synthetic generator**, so everything runs without a network (`quantalgo.data`).
- 🧰 **Batteries included**, typed config, a `quantalgo` CLI, text reports & charts, a
  pytest suite, and CI across Python 3.10-3.12.

## Architecture

```
                ┌──────────────┐      ┌──────────────┐
   data ───────▶│   strategy   │─────▶│   backtest   │─────▶ metrics / equity curve
 (yfinance /    │  ORB signals │      │ sizing+risk  │             │
  synthetic)    └──────────────┘      └──────┬───────┘             ▼
                                             │              ┌──────────────┐
                                             └─ trade P&L ─▶│ montecarlo   │─▶ pass rate / EV
                                                            └──────────────┘
   execution (PaperBroker / TradovateBroker)  ◀─── live & paper sessions
   reporting (tables + matplotlib charts) · config (typed, env-overridable)
```

## Installation

```bash
git clone https://github.com/tylrcc/quantalgo-propfirms.git
cd quantalgo-propfirms

python -m venv .venv && source .venv/bin/activate
pip install -e ".[all]"     # runtime + data + plots + live + env extras
```

Minimal install (`pip install -e .`) only needs `pandas` and `numpy`; live data,
charts and broker connectivity are optional extras (`data`, `plots`, `live`, `env`).

## Quick start

```bash
quantalgo info                                   # config + supported symbols
quantalgo backtest   --symbol MES --days 180 -p  # backtest, save equity_curve.png
quantalgo montecarlo --symbol MES --sims 10000   # estimate challenge pass-rate
```

Example output:

```
──────────────────────────────────────────
 Backtest, MES (2025-12-06 → 2026-06-04)
──────────────────────────────────────────
 Total Trades            42
 Win Rate            64.29%
 Profit Factor         1.83
 Expectancy R        0.2611
 Total Return Pct     5.74%
 Final Equity    $52,870.00
 Max Drawdown     $1,420.00
──────────────────────────────────────────

Challenge outcome: PASSED  •  42 trades
```

### Library usage

```python
from quantalgo.config import get_settings
from quantalgo.data import DataLoader
from quantalgo.strategy import ORBStrategy
from quantalgo.backtest import Backtester
from quantalgo.montecarlo import MonteCarloSimulator

settings = get_settings().with_symbol("MES")
df = DataLoader("MES").load("2025-12-01", "2026-06-01", interval="5m")

trades = ORBStrategy(settings.orb).generate_trades(df)
result = Backtester(settings.challenge, settings.symbol_spec).run(trades)
print(result.metrics, result.outcome)

mc = MonteCarloSimulator(settings.challenge, settings.montecarlo)
print(mc.run([t.pnl_dollars for t in result.trades]).as_dict())
```

## Configuration

All defaults work out of the box; override via environment variables or a `.env`
file (see [`.env.example`](.env.example)). Strategy, risk and simulation parameters are
typed dataclasses in [`quantalgo.config`](src/quantalgo/config.py):

| Group            | Examples                                                        |
|------------------|----------------------------------------------------------------|
| `ORBParams`      | `opening_range_minutes`, `take_profit_mult`, `stop_loss_mult`  |
| `ChallengeRules` | `daily_loss_limit`, `trailing_max_drawdown`, `profit_target`   |
| `MonteCarloParams`| `n_simulations`, `max_trading_days`, `seed`                   |

## Development

```bash
make dev      # install with dev + all extras
make test     # pytest
make cover    # pytest with coverage
make lint     # ruff
```

CI runs lint, the full test-suite, and CLI smoke-tests on Python 3.10/3.11/3.12.

## Project layout

```
src/quantalgo/   config · data · strategy · backtest · montecarlo · execution · reporting · cli
tests/           pytest suite (runs fully offline)
.github/         CI workflow
```

## License

[MIT](LICENSE) © tylrcc
