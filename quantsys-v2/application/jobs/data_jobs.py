"""
数据类定时任务

包含：kline_update, data_quality_check, chip_distribution_update
"""
import logging
from typing import Any, Dict

from application.jobs.job_protocol import Job, JobResult

logger = logging.getLogger(__name__)


class KlineUpdateJob(Job):
    """K线日更任务"""

    @property
    def name(self) -> str:
        return "kline_update"

    @property
    def description(self) -> str:
        return "每日更新K线数据（多数据源 fallback + 限速防封）"

    @property
    def timeout_seconds(self) -> int:
        return 3600  # 1小时

    async def execute(self, params: Dict[str, Any]) -> JobResult:
        try:
            from infrastructure.jobs.kline_update_job import execute
            result = execute(**params)
            return JobResult.ok(
                self.name,
                message=f"K线更新完成",
                details=result
            )
        except Exception as e:
            return JobResult.fail(self.name, str(e))


class DataQualityCheckJob(Job):
    """数据质量检查任务"""

    @property
    def name(self) -> str:
        return "data_quality_check"

    @property
    def description(self) -> str:
        return "检查数据质量并自动回填缺失数据"

    @property
    def timeout_seconds(self) -> int:
        return 3600  # 1小时

    async def execute(self, params: Dict[str, Any]) -> JobResult:
        try:
            from infrastructure.jobs.data_quality_check_job import DataQualityCheckJob as Impl
            job = Impl()
            result = job.run(params)
            if result['success']:
                return JobResult.ok(
                    self.name,
                    message="数据质量检查完成",
                    details=result
                )
            else:
                return JobResult.fail(self.name, result.get('error', 'Unknown error'))
        except Exception as e:
            return JobResult.fail(self.name, str(e))


class ChipDistributionUpdateJob(Job):
    """筹码分布日更任务"""

    @property
    def name(self) -> str:
        return "chip_distribution_update"

    @property
    def description(self) -> str:
        return "计算筹码分布（增量，幂等）"

    @property
    def timeout_seconds(self) -> int:
        return 3600  # 1小时

    async def execute(self, params: Dict[str, Any]) -> JobResult:
        try:
            from infrastructure.jobs.chip_distribution_update_job import execute
            result = execute(**params)
            return JobResult.ok(
                self.name,
                message="筹码分布更新完成",
                details=result
            )
        except Exception as e:
            return JobResult.fail(self.name, str(e))


class DataUpdateJob(Job):
    """全市场数据新鲜度巡检（旧 handle_data_update，ADR-002 Phase 1 补齐）"""

    @property
    def name(self) -> str:
        return "data_update"

    @property
    def description(self) -> str:
        return "检查全市场股票最新K线新鲜度（并发巡检）"

    @property
    def timeout_seconds(self) -> int:
        return 1800

    async def execute(self, params: Dict[str, Any]) -> JobResult:
        import asyncio
        from concurrent.futures import ThreadPoolExecutor

        def _run() -> Dict[str, Any]:
            from infrastructure.persistence.orm import close_session
            from adapters.outbound.repositories import KlineORMRepository, StockORMRepository

            stocks = StockORMRepository().get_all(limit=500)
            symbols = [s['symbol'] for s in stocks]
            if not symbols:
                return {"skipped": True, "reason": "no symbols"}

            def _fetch_one(symbol: str):
                try:
                    return KlineORMRepository().get_latest_daily_kline(symbol)
                finally:
                    close_session()

            updated, errors = 0, []
            with ThreadPoolExecutor(max_workers=8) as executor:
                futures = {executor.submit(_fetch_one, s): s for s in symbols}
                for future in futures:
                    symbol = futures[future]
                    try:
                        future.result()
                        updated += 1
                    except Exception as e:
                        errors.append({"symbol": symbol, "error": str(e)})
            return {"symbols_checked": len(symbols), "symbols_updated": updated, "errors": errors}

        try:
            # 同步阻塞逻辑放线程池，避免卡住事件循环
            result = await asyncio.to_thread(_run)
            if result.get("skipped"):
                return JobResult.ok(self.name, message="无股票可巡检", **result)
            return JobResult.ok(
                self.name,
                message=f"数据巡检完成：{result['symbols_updated']}/{result['symbols_checked']}",
                **result,
            )
        except Exception as e:
            return JobResult.fail(self.name, str(e))


class FinancialTimelinessCheckJob(Job):
    """财报时效性检查任务（僵尸修复：2026-09-05 w-8366e526）

    此前该命令只注册在 scheduler_handlers 的 webhook 通道（agent-os 模式下才有意义），
    JobRegistry 无对应 Job → APScheduler 直连路径执行报
    "Unknown scheduler command: 'financial_timeliness_check'"（task 318 每日 09:00 失败）。
    本类把 infrastructure/jobs/financial_timeliness_check_job 的真实实现接到 JobRegistry，
    与 webhook handler 共享同一实现（execute），两种调度模式各自只执行一次。
    """

    @property
    def name(self) -> str:
        return "financial_timeliness_check"

    @property
    def description(self) -> str:
        return "财报时效性检查：查询持仓财报更新时效，过期预警"

    @property
    def timeout_seconds(self) -> int:
        return 600

    async def execute(self, params: Dict[str, Any]) -> JobResult:
        try:
            from infrastructure.jobs.financial_timeliness_check_job import execute
            result = execute(**(params or {})) or {}
            if result.get('success'):
                return JobResult.ok(
                    self.name,
                    message=result.get('message') or '财报时效性检查完成',
                    details=result,
                )
            return JobResult.fail(self.name, result.get('error') or result.get('message') or 'check failed')
        except Exception as e:
            return JobResult.fail(self.name, str(e))


# 导出所有数据类任务
DATA_JOBS = [
    KlineUpdateJob(),
    DataQualityCheckJob(),
    FinancialTimelinessCheckJob(),
    ChipDistributionUpdateJob(),
    DataUpdateJob(),
]
