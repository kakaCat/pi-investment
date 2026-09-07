"""Shared API client for daemon handlers."""
import aiohttp
from typing import Any, Dict


# API Configuration
API_BASE_URL = "http://127.0.0.1:5001"


async def call_api(method: str, path: str, data: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Call quantsys-v2 REST API.

    Args:
        method: HTTP method (GET, POST, etc.)
        path: API path (e.g., "/api/stocks/AAPL")
        data: Optional request body

    Returns:
        API response as dict

    Raises:
        Exception: If API call fails
    """
    url = f"{API_BASE_URL}{path}"

    async with aiohttp.ClientSession() as session:
        if method == "GET":
            async with session.get(url) as response:
                if response.status != 200:
                    text = await response.text()
                    raise Exception(f"API error {response.status}: {text}")
                return await response.json()

        elif method == "POST":
            async with session.post(url, json=data) as response:
                if response.status not in (200, 201):
                    text = await response.text()
                    raise Exception(f"API error {response.status}: {text}")
                return await response.json()

        else:
            raise ValueError(f"Unsupported HTTP method: {method}")
