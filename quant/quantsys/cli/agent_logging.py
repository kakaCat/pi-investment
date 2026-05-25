"""Agent operation logging commands for QuantSys CLI."""

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
    """Get database connection for agent logging."""
    if db_path is None:
        project_root = Path(__file__).resolve().parents[3]
        db_path = str(project_root / ".pi-invest" / "stock-db" / "stocks.db")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    _ensure_tables(conn)
    return conn


def _ensure_tables(conn: sqlite3.Connection) -> None:
    """Ensure agent logging tables exist."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS agent_logs (
            log_id TEXT PRIMARY KEY,
            timestamp TEXT NOT NULL,
            action_type TEXT NOT NULL,
            symbol TEXT NOT NULL,
            details TEXT NOT NULL,
            result TEXT NOT NULL,
            status TEXT NOT NULL,
            data_snapshot_id TEXT,
            created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_agent_logs_timestamp ON agent_logs(timestamp);
        CREATE INDEX IF NOT EXISTS idx_agent_logs_action_type ON agent_logs(action_type);
        CREATE INDEX IF NOT EXISTS idx_agent_logs_symbol ON agent_logs(symbol);
        CREATE INDEX IF NOT EXISTS idx_agent_logs_status ON agent_logs(status);
    """)
    conn.commit()


def log_agent_action(
    action_type: str,
    symbol: str,
    details: dict[str, Any],
    result: dict[str, Any],
    db_path: str | None = None,
) -> dict[str, Any]:
    """
    Record an agent operation.

    Args:
        action_type: Type of action (analysis, signal_generation, order_creation)
        symbol: Stock symbol
        details: Action details (parameters, reasoning)
        result: Action result
        db_path: Optional database path

    Returns:
        {
            "log_id": "uuid",
            "timestamp": "2026-05-23T10:30:00",
            "action_type": "analysis",
            "symbol": "600519",
            "status": "success"
        }
    """
    try:
        conn = _get_db_connection(db_path)
        log_id = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()
        status = "success" if not result.get("error") else "error"

        # Save data snapshot if needed
        data_snapshot_id = None
        if details.get("save_snapshot"):
            from .data_snapshots import save_snapshot
            data_snapshot_id = save_snapshot({
                "symbol": symbol,
                "data_type": "agent_action",
                "data": {"details": details, "result": result},
                "timestamp": timestamp,
            }, db_path=db_path)

        conn.execute(
            """
            INSERT INTO agent_logs
            (log_id, timestamp, action_type, symbol, details, result, status, data_snapshot_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                log_id,
                timestamp,
                action_type,
                symbol,
                json.dumps(details),
                json.dumps(result),
                status,
                data_snapshot_id,
                timestamp,
            ),
        )
        conn.commit()
        conn.close()

        return {
            "log_id": log_id,
            "timestamp": timestamp,
            "action_type": action_type,
            "symbol": symbol,
            "status": status,
        }
    except Exception as exc:
        logger.error(f"Failed to log agent action: {exc}")
        return {"error": str(exc)}


def get_agent_logs(
    filters: dict[str, Any] | None = None,
    limit: int = 100,
    db_path: str | None = None,
) -> list[dict[str, Any]]:
    """
    Query agent operation logs.

    Args:
        filters: {
            "action_type": str,
            "symbol": str,
            "start_date": str,
            "end_date": str,
            "status": str
        }
        limit: Max number of logs to return
        db_path: Optional database path

    Returns:
        List of log entries
    """
    try:
        conn = _get_db_connection(db_path)
        filters = filters or {}

        query = "SELECT * FROM agent_logs WHERE 1=1"
        params: list[Any] = []

        if filters.get("action_type"):
            query += " AND action_type = ?"
            params.append(filters["action_type"])

        if filters.get("symbol"):
            query += " AND symbol = ?"
            params.append(filters["symbol"])

        if filters.get("start_date"):
            query += " AND timestamp >= ?"
            params.append(filters["start_date"])

        if filters.get("end_date"):
            query += " AND timestamp <= ?"
            params.append(filters["end_date"])

        if filters.get("status"):
            query += " AND status = ?"
            params.append(filters["status"])

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        cursor = conn.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        logs = []
        for row in rows:
            logs.append({
                "log_id": row["log_id"],
                "timestamp": row["timestamp"],
                "action_type": row["action_type"],
                "symbol": row["symbol"],
                "status": row["status"],
                "data_snapshot_id": row["data_snapshot_id"],
            })

        return logs
    except Exception as exc:
        logger.error(f"Failed to get agent logs: {exc}")
        return []


def get_agent_log_detail(log_id: str, db_path: str | None = None) -> dict[str, Any]:
    """
    Get detailed information for a specific log entry.

    Args:
        log_id: Log entry ID
        db_path: Optional database path

    Returns:
        {
            "log_id": str,
            "timestamp": str,
            "action_type": str,
            "symbol": str,
            "details": dict,  # Full parameters and reasoning
            "result": dict,   # Full result data
            "data_snapshot_id": str  # Reference to saved data
        }
    """
    try:
        conn = _get_db_connection(db_path)
        cursor = conn.execute(
            "SELECT * FROM agent_logs WHERE log_id = ?",
            (log_id,),
        )
        row = cursor.fetchone()
        conn.close()

        if not row:
            return {"error": f"Log entry not found: {log_id}"}

        return {
            "log_id": row["log_id"],
            "timestamp": row["timestamp"],
            "action_type": row["action_type"],
            "symbol": row["symbol"],
            "details": json.loads(row["details"]),
            "result": json.loads(row["result"]),
            "status": row["status"],
            "data_snapshot_id": row["data_snapshot_id"],
        }
    except Exception as exc:
        logger.error(f"Failed to get agent log detail: {exc}")
        return {"error": str(exc)}


def register_daemon_handlers() -> None:
    """Register agent logging handlers for daemon mode."""
    from .daemon import register_daemon_method

    register_daemon_method("agent.log_action", lambda params: log_agent_action(
        action_type=params["action_type"],
        symbol=params["symbol"],
        details=params["details"],
        result=params["result"],
        db_path=params.get("db_path"),
    ))

    register_daemon_method("agent.get_logs", lambda params: get_agent_logs(
        filters=params.get("filters"),
        limit=params.get("limit", 100),
        db_path=params.get("db_path"),
    ))

    register_daemon_method("agent.get_log_detail", lambda params: get_agent_log_detail(
        log_id=params["log_id"],
        db_path=params.get("db_path"),
    ))
