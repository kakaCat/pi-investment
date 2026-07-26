"""
日常投资循环编排器 (Daily Investment Orchestrator)

状态机驱动每日投资流程：
IDLE → PRE_MARKET → MARKET_OPEN → INTRADAY → MARKET_CLOSE → POST_MARKET → REVIEW → IDLE

核心职责：
1. 按阶段协调各任务（数据更新→信号生成→交易执行→绩效统计→复盘）
2. 状态持久化到 DB，进程重启后断点续跑
3. 在关键决策点唤醒 Agent
4. 记录每日运行日志

使用方式：
    orchestrator = DailyOrchestrator()
    orchestrator.run()  # 由 APScheduler 每分钟调用，自动判断当前应执行的阶段
"""
from __future__ import annotations

import structlog
from typing import Dict, Any, Optional, List
from datetime import datetime, date, time
from enum import Enum

from infrastructure.persistence.orm import get_session
from infrastructure.persistence.orm.models.orchestrator import DailyOrchestratorState
from application.services.agent_notification_service import agent_service

logger = structlog.get_logger(__name__)


# ============================================================
# 阶段定义
# ============================================================

class Phase(str, Enum):
    IDLE = 'IDLE'
    PRE_MARKET = 'PRE_MARKET'
    MARKET_OPEN = 'MARKET_OPEN'
    INTRADAY = 'INTRADAY'
    MARKET_CLOSE = 'MARKET_CLOSE'
    POST_MARKET = 'POST_MARKET'
    REVIEW = 'REVIEW'


# 阶段时间窗口（24小时制）
PHASE_SCHEDULE = {
    Phase.PRE_MARKET: (time(8, 30), time(9, 25)),
    Phase.MARKET_OPEN: (time(9, 25), time(9, 35)),
    Phase.INTRADAY: (time(9, 35), time(15, 0)),
    Phase.MARKET_CLOSE: (time(15, 0), time(15, 5)),
    Phase.POST_MARKET: (time(15, 30), time(16, 30)),
    Phase.REVIEW: (time(16, 30), time(17, 30)),
}

# 阶段流转顺序
PHASE_ORDER = [
    Phase.IDLE,
    Phase.PRE_MARKET,
    Phase.MARKET_OPEN,
    Phase.INTRADAY,
    Phase.MARKET_CLOSE,
    Phase.POST_MARKET,
    Phase.REVIEW,
]

# 唯一交易账本（2026-07-24 盈利闭环改造）
TRADING_ACCOUNT = 'agent_virtual'


# ============================================================
# 编排器
# ============================================================

class DailyOrchestrator:
    """日常投资循环编排器

    由 APScheduler 每分钟调用 tick()，自动判断当前时间应处于哪个阶段，
    并执行对应的任务。状态持久化到 DB，支持断点续跑。
    """

    def __init__(self, name: str = 'main'):
        self.name = name
        self.session = get_session()
        self._today_state: Optional[DailyOrchestratorState] = None

    # ==================== 主入口 ====================

    def tick(self):
        """每分钟调用一次，驱动状态机前进

        由 APScheduler 注册为 interval 任务（每60秒）。
        """
        now = datetime.now()
        today = now.date()

        # 跳过周末
        if today.weekday() >= 5:
            return

        try:
            # 获取或创建今日状态
            state = self._get_or_create_state(today)
        except Exception as e:
            # 数据库异常（缺表/连接断开）必须 rollback——否则单例 Session
            # 卡在中止事务里，后续每次 tick 都抛 PendingRollbackError，
            # 编排器永久死亡直到进程重启（2026-07-23 code review 发现）
            logger.error(f"orchestrator_tick_state_error", error=str(e))
            self.session.rollback()
            return

        # 判断当前应处于哪个阶段
        target_phase = self._determine_phase(now.time())

        # 如果目标阶段已过（所有阶段都完成），进入 IDLE
        if target_phase == Phase.IDLE and state.current_phase != Phase.IDLE:
            # 检查是否所有阶段都已完成
            if self._all_phases_done(state):
                self._transition(state, Phase.IDLE)
                return

        # 如果当前阶段落后于目标阶段，逐步推进
        current_idx = PHASE_ORDER.index(Phase(state.current_phase))
        target_idx = PHASE_ORDER.index(target_phase)

        if target_idx > current_idx:
            # 需要推进到目标阶段（跳过中间已过的阶段）
            for i in range(current_idx + 1, target_idx + 1):
                phase = PHASE_ORDER[i]
                if phase == Phase.IDLE:
                    continue
                if not self._is_phase_completed(state, phase.value):
                    self._execute_phase(state, phase)

    def run_phase(self, phase_name: str) -> Dict[str, Any]:
        """手动触发某个阶段（用于调试/补跑）

        Args:
            phase_name: 阶段名称，如 'PRE_MARKET'

        Returns:
            执行结果
        """
        today = date.today()
        state = self._get_or_create_state(today)
        phase = Phase(phase_name)
        return self._execute_phase(state, phase)

    def get_status(self) -> Dict[str, Any]:
        """获取编排器当前状态"""
        today = date.today()
        state = self._get_or_create_state(today)
        return state.to_dict()

    # ==================== 阶段执行 ====================

    def _execute_phase(self, state: DailyOrchestratorState, phase: Phase) -> Dict[str, Any]:
        """执行指定阶段的所有任务"""
        phase_name = phase.value
        logger.info(f"orchestrator_phase_start", phase=phase_name, date=str(state.trade_date))

        # 标记阶段开始
        self._transition(state, phase)

        try:
            # 分发到对应的处理方法
            handler = getattr(self, f'_phase_{phase_name.lower()}', None)
            if handler is None:
                logger.warning(f"No handler for phase: {phase_name}")
                result = {'status': 'skipped', 'reason': 'no handler'}
            else:
                result = handler(state)

            # 标记阶段完成
            self._mark_phase_completed(state, phase_name, result)
            logger.info(f"orchestrator_phase_done", phase=phase_name)
            return result

        except Exception as e:
            logger.error(f"orchestrator_phase_error", phase=phase_name, error=str(e))
            state.last_error = str(e)[:500]
            state.error_count += 1
            self.session.commit()
            return {'status': 'error', 'error': str(e)}

    def _phase_pre_market(self, state: DailyOrchestratorState) -> Dict[str, Any]:
        """盘前阶段：数据更新 + 市场风格检测 + 策略轮动 + 信号生成"""
        from application.services.scheduler_tasks import (
            handle_data_update,
            handle_market_style_update,
            handle_signal_generate,
        )

        results = {}

        # 1. 数据更新
        logger.info("pre_market: data_update")
        results['data_update'] = handle_data_update()

        # 2. 市场风格检测
        logger.info("pre_market: market_style_detect")
        results['market_style'] = handle_market_style_update()

        # 保存市场风格到上下文
        if results['market_style'].get('style'):
            self._update_context(state, {
                'market_style': results['market_style'].get('style'),
                'market_confidence': results['market_style'].get('confidence', 0),
            })

        # 3. 策略轮动判断
        logger.info("pre_market: strategy_rotation_check")
        try:
            from application.services.strategy_rotation_engine import get_rotation_engine
            rotation_engine = get_rotation_engine()
            rotation_result = rotation_engine.evaluate()
            results['rotation'] = rotation_result

            if rotation_result.get('needs_rotation'):
                self._update_context(state, {
                    'rotation_proposal': rotation_result.get('proposal'),
                })
                # 唤醒 Agent 做轮动决策（工具链模式）
                self._notify_agent('strategy_rotation', {
                    'market_style': rotation_result.get('market_style'),
                    'confidence': rotation_result.get('proposal', {}).get('confidence', 0),
                    'proposal_summary': rotation_result.get('proposal', {}).get('summary', ''),
                    'trigger': rotation_result.get('proposal', {}).get('trigger', ''),
                    'instructions': (
                        '请使用 rotation_proposal 工具获取详细方案，按决策链操作：\n'
                        '1. rotation_proposal → 2. rotation_simulate → 3. rotation_execute → 4. decision_record'
                    ),
                })
        except Exception as e:
            logger.warning(f"Strategy rotation check failed: {e}")
            results['rotation'] = {'error': str(e)}

        # 4. 信号生成
        logger.info("pre_market: signal_generate")
        results['signal_generate'] = handle_signal_generate()

        # 5. 唤醒 Agent 生成盘前报告
        self._notify_agent('pre_market_summary', {
            'date': str(state.trade_date),
            'market_style': results.get('market_style', {}),
            'signals_generated': results.get('signal_generate', {}).get('signals_count', 0),
        })

        return results

    def _phase_market_open(self, state: DailyOrchestratorState) -> Dict[str, Any]:
        """开盘阶段：汇总当日待处理信号并推送 Agent 决策。

        2026-07-24 盈利闭环改造：v2 不再自动下单。
        买卖决策唯一执行者是 Agent（LLM），账本为 agent_virtual。
        本阶段只负责"信号准备 + 事件推送"。
        """
        # 开盘前 T+1 结转：前日买入的持仓转为可卖（9:25 结转，9:30 开盘即可卖）
        from adapters.outbound.repositories import SimulationORMRepository
        settled = SimulationORMRepository().settle_t1(TRADING_ACCOUNT)
        logger.info("market_open: t1_settled", positions=settled)

        signals = self._collect_pending_signals()

        self._update_context(state, {
            'signals_ready_count': len(signals),
        })

        self._notify_agent('signals_ready', {
            'trade_date': str(state.trade_date),
            'signal_count': len(signals),
            'signals': signals[:20],
            'account': 'agent_virtual',
            'instructions': (
                '请使用工具链处理今日信号：\n'
                '1. decision_history → 检查今日是否已处理过这些信号（按信号ID判重）\n'
                '2. portfolio_status → 查看 agent_virtual 持仓与可用资金\n'
                '3. 逐信号评估后决定买入：portfolio_trade(account=agent_virtual)\n'
                '4. 放弃的信号也要 decision_record 记录理由\n'
                '5. 全部处理完：knowledge_record 摘要 + feishu_notify 简报'
            ),
        })

        return {'status': 'signals_pushed', 'signal_count': len(signals)}

    def _collect_pending_signals(self) -> List[Dict[str, Any]]:
        """收集当日 pending 信号（复用 SignalExecutionScheduler 的收集逻辑，不下单）"""
        from application.services.signal_execution_scheduler import SignalExecutionScheduler
        scheduler = SignalExecutionScheduler()
        return scheduler._collect_signals(date.today().strftime('%Y-%m-%d'))

    def _phase_intraday(self, state: DailyOrchestratorState) -> Dict[str, Any]:
        """盘中阶段：持仓监控 + 止损止盈

        注意：此阶段由独立的 interval 任务每30分钟触发，
        编排器只在首次进入时标记状态。
        """
        # 盘中监控由 IntradayMonitor 独立处理
        # 这里只做标记
        return {'status': 'monitoring', 'note': 'IntradayMonitor handles this phase'}

    def _phase_market_close(self, state: DailyOrchestratorState) -> Dict[str, Any]:
        """收盘阶段：T+1 结转 + 最终市值更新"""
        from adapters.outbound.repositories import SimulationORMRepository

        repo = SimulationORMRepository()

        # T+1 结转：今日买入的股票明日才可卖出
        settled = repo.settle_t1(TRADING_ACCOUNT)

        # 更新最终市值（使用收盘价）
        from live_trading.paper_trading_engine import PaperTradingEngine
        engine = PaperTradingEngine(account_name=TRADING_ACCOUNT)

        # 获取持仓并更新价格
        positions = engine.get_current_positions()
        if positions:
            from application.services.data_service import DataService
            ds = DataService()
            prices = {}
            for p in positions:
                try:
                    kline = ds.kline.get_latest_daily_kline(p['symbol'])
                    if kline:
                        prices[p['symbol']] = float(kline['close'])
                except Exception:
                    pass
            if prices:
                engine._update_position_values(prices)

        return {'settled_positions': settled, 'positions_updated': len(positions)}

    def _phase_post_market(self, state: DailyOrchestratorState) -> Dict[str, Any]:
        """盘后阶段：绩效统计 + 净值快照 + 因子重算"""
        from live_trading.paper_trading_engine import PaperTradingEngine
        from application.services.scheduler_tasks import handle_factor_compute

        engine = PaperTradingEngine(account_name=TRADING_ACCOUNT)

        # 1. 拍摄每日净值快照
        snapshot = engine.take_daily_snapshot()

        # 2. 生成绩效报告
        report = engine.get_performance_report()

        # 3. 因子重算（为明日准备）
        logger.info("post_market: factor_compute")
        factor_result = handle_factor_compute()

        # 保存到上下文
        self._update_context(state, {
            'daily_snapshot': snapshot,
            'performance': {
                'total_value': report.get('total_value'),
                'cumulative_return': report.get('cumulative_return'),
                'today_pnl': report.get('today_pnl'),
                'open_positions': report.get('open_positions'),
            },
        })

        return {
            'snapshot': snapshot,
            'performance_summary': {
                'total_value': report.get('total_value'),
                'cumulative_return_pct': report.get('cumulative_return_pct'),
                'today_pnl': report.get('today_pnl'),
            },
            'factor_compute': factor_result.get('status', 'unknown'),
        }

    def _phase_review(self, state: DailyOrchestratorState) -> Dict[str, Any]:
        """复盘阶段：唤醒 Agent 做智能复盘（工具链模式）"""
        context = state.context or {}

        # 获取今日交易数据
        today_trades = []
        today_pnl = context.get('performance', {}).get('today_pnl', 0)
        try:
            from adapters.outbound.repositories.simulation_repository import SimulationORMRepository
            sim_repo = SimulationORMRepository()
            trades = sim_repo.get_trades_by_account(
                TRADING_ACCOUNT,
                start_date=str(state.trade_date),
                end_date=str(state.trade_date),
            )
            today_trades = [
                {'symbol': t.get('symbol'), 'action': t.get('side'), 'amount': t.get('amount')}
                for t in (trades or [])[:10]
            ]
        except Exception:
            pass

        # 唤醒 Agent 做复盘决策（工具链引导）
        self._notify_agent('daily_review', {
            'trade_date': str(state.trade_date),
            'market_style': context.get('market_style'),
            'performance': context.get('performance', {}),
            'daily_snapshot': context.get('daily_snapshot', {}),
            'today_trades': today_trades,
            'today_pnl': today_pnl,
            'signals_executed': context.get('signals_executed', 0),
            'orders_created': context.get('orders_created', 0),
            'instructions': (
                '请使用工具链完成盘后复盘：\n'
                '1. portfolio_status → 查看持仓和盈亏\n'
                '2. performance_analyzer → 分析绩效\n'
                '3. rotation_verify → 检查轮动效果\n'
                '4. decision_history → 回顾今日决策\n'
                '5. experience_write → 写入经验\n'
                '6. feishu_notify → 发送复盘报告'
            ),
        })

        return {'status': 'agent_notified', 'event': 'daily_review'}

    # ==================== 状态管理 ====================

    def _get_or_create_state(self, trade_date: date) -> DailyOrchestratorState:
        """获取或创建今日状态记录"""
        state = self.session.query(DailyOrchestratorState).filter_by(
            orchestrator_name=self.name,
            trade_date=trade_date,
        ).first()

        if state is None:
            state = DailyOrchestratorState(
                orchestrator_name=self.name,
                trade_date=trade_date,
                current_phase=Phase.IDLE.value,
                phases_completed={},
                context={},
            )
            self.session.add(state)
            self.session.commit()
            self.session.refresh(state)
            logger.info("orchestrator_state_created", date=str(trade_date))

        self._today_state = state
        return state

    def _determine_phase(self, current_time: time) -> Phase:
        """根据当前时间判断应处于哪个阶段"""
        for phase, (start, end) in PHASE_SCHEDULE.items():
            if start <= current_time <= end:
                return phase

        # 不在任何阶段窗口内
        if current_time < time(8, 30):
            return Phase.IDLE
        elif current_time > time(17, 30):
            return Phase.IDLE

        return Phase.IDLE

    def _transition(self, state: DailyOrchestratorState, phase: Phase):
        """状态转换"""
        old_phase = state.current_phase
        state.current_phase = phase.value
        self.session.commit()
        logger.info(
            "orchestrator_transition",
            from_phase=old_phase,
            to_phase=phase.value,
            date=str(state.trade_date),
        )

    def _is_phase_completed(self, state: DailyOrchestratorState, phase_name: str) -> bool:
        """检查某阶段是否已完成"""
        completed = state.phases_completed or {}
        phase_data = completed.get(phase_name, {})
        return phase_data.get('status') == 'completed'

    def _mark_phase_completed(
        self, state: DailyOrchestratorState, phase_name: str, result: Any
    ):
        """标记阶段完成"""
        completed = state.phases_completed or {}
        completed[phase_name] = {
            'status': 'completed',
            'finished_at': datetime.now().isoformat(),
            'result_summary': str(result)[:200] if result else None,
        }
        state.phases_completed = completed
        self.session.commit()

    def _all_phases_done(self, state: DailyOrchestratorState) -> bool:
        """检查所有关键阶段是否完成"""
        completed = state.phases_completed or {}
        critical_phases = ['PRE_MARKET', 'MARKET_OPEN', 'POST_MARKET', 'REVIEW']
        return all(
            completed.get(p, {}).get('status') == 'completed'
            for p in critical_phases
        )

    def _update_context(self, state: DailyOrchestratorState, data: Dict):
        """更新运行上下文"""
        context = state.context or {}
        context.update(data)
        state.context = context
        self.session.commit()

    # ==================== Agent 通知 ====================

    def _notify_agent(self, event: str, data: Dict[str, Any]):
        """唤醒 Agent"""
        try:
            agent_service.notify_agent(event, data)
        except Exception as e:
            logger.warning(f"Failed to notify agent: {e}")

    # ==================== 恢复逻辑 ====================

    def resume_from_breakpoint(self):
        """进程重启后，从断点恢复

        检查今日状态，如果有未完成的阶段且当前时间仍在窗口内，则继续执行。
        """
        now = datetime.now()
        today = now.date()

        if today.weekday() >= 5:
            return

        state = self._get_or_create_state(today)

        if state.current_phase == Phase.IDLE.value:
            # 还没开始，正常走 tick 逻辑
            self.tick()
            return

        # 有未完成的阶段，尝试补跑
        current_phase = Phase(state.current_phase)
        current_idx = PHASE_ORDER.index(current_phase)

        logger.info(
            "orchestrator_resuming",
            date=str(today),
            current_phase=current_phase.value,
        )

        # 从当前阶段开始，补跑所有未完成且时间已过的阶段
        for i in range(current_idx, len(PHASE_ORDER)):
            phase = PHASE_ORDER[i]
            if phase == Phase.IDLE:
                continue
            if not self._is_phase_completed(state, phase.value):
                # 检查该阶段的时间窗口是否已过
                phase_start, phase_end = PHASE_SCHEDULE.get(phase, (time(0, 0), time(23, 59)))
                if now.time() >= phase_start:
                    self._execute_phase(state, phase)


# ============================================================
# 全局单例 + 调度注册
# ============================================================

_orchestrator: Optional[DailyOrchestrator] = None


def get_daily_orchestrator() -> DailyOrchestrator:
    """获取全局编排器实例"""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = DailyOrchestrator(name='main')
    return _orchestrator


def register_orchestrator_to_scheduler():
    """将编排器注册到 APScheduler

    在系统启动时调用：
        from application.services.daily_orchestrator import register_orchestrator_to_scheduler
        register_orchestrator_to_scheduler()
    """
    from application.services.unified_scheduler import get_unified_scheduler

    scheduler = get_unified_scheduler()
    orchestrator = get_daily_orchestrator()

    # 每分钟 tick 一次（工作日 08:00-18:00）
    scheduler.add_cron_job(
        func=orchestrator.tick,
        job_id='daily_orchestrator_tick',
        name='日常编排器 Tick',
        minute='*',
        hour='8-17',
        day_of_week='mon-fri',
    )

    logger.info("DailyOrchestrator registered to scheduler (tick every minute, Mon-Fri 08:00-17:59)")
