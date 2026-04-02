#!/usr/bin/env python3
"""
Prop Firm Challenge Algorithm - Main Entry Point
==================================================
Unified interface for backtesting, simulation, and live trading.
"""

import argparse
import sys
from pathlib import Path


def print_banner():
    """Print application banner."""
    banner = f"""
╔═══════════════════════════════════════════════════════════╗
║  PROP FIRM CHALLENGE ALGORITHM                              ║
║  Topstep-Style Funded Account Optimizer                      ║
╚═══════════════════════════════════════════════════════════╝
    """
    print(banner)


def print_usage():
    """Print usage information."""
    print("""
Usage: python main.py <command> [options]

Commands:
    backtest       Run backtest on historical data
    monte-carlo    Run Monte Carlo pass rate simulation
    paper          Run paper trading session
    analyze        Analyze trade history
    help           Show this help message

Examples:
    python main.py backtest --symbol MES --days 90
    python main.py monte-carlo --simulations 1000
    python main.py paper --symbol MES --sandbox

Options:
    --symbol     Symbol: MES, NQ, or ES (default: MES)
    --days       Number of days for backtest (default: 90)
    --simulations Number of Monte Carlo simulations (default: 1000)
    --sandbox    Enable paper trading mode (default: True)
    --output     Output file path (default: ./output/)
""")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Prop Firm Challenge Algorithm',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # Backtest command
    backtest_parser = subparsers.add_parser(
        'backtest',
        help='Run backtest on historical data',
    )
    backtest_parser.add_argument(
        '--symbol', '-s',
        choices=['MES', 'NQ', 'ES'],
        default='MES',
        help='Trading symbol (default: MES)',
    )
    backtest_parser.add_argument(
        '--days', '-d',
        type=int,
        default=90,
        help='Number of days of data to fetch (default: 90)',
    )
    backtest_parser.add_argument(
        '--plot', '-p',
        action='store_true',
        help='Plot equity curve',
    )

    # Monte Carlo command
    mc_parser = subparsers.add_parser(
        'monte-carlo',
        help='Run Monte Carlo pass rate simulation',
    )
    mc_parser.add_argument(
        '--simulations', '-n',
        type=int,
        default=1000,
        help='Number of simulations (default: 1000)',
    )
    mc_parser.add_argument(
        '--symbol', '-s',
        choices=['MES', 'NQ', 'ES'],
        default='MES',
        help='Trading symbol (default: MES)',
    )

    # Paper trading command
    paper_parser = subparsers.add_parser(
        'paper',
        help='Run paper trading session',
    )
    paper_parser.add_argument(
        '--symbol', '-s',
        choices=['MES', 'NQ', 'ES'],
        default='MES',
        help='Trading symbol (default: MES)',
    )
    paper_parser.add_argument(
        '--sandbox',
        action='store_true',
        default=True,
        help='Enable paper trading mode (default: True)',
    )

    # Analyze command
    analyze_parser = subparsers.add_parser(
        'analyze',
        help='Analyze trade history',
    )
    analyze_parser.add_argument(
        '--file', '-f',
        default='logs/trading_history.json',
        help='Trade history file (default: logs/trading_history.json)',
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    if args.command == 'help':
        print_usage()
        return

    # Import here to avoid circular dependencies
    from config import SYMBOL, SYMBOLS, CHALLENGE_PHASE, ORB, BACKTEST
    from data_loader import DataLoader
    from orb_strategy import ORBStrategy
    from backtester import Backtester
    from monte_carlo import MonteCarloSimulator
    from trader import PropFirmTrader, TradovateAPI
    import asyncio

    # Backtest command
    if args.command == 'backtest':
        print("Running Backtest...")
        print(f"Symbol: {args.symbol}")
        print(f"Days: {args.days}")

        loader = DataLoader(symbol=args.symbol)

        # Calculate date range
        import datetime
        end_date = datetime.date.today()
        start_date = (end_date - datetime.timedelta(days=args.days)).strftime('%Y-%m-%d')

        df = loader.fetch_historical_data(
            start_date=start_date,
            end_date=end_date.strftime('%Y-%m-%d'),
            interval='5m',  # Use 5-min for backtest speed
        )

        if df.empty:
            print("No data received. Try a shorter date range or check internet connection.")
            return

        # Generate signals
        strategy = ORBStrategy(ORB)
        df = strategy.generate_trades(df)

        # Run backtest (adds capital column)
        backtester = Backtester(
            initial_capital=50000,
            contract_size=SYMBOLS[args.symbol]['contract_size'],
            config={
                'daily_loss_limit': CHALLENGE_PHASE['daily_loss_limit'],
                'max_drawdown': CHALLENGE_PHASE['max_drawdown'],
                'profit_target': CHALLENGE_PHASE['profit_target'],
            },
        )
        backtest_result = backtester.backtest(df)

        # Plot if requested
        if args.plot:
            backtester.plot_equity_curve(df)

        # Print analysis
        backtester.analyze(df)

        if args.plot:
            backtester.plot_equity_curve(df)

    # Monte Carlo command
    elif args.command == 'monte-carlo':
        print(f"Running Monte Carlo Simulation ({args.simulations} simulations)...")

        sim = MonteCarloSimulator({
            'n_simulations': args.simulations,
            'trade_correlation': 0.3,
            'daily_loss_limit': CHALLENGE_PHASE['daily_loss_limit'],
            'max_drawdown': CHALLENGE_PHASE['max_drawdown'],
            'profit_target': CHALLENGE_PHASE['profit_target'],
            'trades_per_day': 1,
            'trading_days_per_month': 22,
            'num_months': 2,
        })

        sim.load_trade_data(df)

        results = sim.simulate_challenge()
        metrics = sim.analyze_results(results)

        print(f"\nResults:")
        print(f"  Pass Rate: {metrics['pass_rate']:.1f}%")
        print(f"  Passed: {metrics['n_passed']}")
        print(f"  Avg Payout: ${metrics['avg_payout_passed']:.2f}")
        print(f"  Net EV: ${metrics['net_ev']:.2f}")

        sim.plot_results(results, metrics)

    # Paper trading command
    elif args.command == 'paper':
        print("Starting Paper Trading Session...")

        api = TradovateAPI(
            username="",  # Fill in your credentials
            password="",
            api_key="",
            organization="",
            sandbox=args.sandbox,
        )

        trader = PropFirmTrader(api=api)

        # Run session
        async def run():
            return await trader.run_session()

        summary = asyncio.run(run())
        print(f"\nSession Complete:")
        print(f"  Status: {'PASSED' if summary.get('passed') else 'PENDING'}")
        print(f"  Trades: {summary.get('trade_count', 0)}")
        print(f"  P&L: ${summary.get('total_pnl', 0):.2f}")

    # Analyze command
    elif args.command == 'analyze':
        import json
        with open(args.file, 'r') as f:
            history = json.load(f)

        print("\nTrade History:")
        print("-" * 60)
        for trade in history:
            print(f"  {trade['date']} | {trade['side']} | "
                  f"P&L: ${trade['pnl']:+.2f} | "
                  f"Win/Loss: {'WIN' if trade['is_win'] else 'LOSS'}")

        # Summary stats
        trades = history
        wins = sum(1 for t in trades if t['is_win'])
        print("-" * 60)
        print(f"Total Trades: {len(trades)}")
        print(f"Wins: {wins}")
        print(f"Win Rate: {wins/len(trades)*100:.1f}%")
        print(f"Total P&L: ${sum(t['pnl'] for t in trades):.2f}")

    else:
        parser.print_help()


if __name__ == "__main__":
    print_banner()
    main()
