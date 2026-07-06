"""Typed configuration for the QuantAlgo PropFirms engine.

Configuration is expressed as immutable dataclasses with sensible defaults so the
whole library is usable with zero setup. Secrets and a few common overrides can be
supplied through environment variables (optionally via a local ``.env`` file).

Environment variables (all optional)::

    QA_SYMBOL                 default trading symbol (MES, NQ, ES, YM)
    QA_INITIAL_CAPITAL        starting account balance, float
    QA_TRADOVATE_USERNAME     broker credentials (live/sandbox execution only)
    QA_TRADOVATE_PASSWORD
    QA_TRADOVATE_API_KEY
    QA_TRADOVATE_ORG
    QA_TRADOVATE_SANDBOX      "true"/"false", paper vs live
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field, replace
from functools import lru_cache

try:  # optional dependency, never required
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover - dotenv is a convenience only
    pass


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    try:
        return float(raw) if raw is not None else default
    except ValueError:
        return default


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class SymbolSpec:
    """Contract specification for a futures symbol."""

    code: str
    name: str
    point_value: float  # dollars gained per 1.0 point move, per contract
    tick_size: float
    yahoo_ticker: str


#: Supported futures contracts (CME index futures).
SYMBOLS: dict[str, SymbolSpec] = {
    "MES": SymbolSpec("MES", "Micro E-mini S&P 500", 5.0, 0.25, "MES=F"),
    "ES": SymbolSpec("ES", "E-mini S&P 500", 50.0, 0.25, "ES=F"),
    "NQ": SymbolSpec("NQ", "E-mini Nasdaq 100", 20.0, 0.25, "NQ=F"),
    "YM": SymbolSpec("YM", "E-mini Dow", 5.0, 1.0, "YM=F"),
}


@dataclass(frozen=True)
class ORBParams:
    """Opening Range Breakout strategy parameters."""

    opening_range_minutes: int = 30
    take_profit_mult: float = 0.75  # TP distance = mult * opening-range size
    stop_loss_mult: float = 1.75  # SL distance = mult * opening-range size
    min_range_points: float = 1.0  # volatility filter; skip days quieter than this
    use_volatility_filter: bool = True
    max_trades_per_day: int = 1


@dataclass(frozen=True)
class ChallengeRules:
    """Prop-firm (Topstep-style) account constraints."""

    initial_capital: float = 50_000.0
    daily_loss_limit: float = 1_000.0
    trailing_max_drawdown: float = 2_000.0
    profit_target: float = 3_000.0
    risk_per_trade_fraction: float = 0.20  # fraction of daily loss limit risked / trade
    session_start: str = "09:30"
    session_end: str = "16:00"
    flatten_time: str = "15:55"


@dataclass(frozen=True)
class BacktestParams:
    """Backtest window / resolution settings."""

    interval: str = "5m"
    lookback_days: int = 180


@dataclass(frozen=True)
class MonteCarloParams:
    """Monte-Carlo challenge simulation settings."""

    n_simulations: int = 10_000
    max_trading_days: int = 44  # ~2 months of sessions
    trade_probability: float = 0.85  # chance a valid setup occurs on a given day
    seed: int = 42


@dataclass(frozen=True)
class BrokerCredentials:
    username: str = ""
    password: str = ""
    api_key: str = ""
    organization: str = ""
    sandbox: bool = True

    @property
    def configured(self) -> bool:
        return bool(self.username and self.password and self.api_key)


@dataclass(frozen=True)
class Settings:
    """Top-level settings container."""

    symbol: str = "MES"
    orb: ORBParams = field(default_factory=ORBParams)
    challenge: ChallengeRules = field(default_factory=ChallengeRules)
    backtest: BacktestParams = field(default_factory=BacktestParams)
    montecarlo: MonteCarloParams = field(default_factory=MonteCarloParams)
    broker: BrokerCredentials = field(default_factory=BrokerCredentials)

    @property
    def symbol_spec(self) -> SymbolSpec:
        return SYMBOLS[self.symbol]

    def with_symbol(self, symbol: str) -> Settings:
        if symbol not in SYMBOLS:
            raise ValueError(f"Unknown symbol {symbol!r}; choose from {sorted(SYMBOLS)}")
        return replace(self, symbol=symbol)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Build :class:`Settings`, applying environment overrides where present."""

    symbol = os.getenv("QA_SYMBOL", "MES").upper()
    if symbol not in SYMBOLS:
        symbol = "MES"

    challenge = ChallengeRules(
        initial_capital=_env_float("QA_INITIAL_CAPITAL", ChallengeRules().initial_capital),
    )
    broker = BrokerCredentials(
        username=os.getenv("QA_TRADOVATE_USERNAME", ""),
        password=os.getenv("QA_TRADOVATE_PASSWORD", ""),
        api_key=os.getenv("QA_TRADOVATE_API_KEY", ""),
        organization=os.getenv("QA_TRADOVATE_ORG", ""),
        sandbox=_env_bool("QA_TRADOVATE_SANDBOX", True),
    )
    return Settings(symbol=symbol, challenge=challenge, broker=broker)
