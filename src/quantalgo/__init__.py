"""QuantAlgo PropFirms — an Opening-Range-Breakout engine for funded-account challenges.

The package is organised into small, single-responsibility modules:

* :mod:`quantalgo.config`      – typed configuration loaded from env / defaults
* :mod:`quantalgo.data`        – historical & synthetic OHLCV data loading
* :mod:`quantalgo.strategy`    – the Opening Range Breakout signal engine
* :mod:`quantalgo.backtest`    – event-driven backtester with prop-firm risk rules
* :mod:`quantalgo.montecarlo`  – Monte-Carlo challenge pass-rate simulation
* :mod:`quantalgo.execution`   – broker interface (Tradovate / paper)
* :mod:`quantalgo.reporting`   – metrics formatting and plots
* :mod:`quantalgo.cli`         – command line entry point
"""

from __future__ import annotations

__version__ = "1.0.0"

from quantalgo.config import Settings, get_settings
from quantalgo.strategy import ORBStrategy, Trade

__all__ = ["__version__", "Settings", "get_settings", "ORBStrategy", "Trade"]
