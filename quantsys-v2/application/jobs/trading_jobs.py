"""
交易类定时任务

包含：v13_daily_check, v13_risk_check, v13_verification,
      trade_verify_daily, pool_refresh_daily
"""
import asyncio
import logging
from typing import Any, Dict

from application.jobs.job_protocol import Job, JobResult

logger = logging.getLogger(__name__)


def _ok_or_fail(job_name: str, ok_message: str, result: Any) -> JobResult:
    """把 job 函数返回 dict 的 status 映射为 JobResult，杜绝"内部失败但任务 success"。

    2026-09-11 修复（w-f4aa1f6a，看板事件 dff409c4 / 任务 319）：
    strategy_daily_check 等 job 函数用「返回 dict + status='failed'」表达失败（不抛异常），
    而包装层原先无条件 JobResult.ok → 任务永远标记 success。
    实测后果：昨日重构误删 live_trading/configs/strategies/{v13,v14}.yaml 后，
    v13/v14 策略日检连续失败却无人发现（错误只落在日志里，任务状态全绿）。
    与 PoolRefreshDailyJob 既有写法对齐。
    """
    if isinstance(result, dict):
        status = str(result.get('status') or '').lower()
        if status in ('failed', 'error', 'fail'):
            return JobResult.fail(
                job_name,
                result.get('error') or result.get('message') or f'job 内部 status={status}',
            )
    return JobResult.ok(job_name, message=ok_message, details=result)


class V13DailyCheckJob(Job):
    """V13 模拟交易每日检查"""

    @property
    def name(self) -> str:
        return "v13_daily_check"

    @property
    def description(self) -> str:
        return "V13 模型每日检查（止损、调仓）"

    @property
    def timeout_seconds(self) -> int:
        return 1800  # 30分钟

    @property
    def misfire_grace_time_seconds(self) -> int:
        return 300  # 5分钟

    async def execute(self, params: Dict[str, Any]) -> JobResult:
        try:
            from infrastructure.jobs.strategy_trading_job import v13_daily_check
            result = v13_daily_check(**params)
            return _ok_or_fail(self.name, "V13 每日检查完成", result)
        except Exception as e:
            return JobResult.fail(self.name, str(e))


class V14DailyCheckJob(Job):
    """V14 模拟交易每日检查"""

    @property
    def name(self) -> str:
        return "v14_daily_check"

    @property
    def description(self) -> str:
        return "V14 模型每日检查（止损、调仓）"

    @property
    def timeout_seconds(self) -> int:
        return 1800  # 30分钟

    @property
    def misfire_grace_time_seconds(self) -> int:
        return 300  # 5分钟

    async def execute(self, params: Dict[str, Any]) -> JobResult:
        try:
            from infrastructure.jobs.strategy_trading_job import v14_daily_check
            result = v14_daily_check(**params)
            return _ok_or_fail(self.name, "V14 每日检查完成", result)
        except Exception as e:
            return JobResult.fail(self.name, str(e))


class V13RiskCheckJob(Job):
    """V13 盘后风险检查"""

    @property
    def name(self) -> str:
        return "v13_risk_check"

    @property
    def description(self) -> str:
        return "V13 盘后风险评估"

    @property
    def timeout_seconds(self) -> int:
        return 1800  # 30分钟

    @property
    def misfire_grace_time_seconds(self) -> int:
        return 300  # 5分钟

    async def execute(self, params: Dict[str, Any]) -> JobResult:
        try:
            from infrastructure.jobs.risk_check_job import execute
            result = execute(**params)
            return _ok_or_fail(self.name, "V13 风险检查完成", result)
        except Exception as e:
            return JobResult.fail(self.name, str(e))


class V13VerificationJob(Job):
    """V13 交易验证"""

    @property
    def name(self) -> str:
        return "v13_verification"

    @property
    def description(self) -> str:
        return "V13 交易验证"

    @property
    def timeout_seconds(self) -> int:
        return 1800  # 30分钟

    @property
    def misfire_grace_time_seconds(self) -> int:
        return 43200  # 12小时（周末可能跳过）

    async def execute(self, params: Dict[str, Any]) -> JobResult:
        try:
            from infrastructure.jobs.verification_job import execute
            result = execute(**params)
            return _ok_or_fail(self.name, "V13 验证完成", result)
        except Exception as e:
            return JobResult.fail(self.name, str(e))


class TradeVerifyDailyJob(Job):
    """每日交易对账"""

    @property
    def name(self) -> str:
        return "trade_verify_daily"

    @property
    def description(self) -> str:
        return "每日交易对账（重复成交、字段完整性、持仓勾稽）"

    @property
    def timeout_seconds(self) -> int:
        return 1800  # 30分钟

    async def execute(self, params: Dict[str, Any]) -> JobResult:
        try:
            from datetime import date
            from adapters.outbound.repositories.simulation_repository import SimulationORMRepository

            account_name = params.get("account_name", "agent_virtual")
            date_str = params.get("date")
            target_date = date.fromisoformat(date_str) if date_str else date.today()

            repo = SimulationORMRepository()
            anomalies = []

            # 1. 拉取成交记录
            all_trades = repo.get_trades_by_account(account_name)
            day_trades = [t for t in all_trades if t.trade_date == target_date]

            # 2. 重复成交检测
            seen = {}
            for trade in day_trades:
                trade_time_str = trade.trade_time.strftime('%Y-%m-%d %H:%M') if trade.trade_time else ''
                key = f"{trade.symbol}|{trade.action}|{trade.price}|{trade.shares}|{trade_time_str}"
                if key in seen:
                    seen[key] += 1
                    anomalies.append({
                        "type": "duplicate_trade",
                        "detail": f"疑似重复成交: {trade.symbol} {trade.action}",
                        "trade_id": trade.id
                    })
                else:
                    seen[key] = 1

            # 3. 字段完整性检测
            for trade in day_trades:
                missing = []
                if not trade.symbol:
                    missing.append('symbol')
                if not trade.action:
                    missing.append('action')
                if not trade.price or float(trade.price) <= 0:
                    missing.append('price')
                if not trade.shares or trade.shares <= 0:
                    missing.append('shares')
                if missing:
                    anomalies.append({
                        "type": "missing_fields",
                        "detail": f"成交记录缺字段: {'/'.join(missing)}",
                        "trade_id": trade.id
                    })

            return JobResult.ok(
                self.name,
                message=f"交易对账完成: {len(day_trades)} trades, {len(anomalies)} anomalies",
                details={
                    "total_orders": len(day_trades),
                    "anomalies": anomalies
                }
            )
        except Exception as e:
            return JobResult.fail(self.name, str(e))


class PoolRefreshDailyJob(Job):
    """每日股票池刷新（委托 scheduler_tasks 单一正实现）

    2026-09-05 收敛（w-8366e526）：此前本 Job 自带"全池循环 + 吞错"旧实现，
    与 application.services.scheduler_tasks.handle_pool_refresh_daily（静态池跳过 +
    到期判定 + 成员 diff + pool_changed 通知）形成双实现，注册表后者曾覆盖前者
    但本 Job 类实例是唯一被执行路径 → 3 个 dynamic 池停更 13 天。
    现在本类只做委托，正确逻辑只存在于 scheduler_tasks 一处。
    """

    @property
    def name(self) -> str:
        return "pool_refresh_daily"

    @property
    def description(self) -> str:
        return "刷新动态股票池（静态跳过/到期判定/成员变更通知）"

    @property
    def timeout_seconds(self) -> int:
        return 3600  # 1小时

    async def execute(self, params: Dict[str, Any]) -> JobResult:
        try:
            from application.services.scheduler_tasks import handle_pool_refresh_daily
            result = await asyncio.to_thread(handle_pool_refresh_daily, params or {})
            status = result.get('status')
            if status == 'failed':
                return JobResult.fail(
                    self.name,
                    result.get('error') or result.get('message') or 'unknown error',
                )
            return JobResult.ok(
                self.name,
                message=f"股票池刷新完成: refreshed={result.get('refreshed', 0)}, "
                        f"skipped={result.get('skipped', 0)}, changed={result.get('changed', 0)}, "
                        f"failed={len(result.get('failed') or [])}",
                details=result,
            )
        except Exception as e:
            return JobResult.fail(self.name, str(e))


# 导出所有交易类任务
TRADING_JOBS = [
    V13DailyCheckJob(),
    V14DailyCheckJob(),
    V13RiskCheckJob(),
    V13VerificationJob(),
    TradeVerifyDailyJob(),
    PoolRefreshDailyJob(),
]
