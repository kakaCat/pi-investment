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

    def __init__(self, name: str = 'main', simulation_repo=None):
        """初始化日常编排器

        Args:
            name: 编排器名称
            simulation_repo: 模拟交易仓库（依赖注入）
        """
        self.name = name
        self._session_override = None
        self._today_state: Optional[DailyOrchestratorState] = None
        self._simulation_repo = simulation_repo

    @property
    def session(self):
        """每次经 scoped_session 现取（不在实例上跨 tick 缓存）：

        tick 线程每轮结束会 close_session() 释放连接（orchestrator_bootstrap
        ._monitor_loop，2026-08-18 后台线程连接治理），构造期缓存的 session
        被移出注册表后会脱离该清理路径，重新查询时占住新连接永不归还。
        测试可经 setter 注入 mock（override 优先）。
        """
        if self._session_override is not None:
            return self._session_override
        return get_session()

    @session.setter
    def session(self, value):
        self._session_override = value

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

        # 条件委托撮合：MARKET_OPEN 窗口（9:25-9:35）内 9:31 起的每个 tick 都撮合。
        # 必须挂在 tick 层——_phase_market_open 只在进入阶段时执行一次（通常 9:25，
        # 早于 9:31 门槛），挂在那里会导致挂单永远不被撮合。
        # 幂等：已处理的订单不再是 pending，重复调用无副作用。
        if target_phase == Phase.MARKET_OPEN and now.time() >= time(9, 31):
            self._match_pending_orders()

    def _match_pending_orders(self) -> None:
        """撮合盘前挂单（execute_at='market_open'），失败不阻断主流程"""
        try:
            from application.services.account_trading_service import (
                AccountTradingService,
            )
            match_result = AccountTradingService().execute_pending_orders()
            if match_result['executed'] or match_result['failed']:
                logger.info("market_open: pending_orders_matched",
                            executed=match_result['executed'],
                            failed=match_result['failed'])
        except Exception as e:
            logger.error("market_open: pending_orders_match_error", error=str(e))

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
        if self._simulation_repo is None:
            from infrastructure.services.enhanced_service_factory import EnhancedServiceFactory
            from domain.ports import ISimulationRepository
            simulation_repo = EnhancedServiceFactory.resolve(ISimulationRepository)
        else:
            simulation_repo = self._simulation_repo

        settled = simulation_repo.settle_t1(TRADING_ACCOUNT)
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
                '5. 全部处理完：experience_write 摘要 + feishu_notify 简报'
            ),
        })

        # 条件委托撮合：盘前挂单（execute_at='market_open'）在 9:31 起自动撮合。
        # 主挂载点在 tick()（每个 tick 幂等）；此处兜底覆盖手动 run_phase/迟到启动场景。
        if datetime.now().time() >= time(9, 31):
            self._match_pending_orders()

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
        if self._simulation_repo is None:
            from infrastructure.services.enhanced_service_factory import EnhancedServiceFactory
            from domain.ports import ISimulationRepository
            repo = EnhancedServiceFactory.resolve(ISimulationRepository)
        else:
            repo = self._simulation_repo

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
            if self._simulation_repo is None:
                from infrastructure.services.enhanced_service_factory import EnhancedServiceFactory
                from domain.ports import ISimulationRepository
                sim_repo = EnhancedServiceFactory.resolve(ISimulationRepository)
            else:
                sim_repo = self._simulation_repo
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

# 编排器 tick 的调度宿主 = FastAPI lifespan（orchestrator_bootstrap.py，2026-08-13 起）。
# 原 register_orchestrator_to_scheduler（APScheduler/unified_scheduler 路线）
# 已随 scheduler_daemon 一并删除。
