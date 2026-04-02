"""
Backtesting Engine for Prop Firm Challenge
============================================
Run strategy on historical data and generate performance metrics
Includes equity curve visualization
"""

import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from typing import Dict, Optional, List
from pathlib import Path

from orb_strategy import ORBStrategy


class Backtester:
    """
    Backtesting engine for prop firm challenge strategies.
    """

    def __init__(
        self,
        initial_capital: float = 50000,
        contract_size: float = 5,  # MES contract size
        config: Optional[Dict] = None,
    ):
        self.initial_capital = initial_capital
        self.contract_size = contract_size
        self.config = config or {}

        # Challenge limits
        self.daily_loss_limit = config.get('daily_loss_limit', 1000)
        self.max_drawdown = config.get('max_drawdown', 2000)
        self.profit_target = config.get('profit_target', 3000)
        self.risk_per_trade = config.get('risk_per_trade', 0.20)
        self.max_concurrent_trades = config.get('max_concurrent_trades', 1)

        # Risk-adjusted TP/SL multipliers
        self.tp_multiplier = config.get('funded_tp_multiplier', 0.75)
        self.sl_multiplier = config.get('funded_sl_multiplier', 1.75)

        # Calculate position sizing
        self.risk_dollars = self.daily_loss_limit * self.risk_per_trade
        self.stop_distance = self.daily_loss_limit * 0.5  # Stop at $500 distance
        self.position_size = self.stop_distance / self.contract_size  # Positions at 1:1
        self.position_size = min(self.position_size, 1)  # Cap at 1 position

        # Trade tracking
        self.open_trades = 0
        self.max_open_trades = 0

    def backtest(self, df: pd.DataFrame) -> Dict:
        """
        Run backtest on provided data.

        Args:
            df: DataFrame with columns [timestamp, open, high, low, close, volume]

        Returns:
            Dict with performance metrics and trade logs
        """
        print(f"\n{'='*60}")
        print(f"Backtest Starting")
        print(f"Initial Capital: ${self.initial_capital:,.2f}")
        print(f"Position Size: {self.position_size}")
        print(f"Risk per Trade: ${self.risk_dollars:,.2f}")
        print(f"{'='*60}\n")

        # Initialize
        df = df.copy()

        # Handle datetime index vs column
        if hasattr(df.index, 'date'):
            df['date'] = df.index.date
        elif 'timestamp' in df.columns:
            df['date'] = df['timestamp'].dt.date
        df['day_num'] = df['date'].apply(lambda x: pd.Timestamp(x).normalize())
        df['day_num'] = df['day_num'].dt.date

        # Reset capital
        df['capital'] = self.initial_capital
        df['daily_pnl'] = 0
        df['total_pnl'] = 0
        df['open_trades'] = 0
        df['running_dd'] = 0

        # Trade log
        trades = []

        prev_date = None
        prev_dd = 0
        daily_pnl = 0

        # Fix date column for datetime index
        df['date'] = df.index.date

        # Resample to daily - only keep first bar of each trading day
        df['date'] = df.index.date
        daily_data = df.groupby('date').first().reset_index()

        for idx, row in daily_data.iterrows():
            date = row['date']
            close = row['close']

            # Calculate daily P&L
            if prev_date is not None:
                daily_pnl = df.loc[df['date'].idx.get_loc(prev_date)]['capital'] - df.loc[df['date'].idx.get_loc(prev_date)]['capital']

            daily_data.loc[idx, 'daily_pnl'] = daily_pnl

            # Calculate running drawdown
            running_max = daily_data.loc[:idx, 'capital'].max()
            running_dd = running_max - daily_data.loc[idx, 'capital']

            daily_data.loc[idx, 'running_dd'] = running_dd

            prev_date = date

            # Skip if already at max trades
            if self.open_trades >= self.max_concurrent_trades:
                continue

            # Skip if already at daily loss limit
            if daily_pnl <= -self.daily_loss_limit:
                print(f"{date}: Hit daily loss limit, no more trades")
                continue

            # Skip if at max drawdown
            if running_dd >= self.max_drawdown:
                print(f"{date}: Hit max drawdown ${running_dd:,.2f}, no more trades")
                continue

            # Generate trade signal (would be done by strategy)
            # In real backtest, you'd call ORBStrategy here
            signal = row.get('signal', 0)  # Assume from ORB strategy
            breakout_price = row.get('breakout_price', None)
            opening_range = row.get('opening_range', 0.0)
            pnl_pct = row.get('pnl_pct', 0)

            # Only trade if we have a valid signal
            if signal != 0 and breakout_price is not None:
                self.open_trades += 1
                max_open = max(self.max_open_trades, self.open_trades)
                df.loc[idx, 'max_open_trades'] = max_open
                print(f"{date}: Signal {signal:+d} at ${breakout_price:.2f}")

                # Check if we already have an open trade for this day
                existing_trade = df[df['date'] == date][df['signal'].notna()].iloc[-1]

                if existing_trade is not None:
                    # Close previous trade if exists
                    existing_pnl = (existing_trade['close'] - existing_trade['breakout_price']) / existing_trade['breakout_price']
                    total_pnl = existing_pnl + pnl_pct
                    df.loc[idx, 'capital'] = df.loc[idx, 'capital'] + total_pnl
                    trades.append({
                        'date': date,
                        'entry': existing_trade['breakout_price'],
                        'exit': existing_trade['close'],
                        'pnl_pct': existing_pnl,
                        'exit_reason': 'TP' if existing_pnl > 0 else 'SL',
                        'signal': existing_trade['signal'],
                    })

                    # Reset for new trade
                    self.open_trades -= 1

            # Close any remaining open trades at end of day
            if self.open_trades > 0:
                df.loc[idx, 'capital'] = df.loc[idx, 'capital'] + pnl_pct
                trades.append({
                    'date': date,
                    'entry': breakout_price,
                    'exit': close,
                    'pnl_pct': pnl_pct,
                    'exit_reason': 'TP' if pnl_pct > 0 else 'SL',
                    'signal': signal,
                })
                self.open_trades = 0

        return self._summarize(df, trades)

    def _summarize(self, df: pd.DataFrame, trades: List[Dict]) -> Dict:
        """
        Generate performance summary.
        """
        capital_series = df['capital'].values
        running_dd = df['running_dd'].values

        # Calculate metrics
        final_capital = capital_series[-1]
        total_return = (final_capital - self.initial_capital) / self.initial_capital * 100

        # Calculate drawdown metrics
        peak = capital_series.cummax()
        max_dd_pct = (peak.max() - capital_series.min()) / peak.max() * 100

        # Calculate trade stats
        pnl_values = df['pnl_pct'].values
        trade_count = pd.notna(pnl_values).sum()

        winning_trades = df[pd.notna(df['pnl_pct']) & (df['pnl_pct'] > 0)]
        losing_trades = df[pd.notna(df['pnl_pct']) & (df['pnl_pct'] < 0)]

        win_rate = len(winning_trades) / trade_count * 100 if trade_count > 0 else 0

        if len(winning_trades) > 0:
            avg_win = winning_trades['pnl_pct'].mean()
            avg_loss = losing_trades['pnl_pct'].mean() if len(losing_trades) > 0 else 0
            rr = abs(avg_win / avg_loss) if avg_loss != 0 else 0

            gross_profit = winning_trades['pnl_pct'].sum()
            gross_loss = abs(losing_trades['pnl_pct'].sum())
            profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        else:
            avg_win = 0
            avg_loss = 0
            rr = 0
            profit_factor = 0

        summary = {
            'final_capital': final_capital,
            'total_return_pct': total_return,
            'total_trades': trade_count,
            'winning_trades': len(winning_trades),
            'losing_trades': len(losing_trades),
            'win_rate': win_rate,
            'risk_reward': rr,
            'profit_factor': profit_factor,
            'max_drawdown_pcts': max_dd_pct,
            'max_concurrent_trades': df['max_open_trades'].max() if len(df) > 0 else 0,
        }

        return summary

    def plot_equity_curve(self, df: pd.DataFrame, title: str = "Equity Curve"):
        """
        Plot equity curve with drawdown overlay.
        """
        capital = df['capital']

        # Handle datetime index vs column
        if hasattr(df.index, 'strftime'):
            dates = df.index
        elif 'timestamp' in df.columns:
            dates = df['timestamp']
        else:
            dates = df['date']

        # Create figure
        fig, axes = plt.subplots(2, 1, figsize=(14, 8))

        # Equity curve
        axes[0].plot(dates, capital.values, color='green', linewidth=1.5)
        axes[0].axhline(y=self.initial_capital, color='gray', linestyle='--',
                        label='Starting Capital')
        axes[0].axhline(y=self.initial_capital + self.profit_target, color='orange',
                        linestyle='--', label='Profit Target')
        axes[0].set_ylabel('Capital ($)')
        axes[0].set_title(title)
        axes[0].legend()
        axes[0].grid(True, alpha=0.3)

        # Drawdown
        peak = capital.cummax()
        dd = (peak - capital) / peak * 100
        axes[1].plot(dates, dd.values, color='red', linewidth=1)
        axes[1].axhline(y=-100 * self.max_drawdown / self.initial_capital,
                        color='gray', linestyle='--', label='Max DD Limit')
        axes[1].set_ylabel('Drawdown (%)')
        axes[1].set_xlabel('Date')
        axes[1].set_title('Drawdown')
        axes[1].legend()
        axes[1].grid(True, alpha=0.3)

        plt.tight_layout()
        plt.savefig('equity_curve.png', dpi=150)
        plt.close()
        print("Equity curve saved to equity_curve.png")

    def analyze(self, df: pd.DataFrame) -> None:
        """
        Print analysis to console.
        """
        summary = self._summarize(df, [])

        print("\n" + "="*60)
        print("BACKTEST RESULTS")
        print("="*60)
        print(f"Win Rate: {summary['win_rate']:.1f}%")
        print(f"Risk/Reward: {summary['risk_reward']:.2f}:1")
        print(f"Total Trades: {summary['total_trades']}")
        print(f"Winning Trades: {summary['winning_trades']}")
        print(f"Losing Trades: {summary['losing_trades']}")
        print(f"Profit Factor: {summary['profit_factor']:.2f}")
        print(f"Max Drawdown: {summary['max_drawdown_pcts']:.2f}%")
        print(f"Final Capital: ${summary['final_capital']:,.2f}")
        print(f"Total Return: {summary['total_return_pct']:.2f}%")
        print("="*60)


if __name__ == "__main__":
    from data_loader import DataLoader
    from orb_strategy import ORBStrategy
    from config import SYMBOL, BACKTEST, CHALLENGE_PHASE, RISK, FUNDED_PHASE

    # Load config
    config = {
        **CHALLENGE_PHASE,
        **RISK,
        **FUNDED_PHASE,
        **BACKTEST,
        'contract_size': SYMBOLS[SYMBOL]['contract_size'],
    }

    # Fetch data
    loader = DataLoader(symbol=SYMBOL)
    df = loader.fetch_historical_data(
        start_date=config['start_date'],
        end_date=config['end_date'],
        interval=config['data_interval'],
    )

    if not df.empty:
        # Generate signals
        strategy = ORBStrategy(config)
        df = strategy.generate_trades(df)

        # Run backtest
        backtester = Backtester(
            initial_capital=config['initial_capital'],
            contract_size=config['contract_size'],
            config=config,
        )
        backtester.analyze(df)

        # Plot equity curve
        backtester.plot_equity_curve(df)
