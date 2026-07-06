"""Opening Range Breakout (ORB) signal engine.

The strategy is deliberately simple and fully deterministic so it can be reasoned
about and tested:

1. For each session, the *opening range* is the high/low of the first
   ``opening_range_minutes`` of trading.
2. After that window, the first bar that **closes** beyond the range triggers an
   entry (long above the high, short below the low).
3. Take-profit and stop-loss are placed at fixed multiples of the range size.
4. The trade is resolved bar-by-bar: stop-loss is checked before take-profit within
   the same bar (a conservative assumption), otherwise the position is flattened at
   the session close.

The engine returns price-level :class:`Trade` objects; position sizing and account
risk rules live in :mod:`quantalgo.backtest`, keeping signal logic broker-agnostic.
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field

import pandas as pd

from quantalgo.config import ORBParams


@dataclass
class Trade:
    """A single round-trip trade.

    Price-level fields are filled by the strategy; sizing / dollar fields
    (``contracts``, ``pnl_dollars``, ``equity_after``) are filled by the backtester.
    """

    date: _dt.date
    side: str  # "long" or "short"
    entry_time: pd.Timestamp
    entry_price: float
    stop_price: float
    target_price: float
    range_size: float
    exit_time: pd.Timestamp
    exit_price: float
    exit_reason: str  # "TP", "SL" or "EOD"
    # filled in by the backtester:
    contracts: int = 0
    pnl_points: float = 0.0
    pnl_dollars: float = 0.0
    equity_after: float = 0.0

    @property
    def is_win(self) -> bool:
        return self.pnl_points > 0

    @property
    def stop_distance(self) -> float:
        return abs(self.entry_price - self.stop_price)

    @property
    def r_multiple(self) -> float:
        """Profit/loss expressed in units of initial risk."""
        dist = self.stop_distance
        return self.pnl_points / dist if dist else 0.0


@dataclass
class _DaySignal:
    date: _dt.date
    opening_high: float
    opening_low: float
    range_size: float
    valid: bool
    bars: pd.DataFrame = field(repr=False, default_factory=pd.DataFrame)


class ORBStrategy:
    """Generate ORB trades from intraday OHLCV bars."""

    def __init__(self, params: ORBParams | None = None) -> None:
        self.p = params or ORBParams()

    # ------------------------------------------------------------------ public
    def generate_trades(self, df: pd.DataFrame) -> list[Trade]:
        """Return the list of trades produced over every session in ``df``."""

        if df.empty:
            return []

        trades: list[Trade] = []
        for _, day_bars in df.groupby(df.index.normalize()):
            trade = self._trade_for_day(day_bars.sort_index())
            if trade is not None:
                trades.append(trade)
        return trades

    def opening_range(self, day_bars: pd.DataFrame) -> _DaySignal:
        """Compute the opening range for a single session's bars."""

        date = day_bars.index[0].date()
        if day_bars.empty:
            return _DaySignal(date, 0.0, 0.0, 0.0, False)

        session_open = day_bars.index[0]
        window_end = session_open + _dt.timedelta(minutes=self.p.opening_range_minutes)
        opening = day_bars.loc[day_bars.index < window_end]
        if len(opening) < 1:
            return _DaySignal(date, 0.0, 0.0, 0.0, False)

        hi = float(opening["high"].max())
        lo = float(opening["low"].min())
        size = hi - lo
        valid = (not self.p.use_volatility_filter) or size >= self.p.min_range_points
        post = day_bars.loc[day_bars.index >= window_end]
        return _DaySignal(date, hi, lo, size, valid, post)

    # ----------------------------------------------------------------- private
    def _trade_for_day(self, day_bars: pd.DataFrame) -> Trade | None:
        sig = self.opening_range(day_bars)
        if not sig.valid or sig.bars.empty or sig.range_size <= 0:
            return None

        # 1) find the first bar that closes beyond the opening range
        entry_idx = None
        side = None
        for ts, bar in sig.bars.iterrows():
            if bar["close"] > sig.opening_high:
                entry_idx, side = ts, "long"
                break
            if bar["close"] < sig.opening_low:
                entry_idx, side = ts, "short"
                break
        if entry_idx is None:
            return None

        entry_price = float(sig.bars.loc[entry_idx, "close"])
        tp_dist = self.p.take_profit_mult * sig.range_size
        sl_dist = self.p.stop_loss_mult * sig.range_size
        if side == "long":
            target, stop = entry_price + tp_dist, entry_price - sl_dist
        else:
            target, stop = entry_price - tp_dist, entry_price + sl_dist

        # 2) resolve the exit on subsequent bars (SL checked first within a bar)
        after = sig.bars.loc[sig.bars.index > entry_idx]
        exit_time, exit_price, reason = entry_idx, entry_price, "EOD"
        for ts, bar in after.iterrows():
            hi, lo = float(bar["high"]), float(bar["low"])
            if side == "long":
                if lo <= stop:
                    exit_time, exit_price, reason = ts, stop, "SL"
                    break
                if hi >= target:
                    exit_time, exit_price, reason = ts, target, "TP"
                    break
            else:
                if hi >= stop:
                    exit_time, exit_price, reason = ts, stop, "SL"
                    break
                if lo <= target:
                    exit_time, exit_price, reason = ts, target, "TP"
                    break
        else:
            # never hit a barrier, flatten at the final close of the session
            last_ts = sig.bars.index[-1]
            exit_time = last_ts
            exit_price = float(sig.bars.loc[last_ts, "close"])
            reason = "EOD"

        return Trade(
            date=sig.date,
            side=side,
            entry_time=entry_idx,
            entry_price=entry_price,
            stop_price=stop,
            target_price=target,
            range_size=sig.range_size,
            exit_time=exit_time,
            exit_price=exit_price,
            exit_reason=reason,
        )
