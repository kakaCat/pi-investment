"""
Authentication and Authorization Infrastructure

Provides JWT authentication and API rate limiting.
"""

from infrastructure.auth.jwt_manager import (
    JWTManager,
    get_jwt_manager,
    require_auth,
    require_roles,
)
from infrastructure.auth.rate_limiter import (
    init_rate_limiter,
    get_rate_limiter,
    RateLimits,
    limit_login,
    limit_ml_predict,
    limit_backtest,
    exempt_from_rate_limit,
)

__all__ = [
    "JWTManager",
    "get_jwt_manager",
    "require_auth",
    "require_roles",
    "init_rate_limiter",
    "get_rate_limiter",
    "RateLimits",
    "limit_login",
    "limit_ml_predict",
    "limit_backtest",
    "exempt_from_rate_limit",
]
