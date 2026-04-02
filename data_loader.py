"""
Data Loader for Prop Firm Algorithm
======================================
Fetches historical futures OHLCV data for backtesting
Supports: MES (Micro S&P 500), NQ (Nasdaq), ES (S&P 500)
"""

import datetime
import time
import yfinance as yf
import pandas as pd
from pathlib import Path
from typing import Optional, Dict, Any

# Symbol mappings for yfinance
# Futures tickers on Yahoo Finance (uses .6! suffix for futures)
SYMBOL_MAPPINGS = {
    "MES": "MES6!",         # Micro E-mini S&P 500
    "NQ": "NDQ6!",          # Nasdaq 100
    "ES": "ES6!",           # E-mini S&P 500
    "YM": "YM6!",           # E-mini Dow
}

# Fallback yfinance tickers (without '!' suffix, sometimes works)
ALTERNATIVE_SYMBOLS = {
    "MES": "MES6",
    "NQ": "NDQ6",
    "ES": "ES6",
    "YM": "YM6",
}


class DataLoader:
    """
    Handles fetching and caching of historical futures data.
    Uses yfinance as primary source (free, accessible).
    """

    def __init__(
        self,
        symbol: str = "MES",
        data_dir: str = "./data",
        cache_duration: int = 86400,  # Cache for 24 hours
    ):
        self.symbol = symbol
        self.data_dir = Path(data_dir)
        self.cache_duration = cache_duration
        self._cache_file = self.data_dir / f"{symbol}_data.parquet"

        # Ensure data directory exists
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def fetch_historical_data(
        self,
        start_date: str,
        end_date: str,
        interval: str = "1m",
        adjust: str = "none"
    ) -> pd.DataFrame:
        """
        Fetch historical OHLCV data for a futures contract.

        Args:
            start_date: Start date string (YYYY-MM-DD)
            end_date: End date string (YYYY-MM-DD)
            interval: Time interval (1m, 5m, 15m, 1h, 1d)
            adjust: Price adjustment ('none' for futures, 'divide' for dividends)

        Returns:
            pandas DataFrame with columns: [timestamp, open, high, low, close, volume]
        """
        # yfinance symbol mapping
        yf_symbol = SYMBOL_MAPPINGS.get(self.symbol, f"{self.symbol}6!")

        try:
            print(f"Fetching {yf_symbol} data from {start_date} to {end_date}...")

            # For futures, use yfinance with proper ticker
            # Futures on Yahoo use 1-minute bars like MES6!
            hist = yf.download(
                yf_symbol,
                start=start_date,
                end=end_date,
                interval=interval,
            )

            if hist.empty:
                print(f"No data for {yf_symbol}. Trying alternative ticker...")
                alt_symbol = ALTERNATIVE_SYMBOLS.get(self.symbol, self.symbol)
                hist = yf.download(
                    alt_symbol,
                    start=start_date,
                    end=end_date,
                    interval=interval,
                )

            if hist.empty:
                print("Could not fetch data from Yahoo Finance. Using sample data for demo.")
                # Return sample data for demo purposes
                hist = self._generate_sample_data(start_date, end_date, interval)

            # Reindex to ensure continuous timestamps
            if hist.index[-1].day == end_date.day:
                hist = hist.reindex(index=pd.date_range(
                    start=hist.index.min(),
                    end=hist.index.max() + pd.Timedelta(minutes=1),
                    freq=interval.replace('m', '')
                ))

            # Fill missing columns with forward fill
            for col in ['open', 'high', 'low', 'close', 'volume']:
                if col in hist.columns:
                    hist[col] = hist[col].fillna(hist[col].shift(1))

            # Convert index to DatetimeIndex if needed
            if not isinstance(hist.index, pd.DatetimeIndex):
                hist.index = pd.to_datetime(hist.index)

            # Set timestamps as column for easier handling
            hist = hist.reset_index()
            hist = hist.rename(columns={'Datetime': 'timestamp'})

            print(f"Downloaded {len(hist)} bars")
            return hist

        except Exception as e:
            print(f"Error fetching data: {e}")
            hist = self._generate_sample_data(start_date, end_date, interval)
            print(f"Using sample data: {len(hist)} bars")
            return hist

    def _generate_sample_data(self, start_date, end_date, interval) -> pd.DataFrame:
        """Generate sample OHLCV data for demo purposes."""
        import random

        # Create date range
        start = datetime.datetime.strptime(start_date, '%Y-%m-%d')
        end = datetime.datetime.strptime(end_date, '%Y-%m-%d')

        # Generate trading days (exclude weekends)
        dates = pd.bdate_range(start=start, end=end)
        data = []
        base_price = 4200.0  # MES6! approximate price

        for date in dates:
            # First bar of the day
            open_price = base_price + random.uniform(-10, 10)
            bar = {
                'open': open_price,
                'high': open_price + random.uniform(0, 15),
                'low': open_price - random.uniform(0, 10),
                'close': open_price + random.uniform(-10, 10),
                'volume': random.randint(100000, 500000),
            }
            data.append({
                'timestamp': date,
                'open': bar['open'],
                'high': bar['high'],
                'low': bar['low'],
                'close': bar['close'],
                'volume': bar['volume'],
            })
            # Generate a few more bars
            for _ in range(random.randint(2, 5)):
                open_price = data[-1]['close']
                bar = {
                    'open': open_price,
                    'high': open_price + random.uniform(0, 10),
                    'low': open_price - random.uniform(0, 8),
                    'close': open_price + random.uniform(-5, 5),
                    'volume': random.randint(50000, 200000),
                }
                data.append({
                    'timestamp': open_price,  # Will be converted to datetime
                    'open': bar['open'],
                    'high': bar['high'],
                    'low': bar['low'],
                    'close': bar['close'],
                    'volume': bar['volume'],
                })

        # Convert to DataFrame and fix datetime index
        df = pd.DataFrame(data)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df = df.set_index('timestamp')

        # Fill missing columns with forward fill
        for col in ['open', 'high', 'low', 'close', 'volume']:
            if col in df.columns:
                df[col] = df[col].fillna(df[col].shift(1))

        return df

    def load_from_cache(self) -> Optional[pd.DataFrame]:
        """Load cached data if available and fresh."""
        if self._cache_file.exists():
            try:
                cache_mtime = self._cache_file.stat().st_mtime
                # Check if cache is fresh (within cache_duration seconds)
                if time.time() - cache_mtime < self.cache_duration:
                    print(f"Loading cached data...")
                    return pd.read_parquet(self._cache_file)
            except Exception:
                pass
        return None

    def save_to_cache(self, df: pd.DataFrame) -> None:
        """Save data to cache file."""
        if not df.empty:
            df.to_parquet(self._cache_file, index=False)
            print(f"Saved data to {self._cache_file}")

    def get_range_stats(self, df: pd.DataFrame) -> Dict[str, float]:
        """
        Calculate opening range statistics for each trading day.

        Returns dict with keys:
        - 'highs': Opening range highs
        - 'lows': Opening range lows
        - 'ranges': Opening range sizes
        - 'volumes': Opening range volumes
        """
        if df.empty:
            return {}

        # Resample to daily and get first 30-min bar
        opening_range_minutes = getattr(self, 'opening_range_minutes', 30)

        # Group by day
        df['date'] = df['timestamp'].dt.date

        ranges = {}
        for date, day_data in df.groupby('date'):
            # Get the first opening range bar(s)
            open_range_data = day_data.iloc[:opening_range_minutes]

            high = open_range_data['high'].max()
            low = open_range_data['low'].min()
            range_size = high - low
            volume = open_range_data['volume'].sum()

            ranges[date] = {
                'high': high,
                'low': low,
                'range': range_size,
                'volume': volume,
            }

        return ranges


if __name__ == "__main__":
    import time  # Import here to avoid top-level import
    from config import SYMBOL, BACKTEST

    loader = DataLoader(symbol=SYMBOL)
    df = loader.fetch_historical_data(
        start_date=BACKTEST['start_date'],
        end_date=BACKTEST['end_date'],
        interval=BACKTEST['data_interval'],
    )

    if not df.empty:
        print("\nData shape:", df.shape)
        print("\nColumns:", df.columns.tolist())
        print("\nFirst 5 rows:")
        print(df.head())
