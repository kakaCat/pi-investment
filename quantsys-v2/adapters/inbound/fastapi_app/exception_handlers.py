"""Improved global exception handler for FastAPI.

Replaces broad 'except Exception' with structured exception handling:
- Business exceptions return appropriate HTTP codes (400/404/422/503)
- System exceptions return 500 but don't leak internal details
- All exceptions are logged with full context for debugging
"""
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
import logging
import os
from typing import Union

from domain.exceptions import (
    QuantSysException,
    ValidationException,
    NotFoundException,
    DataSourceException,
    BusinessRuleException,
    should_alert,
)

logger = logging.getLogger(__name__)

# Determine if we're in a development environment
IS_DEV = os.getenv("ENVIRONMENT", "production").lower() in ("dev", "development", "local")


async def quantsys_exception_handler(
    request: Request,
    exc: QuantSysException
) -> JSONResponse:
    """Handle all QuantSysException subclasses with proper HTTP codes.

    Business exceptions (validation, not found, etc.) are logged at INFO level.
    System exceptions (database, config, etc.) are logged at ERROR level.
    """
    # Determine log level based on exception type
    if isinstance(exc, (ValidationException, NotFoundException, BusinessRuleException)):
        log_level = logging.INFO
    else:
        log_level = logging.ERROR

    # Log with full context
    logger.log(
        log_level,
        f"{exc.__class__.__name__}: {exc.message}",
        extra={
            "error_code": exc.error_code,
            "http_status": exc.http_status,
            "details": exc.details,
            "path": request.url.path,
            "method": request.method,
        },
        exc_info=log_level == logging.ERROR,  # Include traceback for system errors
    )

    # Check if we should alert ops team
    if should_alert(exc):
        logger.critical(
            f"ALERT: Critical system error - {exc.__class__.__name__}",
            extra={"error_code": exc.error_code, "details": exc.details}
        )
        # TODO: Integrate with alerting system (PagerDuty, etc.)

    # Return structured response
    return JSONResponse(
        status_code=exc.http_status,
        content={
            "success": False,
            **exc.to_dict(include_details=IS_DEV),  # Only expose details in dev
        },
    )


async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError
) -> JSONResponse:
    """Handle FastAPI/Pydantic validation errors (422 Unprocessable Entity).

    These are raised when request body/query params don't match the schema.
    """
    logger.info(
        f"Validation error on {request.method} {request.url.path}",
        extra={"errors": exc.errors()},
    )

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "success": False,
            "error_code": "VALIDATION_ERROR",
            "message": "Invalid request parameters",
            "errors": exc.errors() if IS_DEV else None,  # Hide details in production
        },
    )


async def http_exception_handler(
    request: Request,
    exc: StarletteHTTPException
) -> JSONResponse:
    """Handle standard HTTP exceptions (404, 405, etc.).

    These are raised by Starlette for protocol-level errors.
    """
    logger.info(
        f"HTTP {exc.status_code} on {request.method} {request.url.path}: {exc.detail}",
    )

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error_code": f"HTTP_{exc.status_code}",
            "message": exc.detail,
        },
    )


async def unhandled_exception_handler(
    request: Request,
    exc: Exception
) -> JSONResponse:
    """Handle truly unexpected exceptions (bugs, third-party lib errors, etc.).

    This is the safety net for exceptions that escaped all other handlers.
    These should be rare and indicate bugs that need to be fixed.
    """
    # Log with full traceback
    logger.exception(
        f"UNHANDLED EXCEPTION: {exc.__class__.__name__} on {request.method} {request.url.path}",
        extra={
            "exception_type": exc.__class__.__name__,
            "exception_module": exc.__class__.__module__,
            "path": request.url.path,
            "method": request.method,
        },
    )

    # Always alert for unhandled exceptions (these are bugs)
    logger.critical(
        f"ALERT: Unhandled exception - {exc.__class__.__name__}: {str(exc)}",
        extra={"path": request.url.path, "method": request.method}
    )
    # TODO: Integrate with alerting system

    # Return generic error (never expose internal details)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "error_code": "INTERNAL_ERROR",
            "message": "An unexpected error occurred. Please contact support.",
            # Only expose exception type in dev (no message, to avoid leaking data)
            "debug_info": {
                "exception_type": exc.__class__.__name__,
                "message": str(exc),
            } if IS_DEV else None,
        },
    )


def register_exception_handlers(app) -> None:
    """Register all exception handlers with the FastAPI app.

    Call this from main.py after creating the app instance.

    Handlers are registered in order of specificity:
    1. QuantSysException subclasses (our business exceptions)
    2. FastAPI validation errors
    3. Starlette HTTP exceptions
    4. Catch-all for truly unexpected exceptions
    """
    # Register our business exception hierarchy
    app.add_exception_handler(QuantSysException, quantsys_exception_handler)

    # Register FastAPI/Starlette built-in exceptions
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)

    # Catch-all for unexpected exceptions (should be rare)
    app.add_exception_handler(Exception, unhandled_exception_handler)

    logger.info("Exception handlers registered successfully")
