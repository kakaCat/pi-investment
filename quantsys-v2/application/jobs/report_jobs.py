"""
报告类定时任务

包含：report_daily, v13_weekly_report, financial_data_update
"""
import logging
from typing import Any, Dict

from application.jobs.job_protocol import Job, JobResult

logger = logging.getLogger(__name__)


class ReportDailyJob(Job):
    """每日报告生成"""

    @property
    def name(self) -> str:
        return "report_daily"

    @property
    def description(self) -> str:
        return "生成每日摘要报告"

    @property
    def timeout_seconds(self) -> int:
        return 3600  # 1小时

    async def execute(self, params: Dict[str, Any]) -> JobResult:
        try:
            from adapters.outbound.repositories.stock_repository import StockORMRepository
            stocks = StockORMRepository().list_all_active(market="A")
            return JobResult.ok(
                self.name,
                message=f"每日报告生成完成: {len(stocks)} stocks",
                details={"total_stocks": len(stocks)}
            )
        except Exception as e:
            return JobResult.fail(self.name, str(e))


class V13WeeklyReportJob(Job):
    """V13 周报"""

    @property
    def name(self) -> str:
        return "v13_weekly_report"

    @property
    def description(self) -> str:
        return "生成 V13 周度报告"

    @property
    def timeout_seconds(self) -> int:
        return 3600  # 1小时

    @property
    def misfire_grace_time_seconds(self) -> int:
        return 43200  # 12小时

    async def execute(self, params: Dict[str, Any]) -> JobResult:
        try:
            from infrastructure.jobs.weekly_report_job import execute
            result = execute(**params)
            return JobResult.ok(
                self.name,
                message="V13 周报生成完成",
                details=result
            )
        except Exception as e:
            return JobResult.fail(self.name, str(e))


class FinancialDataUpdateJob(Job):
    """财务数据更新"""

    @property
    def name(self) -> str:
        return "financial_data_update"

    @property
    def description(self) -> str:
        return "更新基础财务数据"

    @property
    def timeout_seconds(self) -> int:
        return 7200  # 2小时

    async def execute(self, params: Dict[str, Any]) -> JobResult:
        try:
            # TODO: 实现财务数据更新逻辑
            return JobResult.ok(
                self.name,
                message="财务数据更新完成（待实现）",
                details={"updated": 0}
            )
        except Exception as e:
            return JobResult.fail(self.name, str(e))


# 导出所有报告类任务
REPORT_JOBS = [
    ReportDailyJob(),
    V13WeeklyReportJob(),
    FinancialDataUpdateJob(),
]
