"""Domain exception hierarchy for quantsys-v2.

Provides structured exception handling to replace broad 'except Exception' catches.

New code should use QuantSysException hierarchy with structured error codes.
Old DomainError hierarchy is kept for backward compatibility (aliased to new types).
"""
from typing import Optional, Dict, Any


class QuantSysException(Exception):
    """Base exception for all quantsys-v2 errors.

    Attributes:
        message: Human-readable error description
        error_code: Machine-readable error identifier (e.g., "STOCK_NOT_FOUND")
        details: Additional context for debugging (not exposed to clients)
        http_status: Suggested HTTP status code for API responses
    """

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        http_status: int = 500
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code or self.__class__.__name__.upper()
        self.details = details or {}
        self.http_status = http_status

    def to_dict(self, include_details: bool = False) -> Dict[str, Any]:
        """Convert exception to dictionary for API responses.

        Args:
            include_details: If True, include internal debugging details
                            (should only be True in dev/test environments)
        """
        result = {
            "error_code": self.error_code,
            "message": self.message,
        }
        if include_details and self.details:
            result["details"] = self.details
        return result


# ============================================================================
# Legacy DomainError Hierarchy (Backward Compatibility)
# ============================================================================
# These are kept for existing code that catches DomainError, NotFoundError, etc.
# They now inherit from QuantSysException to get structured error handling.

class DomainError(QuantSysException):
    """领域层基础异常 (legacy, aliased to QuantSysException)"""

    def __init__(self, message: str, **kwargs):
        # Default to 400 for generic domain errors
        super().__init__(message, http_status=kwargs.pop('http_status', 400), **kwargs)


class NotFoundError(DomainError):
    """资源不存在 (legacy, aliased to NotFoundException)"""

    def __init__(self, message: str, **kwargs):
        super().__init__(message, http_status=404, **kwargs)


class ValidationError(DomainError):
    """参数校验失败 (legacy, aliased to ValidationException)"""

    def __init__(self, message: str, **kwargs):
        super().__init__(message, http_status=422, **kwargs)


class ConflictError(DomainError):
    """资源冲突 (legacy)"""

    def __init__(self, message: str, **kwargs):
        super().__init__(message, http_status=409, **kwargs)


class ExternalServiceError(DomainError):
    """外部服务调用失败 (legacy, aliased to DataSourceException)"""

    def __init__(self, message: str, **kwargs):
        super().__init__(message, http_status=503, **kwargs)


class DatabaseError(DomainError):
    """数据库操作失败 (legacy, aliased to DatabaseException)"""

    def __init__(self, message: str, **kwargs):
        super().__init__(message, http_status=500, **kwargs)


class AuthenticationError(DomainError):
    """认证失败 (legacy)"""

    def __init__(self, message: str, **kwargs):
        super().__init__(message, http_status=401, **kwargs)


class AuthorizationError(DomainError):
    """权限不足 (legacy)"""

    def __init__(self, message: str, **kwargs):
        super().__init__(message, http_status=403, **kwargs)


# ============================================================================
# Validation and Input Errors (HTTP 400)
# ============================================================================

class ValidationException(QuantSysException):
    """Invalid input data or parameters."""

    def __init__(self, message: str, field: Optional[str] = None, **kwargs):
        super().__init__(message, http_status=400, **kwargs)
        if field:
            self.details["field"] = field


class InvalidSymbolException(ValidationException):
    """Stock symbol format is invalid or not supported."""

    def __init__(self, symbol: str, **kwargs):
        super().__init__(
            f"Invalid stock symbol: {symbol}",
            error_code="INVALID_SYMBOL",
            details={"symbol": symbol},
            **kwargs
        )


class InvalidDateRangeException(ValidationException):
    """Date range parameters are invalid."""

    def __init__(self, start_date: str, end_date: str, **kwargs):
        super().__init__(
            f"Invalid date range: {start_date} to {end_date}",
            error_code="INVALID_DATE_RANGE",
            details={"start_date": start_date, "end_date": end_date},
            **kwargs
        )


# ============================================================================
# Not Found Errors (HTTP 404)
# ============================================================================

class NotFoundException(QuantSysException):
    """Requested resource does not exist."""

    def __init__(self, resource_type: str, identifier: Any, **kwargs):
        super().__init__(
            f"{resource_type} not found: {identifier}",
            http_status=404,
            details={"resource_type": resource_type, "identifier": str(identifier)},
            **kwargs
        )


class StockNotFoundException(NotFoundException):
    """Stock not found in database."""

    def __init__(self, symbol: str, **kwargs):
        super().__init__(
            resource_type="Stock",
            identifier=symbol,
            error_code="STOCK_NOT_FOUND",
            **kwargs
        )


class PoolNotFoundException(NotFoundException):
    """Stock pool not found."""

    def __init__(self, pool_id: Any, **kwargs):
        super().__init__(
            resource_type="Pool",
            identifier=pool_id,
            error_code="POOL_NOT_FOUND",
            **kwargs
        )


class StrategyNotFoundException(NotFoundException):
    """Strategy not found."""

    def __init__(self, strategy_id: Any, **kwargs):
        super().__init__(
            resource_type="Strategy",
            identifier=strategy_id,
            error_code="STRATEGY_NOT_FOUND",
            **kwargs
        )


# ============================================================================
# Data Source Errors (HTTP 503)
# ============================================================================

class DataSourceException(QuantSysException):
    """External data source error (network, API limit, etc.)."""

    def __init__(self, provider: str, operation: str, reason: str, **kwargs):
        super().__init__(
            f"Data source '{provider}' failed on {operation}: {reason}",
            http_status=503,
            details={"provider": provider, "operation": operation, "reason": reason},
            **kwargs
        )


class DataProviderUnavailableException(DataSourceException):
    """All data providers in the fallback chain have failed."""

    def __init__(self, providers_tried: list, **kwargs):
        super().__init__(
            provider="all",
            operation="data_fetch",
            reason=f"All providers failed: {', '.join(providers_tried)}",
            error_code="DATA_PROVIDER_UNAVAILABLE",
            **kwargs
        )
        self.details["providers_tried"] = providers_tried


class NetworkTimeoutException(DataSourceException):
    """Network request timed out."""

    def __init__(self, provider: str, timeout_seconds: float, **kwargs):
        super().__init__(
            provider=provider,
            operation="network_request",
            reason=f"Timeout after {timeout_seconds}s",
            error_code="NETWORK_TIMEOUT",
            **kwargs
        )


class RateLimitException(DataSourceException):
    """API rate limit exceeded."""

    def __init__(self, provider: str, retry_after: Optional[int] = None, **kwargs):
        super().__init__(
            provider=provider,
            operation="api_call",
            reason="Rate limit exceeded",
            error_code="RATE_LIMIT_EXCEEDED",
            **kwargs
        )
        if retry_after:
            self.details["retry_after"] = retry_after


# ============================================================================
# Business Logic Errors (HTTP 422)
# ============================================================================

class BusinessRuleException(QuantSysException):
    """Business rule or constraint violation."""

    def __init__(self, message: str, rule: Optional[str] = None, **kwargs):
        super().__init__(message, http_status=422, **kwargs)
        if rule:
            self.details["rule"] = rule


class InsufficientDataException(BusinessRuleException):
    """Not enough data to perform calculation or analysis."""

    def __init__(self, required_points: int, available_points: int, **kwargs):
        super().__init__(
            f"Insufficient data: need {required_points} points, have {available_points}",
            error_code="INSUFFICIENT_DATA",
            **kwargs
        )
        self.details.update({
            "required_points": required_points,
            "available_points": available_points
        })


class CalculationException(BusinessRuleException):
    """Error during calculation (divide by zero, invalid formula, etc.)."""

    def __init__(self, calculation_type: str, reason: str, **kwargs):
        super().__init__(
            f"Calculation failed ({calculation_type}): {reason}",
            error_code="CALCULATION_ERROR",
            **kwargs
        )
        self.details.update({
            "calculation_type": calculation_type,
            "reason": reason
        })


# ============================================================================
# System/Infrastructure Errors (HTTP 500)
# ============================================================================

class DatabaseException(QuantSysException):
    """Database operation error."""

    def __init__(self, operation: str, reason: str, **kwargs):
        super().__init__(
            f"Database {operation} failed: {reason}",
            error_code="DATABASE_ERROR",
            details={"operation": operation, "reason": reason},
            **kwargs
        )


class ConfigurationException(QuantSysException):
    """Missing or invalid configuration."""

    def __init__(self, config_key: str, reason: str, **kwargs):
        super().__init__(
            f"Configuration error for '{config_key}': {reason}",
            error_code="CONFIGURATION_ERROR",
            details={"config_key": config_key, "reason": reason},
            **kwargs
        )


class CacheException(QuantSysException):
    """Cache operation error (non-fatal, should degrade gracefully)."""

    def __init__(self, operation: str, reason: str, **kwargs):
        super().__init__(
            f"Cache {operation} failed: {reason}",
            error_code="CACHE_ERROR",
            details={"operation": operation, "reason": reason},
            **kwargs
        )


# ============================================================================
# Helper Functions
# ============================================================================

def is_retryable(exc: Exception) -> bool:
    """Check if an exception represents a transient error worth retrying.

    Args:
        exc: The exception to check

    Returns:
        True if the error is likely transient (network timeout, rate limit, etc.)
    """
    if isinstance(exc, (NetworkTimeoutException, RateLimitException)):
        return True
    if isinstance(exc, DataProviderUnavailableException):
        return False  # Already exhausted fallback chain
    if isinstance(exc, DataSourceException):
        return True  # Other data source errors might be transient
    return False


def should_alert(exc: Exception) -> bool:
    """Check if an exception should trigger an alert/notification.

    Args:
        exc: The exception to check

    Returns:
        True if this error indicates a serious system problem
    """
    if isinstance(exc, (ValidationException, NotFoundException)):
        return False  # Client errors, not system problems
    if isinstance(exc, CacheException):
        return False  # Cache failures should degrade gracefully
    if isinstance(exc, DataProviderUnavailableException):
        return True  # All providers down = critical
    if isinstance(exc, DatabaseException):
        return True  # Database errors = critical
    return False
