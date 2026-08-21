"""Circuit breaker for data sources.

Prevents continuous calls to failing data sources.
Implements the Circuit Breaker pattern.
"""

import time
import logging
from typing import Dict, Optional
from enum import Enum

from domain.ports.datasource_ports import ICircuitBreaker

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if recovered


class CircuitBreaker(ICircuitBreaker):
    """Circuit breaker implementation for data sources.

    实现 ICircuitBreaker 接口

    Tracks failures and opens the circuit when threshold is reached.
    After a timeout, allows a test request (half-open state).

    States:
    - CLOSED: Normal operation, all requests allowed
    - OPEN: Too many failures, reject all requests
    - HALF_OPEN: Testing recovery, allow one request

    Example:
        breaker = CircuitBreaker(failure_threshold=3, timeout=60)

        if breaker.is_available():
            try:
                result = call_data_source()
                breaker.record_success()
            except Exception:
                breaker.record_failure()
    """

    def __init__(
        self,
        failure_threshold: int = 3,
        timeout: int = 60,
        success_threshold: int = 1
    ):
        """Initialize circuit breaker.

        Args:
            failure_threshold: Number of failures before opening circuit
            timeout: Seconds to wait before attempting recovery (OPEN -> HALF_OPEN)
            success_threshold: Number of successes in HALF_OPEN before closing
        """
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.success_threshold = success_threshold

        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[float] = None
        self.state = CircuitState.CLOSED

    def is_available(self) -> bool:
        """Check if the circuit breaker allows requests.

        Returns:
            True if requests are allowed, False otherwise
        """
        if self.state == CircuitState.CLOSED:
            return True

        if self.state == CircuitState.OPEN:
            # Check if timeout has elapsed
            if self.last_failure_time and \
               time.time() - self.last_failure_time >= self.timeout:
                logger.info("Circuit breaker transitioning to HALF_OPEN (testing recovery)")
                self.state = CircuitState.HALF_OPEN
                self.success_count = 0
                return True
            return False

        # HALF_OPEN: allow requests to test recovery
        return True

    def record_success(self):
        """Record a successful request."""
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.success_threshold:
                logger.info("Circuit breaker CLOSED (recovered)")
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                self.success_count = 0

        elif self.state == CircuitState.CLOSED:
            # Reset failure count on success
            self.failure_count = 0

    def record_failure(self):
        """Record a failed request."""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.state == CircuitState.HALF_OPEN:
            # Failed during recovery test - back to OPEN
            logger.warning("Circuit breaker reopened (recovery test failed)")
            self.state = CircuitState.OPEN
            self.success_count = 0

        elif self.state == CircuitState.CLOSED:
            if self.failure_count >= self.failure_threshold:
                logger.warning(
                    f"Circuit breaker OPENED after {self.failure_count} failures"
                )
                self.state = CircuitState.OPEN

    def reset(self):
        """Manually reset the circuit breaker to CLOSED state."""
        logger.info("Circuit breaker manually reset")
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None

    def get_state(self) -> Dict[str, any]:
        """Get current circuit breaker state.

        Returns:
            Dict with state information
        """
        return {
            'state': self.state.value,
            'failure_count': self.failure_count,
            'success_count': self.success_count,
            'last_failure_time': self.last_failure_time,
            'is_available': self.is_available()
        }
