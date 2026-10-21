"""
报告类定时任务

包含：report_daily, v13_weekly_report, financial_data_update
"""
import logging
from typing import Any, Dict

from qs_ops.application.jobs.job_protocol import Job, JobResult, result_from_dict

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
            from infrastructure.services.service_factory import ServiceFactory
            stocks = ServiceFactory.get_stock_repository().list_all_active(market="A")
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
            return result_from_dict(self.name, "V13 周报生成完成", result)
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
            from infrastructure.jobs.financial_data_update_job import execute
            result = execute(**params)
            if not result.get("success"):
                return JobResult.fail(self.name, result.get("error", "unknown"))
            return JobResult.ok(
                self.name,
                message=(
                    f"财务数据更新完成: 更新 {result.get('updated', 0)} 只"
                    f" (报告期 {result.get('report_date', '')})"
                ),
                **result,
            )
        except Exception as e:
            return JobResult.fail(self.name, str(e))


class WeeklyProfitReportJob(Job):
    """每周盈利报告（2026-10-19）：盈亏/命中率/机会三段式，周日 20:30"""

    @property
    def name(self) -> str:
        return "weekly_profit_report"

    @property
    def description(self) -> str:
        return "各账户本周已实现盈亏 + 信号命中率 + 机会捕捉/错过清单"

    @property
    def timeout_seconds(self) -> int:
        return 600

    @property
    def misfire_grace_time_seconds(self) -> int:
        return 43200  # 12小时

    async def execute(self, params: Dict[str, Any]) -> JobResult:
        try:
            from qs_ops.infrastructure.jobs.weekly_profit_report_job import execute
            result = execute(params or {})
            return result_from_dict(self.name, "每周盈利报告生成完成", result)
        except Exception as e:
            return JobResult.fail(self.name, str(e))


# 导出所有报告类任务
REPORT_JOBS = [
    ReportDailyJob(),
    V13WeeklyReportJob(),
    FinancialDataUpdateJob(),
    WeeklyProfitReportJob(),
]
