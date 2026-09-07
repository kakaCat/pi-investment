"""Example: Before and After migration for a stock routes module.

This demonstrates the concrete migration from old scoped_session approach
to new FastAPI dependency injection for ORM session management.
"""

# ============================================================================
# BEFORE: Old approach using scoped_session (implicit session management)
# ============================================================================

"""
File: adapters/inbound/fastapi_app/routes/stocks_async_OLD.py
"""

from fastapi import APIRouter, HTTPException
from typing import List, Optional
import structlog

router_OLD = APIRouter(prefix="/api/stocks", tags=["Stocks"])
logger = structlog.get_logger(__name__)


@router_OLD.get("/")
async def list_stocks_OLD(
    limit: int = 100,
    offset: int = 0,
    market: Optional[str] = None
):
    """List stocks with optional filtering.

    PROBLEM: Session is implicitly created by scoped_session.
    Cleanup depends on middleware (release_orm_session) or
    reflection wrapper (install_sync_session_cleanup).
    """
    from infrastructure.persistence.orm import get_session
    from domain.models.stock import Stock

    session = get_session()  # Gets thread-local session

    query = session.query(Stock)
    if market:
        query = query.filter(Stock.market == market)

    stocks = query.offset(offset).limit(limit).all()

    # Session is NOT explicitly closed here
    # Relies on middleware to call close_session()
    # If middleware fails, connection leaks!

    return [
        {
            "symbol": s.symbol,
            "name": s.name,
            "market": s.market
        }
        for s in stocks
    ]


@router_OLD.get("/{symbol}")
async def get_stock_OLD(symbol: str):
    """Get stock by symbol.

    PROBLEM: No explicit transaction management.
    If an exception occurs, transaction might not rollback.
    """
    from infrastructure.persistence.orm import get_session
    from domain.models.stock import Stock

    session = get_session()

    stock = session.query(Stock).filter(Stock.symbol == symbol).first()

    if not stock:
        raise HTTPException(status_code=404, detail=f"Stock {symbol} not found")

    return {
        "symbol": stock.symbol,
        "name": stock.name,
        "market": stock.market,
        "listed_date": stock.listed_date
    }


@router_OLD.post("/")
async def create_stock_OLD(
    symbol: str,
    name: str,
    market: str
):
    """Create a new stock.

    PROBLEM: Manual commit required. If commit fails or is forgotten,
    changes are not persisted. Session cleanup is implicit.
    """
    from infrastructure.persistence.orm import get_session
    from domain.models.stock import Stock

    session = get_session()

    # Check if exists
    existing = session.query(Stock).filter(Stock.symbol == symbol).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"Stock {symbol} already exists")

    # Create new stock
    stock = Stock(symbol=symbol, name=name, market=market)
    session.add(stock)
    session.commit()  # Manual commit - easy to forget!

    return {"symbol": stock.symbol, "message": "Stock created"}


@router_OLD.delete("/{symbol}")
async def delete_stock_OLD(symbol: str):
    """Delete a stock.

    PROBLEM: If exception occurs between query and commit,
    transaction is left open. No explicit rollback.
    """
    from infrastructure.persistence.orm import get_session
    from domain.models.stock import Stock

    session = get_session()

    stock = session.query(Stock).filter(Stock.symbol == symbol).first()
    if not stock:
        raise HTTPException(status_code=404, detail=f"Stock {symbol} not found")

    session.delete(stock)
    session.commit()

    return {"message": f"Stock {symbol} deleted"}


# ============================================================================
# AFTER: New approach using FastAPI dependency injection
# ============================================================================

"""
File: adapters/inbound/fastapi_app/routes/stocks_async_NEW.py
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
import structlog

from adapters.inbound.fastapi_app.dependencies import get_orm_session
from domain.exceptions import StockNotFoundException, ConflictError

router_NEW = APIRouter(prefix="/api/stocks", tags=["Stocks"])
logger = structlog.get_logger(__name__)


@router_NEW.get("/")
async def list_stocks_NEW(
    limit: int = 100,
    offset: int = 0,
    market: Optional[str] = None,
    session: Session = Depends(get_orm_session)  # ← Explicit dependency
):
    """List stocks with optional filtering.

    IMPROVEMENT:
    - Session is explicitly injected as dependency
    - Auto-commits on success
    - Auto-closes after request
    - No middleware dependency
    """
    from domain.models.stock import Stock

    query = session.query(Stock)
    if market:
        query = query.filter(Stock.market == market)

    stocks = query.offset(offset).limit(limit).all()

    # No manual cleanup needed - dependency handles it

    return [
        {
            "symbol": s.symbol,
            "name": s.name,
            "market": s.market
        }
        for s in stocks
    ]


@router_NEW.get("/{symbol}")
async def get_stock_NEW(
    symbol: str,
    session: Session = Depends(get_orm_session)  # ← Explicit dependency
):
    """Get stock by symbol.

    IMPROVEMENT:
    - Uses structured exceptions (StockNotFoundException)
    - Session auto-rollbacks on exception
    - Transaction management is automatic
    """
    from domain.models.stock import Stock

    stock = session.query(Stock).filter(Stock.symbol == symbol).first()

    if not stock:
        raise StockNotFoundException(symbol)  # Returns HTTP 404 automatically

    return {
        "symbol": stock.symbol,
        "name": stock.name,
        "market": stock.market,
        "listed_date": stock.listed_date
    }


@router_NEW.post("/")
async def create_stock_NEW(
    symbol: str,
    name: str,
    market: str,
    session: Session = Depends(get_orm_session)  # ← Explicit dependency
):
    """Create a new stock.

    IMPROVEMENT:
    - No manual commit needed (auto-commits on success)
    - Uses structured exceptions (ConflictError)
    - Auto-rollbacks if exception occurs
    """
    from domain.models.stock import Stock

    # Check if exists
    existing = session.query(Stock).filter(Stock.symbol == symbol).first()
    if existing:
        raise ConflictError(f"Stock {symbol} already exists")  # HTTP 409

    # Create new stock
    stock = Stock(symbol=symbol, name=name, market=market)
    session.add(stock)

    # No manual commit - dependency auto-commits on success!

    return {"symbol": stock.symbol, "message": "Stock created"}


@router_NEW.delete("/{symbol}")
async def delete_stock_NEW(
    symbol: str,
    session: Session = Depends(get_orm_session)  # ← Explicit dependency
):
    """Delete a stock.

    IMPROVEMENT:
    - Automatic transaction management
    - Auto-rollback if exception between query and delete
    - Structured exceptions
    """
    from domain.models.stock import Stock

    stock = session.query(Stock).filter(Stock.symbol == symbol).first()
    if not stock:
        raise StockNotFoundException(symbol)  # HTTP 404

    session.delete(stock)

    # No manual commit - auto-commits on success!

    return {"message": f"Stock {symbol} deleted"}


# ============================================================================
# MIGRATION WITH SERVICE LAYER
# ============================================================================

"""
Example: Route that uses a Service class
"""

# BEFORE: Service gets session from scoped_session

class StockService_OLD:
    def __init__(self):
        from infrastructure.persistence.orm import get_session
        self.session = get_session()  # Implicit session

    def get_stock_with_stats(self, symbol: str):
        from domain.models.stock import Stock
        stock = self.session.query(Stock).filter(Stock.symbol == symbol).first()
        if not stock:
            return None
        # ... compute stats ...
        return {"stock": stock, "stats": {}}


@router_OLD.get("/{symbol}/stats")
async def get_stock_stats_OLD(symbol: str):
    service = StockService_OLD()
    result = service.get_stock_with_stats(symbol)
    if not result:
        raise HTTPException(status_code=404, detail="Stock not found")
    return result


# AFTER: Service receives session via constructor

class StockService_NEW:
    def __init__(self, session: Session):
        self.session = session  # Explicit session injection

    def get_stock_with_stats(self, symbol: str):
        from domain.models.stock import Stock
        from domain.exceptions import StockNotFoundException

        stock = self.session.query(Stock).filter(Stock.symbol == symbol).first()
        if not stock:
            raise StockNotFoundException(symbol)
        # ... compute stats ...
        return {"stock": stock, "stats": {}}


@router_NEW.get("/{symbol}/stats")
async def get_stock_stats_NEW(
    symbol: str,
    session: Session = Depends(get_orm_session)
):
    service = StockService_NEW(session)  # Pass session explicitly
    return service.get_stock_with_stats(symbol)


# ============================================================================
# COMPARISON SUMMARY
# ============================================================================

"""
OLD APPROACH (scoped_session + middleware):
❌ Implicit session management (hard to debug)
❌ Manual commit required (easy to forget)
❌ No automatic rollback on exceptions
❌ Depends on middleware (complex, fragile)
❌ Doesn't cover WebSocket/BackgroundTasks
❌ Hard to test (global scoped_session state)

NEW APPROACH (dependency injection):
✅ Explicit session management (clear lifecycle)
✅ Auto-commits on success
✅ Auto-rollbacks on exceptions
✅ Framework-native (survives FastAPI upgrades)
✅ Covers all scenarios (routes, WebSocket, background tasks)
✅ Easy to test (can mock dependency)
✅ Better error handling (structured exceptions)

MIGRATION EFFORT:
- Simple route: 2-5 minutes (add `session: Session = Depends(get_orm_session)`)
- Route with service: 5-10 minutes (update service constructor)
- Route with repository: 5-10 minutes (update repository constructor)
"""
