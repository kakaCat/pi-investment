"""Order management commands for QuantSys CLI."""

from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _get_db_connection(db_path: str | None = None) -> sqlite3.Connection:
    """Get database connection for order management."""
    if db_path is None:
        project_root = Path(__file__).resolve().parents[3]
        db_path = str(project_root / ".pi-invest" / "stock-db" / "stocks.db")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    _ensure_tables(conn)
    return conn


def _ensure_tables(conn: sqlite3.Connection) -> None:
    """Ensure order management tables exist."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS orders (
            order_id TEXT PRIMARY KEY,
            account_id TEXT NOT NULL DEFAULT 'default',
            symbol TEXT NOT NULL,
            type TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            price REAL NOT NULL,
            submitted_by TEXT NOT NULL,
            reason TEXT,
            confidence REAL,
            agent_decision_id TEXT,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            approved_by TEXT,
            approved_at TEXT,
            executed_at TEXT,
            rejection_reason TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
        CREATE INDEX IF NOT EXISTS idx_orders_symbol ON orders(symbol);
        CREATE INDEX IF NOT EXISTS idx_orders_created_at ON orders(created_at);
        CREATE INDEX IF NOT EXISTS idx_orders_account ON orders(account_id);
    """)
    conn.commit()


def _check_approval_required(order_data: dict[str, Any], db_path: str | None = None) -> bool:
    """Check if order requires approval based on rules."""
    from .approval_rules import get_approval_rules

    rules = get_approval_rules(db_path=db_path)

    # If submitted by agent, check rules
    if order_data.get("submitted_by") == "agent":
        for rule in rules:
            if rule.get("type") == "agent_orders":
                # Check confidence threshold
                min_confidence = rule.get("min_confidence", 0.7)
                if order_data.get("confidence", 0) < min_confidence:
                    return True

                # Check order size
                max_quantity = rule.get("max_quantity")
                if max_quantity and order_data.get("quantity", 0) > max_quantity:
                    return True

                # Check order value
                max_value = rule.get("max_value")
                if max_value:
                    order_value = order_data.get("quantity", 0) * order_data.get("price", 0)
                    if order_value > max_value:
                        return True

        # Default: agent orders require approval
        return True

    # User orders don't require approval by default
    return False


def create_order(order_data: dict[str, Any], db_path: str | None = None) -> dict[str, Any]:
    """
    Create a new order (requires approval if from agent).

    Args:
        order_data: {
            "symbol": str,
            "type": "buy" | "sell",
            "quantity": int,
            "price": float,
            "submitted_by": "agent" | "user",
            "reason": str,
            "confidence": float,
            "agent_decision_id": str,  # if from agent
            "account_id": str  # optional
        }
        db_path: Optional database path

    Returns:
        {
            "order_id": str,
            "status": "pending" | "approved" | "executed",
            "created_at": str
        }
    """
    try:
        conn = _get_db_connection(db_path)
        order_id = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()

        # Determine if approval is required
        requires_approval = _check_approval_required(order_data, db_path)
        status = "pending" if requires_approval else "approved"

        conn.execute(
            """
            INSERT INTO orders
            (order_id, account_id, symbol, type, quantity, price, submitted_by,
             reason, confidence, agent_decision_id, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                order_id,
                order_data.get("account_id", "default"),
                order_data["symbol"],
                order_data["type"],
                order_data["quantity"],
                order_data["price"],
                order_data["submitted_by"],
                order_data.get("reason"),
                order_data.get("confidence"),
                order_data.get("agent_decision_id"),
                status,
                timestamp,
                timestamp,
            ),
        )
        conn.commit()
        conn.close()

        return {
            "order_id": order_id,
            "status": status,
            "created_at": timestamp,
            "requires_approval": requires_approval,
        }
    except Exception as exc:
        logger.error(f"Failed to create order: {exc}")
        return {"error": str(exc)}


def get_pending_orders(account_id: str = "default", db_path: str | None = None) -> list[dict[str, Any]]:
    """
    Get orders awaiting approval.

    Args:
        account_id: Account identifier
        db_path: Optional database path

    Returns:
        List of pending orders
    """
    try:
        conn = _get_db_connection(db_path)
        cursor = conn.execute(
            """
            SELECT * FROM orders
            WHERE account_id = ? AND status = 'pending'
            ORDER BY created_at DESC
            """,
            (account_id,),
        )
        rows = cursor.fetchall()
        conn.close()

        orders = []
        for row in rows:
            orders.append({
                "order_id": row["order_id"],
                "symbol": row["symbol"],
                "type": row["type"],
                "quantity": row["quantity"],
                "price": row["price"],
                "submitted_by": row["submitted_by"],
                "reason": row["reason"],
                "confidence": row["confidence"],
                "agent_decision_id": row["agent_decision_id"],
                "created_at": row["created_at"],
            })

        return orders
    except Exception as exc:
        logger.error(f"Failed to get pending orders: {exc}")
        return []


def approve_order(order_id: str, approved_by: str, db_path: str | None = None) -> dict[str, Any]:
    """
    Approve a pending order.

    Args:
        order_id: Order ID
        approved_by: User who approved the order
        db_path: Optional database path

    Returns:
        Updated order info
    """
    try:
        conn = _get_db_connection(db_path)
        timestamp = datetime.now().isoformat()

        # Check if order exists and is pending
        cursor = conn.execute(
            "SELECT * FROM orders WHERE order_id = ?",
            (order_id,),
        )
        row = cursor.fetchone()

        if not row:
            conn.close()
            return {"error": f"Order not found: {order_id}"}

        if row["status"] != "pending":
            conn.close()
            return {"error": f"Order is not pending: {row['status']}"}

        # Update order status
        conn.execute(
            """
            UPDATE orders
            SET status = 'approved', approved_by = ?, approved_at = ?, updated_at = ?
            WHERE order_id = ?
            """,
            (approved_by, timestamp, timestamp, order_id),
        )
        conn.commit()
        conn.close()

        return {
            "order_id": order_id,
            "status": "approved",
            "approved_by": approved_by,
            "approved_at": timestamp,
        }
    except Exception as exc:
        logger.error(f"Failed to approve order: {exc}")
        return {"error": str(exc)}


def reject_order(order_id: str, reason: str, db_path: str | None = None) -> dict[str, Any]:
    """
    Reject a pending order.

    Args:
        order_id: Order ID
        reason: Rejection reason
        db_path: Optional database path

    Returns:
        Updated order info
    """
    try:
        conn = _get_db_connection(db_path)
        timestamp = datetime.now().isoformat()

        # Check if order exists and is pending
        cursor = conn.execute(
            "SELECT * FROM orders WHERE order_id = ?",
            (order_id,),
        )
        row = cursor.fetchone()

        if not row:
            conn.close()
            return {"error": f"Order not found: {order_id}"}

        if row["status"] != "pending":
            conn.close()
            return {"error": f"Order is not pending: {row['status']}"}

        # Update order status
        conn.execute(
            """
            UPDATE orders
            SET status = 'rejected', rejection_reason = ?, updated_at = ?
            WHERE order_id = ?
            """,
            (reason, timestamp, order_id),
        )
        conn.commit()
        conn.close()

        return {
            "order_id": order_id,
            "status": "rejected",
            "rejection_reason": reason,
        }
    except Exception as exc:
        logger.error(f"Failed to reject order: {exc}")
        return {"error": str(exc)}


def execute_order(order_id: str, db_path: str | None = None) -> dict[str, Any]:
    """
    Execute an approved order.

    Args:
        order_id: Order ID
        db_path: Optional database path

    Returns:
        Execution result
    """
    try:
        conn = _get_db_connection(db_path)
        timestamp = datetime.now().isoformat()

        # Check if order exists and is approved
        cursor = conn.execute(
            "SELECT * FROM orders WHERE order_id = ?",
            (order_id,),
        )
        row = cursor.fetchone()

        if not row:
            conn.close()
            return {"error": f"Order not found: {order_id}"}

        if row["status"] != "approved":
            conn.close()
            return {"error": f"Order is not approved: {row['status']}"}

        # Update position
        from .position_management import update_position

        position_result = update_position(
            symbol=row["symbol"],
            updates={
                "action": row["type"],
                "quantity": row["quantity"],
                "price": row["price"],
                "reason": row["reason"],
            },
            account_id=row["account_id"],
            db_path=db_path,
        )

        if position_result.get("error"):
            conn.close()
            return {"error": f"Failed to update position: {position_result['error']}"}

        # Update order status
        conn.execute(
            """
            UPDATE orders
            SET status = 'executed', executed_at = ?, updated_at = ?
            WHERE order_id = ?
            """,
            (timestamp, timestamp, order_id),
        )
        conn.commit()
        conn.close()

        return {
            "order_id": order_id,
            "status": "executed",
            "executed_at": timestamp,
            "position": position_result,
        }
    except Exception as exc:
        logger.error(f"Failed to execute order: {exc}")
        return {"error": str(exc)}


def get_order_history(
    filters: dict[str, Any] | None = None,
    db_path: str | None = None,
) -> list[dict[str, Any]]:
    """
    Get order history with filters.

    Args:
        filters: {
            "account_id": str,
            "symbol": str,
            "status": str,
            "start_date": str,
            "end_date": str,
            "limit": int
        }
        db_path: Optional database path

    Returns:
        List of orders
    """
    try:
        conn = _get_db_connection(db_path)
        filters = filters or {}

        query = "SELECT * FROM orders WHERE 1=1"
        params: list[Any] = []

        if filters.get("account_id"):
            query += " AND account_id = ?"
            params.append(filters["account_id"])

        if filters.get("symbol"):
            query += " AND symbol = ?"
            params.append(filters["symbol"])

        if filters.get("status"):
            query += " AND status = ?"
            params.append(filters["status"])

        if filters.get("start_date"):
            query += " AND created_at >= ?"
            params.append(filters["start_date"])

        if filters.get("end_date"):
            query += " AND created_at <= ?"
            params.append(filters["end_date"])

        query += " ORDER BY created_at DESC"

        if filters.get("limit"):
            query += " LIMIT ?"
            params.append(filters["limit"])

        cursor = conn.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        orders = []
        for row in rows:
            orders.append({
                "order_id": row["order_id"],
                "symbol": row["symbol"],
                "type": row["type"],
                "quantity": row["quantity"],
                "price": row["price"],
                "submitted_by": row["submitted_by"],
                "reason": row["reason"],
                "confidence": row["confidence"],
                "status": row["status"],
                "created_at": row["created_at"],
                "approved_by": row["approved_by"],
                "approved_at": row["approved_at"],
                "executed_at": row["executed_at"],
                "rejection_reason": row["rejection_reason"],
            })

        return orders
    except Exception as exc:
        logger.error(f"Failed to get order history: {exc}")
        return []


def register_daemon_handlers() -> None:
    """Register order management handlers for daemon mode."""
    from .daemon import register_daemon_method

    register_daemon_method("order.create", lambda params: create_order(
        order_data=params,
        db_path=params.get("db_path"),
    ))

    register_daemon_method("order.get_pending", lambda params: get_pending_orders(
        account_id=params.get("account_id", "default"),
        db_path=params.get("db_path"),
    ))

    register_daemon_method("order.approve", lambda params: approve_order(
        order_id=params["order_id"],
        approved_by=params["approved_by"],
        db_path=params.get("db_path"),
    ))

    register_daemon_method("order.reject", lambda params: reject_order(
        order_id=params["order_id"],
        reason=params["reason"],
        db_path=params.get("db_path"),
    ))

    register_daemon_method("order.execute", lambda params: execute_order(
        order_id=params["order_id"],
        db_path=params.get("db_path"),
    ))

    register_daemon_method("order.get_history", lambda params: get_order_history(
        filters=params.get("filters"),
        db_path=params.get("db_path"),
    ))
