"""Monte-Carlo challenge pass-rate simulation.

Given a sample of realised trades (their dollar P&L), this module bootstrap-resamples
those outcomes to simulate many independent challenge attempts and estimates how often
the account reaches the profit target before breaching the trailing drawdown. This
answers the question that actually matters for a funded-account business: *given this
edge, what fraction of paid challenge attempts pass, and what is the expected value?*
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from quantalgo.config import ChallengeRules, MonteCarloParams


@dataclass
class MonteCarloResult:
    pass_rate: float  # percent
    fail_rate: float  # percent
    timeout_rate: float  # percent (ran out of days, neither passed nor failed)
    avg_days_to_pass: float
    expected_value: float  # mean final P&L across all attempts ($)
    p05_pnl: float
    p95_pnl: float
    n_simulations: int

    def as_dict(self) -> dict[str, float]:
        return {
            "pass_rate": round(self.pass_rate, 2),
            "fail_rate": round(self.fail_rate, 2),
            "timeout_rate": round(self.timeout_rate, 2),
            "avg_days_to_pass": round(self.avg_days_to_pass, 2),
            "expected_value": round(self.expected_value, 2),
            "p05_pnl": round(self.p05_pnl, 2),
            "p95_pnl": round(self.p95_pnl, 2),
            "n_simulations": float(self.n_simulations),
        }


class MonteCarloSimulator:
    """Bootstrap challenge attempts from a sample of trade P&Ls."""

    def __init__(self, rules: ChallengeRules, params: MonteCarloParams) -> None:
        self.rules = rules
        self.params = params

    def run(self, trade_pnls: Sequence[float]) -> MonteCarloResult:
        """Simulate ``n_simulations`` challenge attempts.

        ``trade_pnls`` is the empirical distribution of per-trade dollar outcomes
        (e.g. from a backtest). If it is empty a synthetic distribution is used so the
        simulator still produces a sensible answer.
        """

        pnls = np.asarray(trade_pnls, dtype=float)
        if pnls.size == 0:
            pnls = self._synthetic_distribution()

        rng = np.random.default_rng(self.params.seed)
        rules, p = self.rules, self.params
        drawdown_floor = -rules.trailing_max_drawdown
        target = rules.profit_target

        passed = failed = timeout = 0
        days_to_pass: list[int] = []
        final_pnls = np.empty(p.n_simulations)

        for i in range(p.n_simulations):
            equity = 0.0  # tracked relative to starting balance
            peak = 0.0
            outcome = "timeout"
            for day in range(p.max_trading_days):
                if rng.random() <= p.trade_probability:
                    equity += float(rng.choice(pnls))
                peak = max(peak, equity)
                if equity - peak <= drawdown_floor:
                    outcome = "failed"
                    break
                if equity >= target:
                    outcome = "passed"
                    days_to_pass.append(day + 1)
                    break
            final_pnls[i] = equity
            if outcome == "passed":
                passed += 1
            elif outcome == "failed":
                failed += 1
            else:
                timeout += 1

        n = float(p.n_simulations)
        return MonteCarloResult(
            pass_rate=passed / n * 100,
            fail_rate=failed / n * 100,
            timeout_rate=timeout / n * 100,
            avg_days_to_pass=float(np.mean(days_to_pass)) if days_to_pass else 0.0,
            expected_value=float(np.mean(final_pnls)),
            p05_pnl=float(np.percentile(final_pnls, 5)),
            p95_pnl=float(np.percentile(final_pnls, 95)),
            n_simulations=p.n_simulations,
        )

    def _synthetic_distribution(self) -> np.ndarray:
        """A plausible ORB outcome distribution: ~65% wins, tight TP / wide SL."""

        rng = np.random.default_rng(self.params.seed)
        win_amt = self.rules.daily_loss_limit * 0.30
        loss_amt = -self.rules.daily_loss_limit * 0.50
        draws = rng.random(400)
        return np.where(draws < 0.65, win_amt, loss_amt)
