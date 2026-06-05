"""Command-line interface for QuantAlgo PropFirms.

Subcommands::

    quantalgo backtest   --symbol MES --days 180 [--plot]
    quantalgo montecarlo --symbol MES --sims 10000 [--plot]
    quantalgo info

Everything runs offline by default: if Yahoo Finance data is unavailable the loader
falls back to a deterministic synthetic series so the commands always produce output.
"""

from __future__ import annotations

import argparse
import datetime as dt
from dataclasses import replace

from quantalgo import __version__
from quantalgo.backtest import Backtester
from quantalgo.config import SYMBOLS, get_settings
from quantalgo.data import DataLoader
from quantalgo.montecarlo import MonteCarloSimulator
from quantalgo.reporting import format_metrics
from quantalgo.strategy import ORBStrategy

_BANNER = r"""
   ___                  _   ___ _             ___          ___ _
  / _ \ _  _ __ _ _ _ | |_/ _ \ |__ _ ___  | _ \_ _ ___ _| _ (_)_ _ __ ___
 | (_) | || / _` | ' \|  _\ (_) | ' \ V / ' \  _/ '_/ _ \ _|  _/ | '_(_-</ -_)
  \__\_\\_,_\__,_|_||_|\__|\__\_\_||_\_/|_||_|_| |_| \___/_| |_| |_|_| /__/\___|
        Opening-Range-Breakout engine for funded-account challenges
"""


def _date_range(days: int) -> tuple[str, str]:
    end = dt.date.today()
    start = end - dt.timedelta(days=days)
    return start.isoformat(), end.isoformat()


def cmd_backtest(args: argparse.Namespace) -> int:
    settings = get_settings().with_symbol(args.symbol)
    start, end = _date_range(args.days)

    loader = DataLoader(symbol=settings.symbol)
    df = loader.load(start, end, interval=settings.backtest.interval)
    if df.empty:
        print("No data available for the requested window.")
        return 1

    trades = ORBStrategy(settings.orb).generate_trades(df)
    result = Backtester(settings.challenge, settings.symbol_spec).run(trades)

    print(format_metrics(f"Backtest — {settings.symbol} ({start} → {end})", result.metrics))
    print(f"\nChallenge outcome: {result.outcome.upper()}  •  {len(result.trades)} trades")

    if args.plot and result.trades:
        from quantalgo.reporting import equity_curve_plot

        path = equity_curve_plot(result.equity_curve, "equity_curve.png", settings.challenge.initial_capital)
        print(f"Saved equity curve → {path}")
    return 0


def cmd_montecarlo(args: argparse.Namespace) -> int:
    settings = get_settings().with_symbol(args.symbol)
    settings = replace(settings, montecarlo=replace(settings.montecarlo, n_simulations=args.sims))
    start, end = _date_range(settings.backtest.lookback_days)

    loader = DataLoader(symbol=settings.symbol)
    df = loader.load(start, end, interval=settings.backtest.interval)
    trades = ORBStrategy(settings.orb).generate_trades(df)
    pnls = [
        t.pnl_dollars
        for t in Backtester(settings.challenge, settings.symbol_spec).run(trades).trades
    ]

    sim = MonteCarloSimulator(settings.challenge, settings.montecarlo)
    result = sim.run(pnls)
    print(format_metrics(f"Monte-Carlo — {settings.symbol} ({args.sims:,} sims)", result.as_dict()))
    return 0


def cmd_info(_args: argparse.Namespace) -> int:
    settings = get_settings()
    print(f"QuantAlgo PropFirms v{__version__}")
    print(f"Default symbol : {settings.symbol}")
    print(f"Initial capital: ${settings.challenge.initial_capital:,.0f}")
    print("Supported symbols:")
    for spec in SYMBOLS.values():
        print(f"  • {spec.code:<4} {spec.name:<24} ${spec.point_value:>6.2f}/pt")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="quantalgo", description=__doc__)
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    bt = sub.add_parser("backtest", help="Backtest the ORB strategy on historical data")
    bt.add_argument("-s", "--symbol", choices=sorted(SYMBOLS), default="MES")
    bt.add_argument("-d", "--days", type=int, default=180)
    bt.add_argument("-p", "--plot", action="store_true")
    bt.set_defaults(func=cmd_backtest)

    mc = sub.add_parser("montecarlo", help="Estimate challenge pass-rate via Monte-Carlo")
    mc.add_argument("-s", "--symbol", choices=sorted(SYMBOLS), default="MES")
    mc.add_argument("-n", "--sims", type=int, default=10_000)
    mc.add_argument("-p", "--plot", action="store_true")
    mc.set_defaults(func=cmd_montecarlo)

    info = sub.add_parser("info", help="Show configuration and supported symbols")
    info.set_defaults(func=cmd_info)
    return parser


def main(argv: list[str] | None = None) -> int:
    print(_BANNER)
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
