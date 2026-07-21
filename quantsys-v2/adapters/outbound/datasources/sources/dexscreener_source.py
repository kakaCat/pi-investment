"""Dexscreener DEX trading data source.

Provides access to decentralized exchange (DEX) trading data including
pairs, tokens, and real-time trading information.

API Documentation: https://docs.dexscreener.com/api/reference
No API key required.
"""

from typing import Optional, Dict, Any, List
import logging

from adapters.outbound.datasources.base import EconomicDataSource, DataSourceResponse
from adapters.outbound.datasources.session_manager import SessionManager
from adapters.outbound.datasources.error_handler import handle_request_error

logger = logging.getLogger(__name__)


class DexscreenerSource(EconomicDataSource):
    """Dexscreener DEX trading data source.

    Provides access to:
    - DEX pair data
    - Token information
    - Real-time trading data
    - Price and volume data
    - Liquidity information

    No API key required.
    """

    BASE_URL = "https://api.dexscreener.com/latest/dex"

    # Supported chains
    CHAINS = [
        "ethereum", "bsc", "polygon", "avalanche", "fantom", "arbitrum",
        "optimism", "base", "solana", "sui", "aptos"
    ]

    def __init__(self):
        """Initialize Dexscreener data source."""
        super().__init__(name="Dexscreener", requires_api_key=False)
        self.session = SessionManager.get_session("dexscreener")

    def validate_config(self) -> bool:
        """Validate configuration.

        Returns:
            True (no API key required)
        """
        return True

    def test_connection(self) -> DataSourceResponse:
        """Test connection to Dexscreener API.

        Returns:
            DataSourceResponse with connection status
        """
        try:
            # Test with a known token address (WETH on Ethereum)
            response = self.session.get(
                f"{self.BASE_URL}/tokens/0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
                timeout=10
            )
            response.raise_for_status()

            return DataSourceResponse.success_response(
                data={"status": "connected", "api": "Dexscreener"},
                metadata={"source": "Dexscreener", "base_url": self.BASE_URL}
            )
        except Exception as e:
            logger.error(f"Dexscreener connection test failed: {e}")
            return DataSourceResponse.error_response(
                error=f"Connection failed: {str(e)}"
            )

    def _make_request(self, endpoint: str) -> Dict[str, Any]:
        """Make request to Dexscreener API.

        Args:
            endpoint: API endpoint path

        Returns:
            JSON response data

        Raises:
            Exception: If request fails
        """
        url = f"{self.BASE_URL}/{endpoint}"
        response = self.session.get(url, timeout=30)
        response.raise_for_status()
        return response.json()

    def get_pairs_by_chain_and_address(
        self,
        chain: str,
        pair_addresses: List[str]
    ) -> DataSourceResponse:
        """Get pair data by chain and pair addresses.

        Args:
            chain: Blockchain name (e.g., 'ethereum', 'bsc', 'polygon')
            pair_addresses: List of pair addresses (max 30)

        Returns:
            DataSourceResponse with pair data
        """
        try:
            if len(pair_addresses) > 30:
                return DataSourceResponse.error_response(
                    error="Maximum 30 pair addresses allowed per request"
                )

            addresses = ",".join(pair_addresses)
            data = self._make_request(f"pairs/{chain}/{addresses}")

            return DataSourceResponse.success_response(
                data=data.get("pairs", []),
                metadata={
                    "source": "Dexscreener",
                    "chain": chain,
                    "count": len(data.get("pairs", []))
                }
            )
        except Exception as e:
            return handle_request_error(e, "Dexscreener", "get_pairs_by_chain_and_address")

    def get_pairs_by_token_address(
        self,
        token_addresses: List[str]
    ) -> DataSourceResponse:
        """Get pairs by token addresses (across all chains).

        Args:
            token_addresses: List of token addresses (max 30)

        Returns:
            DataSourceResponse with pair data
        """
        try:
            if len(token_addresses) > 30:
                return DataSourceResponse.error_response(
                    error="Maximum 30 token addresses allowed per request"
                )

            addresses = ",".join(token_addresses)
            data = self._make_request(f"tokens/{addresses}")

            return DataSourceResponse.success_response(
                data=data.get("pairs", []),
                metadata={
                    "source": "Dexscreener",
                    "count": len(data.get("pairs", []))
                }
            )
        except Exception as e:
            return handle_request_error(e, "Dexscreener", "get_pairs_by_token_address")

    def search_pairs(self, query: str) -> DataSourceResponse:
        """Search for pairs by token symbol or name.

        Args:
            query: Search query (token symbol or name)

        Returns:
            DataSourceResponse with search results
        """
        try:
            data = self._make_request(f"search?q={query}")

            return DataSourceResponse.success_response(
                data=data.get("pairs", []),
                metadata={
                    "source": "Dexscreener",
                    "query": query,
                    "count": len(data.get("pairs", []))
                }
            )
        except Exception as e:
            return handle_request_error(e, "Dexscreener", "search_pairs")

    def get_token_profiles(
        self,
        token_addresses: List[str]
    ) -> DataSourceResponse:
        """Get token profiles (social links, description, etc.).

        Args:
            token_addresses: List of token addresses (max 30)

        Returns:
            DataSourceResponse with token profile data
        """
        try:
            if len(token_addresses) > 30:
                return DataSourceResponse.error_response(
                    error="Maximum 30 token addresses allowed per request"
                )

            addresses = ",".join(token_addresses)
            data = self._make_request(f"token-profiles/latest/v1/{addresses}")

            return DataSourceResponse.success_response(
                data=data,
                metadata={
                    "source": "Dexscreener",
                    "count": len(token_addresses)
                }
            )
        except Exception as e:
            return handle_request_error(e, "Dexscreener", "get_token_profiles")

    def get_boosted_tokens(self, chain: Optional[str] = None) -> DataSourceResponse:
        """Get list of boosted tokens (promoted tokens).

        Args:
            chain: Optional chain filter (e.g., 'ethereum', 'bsc')

        Returns:
            DataSourceResponse with boosted token data
        """
        try:
            endpoint = "token-boosts/latest/v1"
            if chain:
                endpoint = f"token-boosts/top/v1/{chain}"

            data = self._make_request(endpoint)

            return DataSourceResponse.success_response(
                data=data,
                metadata={
                    "source": "Dexscreener",
                    "chain": chain
                }
            )
        except Exception as e:
            return handle_request_error(e, "Dexscreener", "get_boosted_tokens")

    def get_orders_paid(self, chain: str) -> DataSourceResponse:
        """Get latest paid orders (ads) for a chain.

        Args:
            chain: Blockchain name (e.g., 'ethereum', 'bsc')

        Returns:
            DataSourceResponse with paid order data
        """
        try:
            data = self._make_request(f"orders/paid/v1/{chain}")

            return DataSourceResponse.success_response(
                data=data,
                metadata={
                    "source": "Dexscreener",
                    "chain": chain
                }
            )
        except Exception as e:
            return handle_request_error(e, "Dexscreener", "get_orders_paid")
