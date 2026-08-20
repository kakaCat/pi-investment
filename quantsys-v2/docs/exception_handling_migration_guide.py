"""Migration guide: Replacing 'except Exception' with structured exceptions.

This file demonstrates best practices for exception handling in quantsys-v2.

BEFORE (P0-2 Problem):
    try:
        result = fetch_stock_data(symbol)
    except Exception as e:
        logger.error(f"Failed: {e}")
        return {"status": "error", "error": str(e)}

AFTER (P0-2 Fix):
    try:
        result = fetch_stock_data(symbol)
    except InvalidSymbolException as e:
        # Client error - log at INFO, return 400
        logger.info(f"Invalid symbol request: {symbol}")
        raise  # Let global handler return proper HTTP 400
    except DataProviderUnavailableException as e:
        # System error - log at ERROR, return 503
        logger.error(f"All data providers failed: {e.details}")
        raise  # Let global handler return proper HTTP 503
"""

from domain.exceptions import (
    # Validation errors
    InvalidSymbolException,
    InvalidDateRangeException,
    ValidationException,

    # Not found errors
    StockNotFoundException,
    PoolNotFoundException,
    StrategyNotFoundException,

    # Data source errors
    DataProviderUnavailableException,
    NetworkTimeoutException,
    RateLimitException,

    # Business logic errors
    InsufficientDataException,
    CalculationException,

    # System errors
    DatabaseException,
    ConfigurationException,
)


# ============================================================================
# Example 1: Validation in API Route
# ============================================================================

def example_validate_stock_symbol(symbol: str) -> dict:
    """BEFORE: Broad except Exception swallows validation errors"""
    # try:
    #     if not symbol or len(symbol) < 6:
    #         raise ValueError("Invalid symbol")
    #     return fetch_data(symbol)
    # except Exception as e:
    #     return {"error": str(e)}  # All errors look the same to caller

    """AFTER: Specific exceptions with proper HTTP codes"""
    if not symbol or len(symbol) < 6:
        raise InvalidSymbolException(symbol)  # Returns HTTP 400

    return fetch_data(symbol)  # Other exceptions propagate naturally


# ============================================================================
# Example 2: Data Fetching with Fallback Chain
# ============================================================================

def example_fetch_with_fallback(symbol: str, start_date: str) -> dict:
    """BEFORE: Silent failures in fallback chain"""
    # providers = ['akshare', 'tushare', 'eastmoney']
    # for provider in providers:
    #     try:
    #         return fetch_from_provider(provider, symbol, start_date)
    #     except Exception as e:
    #         logger.warning(f"{provider} failed: {e}")
    #         continue
    # return None  # All failed, but caller doesn't know why

    """AFTER: Structured exceptions with provider tracking"""
    from domain.exceptions import DataSourceException

    providers_tried = []
    last_error = None

    for provider in ['akshare', 'tushare', 'eastmoney']:
        try:
            return fetch_from_provider(provider, symbol, start_date)
        except NetworkTimeoutException as e:
            providers_tried.append(provider)
            last_error = e
            logger.warning(f"{provider} timed out, trying next")
            continue
        except RateLimitException as e:
            providers_tried.append(provider)
            last_error = e
            logger.warning(f"{provider} rate limited, trying next")
            continue

    # All providers failed - raise structured exception
    raise DataProviderUnavailableException(
        providers_tried=providers_tried
    )  # Returns HTTP 503 with details


# ============================================================================
# Example 3: Calculation with Business Rules
# ============================================================================

def example_calculate_indicator(prices: list, period: int = 20) -> float:
    """BEFORE: Calculation errors mixed with data errors"""
    # try:
    #     if len(prices) < period:
    #         return None
    #     result = sum(prices[-period:]) / period
    #     return result
    # except Exception as e:
    #     logger.error(f"Calculation failed: {e}")
    #     return None

    """AFTER: Distinguish data problems from calculation problems"""
    if len(prices) < period:
        raise InsufficientDataException(
            required_points=period,
            available_points=len(prices)
        )  # Returns HTTP 422 - business rule violation

    try:
        result = sum(prices[-period:]) / period
        return result
    except (ZeroDivisionError, TypeError, ValueError) as e:
        raise CalculationException(
            calculation_type="moving_average",
            reason=str(e)
        )  # Returns HTTP 422 - calculation error


# ============================================================================
# Example 4: Database Operations
# ============================================================================

def example_database_operation(stock_id: int) -> dict:
    """BEFORE: Database errors swallowed silently"""
    # try:
    #     stock = db.query(Stock).filter(Stock.id == stock_id).first()
    #     if not stock:
    #         return None
    #     return stock.to_dict()
    # except Exception as e:
    #     logger.error(f"DB error: {e}")
    #     return None

    """AFTER: Distinguish not found from database errors"""
    from sqlalchemy.exc import OperationalError, IntegrityError

    try:
        stock = db.query(Stock).filter(Stock.id == stock_id).first()
        if not stock:
            raise StockNotFoundException(symbol=f"id={stock_id}")  # HTTP 404
        return stock.to_dict()
    except (OperationalError, IntegrityError) as e:
        raise DatabaseException(
            operation="query_stock",
            reason=str(e)
        )  # HTTP 500, triggers alert


# ============================================================================
# Example 5: External Service Calls
# ============================================================================

def example_external_api_call(symbol: str) -> dict:
    """BEFORE: All HTTP errors treated the same"""
    # try:
    #     response = requests.get(f"https://api.example.com/stock/{symbol}")
    #     return response.json()
    # except Exception as e:
    #     logger.error(f"API failed: {e}")
    #     return {"error": "Service unavailable"}

    """AFTER: Distinguish timeout, rate limit, and server errors"""
    import requests
    from requests.exceptions import Timeout, HTTPError

    try:
        response = requests.get(
            f"https://api.example.com/stock/{symbol}",
            timeout=5
        )
        response.raise_for_status()
        return response.json()
    except Timeout:
        raise NetworkTimeoutException(
            provider="example_api",
            timeout_seconds=5
        )  # HTTP 503, retryable
    except HTTPError as e:
        if e.response.status_code == 429:
            retry_after = e.response.headers.get('Retry-After')
            raise RateLimitException(
                provider="example_api",
                retry_after=int(retry_after) if retry_after else None
            )  # HTTP 503, retryable
        elif e.response.status_code == 404:
            raise StockNotFoundException(symbol)  # HTTP 404
        else:
            raise DataSourceException(
                provider="example_api",
                operation="fetch_stock",
                reason=f"HTTP {e.response.status_code}"
            )  # HTTP 503


# ============================================================================
# Migration Checklist
# ============================================================================

"""
When replacing 'except Exception' blocks:

1. Identify what can go wrong:
   - Client error (bad input)? → ValidationException or NotFoundException
   - External service? → DataSourceException subclasses
   - Business rule? → BusinessRuleException subclasses
   - System/infrastructure? → DatabaseException, ConfigurationException

2. Catch specific exceptions first, broader ones last:
   except InvalidSymbolException:  # Most specific
       ...
   except ValidationException:     # Broader category
       ...
   except QuantSysException:       # Catch-all for our exceptions
       ...
   # Let truly unexpected exceptions propagate to global handler

3. Don't swallow exceptions that should stop execution:
   - Use 'raise' to propagate after logging
   - Only return error dicts for non-critical errors

4. Log at appropriate levels:
   - logger.info() for client errors (400, 404, 422)
   - logger.warning() for retryable errors (503 with fallback)
   - logger.error() for system errors (500, database, config)
   - logger.critical() for alerts (all providers down, DB unreachable)

5. Test error paths:
   - Mock external services to return errors
   - Verify correct HTTP codes are returned
   - Check logs contain useful debugging info
"""
