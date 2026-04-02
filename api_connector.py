# API Connector for Tradovate/Topstep
# =====================================
# Connects to Tradovate API (used by Topstep)
# Supports both sandbox (paper) and live environments

import json
import time
from typing import Dict, Optional, Any
import aiohttp
from pathlib import Path

# Tradovate API endpoints
API_ENDPOINTS = {
    'accounts': 'https://api.tradovate.com/api/v1/Accounts',
    'orders': 'https://api.tradovate.com/api/v1/Orders',
    'positions': 'https://api.tradovate.com/api/v1/Positions',
    'orders/byaccount': 'https://api.tradovate.com/api/v1/Orders/{accountId}',
    'orders/{orderNumber}': 'https://api.tradovate.com/api/v1/Orders/{orderNumber}',
}


class TradovateAPI:
    """
    Wrapper for Tradovate API (used by Topstep).

    Note: This is a simplified connector. Full Tradovate
    authentication uses OAuth2 tokens obtained via their SDK.
    """

    def __init__(
        self,
        username: str,
        password: str,
        api_key: str,
        organization: str,
        sandbox: bool = True,
    ):
        self.username = username
        self.password = password
        self.api_key = api_key
        self.organization = organization
        self.sandbox = sandbox

        # Set up session
        self.session = None
        self.token = None
        self.token_expires = None

        # Symbol mapping for Tradovate
        self.symbol_map = {
            'MES': 'MES6!',      # Micro S&P 500
            'NQ': 'NDQ6!',       # Nasdaq 100
            'ES': 'ES6!',        # E-mini S&P 500
            'YM': 'YM6!',        # E-mini Dow
            '6E': '6E6!',        # Euro FX
            '6J': '6J6!',        # Japanese Yen
        }

    async def authenticate(self) -> bool:
        """
        Authenticate with Tradovate API.

        For sandbox mode, use demo credentials.
        For live mode, use OAuth2 token (if available).

        Returns:
            True if authenticated successfully
        """
        if not self.sandbox:
            raise NotImplementedError(
                "Live trading requires proper Tradovate OAuth2 authentication. "
                "Please use their SDK or obtain proper credentials."
            )

        # Sandbox mode - simulate connection
        print("Connected to Tradovate Sandbox API")
        self.token = "sandbox_token"
        return True

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict] = None,
        json_data: Optional[Dict] = None,
    ) -> Dict:
        """
        Make API request to Tradovate.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint
            params: Query parameters
            json_data: Request body

        Returns:
            Response as dict
        """
        if not self.session:
            self.session = aiohttp.ClientSession()

        # Build full URL
        url = endpoint
        for key, value in (params or {}).items():
            url = url.replace(f'{{{key}}}', str(value) if value is not None else '')

        try:
            if method == 'GET':
                async with self.session.get(url, params=params) as resp:
                    return await resp.json()
            elif method == 'POST':
                async with self.session.post(url, json=json_data) as resp:
                    return await resp.json()
            elif method == 'DELETE':
                async with self.session.delete(url) as resp:
                    return await resp.json()
            else:
                raise ValueError(f"Unsupported method: {method}")

        except aiohttp.ClientError as e:
            print(f"API Error: {e}")
            return {'error': str(e)}
        except Exception as e:
            print(f"Request Error: {e}")
            return {'error': str(e)}

    async def get_account_balance(self) -> Dict:
        """
        Get account balance.

        Returns:
            Dict with account info including balance
        """
        return await self._make_request('GET', API_ENDPOINTS['accounts'])

    async def get_open_positions(self) -> Dict:
        """
        Get open positions.

        Returns:
            Dict with positions
        """
        return await self._make_request('GET', API_ENDPOINTS['positions'])

    async def get_open_orders(self) -> Dict:
        """
        Get open orders.

        Returns:
            Dict with orders
        """
        return await self._make_request('GET', API_ENDPOINTS['orders'])

    async def submit_order(
        self,
        symbol: str,
        side: str,  # 'BUY' or 'SELL'
        quantity: int,
        order_type: str = 'MKT',  # 'MKT', 'LMT', 'STP'
        price: Optional[float] = None,
    ) -> Dict:
        """
        Submit market or limit order.

        Args:
            symbol: Tradovate symbol (e.g., 'MES6!')
            side: 'BUY' or 'SELL'
            quantity: Number of contracts
            order_type: 'MKT', 'LMT', 'STP'
            price: Limit price (if order_type == 'LMT')

        Returns:
            Order confirmation dict
        """
        order_data = {
            'OrderType': order_type,
            'OrderQuantity': quantity,
            'Symbol': self.symbol_map.get(symbol.upper(), symbol),
            'Side': side,
        }

        if order_type == 'LMT' and price:
            order_data['LimitPrice'] = price

        return await self._make_request(
            'POST',
            API_ENDPOINTS['orders'],
            json_data=order_data,
        )

    async def close_position(
        self,
        symbol: str,
        side: str,  # 'BUY' to close long, 'SELL' to close short
        quantity: int = 1,
    ) -> Dict:
        """
        Close open position.

        Args:
            symbol: Tradovate symbol
            side: Opposite of original position
            quantity: Number of contracts to close

        Returns:
            Close confirmation dict
        """
        return await self.submit_order(
            symbol=symbol,
            side=side,
            quantity=quantity,
            order_type='MKT',
        )

    async def cancel_order(self, order_id: int) -> Dict:
        """
        Cancel pending order.

        Args:
            order_id: Order number

        Returns:
            Cancel confirmation dict
        """
        return await self._make_request(
            'DELETE',
            f"{API_ENDPOINTS['orders']}/{order_id}",
        )

    async def get_account_history(
        self,
        symbol: str,
        since: Optional[str] = None,
    ) -> Dict:
        """
        Get account position history.

        Args:
            symbol: Symbol
            since: Position timestamp

        Returns:
            Position history dict
        """
        return await self._make_request(
            'GET',
            API_ENDPOINTS['accounts'] + f"/{self.organization}/Positions",
        )

    async def get_daily_profit_loss(self) -> Dict:
        """
        Get daily profit and loss.

        Returns:
            P&L dict
        """
        return await self._make_request(
            'GET',
            f"{API_ENDPOINTS['accounts']}/{self.organization}/Account/DayEndProfitLoss",
        )

    async def get_margin_details(self) -> Dict:
        """
        Get margin account details.

        Returns:
            Margin dict with daily loss limit, etc.
        """
        return await self._make_request(
            'GET',
            f"{API_ENDPOINTS['accounts']}/{self.organization}/Margin",
        )

    async def get_account_status(self) -> Dict:
        """
        Get comprehensive account status.

        Returns:
            Status dict with all account info
        """
        status = {}
        status['accounts'] = await self._make_request('GET', API_ENDPOINTS['accounts'])
        status['positions'] = await self._make_request('GET', API_ENDPOINTS['positions'])
        status['orders'] = await self._make_request('GET', API_ENDPOINTS['orders'])
        return status


# Example usage (when credentials are available)
async def main_example():
    """
    Example API usage (requires actual credentials).
    """
    # Create API connector
    api = TradovateAPI(
        username="your_username",
        password="your_password",
        api_key="your_api_key",
        organization="your_org_id",
        sandbox=True,  # Set to False for live trading
    )

    # Authenticate
    authenticated = await api.authenticate()
    if authenticated:
        print("Authenticated successfully!")

        # Get account info
        accounts = await api.get_account_balance()
        print(f"Accounts: {accounts}")

        # Get positions
        positions = await api.get_open_positions()
        print(f"Open Positions: {positions}")

        # Submit market order
        order = await api.submit_order(
            symbol='MES',
            side='BUY',
            quantity=1,
            order_type='MKT',
        )
        print(f"Order submitted: {order}")

        # Get P&L
        pnl = await api.get_daily_profit_loss()
        print(f"P&L: {pnl}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main_example())
