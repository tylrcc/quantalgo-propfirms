"""
Opening Range Breakout (ORB) Strategy
========================================
High win-rate strategy optimized for prop firm challenges
- Tight TP / Wide SL = High win rate structure
- One trade per day max
"""

import pandas as pd
import numpy as np
from typing import Dict, Tuple, Optional


class ORBStrategy:
    """
    Opening Range Breakout Strategy.

    Logic:
    1. Define opening range as first N minutes of RTH session
    2. Long when price breaks above range high
    3. Short when price breaks below range low
    4. TP = multiplier_x * opening_range_size
    5. SL = multiplier_y * opening_range_size
    """

    def __init__(self, config: Dict):
        self.opening_range_minutes = config.get('opening_range_minutes', 30)
        self.breakout_threshold = config.get('breakout_threshold', 1.05)
        self.tp_multiplier = config.get('tp_multiplier', 0.75)
        self.sl_multiplier = config.get('sl_multiplier', 1.75)
        self.max_trades_per_day = config.get('max_trades_per_day', 1)
        self.require_volatility_filter = config.get('require_volatility_filter', True)
        self.volatility_threshold = config.get('volatility_threshold', 0.50)  # $0.50 min range

    def calculate_opening_range(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate opening range for each trading day.

        Returns DataFrame with new columns:
        - opening_high, opening_low, opening_range, valid_open_range
        """
        df = df.copy()

        # Handle both column-based and index-based timestamps
        if 'timestamp' in df.columns:
            timestamp_col = 'timestamp'
        else:
            timestamp_col = None

        df['date'] = df[timestamp_col].dt.date if timestamp_col else df.index.date

        # Calculate first N minutes range for each day
        for _, row in df.iterrows():
            date = row['date']
            day_data = df[df['date'] == date].sort_index()

            # Get first opening range bars
            open_range_data = day_data.iloc[:self.opening_range_minutes]

            if len(open_range_data) < 2:
                continue

            opening_high = open_range_data['high'].max()
            opening_low = open_range_data['low'].min()
            opening_range = opening_high - opening_low

            # Filter by volatility if enabled
            valid = False
            if not self.require_volatility_filter:
                valid = True
            elif opening_range >= self.volatility_threshold:
                valid = True

            df.loc[row.name, 'opening_high'] = opening_high
            df.loc[row.name, 'opening_low'] = opening_low
            df.loc[row.name, 'opening_range'] = opening_range
            df.loc[row.name, 'valid_open_range'] = valid

        return df

    def identify_breakouts(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Identify breakout signals after opening range is established.

        Returns DataFrame with:
        - signal: -1 (short), 1 (long), 0 (no signal)
        - breakout_price: Price where breakout occurred
        """
        df = df.copy()

        for _, row in df.iterrows():
            date = row['date']
            valid = row.get('valid_open_range', False)

            if not valid:
                df.loc[row.name, 'signal'] = 0
                df.loc[row.name, 'breakout_price'] = None
                continue

            opening_high = row['opening_high']
            opening_low = row['opening_low']

            current_price = row['close']

            # Check for long breakout
            is_long_breakout = current_price > (opening_high * self.breakout_threshold)
            # Check for short breakout
            is_short_breakout = current_price < (opening_low * (1 - self.breakout_threshold))

            if is_long_breakout:
                df.loc[row.name, 'signal'] = 1
                df.loc[row.name, 'breakout_price'] = current_price
            elif is_short_breakout:
                df.loc[row.name, 'signal'] = -1
                df.loc[row.name, 'breakout_price'] = current_price
            else:
                df.loc[row.name, 'signal'] = 0
                df.loc[row.name, 'breakout_price'] = None

        return df

    def calculate_stop_loss(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate stop loss and take profit levels.

        Returns DataFrame with:
        - tp_price, sl_price
        """
        df = df.copy()

        for _, row in df.iterrows():
            if pd.isna(row['signal']) or row['signal'] == 0:
                df.loc[row.name, 'tp_price'] = None
                df.loc[row.name, 'sl_price'] = None
                continue

            opening_range = row['opening_range']
            signal = row['signal']

            # Calculate TP and SL
            if signal > 0:  # Long position
                df.loc[row.name, 'tp_price'] = row['breakout_price'] + (opening_range * self.tp_multiplier)
                df.loc[row.name, 'sl_price'] = row['breakout_price'] - (opening_range * self.sl_multiplier)
            else:  # Short position
                df.loc[row.name, 'tp_price'] = row['breakout_price'] - (opening_range * self.tp_multiplier)
                df.loc[row.name, 'sl_price'] = row['breakout_price'] + (opening_range * self.sl_multiplier)

        return df

    def generate_trades(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Generate trade signals and prepare for backtesting.

        Returns DataFrame with trade-related columns.
        """
        # Step 1: Calculate opening range
        df = self.calculate_opening_range(df)

        # Step 2: Identify breakouts
        df = self.identify_breakouts(df)

        # Step 3: Calculate TP/SL
        df = self.calculate_stop_loss(df)

        return df

    def analyze_trades(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add columns to track trade performance.

        Returns DataFrame with:
        - exit_reason: 'TP', 'SL', 'manual'
        - pnl_pct: Percentage P&L
        """
        df = df.copy()

        for _, row in df.iterrows():
            if pd.isna(row['signal']):
                continue

            entry_price = row['breakout_price']
            exit_price = row['close']

            if pd.isna(entry_price) or pd.isna(exit_price):
                continue

            # Calculate P&L
            if row['signal'] > 0:  # Long
                pnl_pct = (exit_price - entry_price) / entry_price
                tp_price = row['tp_price'] or (entry_price + (row['opening_range'] * self.tp_multiplier))
                sl_price = row['sl_price'] or (entry_price - (row['opening_range'] * self.sl_multiplier))
            else:  # Short
                pnl_pct = (entry_price - exit_price) / entry_price
                tp_price = row['tp_price'] or (entry_price - (row['opening_range'] * self.tp_multiplier))
                sl_price = row['sl_price'] or (entry_price + (row['opening_range'] * self.sl_multiplier))

            # Determine exit reason
            if pd.notna(tp_price) and exit_price >= tp_price:
                exit_reason = 'TP'
            elif pd.notna(sl_price) and exit_price <= sl_price:
                exit_reason = 'SL'
            else:
                exit_reason = 'partial'  # Partial profit/loss at end of day

            df.loc[row.name, 'pnl_pct'] = pnl_pct
            df.loc[row.name, 'exit_reason'] = exit_reason
            df.loc[row.name, 'tp_price'] = tp_price
            df.loc[row.name, 'sl_price'] = sl_price

        return df

    def filter_partial_closes(self, df: pd.DataFrame, end_time: str = "16:00") -> pd.DataFrame:
        """
        Filter trades that were partially closed at session end.

        For prop firm challenges, we typically:
        - Close all positions before market close
        - Only count as win/loss based on final P&L
        """
        df = df.copy()

        # Assume trades are closed at end of session
        # Mark remaining open positions as SL or TP based on final P&L
        for date in df['date'].unique():
            day_data = df[df['date'] == date]
            remaining = day_data[day_data['signal'].notna() &
                              (day_data['exit_reason'].isin(['partial', None]))]

            if len(remaining) > 0:
                # Use final close as exit
                final_close = day_data['close'].iloc[-1]
                for idx in remaining.index:
                    pnl_pct = (final_close - day_data.loc[idx, 'breakout_price']) / \
                               day_data.loc[idx, 'breakout_price']
                    if pnl_pct > 0:
                        day_data.loc[idx, 'exit_reason'] = 'TP'
                    else:
                        day_data.loc[idx, 'exit_reason'] = 'SL'

        return df


if __name__ == "__main__":
    from data_loader import DataLoader
    from config import SYMBOL, BACKTEST, ORB

    # Fetch data
    loader = DataLoader(symbol=SYMBOL)
    df = loader.fetch_historical_data(
        start_date=BACKTEST['start_date'],
        end_date=BACKTEST['end_date'],
        interval=BACKTEST['data_interval'],
    )

    if not df.empty:
        # Generate trade signals
        strategy = ORBStrategy(ORB)
        df_with_signals = strategy.generate_trades(df)
        df_with_signals = strategy.analyze_trades(df_with_signals)

        print("\nTrade Analysis:")
        print(df_with_signals[['date', 'signal', 'breakout_price', 'pnl_pct', 'exit_reason']].tail())
