"""HTTP session manager with connection pooling.

Inspired by FinceptTerminal's connection pool optimization pattern.
Provides reusable sessions with retry logic and connection pooling.
"""

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


class SessionManager:
    """Manages HTTP sessions with connection pooling and retry logic.

    Benefits:
    - Reuses TCP connections (faster than creating new connections)
    - Automatic retry on transient failures
    - Connection pooling reduces overhead

    Usage:
        session = SessionManager.get_session()
        response = session.get(url, params=params, timeout=30)
    """

    _sessions: Dict[str, requests.Session] = {}

    @classmethod
    def get_session(
        cls,
        name: str = "default",
        pool_connections: int = 10,
        pool_maxsize: int = 10,
        max_retries: int = 3,
        backoff_factor: float = 0.3,
        status_forcelist: tuple = (500, 502, 503, 504)
    ) -> requests.Session:
        """Get or create a named session with connection pooling.

        Args:
            name: Session name (allows multiple sessions for different sources)
            pool_connections: Number of connection pools to cache
            pool_maxsize: Maximum number of connections per pool
            max_retries: Maximum number of retry attempts
            backoff_factor: Backoff factor for retries (0.3 means 0.3s, 0.6s, 1.2s...)
            status_forcelist: HTTP status codes to retry on

        Returns:
            Configured requests.Session instance
        """
        if name not in cls._sessions:
            session = requests.Session()

            # Configure retry strategy
            retry_strategy = Retry(
                total=max_retries,
                backoff_factor=backoff_factor,
                status_forcelist=status_forcelist,
                allowed_methods=["HEAD", "GET", "OPTIONS", "POST"]
            )

            # Configure adapter with connection pooling
            adapter = HTTPAdapter(
                pool_connections=pool_connections,
                pool_maxsize=pool_maxsize,
                max_retries=retry_strategy
            )

            # Mount adapter for both HTTP and HTTPS
            session.mount("https://", adapter)
            session.mount("http://", adapter)

            cls._sessions[name] = session
            logger.info(f"Created session '{name}' with pool_size={pool_maxsize}, max_retries={max_retries}")

        return cls._sessions[name]

    @classmethod
    def close_session(cls, name: str = "default") -> None:
        """Close and remove a named session."""
        if name in cls._sessions:
            cls._sessions[name].close()
            del cls._sessions[name]
            logger.info(f"Closed session '{name}'")

    @classmethod
    def close_all_sessions(cls) -> None:
        """Close all sessions."""
        for name in list(cls._sessions.keys()):
            cls.close_session(name)
        logger.info("Closed all sessions")

    @classmethod
    def get_session_stats(cls) -> Dict[str, int]:
        """Get statistics about active sessions."""
        return {
            "active_sessions": len(cls._sessions),
            "session_names": list(cls._sessions.keys())
        }


def make_request(
    url: str,
    params: Optional[Dict] = None,
    headers: Optional[Dict] = None,
    timeout: int = 30,
    session_name: str = "default"
) -> requests.Response:
    """Make an HTTP GET request using a managed session.

    Args:
        url: Request URL
        params: Query parameters
        headers: Request headers
        timeout: Request timeout in seconds
        session_name: Name of the session to use

    Returns:
        requests.Response object

    Raises:
        requests.exceptions.RequestException: On request failure
    """
    session = SessionManager.get_session(session_name)
    response = session.get(url, params=params, headers=headers, timeout=timeout)
    response.raise_for_status()
    return response
