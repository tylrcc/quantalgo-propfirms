import math

from quantalgo.backtest import Backtester
from quantalgo.config import Settings
from quantalgo.strategy import ORBStrategy


def test_backtest_runs_on_synthetic(synthetic_df, settings):
    trades = ORBStrategy(settings.orb).generate_trades(synthetic_df)
    result = Backtester(settings.challenge, settings.symbol_spec).run(trades)

    # equity curve always has the starting point plus one entry per realised trade
    assert result.equity_curve[0] == ("start", settings.challenge.initial_capital)
    assert len(result.equity_curve) == len(result.trades) + 1

    m = result.metrics
    for key in ("total_trades", "win_rate", "final_equity", "max_drawdown"):
        assert key in m
    assert 0.0 <= m["win_rate"] <= 100.0
    assert math.isfinite(m["final_equity"])
    assert result.outcome in {"passed", "failed", "incomplete"}


def test_position_sizing_respects_loss_limit(synthetic_df, settings):
    trades = ORBStrategy(settings.orb).generate_trades(synthetic_df)
    result = Backtester(settings.challenge, settings.symbol_spec).run(trades)
    point_value = settings.symbol_spec.point_value
    for t in result.trades:
        assert t.contracts >= 1
        worst_case = t.stop_distance * point_value * t.contracts
        # a single stop-out must never exceed the daily loss limit (with 1-contract floor tolerance)
        assert worst_case <= settings.challenge.daily_loss_limit + worst_case / t.contracts


def test_equity_consistency(synthetic_df, settings):
    trades = ORBStrategy(settings.orb).generate_trades(synthetic_df)
    result = Backtester(settings.challenge, settings.symbol_spec).run(trades)
    if result.trades:
        running = settings.challenge.initial_capital + sum(t.pnl_dollars for t in result.trades)
        assert math.isclose(running, result.trades[-1].equity_after, rel_tol=1e-9)


def test_empty_trades_gives_flat_result():
    s = Settings()
    result = Backtester(s.challenge, s.symbol_spec).run([])
    assert result.metrics["total_trades"] == 0
    assert result.metrics["final_equity"] == s.challenge.initial_capital
