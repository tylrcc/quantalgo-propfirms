"""
Live Trading Script for Prop Firm Challenge
===========================================
Main entry point for paper and live trading
Connects to Tradovate/Topstep API
"""

import asyncio
import sys
import os
import logging
import json
from datetime import datetime, timedelta
from pathlib import Path

from data_loader import DataLoader
from orb_strategy import ORBStrategy
from api_connector import TradovateAPI
from config import (
    SYMBOL, SYMBOLS, CHALLENGE_PHASE, RISK, FUNDED_PHASE, BACKTEST, LOG, ORB,
)


# Set up logging
log_dir = Path('logs')
log_dir.mkdir(exist_ok=True)
logger = logging.getLogger(__name__)
logger.setLevel(LOG['level'])

# File handler
fh = logging.FileHandler(LOG['file'])
fh.setLevel(LOG['level'])
fh.setFormatter(logging.Formatter(LOG['format']))
logger.addHandler(fh)

# Console handler
ch = logging.StreamHandler()
ch.setLevel(LOG['level'])
ch.setFormatter(logging.Formatter(LOG['format']))
logger.addHandler(ch)


class ChallengeTracker:
    """
    Tracks challenge progress during trading session.
    """

    def __init__(
        self,
        config: dict,
        initial_capital: float = 50000,
    ):
        self.config = config
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.day_count = 0
        self.trade_count = 0
        self.today_pnl = 0
        self.today_dd = 0
        self.passed = False

    def record_trade(self, pnl: float, signal: int, pnl_pct: float):
        """
        Record trade outcome.
        """
        self.trade_count += 1
        self.today_pnl += pnl
        self.current_capital += pnl

        if pnl > 0:
            # Calculate drawdown
            peak = max(self.initial_capital, self.current_capital - self.today_pnl)
            self.today_dd = peak - self.current_capital
        else:
            self.today_dd = self.today_pnl

        logger.info(
            f"Trade #{self.trade_count} | PnL: ${pnl:+.2f} | "
            f"Daily P&L: ${self.today_pnl:+.2f} | "
            f"Daily DD: ${self.today_dd:+.2f} | "
            f"PnL%: {pnl_pct*100:+.2f}%"
        )

    def check_limits(self) -> tuple[bool, str]:
        """
        Check if limits exceeded.

        Returns:
            (is_valid, message)
        """
        # Check daily loss limit
        if self.today_pnl <= -self.config['daily_loss_limit']:
            return False, f"Daily loss limit hit: ${self.today_pnl:+.2f}"

        # Check max drawdown
        if abs(self.today_dd) >= self.config['max_drawdown']:
            return False, f"Max drawdown hit: ${self.today_dd:+.2f}"

        # Check if challenge is passed
        if self.current_capital >= self.initial_capital + self.config['profit_target']:
            return False, "Challenge passed!"

        # Check if we hit daily loss limit (hard stop)
        if self.config['max_concurrent_trades'] == 1 and self.trade_count >= 2:
            return False, f"Max trades per day reached: {self.trade_count}"

        return True, ""

    def check_challenged(self) -> bool:
        """
        Check if challenge phase has been completed.

        Returns:
            True if challenge is passed or failed
        """
        # Passed if we reached profit target
        if self.current_capital >= self.initial_capital + self.config['profit_target']:
            return True

        # Failed if we hit daily loss limit
        if self.today_pnl <= -self.config['daily_loss_limit']:
            return True

        # Failed if max drawdown hit
        if abs(self.today_dd) >= self.config['max_drawdown']:
            return True

        return False


class PropFirmTrader:
    """
    Main trading engine for prop firm challenges.
    """

    def __init__(self, api: TradovateAPI, config: dict = None):
        self.api = api
        self.config = config or {}

        self.symbol = config.get('symbol', SYMBOL)
        self.contract_size = SYMBOLS[self.symbol]['contract_size']

        self.challenge_config = {
            **CHALLENGE_PHASE,
            **RISK,
        }

        self.tracker = ChallengeTracker(
            config=self.challenge_config,
            initial_capital=self.challenge_config['initial_capital'] or 50000,
        )

        self.strategy = ORBStrategy(ORB)
        self.data_loader = DataLoader(symbol=self.symbol)

        self.is_challenged = False
        self.is_passed = False

    async def pre_session_check(self) -> dict:
        """
        Pre-trading session checks.
        """
        logger.info("Starting pre-session checks...")

        try:
            # Get account status
            status = await self.api.get_account_status()
            logger.info(f"Account status: {status}")

            # Get margin details (for daily limits)
            margin = await self.api.get_margin_details()
            logger.info(f"Margin details: {margin}")

            # Check open positions
            positions = status.get('positions', [])
            if positions:
                logger.warning(f"Open positions: {positions}")

            return {
                'status': 'ready',
                'account': status.get('accounts', {}),
                'positions': positions,
            }

        except Exception as e:
            logger.error(f"Pre-session check failed: {e}")
            return {'status': 'error', 'error': str(e)}

    async def session_loop(self):
        """
        Main trading session loop.
        """
        logger.info(f"Trading session started for {self.symbol}")

        while not self.is_challenged:
            try:
                # Pre-trade checks
                is_valid, message = self.tracker.check_limits()
                if not is_valid:
                    logger.info(message)
                    break

                # Check time - only trade during session
                now = datetime.now()
                if not (self.challenge_config['session_start'] <= now.strftime('%H:%M') <=
                        self.challenge_config['session_end']):
                    logger.info(
                        f"Not yet session start ({self.challenge_config['session_start']}) "
                        f"or past session end ({self.challenge_config['session_end']})"
                    )
                    break

                # Fetch data
                df = self.data_loader.fetch_historical_data(
                    start_date=datetime.now().strftime('%Y-%m-%d'),
                    end_date=datetime.now().strftime('%Y-%m-%d'),
                    interval='1m',
                )

                if df.empty:
                    logger.warning("No data received")
                    continue

                # Generate signals
                df = self.strategy.generate_trades(df)

                # Check for breakout
                signal = df.iloc[-1].get('signal')
                breakout_price = df.iloc[-1].get('breakout_price')

                if signal and breakout_price:
                    # Check if we already have an open trade
                    positions = await self.api.get_open_positions()
                    open_orders = await self.api.get_open_orders()

                    # Simple check: if we have no open position for this symbol
                    if not positions or positions.get('Positions', {}).get(self.symbol) != 1:
                        # Submit order
                        order = await self.api.submit_order(
                            symbol=self.symbol,
                            side='BUY' if signal > 0 else 'SELL',
                            quantity=1,
                            order_type='MKT',
                        )

                        if order.get('OrderNumber'):
                            pnl_pct = df.iloc[-1].get('pnl_pct', 0)
                            self.tracker.record_trade(pnl_pct, signal, pnl_pct)

                # Check if challenged
                self.is_challenged = self.tracker.check_challenged()
                self.is_passed = self.is_challenged and self.tracker.today_pnl > 0

            except Exception as e:
                logger.error(f"Trading session error: {e}")
                break

    async def run_session(self) -> dict:
        """
        Run a complete trading session.
        """
        logger.info("=" * 60)
        logger.info("PROFIRM TRADING SESSION")
        logger.info("=" * 60)

        # Pre-session check
        status = await self.pre_session_check()

        if status['status'] == 'error':
            return {'status': 'error', 'message': status.get('error', 'Unknown error')}

        # Run session loop
        await self.session_loop()

        # Summary
        summary = {
            'passed': self.is_passed,
            'trade_count': self.tracker.trade_count,
            'total_pnl': self.tracker.today_pnl,
            'ending_capital': self.tracker.current_capital,
        }

        logger.info("=" * 60)
        logger.info("SESSION SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Status: {'PASSED' if self.is_passed else 'PENDING' if not self.is_challenged else 'FAILED'}")
        logger.info(f"Trades: {summary['trade_count']}")
        logger.info(f"P&L: ${summary['total_pnl']:+.2f}")
        logger.info(f"Ending Capital: ${summary['ending_capital']:.2f}")

        return summary


async def main():
    """
    Main entry point.
    """
    # Create API connector
    api = TradovateAPI(
        username=API_CONFIG['TRADOVATE']['username'],
        password=API_CONFIG['TRADOVATE']['password'],
        api_key=API_CONFIG['TRADOVATE']['api_key'],
        organization=API_CONFIG['TRADOVATE']['organization'],
        sandbox=API_CONFIG['TRADOVATE']['sandbox'],
    )

    # Create trader
    trader = PropFirmTrader(api=api)

    # Run session
    summary = await trader.run_session()

    # Save to file
    log_file = Path('logs/session_summary.json')
    with open(log_file, 'w') as f:
        json.dump(summary, f, indent=2)

    print(f"\nSession summary saved to {log_file}")
    return summary


if __name__ == "__main__":
    asyncio.run(main())
