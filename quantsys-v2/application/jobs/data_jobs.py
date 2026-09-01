"""
数据类定时任务

包含：kline_update, data_quality_check, data_pipeline_daily,
      data_pipeline_weekly, chip_distribution_update
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


class DataPipelineDailyJob(Job):
    """每日数据管道任务"""

    @property
    def name(self) -> str:
        return "data_pipeline_daily"

    @property
    def description(self) -> str:
        return "每日增量更新（CSI 300 成分股）"

    @property
    def timeout_seconds(self) -> int:
        return 7200  # 2小时

    async def execute(self, params: Dict[str, Any]) -> JobResult:
        try:
            from application.services.data_pipeline_service import DataPipelineService
            from datetime import date

            pipeline = DataPipelineService()
            today = date.today()
            result = pipeline.run_incremental_update(
                symbols=params.get('symbols'),
                end_date=today
            )
            return JobResult.ok(
                self.name,
                message="每日数据管道完成",
                details=result
            )
        except Exception as e:
            return JobResult.fail(self.name, str(e))


class DataPipelineWeeklyJob(Job):
    """每周数据管道任务（全量重建）"""

    @property
    def name(self) -> str:
        return "data_pipeline_weekly"

    @property
    def description(self) -> str:
        return "每周全量重建（最近90天）"

    @property
    def timeout_seconds(self) -> int:
        return 14400  # 4小时

    async def execute(self, params: Dict[str, Any]) -> JobResult:
        try:
            from application.services.data_pipeline_service import DataPipelineService
            from datetime import date, timedelta

            pipeline = DataPipelineService()
            end_date = date.today()
            start_date = end_date - timedelta(days=90)
            result = pipeline.run_full_rebuild(
                symbols=params.get('symbols'),
                start_date=start_date,
                end_date=end_date
            )
            return JobResult.ok(
                self.name,
                message="每周全量重建完成",
                details=result
            )
        except Exception as e:
            return JobResult.fail(self.name, str(e))


class DataUpdateJob(Job):
    """全量数据更新（拉取所有股票最新 K 线）"""

    @property
    def name(self) -> str:
        return "data_update"

    @property
    def description(self) -> str:
        return "全量拉取所有股票最新 K 线数据"

    @property
    def timeout_seconds(self) -> int:
        return 7200

    async def execute(self, params: Dict[str, Any]) -> JobResult:
        try:
            from concurrent.futures import ThreadPoolExecutor, as_completed
            from infrastructure.services.enhanced_service_factory import EnhancedServiceFactory
            from domain.ports import IStockRepository

            repo = EnhancedServiceFactory.resolve(IStockRepository)
            stocks = repo.get_all(limit=params.get("max_symbols", 500))
            symbols = [s["symbol"] for s in stocks]

            if not symbols:
                return JobResult.ok(self.name, message="No symbols to update",
                                    details={"symbols_checked": 0})

            def _fetch_one(symbol: str):
                from infrastructure.persistence.orm import close_session
                from adapters.outbound.repositories import KlineORMRepository
                try:
                    return KlineORMRepository().get_latest_daily_kline(symbol)
                finally:
                    close_session()

            updated = 0
            errors = []
            with ThreadPoolExecutor(max_workers=8) as executor:
                futures = {executor.submit(_fetch_one, s): s for s in symbols}
                for future in as_completed(futures):
                    symbol = futures[future]
                    try:
                        future.result()
                        updated += 1
                    except Exception as e:
                        errors.append({"symbol": symbol, "error": str(e)})

            return JobResult.ok(
                self.name,
                message=f"数据更新完成: {updated}/{len(symbols)}",
                details={
                    "symbols_checked": len(symbols),
                    "symbols_updated": updated,
                    "errors": errors[:20],
                },
            )
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


# 导出所有数据类任务
DATA_JOBS = [
    DataUpdateJob(),
    KlineUpdateJob(),
    DataQualityCheckJob(),
    DataPipelineDailyJob(),
    DataPipelineWeeklyJob(),
    ChipDistributionUpdateJob(),
]
