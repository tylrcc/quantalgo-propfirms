"""Broker execution interfaces.

Two implementations share a tiny :class:`Broker` protocol:

* :class:`PaperBroker` — an in-process simulator used for paper trading and tests. It
  fills market orders instantly at the supplied reference price and tracks a flat/long/
  short position plus realised P&L.
* :class:`TradovateBroker` — a thin async wrapper around the Tradovate REST API (the
  venue behind Topstep). Sandbox mode is supported for paper accounts; live trading is
  intentionally guarded until real OAuth2 credentials are wired in.

Keeping execution behind an interface means the strategy / session code never depends
on a concrete venue, and the whole stack is testable without a network.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from quantalgo.config import BrokerCredentials, SymbolSpec

logger = logging.getLogger(__name__)


@dataclass
class Position:
    symbol: str
    quantity: int = 0  # +long / -short / 0 flat
    avg_price: float = 0.0

    @property
    def is_flat(self) -> bool:
        return self.quantity == 0


@dataclass
class Fill:
    symbol: str
    side: str  # "BUY" / "SELL"
    quantity: int
    price: float


@runtime_checkable
class Broker(Protocol):
    """Minimal synchronous broker protocol used by the paper engine."""

    def market_order(self, symbol: str, side: str, quantity: int, price: float) -> Fill: ...

    def position(self, symbol: str) -> Position: ...


class PaperBroker:
    """Deterministic in-memory broker for paper trading and tests."""

    def __init__(self, spec: SymbolSpec, starting_cash: float = 50_000.0) -> None:
        self.spec = spec
        self.cash = starting_cash
        self.realised_pnl = 0.0
        self._positions: dict[str, Position] = {}

    def position(self, symbol: str) -> Position:
        return self._positions.setdefault(symbol, Position(symbol))

    def market_order(self, symbol: str, side: str, quantity: int, price: float) -> Fill:
        if quantity <= 0:
            raise ValueError("quantity must be positive")
        signed = quantity if side.upper() == "BUY" else -quantity
        pos = self.position(symbol)

        # realise P&L on the portion that reduces an existing opposite position
        if pos.quantity != 0 and (pos.quantity > 0) != (signed > 0):
            closing = min(abs(signed), abs(pos.quantity))
            direction = 1.0 if pos.quantity > 0 else -1.0
            self.realised_pnl += direction * (price - pos.avg_price) * closing * self.spec.point_value

        new_qty = pos.quantity + signed
        if new_qty == 0:
            pos.avg_price = 0.0
        elif (pos.quantity >= 0) == (signed >= 0) and pos.quantity != 0:
            # adding to the same side -> blended average price
            pos.avg_price = (pos.avg_price * abs(pos.quantity) + price * abs(signed)) / abs(new_qty)
        else:
            pos.avg_price = price
        pos.quantity = new_qty

        logger.info("PAPER %s %s x%d @ %.2f", side.upper(), symbol, quantity, price)
        return Fill(symbol, side.upper(), quantity, price)

    def flatten(self, symbol: str, price: float) -> Fill | None:
        pos = self.position(symbol)
        if pos.is_flat:
            return None
        side = "SELL" if pos.quantity > 0 else "BUY"
        return self.market_order(symbol, side, abs(pos.quantity), price)


# Tradovate REST endpoints (demo vs live hosts).
_TRADOVATE_HOSTS = {
    True: "https://demo.tradovateapi.com/v1",
    False: "https://live.tradovateapi.com/v1",
}


class TradovateBroker:
    """Async wrapper around the Tradovate REST API (Topstep's venue).

    Only the calls the strategy needs are implemented. Live trading is gated behind an
    explicit credential check because it requires a full OAuth2 access-token exchange.
    """

    def __init__(self, creds: BrokerCredentials) -> None:
        self.creds = creds
        self.host = _TRADOVATE_HOSTS[creds.sandbox]
        self._token: str | None = None
        self._session = None  # created lazily to avoid importing aiohttp at import time

    async def authenticate(self) -> bool:
        if not self.creds.sandbox and not self.creds.configured:
            raise PermissionError(
                "Live Tradovate trading requires username/password/api_key via "
                "QA_TRADOVATE_* environment variables."
            )
        import aiohttp

        if self._session is None:
            self._session = aiohttp.ClientSession()
        payload = {
            "name": self.creds.username,
            "password": self.creds.password,
            "appId": "quantalgo-propfirms",
            "appVersion": "1.0.0",
            "cid": self.creds.organization,
            "sec": self.creds.api_key,
        }
        async with self._session.post(f"{self.host}/auth/accesstokenrequest", json=payload) as r:
            data = await r.json()
        self._token = data.get("accessToken")
        return self._token is not None

    async def close(self) -> None:
        if self._session is not None:
            await self._session.close()
            self._session = None
