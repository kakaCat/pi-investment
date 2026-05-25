"""Position management commands for QuantSys CLI."""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _get_db_connection(db_path: str | None = None) -> sqlite3.Connection:
    """Get database connection for position management."""
    if db_path is None:
        project_root = Path(__file__).resolve().parents[3]
        db_path = str(project_root / ".pi-invest" / "stock-db" / "stocks.db")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    _ensure_tables(conn)
    return conn


def _ensure_tables(conn: sqlite3.Connection) -> None:
    """Ensure position management tables exist."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS positions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id TEXT NOT NULL DEFAULT 'default',
            symbol TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            cost_basis REAL NOT NULL,
            stop_loss REAL,
            take_profit REAL,
            entry_date TEXT NOT NULL,
            entry_reason TEXT,
            updated_at TEXT NOT NULL,
            UNIQUE(account_id, symbol)
        );

        CREATE TABLE IF NOT EXISTS position_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id TEXT NOT NULL,
            symbol TEXT NOT NULL,
            action TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            price REAL NOT NULL,
            timestamp TEXT NOT NULL,
            reason TEXT,
            metadata TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_positions_account ON positions(account_id);
        CREATE INDEX IF NOT EXISTS idx_positions_symbol ON positions(symbol);
        CREATE INDEX IF NOT EXISTS idx_position_history_symbol ON position_history(symbol);
        CREATE INDEX IF NOT EXISTS idx_position_history_timestamp ON position_history(timestamp);
    """)
    conn.commit()


def _get_current_price(symbol: str) -> float | None:
    """Get current price for a symbol."""
    try:
        from .stock_query import get_stock_quote
        quote = get_stock_quote(symbol)
        return quote.get("current_price") or quote.get("price")
    except Exception as exc:
        logger.warning(f"Failed to get current price for {symbol}: {exc}")
        return None


def get_positions(account_id: str = "default", db_path: str | None = None) -> list[dict[str, Any]]:
    """
    Get current positions.

    Args:
        account_id: Account identifier
        db_path: Optional database path

    Returns:
        [
            {
                "symbol": "600519",
                "quantity": 100,
                "cost_basis": 1820.0,
                "current_price": 1850.0,
                "market_value": 185000.0,
                "unrealized_pnl": 3000.0,
                "unrealized_pnl_pct": 1.65,
                "stop_loss": 1750.0,
                "take_profit": 2100.0,
                "entry_date": "2026-05-10",
                "entry_reason": "RSI oversold + MACD golden cross"
            }
        ]
    """
    try:
        conn = _get_db_connection(db_path)
        cursor = conn.execute(
            "SELECT * FROM positions WHERE account_id = ? ORDER BY symbol",
            (account_id,),
        )
        rows = cursor.fetchall()
        conn.close()

        positions = []
        for row in rows:
            current_price = _get_current_price(row["symbol"])
            cost_basis = row["cost_basis"]
            quantity = row["quantity"]

            if current_price:
                market_value = current_price * quantity
                unrealized_pnl = market_value - (cost_basis * quantity)
                unrealized_pnl_pct = (unrealized_pnl / (cost_basis * quantity)) * 100
            else:
                market_value = None
                unrealized_pnl = None
                unrealized_pnl_pct = None

            positions.append({
                "symbol": row["symbol"],
                "quantity": quantity,
                "cost_basis": cost_basis,
                "current_price": current_price,
                "market_value": market_value,
                "unrealized_pnl": unrealized_pnl,
                "unrealized_pnl_pct": unrealized_pnl_pct,
                "stop_loss": row["stop_loss"],
                "take_profit": row["take_profit"],
                "entry_date": row["entry_date"],
                "entry_reason": row["entry_reason"],
            })

        return positions
    except Exception as exc:
        logger.error(f"Failed to get positions: {exc}")
        return []


def update_position(
    symbol: str,
    updates: dict[str, Any],
    account_id: str = "default",
    db_path: str | None = None,
) -> dict[str, Any]:
    """
    Update position (buy, sell, adjust stop-loss/take-profit).

    Args:
        symbol: Stock symbol
        updates: {
            "action": "buy" | "sell" | "adjust",
            "quantity": int,  # for buy/sell
            "price": float,  # for buy/sell
            "stop_loss": float,  # for adjust
            "take_profit": float,  # for adjust
            "reason": str  # optional reason
        }
        account_id: Account identifier
        db_path: Optional database path

    Returns:
        Updated position info
    """
    try:
        conn = _get_db_connection(db_path)
        action = updates.get("action")
        timestamp = datetime.now().isoformat()

        if action == "buy":
            quantity = updates["quantity"]
            price = updates["price"]
            reason = updates.get("reason", "")

            # Check if position exists
            cursor = conn.execute(
                "SELECT * FROM positions WHERE account_id = ? AND symbol = ?",
                (account_id, symbol),
            )
            existing = cursor.fetchone()

            if existing:
                # Update existing position (average cost)
                old_quantity = existing["quantity"]
                old_cost = existing["cost_basis"]
                new_quantity = old_quantity + quantity
                new_cost = ((old_quantity * old_cost) + (quantity * price)) / new_quantity

                conn.execute(
                    """
                    UPDATE positions
                    SET quantity = ?, cost_basis = ?, updated_at = ?
                    WHERE account_id = ? AND symbol = ?
                    """,
                    (new_quantity, new_cost, timestamp, account_id, symbol),
                )
            else:
                # Create new position
                conn.execute(
                    """
                    INSERT INTO positions
                    (account_id, symbol, quantity, cost_basis, entry_date, entry_reason, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (account_id, symbol, quantity, price, timestamp[:10], reason, timestamp),
                )

            # Record history
            conn.execute(
                """
                INSERT INTO position_history
                (account_id, symbol, action, quantity, price, timestamp, reason)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (account_id, symbol, "buy", quantity, price, timestamp, reason),
            )

        elif action == "sell":
            quantity = updates["quantity"]
            price = updates["price"]
            reason = updates.get("reason", "")

            # Get existing position
            cursor = conn.execute(
                "SELECT * FROM positions WHERE account_id = ? AND symbol = ?",
                (account_id, symbol),
            )
            existing = cursor.fetchone()

            if not existing:
                conn.close()
                return {"error": f"No position found for {symbol}"}

            old_quantity = existing["quantity"]
            if quantity > old_quantity:
                conn.close()
                return {"error": f"Cannot sell {quantity} shares, only {old_quantity} available"}

            new_quantity = old_quantity - quantity

            if new_quantity == 0:
                # Close position
                conn.execute(
                    "DELETE FROM positions WHERE account_id = ? AND symbol = ?",
                    (account_id, symbol),
                )
            else:
                # Reduce position
                conn.execute(
                    """
                    UPDATE positions
                    SET quantity = ?, updated_at = ?
                    WHERE account_id = ? AND symbol = ?
                    """,
                    (new_quantity, timestamp, account_id, symbol),
                )

            # Record history
            conn.execute(
                """
                INSERT INTO position_history
                (account_id, symbol, action, quantity, price, timestamp, reason)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (account_id, symbol, "sell", quantity, price, timestamp, reason),
            )

        elif action == "adjust":
            stop_loss = updates.get("stop_loss")
            take_profit = updates.get("take_profit")
            reason = updates.get("reason", "")

            # Check if position exists
            cursor = conn.execute(
                "SELECT * FROM positions WHERE account_id = ? AND symbol = ?",
                (account_id, symbol),
            )
            existing = cursor.fetchone()

            if not existing:
                conn.close()
                return {"error": f"No position found for {symbol}"}

            # Update stop-loss and take-profit
            if stop_loss is not None:
                conn.execute(
                    """
                    UPDATE positions
                    SET stop_loss = ?, updated_at = ?
                    WHERE account_id = ? AND symbol = ?
                    """,
                    (stop_loss, timestamp, account_id, symbol),
                )

            if take_profit is not None:
                conn.execute(
                    """
                    UPDATE positions
                    SET take_profit = ?, updated_at = ?
                    WHERE account_id = ? AND symbol = ?
                    """,
                    (take_profit, timestamp, account_id, symbol),
                )

            # Record history
            metadata = json.dumps({"stop_loss": stop_loss, "take_profit": take_profit})
            conn.execute(
                """
                INSERT INTO position_history
                (account_id, symbol, action, quantity, price, timestamp, reason, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (account_id, symbol, "adjust", 0, 0, timestamp, reason, metadata),
            )

        else:
            conn.close()
            return {"error": f"Invalid action: {action}"}

        conn.commit()

        # Get updated position
        cursor = conn.execute(
            "SELECT * FROM positions WHERE account_id = ? AND symbol = ?",
            (account_id, symbol),
        )
        row = cursor.fetchone()
        conn.close()

        if not row:
            return {"message": f"Position closed for {symbol}"}

        current_price = _get_current_price(symbol)
        return {
            "symbol": row["symbol"],
            "quantity": row["quantity"],
            "cost_basis": row["cost_basis"],
            "current_price": current_price,
            "stop_loss": row["stop_loss"],
            "take_profit": row["take_profit"],
            "entry_date": row["entry_date"],
            "entry_reason": row["entry_reason"],
        }

    except Exception as exc:
        logger.error(f"Failed to update position: {exc}")
        return {"error": str(exc)}


def get_position_history(
    symbol: str,
    account_id: str = "default",
    db_path: str | None = None,
) -> list[dict[str, Any]]:
    """
    Get position change history for a symbol.

    Args:
        symbol: Stock symbol
        account_id: Account identifier
        db_path: Optional database path

    Returns:
        List of position changes (entries, exits, adjustments)
    """
    try:
        conn = _get_db_connection(db_path)
        cursor = conn.execute(
            """
            SELECT * FROM position_history
            WHERE account_id = ? AND symbol = ?
            ORDER BY timestamp DESC
            """,
            (account_id, symbol),
        )
        rows = cursor.fetchall()
        conn.close()

        history = []
        for row in rows:
            entry = {
                "action": row["action"],
                "quantity": row["quantity"],
                "price": row["price"],
                "timestamp": row["timestamp"],
                "reason": row["reason"],
            }
            if row["metadata"]:
                entry["metadata"] = json.loads(row["metadata"])
            history.append(entry)

        return history
    except Exception as exc:
        logger.error(f"Failed to get position history: {exc}")
        return []


def register_daemon_handlers() -> None:
    """Register position management handlers for daemon mode."""
    from .daemon import register_daemon_method

    register_daemon_method("position.get_positions", lambda params: get_positions(
        account_id=params.get("account_id", "default"),
        db_path=params.get("db_path"),
    ))

    register_daemon_method("position.update", lambda params: update_position(
        symbol=params["symbol"],
        updates=params["updates"],
        account_id=params.get("account_id", "default"),
        db_path=params.get("db_path"),
    ))

    register_daemon_method("position.get_history", lambda params: get_position_history(
        symbol=params["symbol"],
        account_id=params.get("account_id", "default"),
        db_path=params.get("db_path"),
    ))
