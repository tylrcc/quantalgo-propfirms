"""
Monte Carlo Pass Rate Simulator for Prop Firm Challenges
=============================================================
Simulates challenge attempts to calculate pass probability
Uses historical trade distribution to model future attempts
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from typing import Dict, Optional, List
from pathlib import Path

from orb_strategy import ORBStrategy


class MonteCarloSimulator:
    """
    Monte Carlo simulator for prop firm challenge pass rates.

    Approach:
    1. Collect historical trade outcomes (pnl, win/loss ratio)
    2. Simulate N challenge attempts with correlated trades
    3. Track daily P&L, drawdown, and profit target
    4. Calculate pass rate and average payout
    """

    def __init__(self, config: Dict):
        self.challenge_config = {
            'daily_loss_limit': config.get('daily_loss_limit', 1000),
            'max_drawdown': config.get('max_drawdown', 2000),
            'profit_target': config.get('profit_target', 3000),
        }

        self.n_simulations = config.get('n_simulations', 1000)
        self.trade_correlation = config.get('trade_correlation', 0.3)
        self.dd_factor = config.get('dd_factor', 1.0)

        self.historical_trades = None
        self.trades_per_day = config.get('trades_per_day', 1)

        # Challenge phase duration in trading days
        self.trading_days_per_month = config.get('trading_days_per_month', 22)
        self.num_months = config.get('num_months', 2)  # 2 months = typical challenge length

    def load_trade_data(self, df: pd.DataFrame) -> None:
        """
        Load historical trade data for simulation.

        Args:
            df: DataFrame from ORB strategy with pnl_pct, signal columns
        """
        # Filter to valid trades
        self.historical_trades = df[pd.notna(df['pnl_pct']) &
                                   (df['signal'].notna())].copy()

        if self.historical_trades.empty:
            # Generate synthetic trade distribution if no historical data
            self._generate_synthetic_trades()

    def _generate_synthetic_trades(self) -> None:
        """
        Generate synthetic trade distribution based on strategy parameters.
        Used when no historical data available.
        """
        np.random.seed(42)

        # Typical ORB stats: ~65% win rate, 1:0.75 RR
        n_trades = 300
        win_rate = 0.65
        avg_win = 0.008  # 80 pips
        avg_loss = -0.0107  # 107 pips

        wins = np.random.choice([1, -1], size=n_trades, p=[win_rate, 1-win_rate])
        pnl = wins * np.array([avg_win] * (wins.sum()) + [avg_loss] * (n_trades - wins.sum()))

        self.historical_trades = pd.DataFrame({
            'pnl_pct': pnl,
            'pnl_dollar': pnl * 100,  # Assume $100 base for synthetic
        })

    def simulate_challenge(self) -> pd.DataFrame:
        """
        Run Monte Carlo simulations.

        Returns:
            DataFrame with simulation results
        """
        if self.historical_trades is None:
            self._generate_synthetic_trades()

        n_simulations = self.n_simulations

        # Extract trade outcomes
        pnl_values = self.historical_trades['pnl_pct'].values
        pnl_dollar = self.historical_trades['pnl_dollar'].values

        # Simulate each challenge
        sim_results = {
            'simulation_id': np.arange(n_simulations),
            'days_traded': np.zeros(n_simulations),
            'total_trades': np.zeros(n_simulations),
            'daily_pnl': np.zeros(n_simulations),
            'running_dd': np.zeros(n_simulations),
            'profit_target': np.zeros(n_simulations),
            'passed': np.zeros(n_simulations, dtype=bool),
            'final_pnl': np.zeros(n_simulations),
        }

        daily_pnl = np.zeros(n_simulations)
        running_dd = np.zeros(n_simulations)
        total_trades = np.zeros(n_simulations)
        days_traded = np.zeros(n_simulations)

        # Correlation structure for trades
        # Positive correlation means winning/losing streaks
        corr_matrix = np.eye(len(pnl_values))
        corr_matrix = corr_matrix * self.trade_correlation

        for sim_idx in range(n_simulations):
            # Random correlation weight
            corr_weight = np.random.dirichlet(np.ones(len(pnl_values)))

            # Simulate daily P&L with correlated trades
            for day_idx in range(self.trading_days_per_month * self.num_months):
                # Number of trades this day (0 or 1)
                trade_this_day = np.random.poisson(
                    self.trades_per_day,
                )

                if trade_this_day > 0:
                    # Sample trade outcomes
                    trade_outcomes = np.random.choice(
                        pnl_values,
                        size=trade_this_day,
                        p=[
                            1 / (1 + np.exp(-p))
                            for p in np.log(pnl_values + 1)
                        ][:trade_this_day],
                    )

                    # Apply correlation
                    daily_pnl[sim_idx] += trade_outcomes.mean() * self.challenge_config['daily_loss_limit']
                    daily_pnl[sim_idx] += np.random.normal(
                        0,
                        self.challenge_config['daily_loss_limit'] * 0.05,
                    )

                    total_trades[sim_idx] += trade_this_day

                # Check if passed (reached profit target)
                if daily_pnl[sim_idx] >= self.challenge_config['profit_target']:
                    sim_results['passed'][sim_idx] = True
                    break

                # Check if failed (hit daily loss limit)
                if daily_pnl[sim_idx] <= -self.challenge_config['daily_loss_limit']:
                    break

                # Check drawdown
                running_dd[sim_idx] = abs(daily_pnl[sim_idx])
                if running_dd[sim_idx] >= self.challenge_config['max_drawdown']:
                    break

            days_traded[sim_idx] = day_idx + 1

        # Convert to DataFrame
        results = pd.DataFrame(sim_results)
        results['days_traded'] = days_traded
        results['final_pnl'] = daily_pnl

        return results

    def analyze_results(self, results: pd.DataFrame) -> Dict:
        """
        Analyze simulation results.

        Returns:
            Dict with pass rate and performance metrics
        """
        passed = results['passed'].sum()
        passed_rate = passed / len(results) * 100

        passed_results = results[results['passed']]
        failed_results = results[~results['passed']]

        # Average payout for passed challenges
        avg_pnl = passed_results['final_pnl'].mean() if len(passed_results) > 0 else 0

        # Average payout for failed challenges
        avg_loss = abs(failed_results['final_pnl'].mean()) if len(failed_results) > 0 else 0

        # Net EV per attempt
        net_ev = avg_pnl - avg_loss

        # Payout ratio
        payout_ratio = abs(avg_pnl) / (self.challenge_config['profit_target'] - avg_loss) if avg_loss > 0 else float('inf')

        metrics = {
            'pass_rate': passed_rate,
            'n_passed': int(passed),
            'n_failed': int(len(results) - passed),
            'avg_payout_passed': avg_pnl,
            'avg_loss_failed': avg_loss,
            'net_ev': net_ev,
            'payout_ratio': payout_ratio,
            'avg_trades_per_challenge': results['total_trades'].mean(),
            'avg_trades_to_pass': passed_results['total_trades'].mean() if len(passed_results) > 0 else 0,
            'trading_days_per_challenge': results['days_traded'].mean(),
        }

        return metrics

    def plot_results(self, results: pd.DataFrame, metrics: Dict) -> None:
        """
        Plot simulation results.
        """
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))

        # Pass rate histogram
        passed = results['passed']
        axes[0, 0].bar(['Passed', 'Failed'],
                       [passed.sum(), (~passed).sum()],
                       color=['green', 'red'])
        axes[0, 0].set_title(f'Challenge Results\nPass Rate: {metrics["pass_rate"]:.1f}%')
        axes[0, 0].set_ylabel('Count')

        # Payout distribution
        passed_pnl = results[passed]['final_pnl']
        failed_pnl = results[~passed]['final_pnl']
        axes[0, 1].hist(passed_pnl, bins=30, alpha=0.6, label='Passed', color='green')
        axes[0, 1].hist(failed_pnl, bins=30, alpha=0.6, label='Failed', color='red')
        axes[0, 1].axvline(0, color='gray', linestyle='--')
        axes[0, 1].set_title('Final P&L Distribution')
        axes[0, 1].set_xlabel('P&L ($)')
        axes[0, 1].set_ylabel('Frequency')
        axes[0, 1].legend()

        # Pass rate vs simulation count
        n_passed = [passed[:i].sum() for i in range(1, len(results) + 1)]
        axes[1, 0].plot(range(1, len(results) + 1), n_passed, color='green')
        axes[1, 0].axhline(metrics['pass_rate'], color='red', linestyle='--',
                           label=f'Target: {metrics["pass_rate"]:.1f}%')
        axes[1, 0].set_title('Cumulative Pass Rate')
        axes[1, 0].set_xlabel('Simulation')
        axes[1, 0].set_ylabel('Passes')
        axes[1, 0].legend()

        # Net EV
        axes[1, 1].bar(['Net EV'], [metrics['net_ev']], color='blue')
        axes[1, 1].set_title('Net EV per Challenge')
        axes[1, 1].set_ylabel('Dollars')
        axes[1, 1].grid(True, alpha=0.3)

        plt.tight_layout()
        plt.savefig('monte_carlo_results.png', dpi=150)
        plt.close()
        print("Monte Carlo results saved to monte_carlo_results.png")


def run_simulation(config: Optional[Dict] = None) -> None:
    """
    Run Monte Carlo simulation with default config.
    """
    if config is None:
        config = {
            'n_simulations': 1000,
            'trade_correlation': 0.3,
            'daily_loss_limit': 1000,
            'max_drawdown': 2000,
            'profit_target': 3000,
            'trades_per_day': 1,
            'trading_days_per_month': 22,
            'num_months': 2,
        }

    print("\n" + "="*60)
    print("Monte Carlo Pass Rate Simulation")
    print("="*60)

    sim = MonteCarloSimulator(config)

    # Load trade data from backtest
    from backtester import Backtester
    from orb_strategy import ORBStrategy
    from data_loader import DataLoader
    from config import SYMBOL, BACKTEST, CHALLENGE_PHASE, RISK, FUNDED_PHASE, ORB

    config_full = {
        **CHALLENGE_PHASE,
        **RISK,
        **FUNDED_PHASE,
        **BACKTEST,
        **ORB,
    }

    loader = DataLoader(symbol=SYMBOL)
    df = loader.fetch_historical_data(
        start_date=BACKTEST['start_date'],
        end_date=BACKTEST['end_date'],
        interval=BACKTEST['data_interval'],
    )

    if not df.empty:
        strategy = ORBStrategy(ORB)
        df = strategy.generate_trades(df)

    # Load trade data
    sim.load_trade_data(df)

    # Run simulation
    results = sim.simulate_challenge()

    # Analyze
    metrics = sim.analyze_results(results)

    print(f"\nSimulation Results:")
    print(f"  Pass Rate: {metrics['pass_rate']:.1f}%")
    print(f"  Passed: {metrics['n_passed']} / {metrics['n_passed'] + metrics['n_failed']}")
    print(f"  Avg Payout (Passed): ${metrics['avg_payout_passed']:.2f}")
    print(f"  Avg Loss (Failed): ${metrics['avg_loss_failed']:.2f}")
    print(f"  Net EV: ${metrics['net_ev']:.2f}")
    print("="*60)

    # Plot
    sim.plot_results(results, metrics)

    return metrics


if __name__ == "__main__":
    run_simulation()
