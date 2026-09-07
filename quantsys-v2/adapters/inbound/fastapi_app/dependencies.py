"""Improved ORM Session management using FastAPI dependency injection.

This replaces the complex middleware + reflection-based cleanup with
FastAPI's native Depends() mechanism, which is:
- More maintainable (no reflection hacks)
- Framework-native (survives FastAPI upgrades)
- Comprehensive (covers sync/async routes, WebSocket, background tasks)

Usage in routes:
    from adapters.inbound.fastapi_app.dependencies import get_orm_session

    @app.get("/stocks/{symbol}")
    async def get_stock(symbol: str, session: Session = Depends(get_orm_session)):
        stock = session.query(Stock).filter(Stock.symbol == symbol).first()
        return stock

The session is automatically:
- Created when the request starts
- Committed if no exceptions
- Rolled back on exceptions
- Closed when the request ends
"""
from typing import Generator
from sqlalchemy.orm import Session
from contextlib import contextmanager
import logging

logger = logging.getLogger(__name__)


def get_orm_session() -> Generator[Session, None, None]:
    """FastAPI dependency that provides a database session.

    Features:
    - Auto-commits on success
    - Auto-rollbacks on exception
    - Auto-closes after request
    - Works with sync and async routes
    - Thread-safe (each request gets its own session)

    Usage:
        @app.get("/items")
        def list_items(session: Session = Depends(get_orm_session)):
            return session.query(Item).all()
    """
    from infrastructure.persistence.orm import get_session, close_session

    session = get_session()
    try:
        yield session
        # If we reach here without exception, commit the transaction
        session.commit()
    except Exception as e:
        # On error, rollback to avoid leaving transaction open
        logger.warning(f"Rolling back session due to exception: {e}")
        session.rollback()
        raise
    finally:
        # Always close the session to return connection to pool
        close_session()


@contextmanager
def orm_session_context():
    """Context manager for non-route code (scripts, background tasks, tests).

    Usage:
        from adapters.inbound.fastapi_app.dependencies import orm_session_context

        with orm_session_context() as session:
            stock = session.query(Stock).first()
            # session auto-commits on exit (if no exception)
    """
    from infrastructure.persistence.orm import get_session, close_session

    session = get_session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        close_session()


# ============================================================================
# Legacy Support: Gradual Migration
# ============================================================================

def get_orm_session_optional() -> Generator[Session, None, None]:
    """Optional dependency for gradual migration.

    Use this when route might be called without the dependency
    (e.g., during migration period when some callers haven't updated yet).

    Usage:
        @app.get("/items")
        def list_items(session: Session = Depends(get_orm_session_optional)):
            if session is None:
                # Fallback to old scoped_session approach
                from infrastructure.persistence.orm import get_session
                session = get_session()
            return session.query(Item).all()
    """
    try:
        yield from get_orm_session()
    except Exception as e:
        logger.error(f"Failed to provide ORM session: {e}")
        yield None


# ============================================================================
# Background Task Support
# ============================================================================

def get_background_orm_session():
    """Get a session for background tasks (not request-scoped).

    Background tasks run after the response is sent, so they can't use
    request-scoped dependencies. Use this for BackgroundTasks:

    Usage:
        from fastapi import BackgroundTasks

        @app.post("/process")
        async def process_data(background_tasks: BackgroundTasks):
            background_tasks.add_task(process_in_background)
            return {"status": "processing"}

        def process_in_background():
            with orm_session_context() as session:
                # Do work with session
                session.add(ProcessedItem())
    """
    # Background tasks should use orm_session_context() directly
    # This function is here for documentation
    raise NotImplementedError(
        "Background tasks should use orm_session_context() directly. "
        "See adapters/inbound/fastapi_app/dependencies.py for example."
    )


# ============================================================================
# WebSocket Support
# ============================================================================

async def websocket_orm_session_manager(websocket):
    """Manage ORM sessions for WebSocket connections.

    WebSockets are long-lived, so we can't use request-scoped sessions.
    Instead, create a new session for each message/operation:

    Usage:
        @app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            await websocket.accept()
            while True:
                data = await websocket.receive_text()

                # Create session per message
                with orm_session_context() as session:
                    result = process_message(session, data)
                    await websocket.send_json(result)
    """
    # WebSocket should use orm_session_context() for each message
    # This function is here for documentation
    raise NotImplementedError(
        "WebSocket handlers should use orm_session_context() per message. "
        "See adapters/inbound/fastapi_app/dependencies.py for example."
    )
