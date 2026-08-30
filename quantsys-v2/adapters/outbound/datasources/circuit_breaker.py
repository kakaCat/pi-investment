"""Circuit breaker for data sources using pybreaker.

Prevents continuous calls to failing data sources.
Implements the Circuit Breaker pattern using the pybreaker library.
"""

import logging
from typing import Any, Dict, Optional
import pybreaker

from domain.ports.datasource_ports import ICircuitBreaker

logger = logging.getLogger(__name__)


class _StateListener(pybreaker.CircuitBreakerListener):
    """Internal listener to track state changes from pybreaker."""

    def __init__(self, parent: 'CircuitBreaker'):
        self._parent = parent

    def state_change(self, cb: pybreaker.CircuitBreaker, old_state: str, new_state: str):
        """Called when circuit breaker state changes."""
        self._parent._state = new_state
        logger.info(f"Circuit breaker '{self._parent.name}' state changed: {old_state} -> {new_state}")

    def before_call(self, cb: pybreaker.CircuitBreaker, func, *args, **kwargs):
        """Called before a function call."""
        pass

    def success(self, cb: pybreaker.CircuitBreaker):
        """Called after a successful call."""
        pass

    def failure(self, cb: pybreaker.CircuitBreaker, exc):
        """Called after a failed call."""
        pass


class CircuitBreaker(ICircuitBreaker):
    """Circuit breaker implementation using pybreaker.

    实现 ICircuitBreaker 接口，内部使用 pybreaker 库

    Tracks failures and opens the circuit when threshold is reached.
    After a timeout, allows a test request (half-open state).

    States:
    - CLOSED: Normal operation, all requests allowed
    - OPEN: Too many failures, reject all requests
    - HALF_OPEN: Testing recovery, allow one request

    Example:
        breaker = CircuitBreaker(failure_threshold=3, timeout=60)

        # 方式1: 使用 call 方法
        result = breaker.call(some_function, arg1, arg2)

        # 方式2: 使用装饰器
        @breaker.decorator
        def my_function():
            return data_provider.get_data()
    """

    def __init__(
        self,
        failure_threshold: int = 3,
        timeout: int = 60,
        success_threshold: int = 1,
        name: Optional[str] = None
    ):
        """Initialize circuit breaker.

        Args:
            failure_threshold: Number of failures before opening circuit
            timeout: Seconds to wait before attempting recovery (OPEN -> HALF_OPEN)
            success_threshold: Number of successes in HALF_OPEN before closing
            name: Optional name for the circuit breaker (for logging)
        """
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.success_threshold = success_threshold
        self.name = name or "default"

        listener = _StateListener(self)

        self._breaker = pybreaker.CircuitBreaker(
            fail_max=failure_threshold,
            reset_timeout=timeout,
            success_threshold=success_threshold,
            name=self.name,
            listeners=[listener]
        )

        self._state = self._breaker.current_state

    def is_available(self) -> bool:
        """Check if the circuit breaker allows requests.

        Returns:
            True if requests are allowed, False otherwise
        """
        return self._state != pybreaker.STATE_OPEN

    def is_open(self) -> bool:
        """Check if circuit is open (ICircuitBreaker interface method).

        Returns:
            True if circuit is open (rejecting requests), False otherwise
        """
        return self._state == pybreaker.STATE_OPEN

    def call(self, func, *args, **kwargs) -> Any:
        """Execute a function with circuit breaker protection (ICircuitBreaker interface method).

        Args:
            func: Function to execute
            *args: Positional arguments for func
            **kwargs: Keyword arguments for func

        Returns:
            Result of func if successful

        Raises:
            pybreaker.CircuitBreakerError: If circuit is open
            Exception: If func fails
        """
        return self._breaker.call(func, *args, **kwargs)

    def decorator(self, func):
        """Get a decorator for the given function.

        Args:
            func: Function to decorate

        Returns:
            Decorated function with circuit breaker protection
        """
        return self._breaker(func)

    def reset(self):
        """Manually reset the circuit breaker to CLOSED state."""
        logger.info(f"Circuit breaker '{self.name}' manually reset")
        self._breaker.close()

    def get_state(self) -> Dict[str, Any]:
        """Get current circuit breaker state.

        Returns:
            Dict with state information
        """
        return {
            'state': self._breaker.current_state,
            'name': self.name,
            'failure_threshold': self.failure_threshold,
            'timeout': self.timeout,
            'is_available': self.is_available()
        }
