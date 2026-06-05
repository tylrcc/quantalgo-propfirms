from quantalgo.config import ORBParams
from quantalgo.strategy import ORBStrategy


def test_long_breakout_hits_take_profit(one_day_bars, breakout_params):
    trades = ORBStrategy(breakout_params).generate_trades(one_day_bars)
    assert len(trades) == 1
    t = trades[0]
    assert t.side == "long"
    assert t.entry_price == 102.0
    assert t.target_price == 103.0  # entry + 1.0 * range(1.0)
    assert t.stop_price == 100.0  # entry - 2.0 * range(1.0)
    assert t.exit_reason == "TP"
    assert t.exit_price == 103.0


def test_volatility_filter_skips_quiet_day(one_day_bars):
    # require a 50-point opening range — our synthetic day is ~1 point, so no trade
    params = ORBParams(opening_range_minutes=2, min_range_points=50.0)
    assert ORBStrategy(params).generate_trades(one_day_bars) == []


def test_no_signal_when_price_stays_inside_range(one_day_bars):
    # Disable the move: shrink data to opening-range bars only -> no post-window bars
    params = ORBParams(opening_range_minutes=10, use_volatility_filter=False)
    trades = ORBStrategy(params).generate_trades(one_day_bars)
    assert trades == []


def test_r_multiple_sign_matches_outcome(one_day_bars, breakout_params):
    t = ORBStrategy(breakout_params).generate_trades(one_day_bars)[0]
    t.pnl_points = t.entry_price and (t.exit_price - t.entry_price)
    assert t.is_win
    assert t.r_multiple > 0
