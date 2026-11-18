"""组合决策 provider：复用 core 组合算法，但不写 core_plan.json（REQ-261026140857-c192）"""

from __future__ import annotations

from datetime import date, datetime, time, timezone
from typing import Any, Dict, List

from qs_plan.application.ports import PortfolioDecision, TargetAllocation


def _parse_data_as_of(plan: Dict[str, Any]) -> datetime:
    data_date = str(plan.get("data_date") or "")
    try:
        parsed_date = date.fromisoformat(data_date)
        return datetime.combine(parsed_date, time(15, 0), tzinfo=timezone.utc)
    except ValueError:
        generated = str(plan.get("generated_at") or "")
        try:
            parsed = datetime.fromisoformat(generated)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed
        except ValueError:
            return datetime.now(timezone.utc)


class PortfolioDecisionProviderAdapter:
    """旧 core 组合算法的新链路适配器。

    调用 `portfolio_decision_service.generate(_write=False)`：保留选股/风险计算，不写文件、不打印计划、不创建执行计划。
    """

    def build(self, *, account: str, trade_date: date) -> PortfolioDecision:
        from application.services import portfolio_decision_service

        plan = portfolio_decision_service.generate(account=account, _write=False)
        exposure = plan.get("exposure") or {}
        core_exposure = float(exposure.get("target_pct") or 0)
        sleeve = plan.get("growth_sleeve") or {}
        sleeve_meta = sleeve.get("meta") or {}
        sleeve_exposure = float(sleeve_meta.get("exposure_pct_of_total") or 0)

        batch_by_symbol = {
            str(detail.get("symbol")): int(batch.get("batch"))
            for batch in (plan.get("execution_plan") or {}).get("batches") or []
            for detail in batch.get("detail") or []
            if detail.get("symbol") and batch.get("batch") is not None
        }
        targets: List[TargetAllocation] = []
        for row in plan.get("holdings") or []:
            weight = float(row.get("weight_pct_of_core") or 0) / 100.0
            targets.append(
                TargetAllocation(
                    symbol=str(row.get("symbol")),
                    target_weight=round(core_exposure * weight, 6),
                    target_qty=(int(row["lots"]) * 100 if row.get("lots") is not None else None),
                    horizon="swing",
                    thesis="core 组合目标",
                    invalidation="core 组合目标失效",
                    stop_loss={"type": "pct", "value": 8},
                    evidence={"source": "portfolio_decision", "role": row.get("role"), "row": row},
                    execution_batch=batch_by_symbol.get(str(row.get("symbol"))),
                    max_chase_pct=row.get("max_chase_pct"),
                )
            )
        for row in sleeve.get("holdings") or []:
            weight = float(row.get("weight_pct_of_sleeve") or 0) / 100.0
            targets.append(
                TargetAllocation(
                    symbol=str(row.get("symbol")),
                    target_weight=round(sleeve_exposure * weight, 6),
                    target_qty=(int(row["lots"]) * 100 if row.get("lots") is not None else None),
                    horizon="swing",
                    thesis="growth sleeve 组合目标",
                    invalidation="growth sleeve 目标失效",
                    stop_loss={"type": "pct", "value": 8},
                    evidence={"source": "portfolio_decision", "role": row.get("role"), "row": row},
                    execution_batch=batch_by_symbol.get(str(row.get("symbol"))),
                    max_chase_pct=row.get("max_chase_pct"),
                )
            )

        return PortfolioDecision(
            account=str(plan.get("account") or account),
            trade_date=trade_date,
            data_as_of=_parse_data_as_of(plan),
            targets=tuple(targets),
            market_gate={"style": (plan.get("market_style") or {}).get("style"), "allowed": True},
            risk_budget={
                "max_total_exposure": float(exposure.get("first_phase_cap_pct") or 0),
                "target_exposure": core_exposure,
                "sleeve_exposure": sleeve_exposure,
                "risk_lens": plan.get("risk_lens") or {},
            },
            evidence={
                "generated_at": plan.get("generated_at"),
                "data_date": plan.get("data_date"),
                "mode": plan.get("mode"),
            },
        )
