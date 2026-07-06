"""Shared pytest fixtures."""

from __future__ import annotations

import pandas as pd
import pytest

from quantalgo.config import ORBParams, Settings
from quantalgo.data import DataLoader


@pytest.fixture
def settings() -> Settings:
    return Settings()


@pytest.fixture
def synthetic_df() -> pd.DataFrame:
    """A reproducible ~2 week intraday series for MES."""
    loader = DataLoader(symbol="MES", data_dir="/tmp/qa-test-data")
    return loader.synthetic("2026-01-05", "2026-01-17", interval="5m", seed=7)


@pytest.fixture
def one_day_bars() -> pd.DataFrame:
    """A hand-crafted single session with a clean long breakout to take-profit."""
    rows = [
        # (time, open, high, low, close), opening range (first 2 min) = [100, 101]
        ("09:30", 100.5, 101.0, 100.0, 100.5),
        ("09:31", 100.5, 101.0, 100.0, 100.5),
        ("09:32", 100.6, 102.2, 100.5, 102.0),  # close 102 > 101 -> long entry
        ("09:33", 102.0, 103.5, 102.0, 103.2),  # high 103.5 >= TP(103) -> exit TP
        ("09:34", 103.2, 103.4, 102.9, 103.0),
    ]
    idx = [pd.Timestamp(f"2026-01-05 {t}") for t, *_ in rows]
    data = {
        "open": [r[1] for r in rows],
        "high": [r[2] for r in rows],
        "low": [r[3] for r in rows],
        "close": [r[4] for r in rows],
        "volume": [1000.0] * len(rows),
    }
    return pd.DataFrame(data, index=pd.DatetimeIndex(idx))


@pytest.fixture
def breakout_params() -> ORBParams:
    return ORBParams(
        opening_range_minutes=2,
        take_profit_mult=1.0,
        stop_loss_mult=2.0,
        min_range_points=0.5,
        use_volatility_filter=True,
    )
