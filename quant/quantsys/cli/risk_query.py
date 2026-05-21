"""Risk management helpers exposed through the QuantSys CLI."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def check_trade_risk(
    symbol: str,
    action: str,
    price: float,
    shares: int,
) -> dict[str, Any]:
    """Run pre-trade risk checks through the portfolio risk bridge."""
    bridge = _build_bridge()
    return bridge.check_trade_risk(symbol, action, price, shares)


def calculate_position_size(
    symbol: str,
    price: float,
    signal_strength: float = 1.0,
) -> dict[str, Any]:
    """Calculate Kelly-style position size through the portfolio risk bridge."""
    bridge = _build_bridge()
    return bridge.calculate_position_size(symbol, price, signal_strength)


def calculate_stop_loss(
    symbol: str,
    entry_price: float,
    current_price: float | None = None,
    highest_price: float | None = None,
) -> dict[str, Any]:
    """Calculate fixed or trailing stop-loss through the portfolio risk bridge."""
    bridge = _build_bridge()
    return bridge.calculate_stop_loss(symbol, entry_price, current_price, highest_price)


def _build_bridge():
    from quantsys.risk.bridge import RiskBridge

    project_root = Path(__file__).resolve().parents[3]
    portfolio_db = project_root / ".pi-invest" / "portfolio.db"
    quant_db = project_root / ".pi-invest" / "stock-db" / "stocks.db"
    return RiskBridge(str(portfolio_db), str(quant_db))
