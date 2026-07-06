"""Historical and synthetic OHLCV data loading.

The :class:`DataLoader` pulls intraday futures bars from Yahoo Finance via
``yfinance`` when available, transparently caches them to Parquet, and falls back
to a deterministic synthetic generator when the network (or ``yfinance``) is not
available. The synthetic generator is also what the test-suite runs against, so the
whole pipeline is exercised offline.

All returned frames share one canonical schema: a tz-naive ``DatetimeIndex`` plus
``open, high, low, close, volume`` float columns, restricted to the Regular Trading
Hours session (09:30-16:00 US/Eastern, expressed in naive local time).
"""

from __future__ import annotations

import logging
from datetime import datetime, time, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from quantalgo.config import SYMBOLS

logger = logging.getLogger(__name__)

OHLCV_COLUMNS = ["open", "high", "low", "close", "volume"]
_RTH_START = time(9, 30)
_RTH_END = time(16, 0)

# Rough starting price per symbol, used only by the synthetic generator.
_BASE_PRICE = {"MES": 5200.0, "ES": 5200.0, "NQ": 18200.0, "YM": 39000.0}


class DataLoader:
    """Fetch, cache and (if needed) synthesise intraday OHLCV data."""

    def __init__(self, symbol: str = "MES", data_dir: str | Path = "./data") -> None:
        if symbol not in SYMBOLS:
            raise ValueError(f"Unknown symbol {symbol!r}")
        self.symbol = symbol
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ public
    def load(
        self,
        start: str,
        end: str,
        interval: str = "5m",
        *,
        use_cache: bool = True,
        allow_synthetic: bool = True,
    ) -> pd.DataFrame:
        """Return RTH OHLCV bars for ``[start, end)``.

        Tries cache → Yahoo Finance → synthetic (if ``allow_synthetic``).
        """

        cache = self.data_dir / f"{self.symbol}_{interval}_{start}_{end}.parquet"
        if use_cache and cache.exists():
            try:
                logger.info("Loading cached bars from %s", cache)
                return pd.read_parquet(cache)
            except Exception as exc:  # missing parquet engine, corrupt file, ...
                logger.warning("Could not read cache %s: %s", cache, exc)

        df = self._download(start, end, interval)
        if df.empty and allow_synthetic:
            logger.warning("No live data for %s; generating synthetic bars", self.symbol)
            df = self.synthetic(start, end, interval)

        df = self._to_rth(df)
        if use_cache and not df.empty:
            self._write_cache(df, cache)
        return df

    def synthetic(
        self, start: str, end: str, interval: str = "5m", *, seed: int | None = None
    ) -> pd.DataFrame:
        """Generate a deterministic intraday random walk for ``[start, end)``.

        Produces realistic-looking RTH sessions: a daily gap, an intraday drift and
        Gaussian bar noise. ``seed`` defaults to one derived from the symbol so the
        same arguments always yield the same data (important for reproducible tests).
        """

        step = _interval_minutes(interval)
        rng = np.random.default_rng(
            seed if seed is not None else abs(hash(self.symbol)) % (2**32)
        )
        base = _BASE_PRICE.get(self.symbol, 5000.0)
        tick = SYMBOLS[self.symbol].tick_size

        sessions = pd.bdate_range(start=start, end=end)
        rows: list[dict] = []
        price = base
        for day in sessions:
            price *= 1.0 + rng.normal(0, 0.004)  # overnight gap
            stamps = _session_timestamps(day, step)
            # intraday drift gives some days a directional breakout
            drift = rng.normal(0, 0.00008)
            for ts in stamps:
                ret = rng.normal(drift, 0.0006)
                open_p = price
                close_p = open_p * (1.0 + ret)
                hi = max(open_p, close_p) * (1.0 + abs(rng.normal(0, 0.0004)))
                lo = min(open_p, close_p) * (1.0 - abs(rng.normal(0, 0.0004)))
                rows.append(
                    {
                        "timestamp": ts,
                        "open": _round_tick(open_p, tick),
                        "high": _round_tick(hi, tick),
                        "low": _round_tick(lo, tick),
                        "close": _round_tick(close_p, tick),
                        "volume": float(rng.integers(800, 6000)),
                    }
                )
                price = close_p

        df = pd.DataFrame(rows).set_index("timestamp")
        df.index = pd.to_datetime(df.index)
        return df[OHLCV_COLUMNS]

    # ----------------------------------------------------------------- private
    def _download(self, start: str, end: str, interval: str) -> pd.DataFrame:
        try:
            import yfinance as yf  # imported lazily so the dep is optional at runtime
        except Exception:  # pragma: no cover - exercised only without yfinance
            logger.info("yfinance not installed; skipping live download")
            return pd.DataFrame(columns=OHLCV_COLUMNS)

        ticker = SYMBOLS[self.symbol].yahoo_ticker
        try:
            raw = yf.download(
                ticker, start=start, end=end, interval=interval, progress=False, auto_adjust=False
            )
        except Exception as exc:  # pragma: no cover - network dependent
            logger.warning("Yahoo download failed for %s: %s", ticker, exc)
            return pd.DataFrame(columns=OHLCV_COLUMNS)

        if raw is None or raw.empty:
            return pd.DataFrame(columns=OHLCV_COLUMNS)

        # yfinance may return a MultiIndex (field, ticker); flatten to fields.
        if isinstance(raw.columns, pd.MultiIndex):
            raw.columns = raw.columns.get_level_values(0)
        raw = raw.rename(columns=str.lower)
        raw = raw[[c for c in OHLCV_COLUMNS if c in raw.columns]].astype(float)
        raw.index = pd.to_datetime(raw.index).tz_localize(None)
        return raw

    @staticmethod
    def _to_rth(df: pd.DataFrame) -> pd.DataFrame:
        """Keep only Regular Trading Hours bars and sort by time."""

        if df.empty:
            return df
        df = df.sort_index()
        mask = (df.index.time >= _RTH_START) & (df.index.time < _RTH_END)
        return df.loc[mask, OHLCV_COLUMNS].copy()

    @staticmethod
    def _write_cache(df: pd.DataFrame, cache: Path) -> None:
        """Persist bars to Parquet, silently skipping if no engine is installed."""

        try:
            df.to_parquet(cache)
        except Exception as exc:  # pyarrow/fastparquet not installed, caching optional
            logger.info("Skipping cache write (%s)", exc)


# --------------------------------------------------------------------- helpers
def _interval_minutes(interval: str) -> int:
    interval = interval.strip().lower()
    if interval.endswith("m"):
        return max(1, int(interval[:-1] or 1))
    if interval.endswith("h"):
        return max(1, int(interval[:-1] or 1)) * 60
    raise ValueError(f"Unsupported interval {interval!r}")


def _session_timestamps(day: pd.Timestamp, step_minutes: int) -> list[pd.Timestamp]:
    start = datetime.combine(day.date(), _RTH_START)
    end = datetime.combine(day.date(), _RTH_END)
    out: list[pd.Timestamp] = []
    cur = start
    while cur < end:
        out.append(pd.Timestamp(cur))
        cur += timedelta(minutes=step_minutes)
    return out


def _round_tick(price: float, tick: float) -> float:
    return round(round(price / tick) * tick, 4)
