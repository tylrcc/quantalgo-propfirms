"""Event-driven backtester with prop-firm risk rules.

The backtester takes the price-level trades produced by :class:`quantalgo.strategy.ORBStrategy`,
sizes each position from the account's per-trade risk budget, then walks the trades in
chronological order while enforcing Topstep-style constraints:

* a per-trade size cap so a stop-out never exceeds the daily loss limit,
* a trailing maximum drawdown (relative to the equity peak), and
* a profit target that ends the challenge as *passed*.

It returns a :class:`BacktestResult` with the realised trades, the equity curve and a
dictionary of performance metrics.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from quantalgo.config import ChallengeRules, SymbolSpec
from quantalgo.strategy import Trade


@dataclass
class BacktestResult:
    trades: list[Trade]
    equity_curve: list[tuple[str, float]]  # (ISO date, equity)
    metrics: dict[str, float] = field(default_factory=dict)
    outcome: str = "incomplete"  # "passed", "failed" or "incomplete"


class Backtester:
    """Run a sized, risk-managed backtest over a list of strategy trades."""

    def __init__(self, rules: ChallengeRules, symbol_spec: SymbolSpec) -> None:
        self.rules = rules
        self.spec = symbol_spec

    # ------------------------------------------------------------------ public
    def run(self, trades: list[Trade]) -> BacktestResult:
        rules, spec = self.rules, self.spec
        risk_budget = rules.daily_loss_limit * rules.risk_per_trade_fraction

        equity = rules.initial_capital
        peak = equity
        curve: list[tuple[str, float]] = [("start", equity)]
        realised: list[Trade] = []
        outcome = "incomplete"

        for trade in sorted(trades, key=lambda t: t.entry_time):
            contracts = self._size(trade, risk_budget)

            direction = 1.0 if trade.side == "long" else -1.0
            trade.pnl_points = direction * (trade.exit_price - trade.entry_price)
            trade.contracts = contracts
            trade.pnl_dollars = trade.pnl_points * spec.point_value * contracts

            equity += trade.pnl_dollars
            trade.equity_after = equity
            realised.append(trade)
            curve.append((trade.date.isoformat(), equity))

            peak = max(peak, equity)
            # terminal conditions
            if equity >= rules.initial_capital + rules.profit_target:
                outcome = "passed"
                break
            if peak - equity >= rules.trailing_max_drawdown:
                outcome = "failed"
                break

        metrics = self._metrics(realised, rules.initial_capital, equity, peak)
        return BacktestResult(realised, curve, metrics, outcome)

    # ----------------------------------------------------------------- private
    def _size(self, trade: Trade, risk_budget: float) -> int:
        """Contracts to trade, capped so a stop-out stays within the loss limit."""

        per_contract_risk = trade.stop_distance * self.spec.point_value
        if per_contract_risk <= 0:
            return 1
        contracts = int(risk_budget // per_contract_risk)
        hard_cap = int(self.rules.daily_loss_limit // per_contract_risk)
        return max(1, min(contracts or 1, max(1, hard_cap)))

    @staticmethod
    def _metrics(
        trades: list[Trade], initial: float, final: float, peak: float
    ) -> dict[str, float]:
        n = len(trades)
        if n == 0:
            return {
                "total_trades": 0,
                "win_rate": 0.0,
                "profit_factor": 0.0,
                "expectancy_r": 0.0,
                "total_return_pct": 0.0,
                "final_equity": final,
                "max_drawdown": 0.0,
            }

        wins = [t for t in trades if t.pnl_dollars > 0]
        losses = [t for t in trades if t.pnl_dollars < 0]
        gross_profit = sum(t.pnl_dollars for t in wins)
        gross_loss = abs(sum(t.pnl_dollars for t in losses))

        # running max drawdown in dollars
        running_peak = initial
        max_dd = 0.0
        for t in trades:
            running_peak = max(running_peak, t.equity_after)
            max_dd = max(max_dd, running_peak - t.equity_after)

        r_multiples = [t.r_multiple for t in trades]
        return {
            "total_trades": float(n),
            "winning_trades": float(len(wins)),
            "losing_trades": float(len(losses)),
            "win_rate": round(len(wins) / n * 100, 2),
            "profit_factor": round(gross_profit / gross_loss, 3)
            if gross_loss > 0
            else float("inf"),
            "avg_win": round(gross_profit / len(wins), 2) if wins else 0.0,
            "avg_loss": round(-gross_loss / len(losses), 2) if losses else 0.0,
            "expectancy_r": round(sum(r_multiples) / n, 4),
            "total_return_pct": round((final - initial) / initial * 100, 2),
            "final_equity": round(final, 2),
            "max_drawdown": round(max_dd, 2),
            "best_trade": round(max(t.pnl_dollars for t in trades), 2),
            "worst_trade": round(min(t.pnl_dollars for t in trades), 2),
        }
