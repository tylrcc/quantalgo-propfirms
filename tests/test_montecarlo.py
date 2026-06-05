from quantalgo.config import ChallengeRules, MonteCarloParams
from quantalgo.montecarlo import MonteCarloSimulator


def _sim(n=2000):
    return MonteCarloSimulator(
        ChallengeRules(),
        MonteCarloParams(n_simulations=n, max_trading_days=44, seed=123),
    )


def test_rates_sum_to_100():
    res = _sim().run([300.0, -500.0, 300.0, 300.0, -500.0])
    total = res.pass_rate + res.fail_rate + res.timeout_rate
    assert abs(total - 100.0) < 1e-6


def test_reproducible_with_seed():
    pnls = [250.0, -400.0, 250.0, 250.0]
    a = _sim().run(pnls)
    b = _sim().run(pnls)
    assert a.as_dict() == b.as_dict()


def test_positive_edge_beats_negative_edge():
    good = _sim().run([400.0, 400.0, -300.0])  # strong positive expectancy
    bad = _sim().run([300.0, -500.0, -500.0])  # negative expectancy
    assert good.pass_rate > bad.pass_rate


def test_falls_back_to_synthetic_distribution():
    res = _sim(n=1000).run([])
    assert 0.0 <= res.pass_rate <= 100.0
    assert res.n_simulations == 1000


def test_percentile_ordering():
    res = _sim().run([300.0, -500.0, 300.0])
    assert res.p05_pnl <= res.p95_pnl
