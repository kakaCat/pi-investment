"""计划推进端口（t8 · REQ-261021222905-6dff）：成交事实 → 计划状态推进。

被 FillSyncService 注入（组合根装配）；只对带 plan_id 的成交生效。
持仓剩余量从 simulation_positions 读真值；读失败按「维持现状」处理（不臆造清仓）。
累计卖出量从 simulation_trades 读真值；读失败按 degraded 处理（不拿单笔下比例冒充累计）。
"""

from typing import Any, Dict, Optional

import structlog
from sqlalchemy import text

from qs_plan.application.plan_service import PlanError, PlanService

logger = structlog.get_logger(__name__)


def _remaining_qty(account: str, symbol: str) -> Optional[int]:
    try:
        from qs_kernel.infrastructure.persistence.database.engine import get_engine

        bare = str(symbol or "").split(".")[0]
        with get_engine().connect() as conn:
            row = conn.execute(
                text(
                    "SELECT coalesce(sum(shares_total),0) FROM quant.simulation_positions "
                    "WHERE split_part(symbol,'.',1) = :sym "
                    "AND (NULLIF(btrim(account_name),'') IS NULL OR btrim(account_name)=btrim(:acct))"
                ),
                {"sym": bare, "acct": account or ""},
            ).scalar()
        return int(row or 0)
    except Exception as e:  # noqa: BLE001
        logger.warning("计划推进读持仓失败（维持现状）", symbol=symbol, error=str(e))
        return None


def _sold_qty(plan_id: int, account: str, symbol: str) -> Optional[int]:
    """该计划、标的截至当前的累计 SELL 股数（成交已落库口径）。"""
    try:
        from qs_kernel.infrastructure.persistence.database.engine import get_engine

        bare = str(symbol or "").split(".")[0]
        with get_engine().connect() as conn:
            row = conn.execute(
                text(
                    "SELECT coalesce(sum(shares),0) FROM quant.simulation_trades "
                    "WHERE plan_id = :pid AND lower(action) = 'sell' "
                    "AND split_part(symbol,'.',1) = :sym "
                    "AND (NULLIF(btrim(account_name),'') IS NULL OR btrim(account_name)=btrim(:acct))"
                ),
                {"pid": int(plan_id), "sym": bare, "acct": account or ""},
            ).scalar()
        return int(row or 0)
    except Exception as e:  # noqa: BLE001
        logger.warning(
            "计划推进读累计卖出失败（批次只留痕不退役）",
            plan_id=plan_id,
            symbol=symbol,
            error=str(e),
        )
        return None


class PlanProgressPort:
    """__call__(fill) → dict：推进计划状态并返回结果（供回执留痕）。"""

    def __init__(self, repo=None, remaining_provider=None, rule_port=None, sold_qty_provider=None):
        self._repo = repo
        self._remaining = remaining_provider or _remaining_qty
        self._rule_port = rule_port
        self._sold_qty = sold_qty_provider or _sold_qty

    def _service(self) -> PlanService:
        if self._repo is None:
            from adapters.outbound.repositories.trading_plan_repository import (
                TradingPlanRepository,
            )

            self._repo = TradingPlanRepository()
        if self._rule_port is None:
            try:
                from adapters.outbound.repositories.plan_rule_port import PlanRulePort

                self._rule_port = PlanRulePort()
            except Exception:  # noqa: BLE001 - 端口装配失败只影响退役，不影响状态推进
                self._rule_port = None
        return PlanService(self._repo, rule_port=self._rule_port)

    def __call__(self, fill: Dict[str, Any]) -> Dict[str, Any]:
        plan_id = fill.get("plan_id")
        if plan_id is None:
            return {"status": "skipped", "reason": "no_plan_id"}
        account = fill.get("account") or fill.get("account_name") or ""
        symbol = fill.get("symbol") or ""
        side = str(fill.get("action") or "").lower()
        remaining = self._remaining(account, symbol)
        if remaining is None:
            return {"status": "degraded", "reason": "position_read_failed"}

        shares = int(fill.get("shares") or 0)
        sold_qty = 0
        sold_ratio = 0.0
        if side == "sell":
            sold_qty = self._sold_qty(int(plan_id), account, symbol)
            if sold_qty is None:
                return {"status": "degraded", "reason": "sold_qty_read_failed"}
            # 累计口径：累计卖出 /（累计卖出 + 成交后剩余）。
            # 单笔 fill 的 shares 不进分子——部分成交与合单下笔数不可靠，trade 表才是真值。
            denom = sold_qty + max(int(remaining or 0), 0)
            sold_ratio = (
                1.0 if remaining <= 0 and sold_qty > 0 else (sold_qty / denom if denom > 0 else 0.0)
            )

        try:
            status = self._service().on_fill(
                int(plan_id),
                side=side,
                qty=shares,
                remaining_qty=remaining,
                trade_id=str(fill.get("trade_id")),
                sold_ratio=sold_ratio,
            )
            out = {"status": "ok", "plan_id": int(plan_id), "plan_status": status}
            if side == "sell":
                out["sold_qty"] = sold_qty
                out["sold_ratio"] = round(sold_ratio, 6)
            return out
        except PlanError as e:
            logger.error("计划推进被拒", plan_id=plan_id, code=e.code, error=e.message)
            return {"status": "rejected", "code": e.code, "error": e.message}
