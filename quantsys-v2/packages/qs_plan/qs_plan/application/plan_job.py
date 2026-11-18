"""账户级交易计划调度任务（REQ-261026140857-c192）"""

from __future__ import annotations

import asyncio
from datetime import date
from typing import Any, Dict, Optional


class TradingPlanGenerateJob:
    name = "trading_plan_generate_daily"
    description = "账户级交易计划每日生成：组合决策 + 持仓合并 + draft revision 落库"
    timeout_seconds = 600

    def __init__(self, service=None, account_provider=None, now_date=lambda: date.today()):
        self._service = service
        self._account_provider = account_provider
        self._now_date = now_date

    async def execute(self, params: Optional[Dict[str, Any]] = None):
        from qs_ops.application.jobs.job_protocol import JobResult

        params = params or {}
        try:
            if self._service is None:
                return JobResult.fail(self.name, "未注入 PlanGenerationService")
            accounts = params.get("accounts")
            if accounts is None:
                if self._account_provider is None:
                    return JobResult.fail(self.name, "未注入账户提供者")
                accounts = self._account_provider()
            results = []
            for account in accounts:
                result = await asyncio.to_thread(
                    self._service.generate,
                    account=account,
                    trade_date=params.get("trade_date") or self._now_date(),
                    actor=params.get("actor") or "system",
                    idempotency_key=params.get("idempotency_key")
                    or "%s:%s:generate" % (account, params.get("trade_date") or self._now_date()),
                )
                results.append({"account": account, **result})
            return JobResult.ok(self.name, "generated=%d" % len(results), results=results)
        except Exception as exc:  # noqa: BLE001 - 调度失败必须显式
            return JobResult.fail(self.name, "%s: %s" % (type(exc).__name__, exc))


class TradingPlanReadinessJob:
    name = "trading_plan_readiness"
    description = "账户级交易计划 readiness/运行时对账"
    timeout_seconds = 300

    def __init__(self, service=None, account_provider=None, now_date=lambda: date.today()):
        self._service = service
        self._account_provider = account_provider
        self._now_date = now_date

    async def execute(self, params: Optional[Dict[str, Any]] = None):
        from qs_ops.application.jobs.job_protocol import JobResult

        params = params or {}
        try:
            if self._service is None:
                return JobResult.fail(self.name, "未注入 PlanReadinessService")
            accounts = params.get("accounts")
            if accounts is None:
                if self._account_provider is None:
                    return JobResult.fail(self.name, "未注入账户提供者")
                accounts = self._account_provider()
            results = []
            for account in accounts:
                result = await asyncio.to_thread(
                    self._service.evaluate,
                    account=account,
                    trade_date=params.get("trade_date") or self._now_date(),
                    stage=params.get("stage") or "runtime",
                )
                results.append(result)
            ready = sum(1 for item in results if item.get("ready"))
            return JobResult.ok(self.name, "ready=%d/%d" % (ready, len(results)), results=results)
        except Exception as exc:  # noqa: BLE001
            return JobResult.fail(self.name, "%s: %s" % (type(exc).__name__, exc))


def build_trading_plan_jobs(generation_service=None, readiness_service=None, account_provider=None):
    return [
        TradingPlanGenerateJob(service=generation_service, account_provider=account_provider),
        TradingPlanReadinessJob(service=readiness_service, account_provider=account_provider),
    ]
