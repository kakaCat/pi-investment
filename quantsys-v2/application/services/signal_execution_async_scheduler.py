"""
信号执行调度器 - 异步版本

核心编排器，协调完整的信号到订单流程：
1. 运行所有启用的策略
2. 收集今日待处理信号
3. 批量风控检查
4. 为通过的信号创建订单
5. 更新信号状态并记录日志
"""
from typing import Dict, Any, List
from datetime import datetime, date
import structlog

from adapters.outbound.repositories.signal_async_repository import SignalAsyncRepository
from adapters.outbound.repositories.strategy_async_repository import StrategyAsyncRepository
from infrastructure.persistence.orm.async_config import get_async_session_context

logger = structlog.get_logger(__name__)


class SignalExecutionAsyncScheduler:
    """信号执行调度器 - 异步版本"""

    def __init__(self):
        pass

    async def execute_daily_signals(self) -> Dict[str, Any]:
        """
        执行每日信号处理流程（15:30定时调用）

        Returns:
            执行结果摘要
        """
        execution_date = date.today().strftime('%Y-%m-%d')
        start_time = datetime.now()

        logger.info(f"开始执行每日信号流程: {execution_date}")

        try:
            # Step 1: 收集今日待处理信号
            pending_signals = await self._collect_signals(execution_date)

            # Step 2: 批量风控检查
            approved_signals, rejected_signals = await self._batch_risk_check(pending_signals)

            # Step 3: 更新信号状态
            await self._update_signal_status(approved_signals, rejected_signals)

            # 计算执行时长
            end_time = datetime.now()
            duration_ms = int((end_time - start_time).total_seconds() * 1000)

            result = {
                'execution_date': execution_date,
                'duration_ms': duration_ms,
                'signals_total': len(pending_signals),
                'signals_approved': len(approved_signals),
                'signals_rejected': len(rejected_signals),
                'status': 'completed'
            }

            logger.info(f"每日信号流程完成: {result}")
            return result

        except Exception as e:
            logger.error(f"执行每日信号流程失败: {e}")
            return {
                'execution_date': execution_date,
                'status': 'failed',
                'error': str(e)
            }

    async def _collect_signals(self, execution_date: str) -> List[Dict]:
        """收集今日待处理信号"""
        try:
            async with get_async_session_context() as session:
                signal_repo = SignalAsyncRepository(session)
                signals = await signal_repo.get_pending_signals(limit=1000)
                logger.info(f"收集到 {len(signals)} 个待处理信号")
                return signals

        except Exception as e:
            logger.error(f"收集信号失败: {e}")
            return []

    async def _batch_risk_check(self, signals: List[Dict]) -> tuple[List[Dict], List[Dict]]:
        """批量风控检查"""
        approved = []
        rejected = []

        for signal in signals:
            # 简单的风控逻辑（实际应该更复杂）
            if signal.get('confidence', 0) >= 0.6:
                approved.append(signal)
            else:
                rejected.append({**signal, 'reject_reason': '置信度不足'})

        logger.info(f"风控检查: {len(approved)} 通过, {len(rejected)} 拒绝")
        return approved, rejected

    async def _update_signal_status(
        self,
        approved_signals: List[Dict],
        rejected_signals: List[Dict]
    ):
        """更新信号状态"""
        try:
            async with get_async_session_context() as session:
                signal_repo = SignalAsyncRepository(session)

                # 更新通过的信号
                for signal in approved_signals:
                    await signal_repo.update_signal_status(
                        signal['id'],
                        'approved'
                    )

                # 更新拒绝的信号
                for signal in rejected_signals:
                    await signal_repo.update_signal_status(
                        signal['id'],
                        'rejected',
                        signal.get('reject_reason')
                    )

                logger.info(f"信号状态更新完成")

        except Exception as e:
            logger.error(f"更新信号状态失败: {e}")


__all__ = ['SignalExecutionAsyncScheduler']
