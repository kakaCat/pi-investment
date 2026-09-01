"""
Agent 决策执行 API

Agent 通过此 API 将决策反馈给 V2 执行：
- 调整策略权重
- 执行策略轮动
- 修改风控参数
- 记录决策日志
- 查询绩效报告

Agent 收到 wake 事件后，分析完毕调用这些接口执行决策。
"""
from fastapi import APIRouter, Body
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
import structlog

logger = structlog.get_logger(__name__)

router = APIRouter(
    prefix="/api/agent",
    tags=["Agent Decision - Agent决策执行"]
)


# ============================================================
# 请求模型
# ============================================================

class StrategyWeightUpdate(BaseModel):
    """策略权重调整"""
    strategy_id: int = Field(..., description="策略ID")
    new_weight: float = Field(..., ge=0, le=3.0, description="新权重")
    reason: str = Field('', description="调整原因")


class RotationExecution(BaseModel):
    """轮动执行"""
    actions: List[Dict[str, Any]] = Field(..., description="轮动动作列表")
    decision: str = Field('approve', description="决策: approve/partial/reject")
    reason: str = Field('', description="决策原因")
    dry_run: bool = Field(False, description="是否模拟执行（不实际落库，2026-09-01 补：此前工具层 dry_run 被忽略会真执行）")


class RotationSimulate(BaseModel):
    """轮动模拟"""
    actions: List[Dict[str, Any]] = Field(..., description="轮动动作列表")


class RiskParamUpdate(BaseModel):
    """风控参数调整"""
    stop_loss_pct: Optional[float] = Field(None, ge=-0.3, le=0, description="止损比例")
    take_profit_pct: Optional[float] = Field(None, ge=0, le=1.0, description="止盈比例")
    max_position_pct: Optional[float] = Field(None, ge=0.05, le=0.5, description="单票最大仓位")
    max_total_position_pct: Optional[float] = Field(None, ge=0.1, le=1.0, description="总仓位上限")
    reason: str = Field('', description="调整原因")


class DecisionLog(BaseModel):
    """决策日志"""
    decision_type: str = Field(..., description="决策类型: rotation/risk/position/style")
    action: str = Field(..., description="具体操作")
    reason: str = Field(..., description="决策原因")
    context: Optional[Dict] = Field(None, description="决策上下文")
    outcome_expected: Optional[str] = Field(None, description="预期结果")


# ============================================================
# API 端点
# ============================================================

@router.post("/strategy/weight", summary="调整策略权重")
async def update_strategy_weight(update: StrategyWeightUpdate):
    """Agent 调整策略权重"""
    try:
        from adapters.outbound.repositories import StrategyORMRepository
        repo = StrategyORMRepository()

        success = repo.update_strategy(update.strategy_id, {
            'weight': update.new_weight,
        })

        if success:
            logger.info(
                "agent_strategy_weight_updated",
                strategy_id=update.strategy_id,
                new_weight=update.new_weight,
                reason=update.reason,
            )
            return {
                'success': True,
                'message': f'策略 {update.strategy_id} 权重已调整为 {update.new_weight}',
            }
        else:
            return {'success': False, 'error': 'Strategy not found or update failed'}

    except Exception as e:
        logger.error(f"Agent strategy weight update failed: {e}")
        return {'success': False, 'error': str(e)}


# ============================================================
# API 端点 — 轮动决策链
# ============================================================

@router.get("/rotation/proposal", summary="获取轮动方案（富数据）")
async def get_rotation_proposal():
    """Agent 获取轮动方案 — 决策链第一步

    返回完整上下文供 Agent 多步推理：
    - 市场风格 + 置信度 + 历史
    - 当前策略组合 + 近期表现
    - 轮动建议 + 预期影响
    - 约束条件（冷却期等）
    - 下一步建议
    """
    try:
        from application.services.strategy_rotation_engine import get_rotation_engine
        engine = get_rotation_engine()
        context = engine.get_proposal_context()

        return {'success': True, 'data': context}

    except Exception as e:
        logger.error(f"Get rotation proposal failed: {e}")
        return {'success': False, 'error': str(e)}


@router.post("/rotation/simulate", summary="模拟轮动执行")
async def simulate_rotation(sim: RotationSimulate):
    """Agent 模拟执行轮动 — 决策链第二步

    不真正执行，返回模拟交易、组合变化、风险提示。
    Agent 可以修改 actions 后重新模拟。
    """
    try:
        from application.services.strategy_rotation_engine import get_rotation_engine
        engine = get_rotation_engine()
        result = engine.simulate_rotation(sim.actions)

        return {'success': True, 'data': result}

    except Exception as e:
        logger.error(f"Simulate rotation failed: {e}")
        return {'success': False, 'error': str(e)}


@router.post("/rotation/execute", summary="执行策略轮动")
async def execute_rotation(execution: RotationExecution):
    """Agent 确认并执行策略轮动 — 决策链第三步

    执行后返回完整状态：新策略组合、持仓变化、决策ID。
    """
    try:
        # 2026-09-01：dry_run=true 时只模拟不执行（此前工具层 dry_run 被忽略会真下单）
        if execution.dry_run:
            from application.services.strategy_rotation_engine import get_rotation_engine
            engine = get_rotation_engine()
            sim = engine.simulate_rotation(execution.actions)
            return {
                'success': True,
                'data': {
                    'decision': execution.decision,
                    'dry_run': True,
                    'simulated': sim,
                    'executed_actions': [],
                    'failed_actions': [],
                    'portfolio_state': None,
                    'decision_id': f"dec_dry_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                    'next_steps': ['dry_run 未落库，确认后去掉 dry_run 重新调用'],
                },
            }

        if execution.decision == 'reject':
            logger.info("agent_rotation_rejected", reason=execution.reason)

            # 持久化拒绝记录（反馈闭环：避免重复推荐被拒方案）
            try:
                from adapters.outbound.repositories.agent_intelligence_repository import AgentIntelligenceORMRepository
                repo = AgentIntelligenceORMRepository()
                repo.create_decision({
                    'decision_type': 'rotation_reject',
                    'context': {'actions': execution.actions},
                    'parameters': {'decision': 'reject'},
                    'reasoning': execution.reason,
                    'created_by': 'agent',
                })
            except Exception as e:
                logger.warning(f"Persist reject failed: {e}")

            return {
                'success': True,
                'data': {
                    'decision': 'reject',
                    'reason': execution.reason,
                    'executed_actions': [],
                    'failed_actions': [],
                    'new_active_strategies': [],
                    'portfolio_state': None,
                    'decision_id': f"dec_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                    'next_steps': [
                        '调用 decision_log 记录否决原因',
                        '调用 rotation_proposal 查看是否有新方案',
                    ],
                },
            }

        from application.services.strategy_rotation_engine import get_rotation_engine
        engine = get_rotation_engine()

        proposal = {'actions': execution.actions, 'target_style': None}
        result = engine.execute_rotation(proposal)

        # 获取执行后的策略列表
        from adapters.outbound.repositories import StrategyORMRepository
        repo = StrategyORMRepository()
        new_strategies = repo.get_all(active_only=True)

        # 获取执行后的持仓状态
        portfolio_state = None
        try:
            from adapters.outbound.repositories.simulation_repository import SimulationORMRepository
            sim_repo = SimulationORMRepository()
            account = sim_repo.get_account('rotation_main')
            if account:
                portfolio_state = {
                    'cash': account.get('cash_available', 0),
                    'total_value': account.get('total_value', 0),
                    'positions_count': len(sim_repo.get_all_positions('rotation_main') or []),
                }
        except Exception:
            pass

        decision_id = f"dec_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        logger.info(
            "agent_rotation_executed",
            decision=execution.decision,
            executed=result.get('executed', 0),
            decision_id=decision_id,
        )

        return {
            'success': result.get('success', False),
            'data': {
                'executed_actions': execution.actions[:result.get('executed', 0)],
                'failed_actions': result.get('error_details', []),
                'new_active_strategies': [
                    {'id': s.get('id'), 'name': s.get('strategy_name'), 'type': s.get('strategy_type')}
                    for s in (new_strategies or [])
                ],
                'portfolio_state': portfolio_state,
                'decision_id': decision_id,
                'reason': execution.reason,
                'next_steps': [
                    '调用 decision_record 记录决策原因和预期',
                    '明日调用 rotation_verify 验证执行效果',
                    '通过 feishu_notify 通知用户轮动结果',
                ],
            },
        }

    except Exception as e:
        logger.error(f"Agent rotation execution failed: {e}")
        return {'success': False, 'error': str(e)}


@router.get("/rotation/verify", summary="验证轮动效果")
async def verify_rotation(rotation_date: Optional[str] = None):
    """Agent 验证轮动效果 — 决策链第四步（复盘用）

    对比轮动前后的实际表现 vs 预期。
    """
    try:
        from application.services.strategy_rotation_engine import get_rotation_engine
        engine = get_rotation_engine()
        result = engine.verify_rotation(rotation_date)

        return {'success': True, 'data': result}

    except Exception as e:
        logger.error(f"Verify rotation failed: {e}")
        return {'success': False, 'error': str(e)}


@router.post("/risk/update", summary="调整风控参数")
async def update_risk_params(update: RiskParamUpdate):
    """Agent 调整风控参数"""
    try:
        from live_trading.paper_trading_engine import PaperTradingEngine
        engine = PaperTradingEngine(account_name='rotation_main')

        changes = {}
        if update.stop_loss_pct is not None:
            engine.risk_config['stop_loss_pct'] = update.stop_loss_pct
            changes['stop_loss_pct'] = update.stop_loss_pct
        if update.take_profit_pct is not None:
            engine.risk_config['take_profit_pct'] = update.take_profit_pct
            changes['take_profit_pct'] = update.take_profit_pct
        if update.max_position_pct is not None:
            engine.risk_config['max_single_position_pct'] = update.max_position_pct
            changes['max_single_position_pct'] = update.max_position_pct

        logger.info("agent_risk_params_updated", changes=changes, reason=update.reason)

        return {
            'success': True,
            'message': f'风控参数已调整: {changes}',
            'changes': changes,
        }

    except Exception as e:
        logger.error(f"Agent risk param update failed: {e}")
        return {'success': False, 'error': str(e)}


@router.post("/decision/log", summary="记录决策日志")
async def log_decision(decision: DecisionLog):
    """Agent 记录决策日志（用于复盘和经验积累）

    持久化到 agent_decisions 表，供轮动引擎读取反馈。
    """
    try:
        from adapters.outbound.repositories.agent_intelligence_repository import AgentIntelligenceORMRepository
        repo = AgentIntelligenceORMRepository()
        record = repo.create_decision({
            'decision_type': decision.decision_type,
            'context': decision.context or {},
            'parameters': {'action': decision.action, 'outcome_expected': decision.outcome_expected},
            'reasoning': decision.reason,
            'created_by': 'agent',
        })

        logger.info("agent_decision_logged", decision_id=record.get('decision_id'))

        return {
            'success': True,
            'message': '决策已记录',
            'decision_id': record.get('decision_id'),
        }

    except Exception as e:
        logger.error(f"Agent decision log failed: {e}")
        return {'success': False, 'error': str(e)}


@router.get("/performance", summary="查询绩效报告")
async def get_performance():
    """Agent 查询当前绩效（用于复盘决策）

    增强版：包含决策上下文、策略贡献、风险暴露。
    """
    try:
        from application.services.performance_tracker import get_performance_tracker
        tracker = get_performance_tracker()
        report = tracker.get_full_report()

        # 增强：添加决策上下文
        recent_decisions = []
        try:
            # 从日志或 DB 获取最近决策
            recent_decisions = _get_recent_decisions(limit=5)
        except Exception:
            pass

        # 增强：策略贡献
        strategy_contribution = report.get('strategy_attribution', [])

        # 增强：风险暴露
        risk_exposure = None
        try:
            from application.services.strategy_rotation_engine import get_rotation_engine
            engine = get_rotation_engine()
            positions = engine._get_current_positions()
            risk_exposure = engine._calculate_risk_metrics(positions)
        except Exception:
            pass

        report['recent_decisions'] = recent_decisions
        report['strategy_contribution'] = strategy_contribution
        report['risk_exposure'] = risk_exposure

        return {
            'success': True,
            'data': report,
        }

    except Exception as e:
        logger.error(f"Performance query failed: {e}")
        return {'success': False, 'error': str(e)}


def _get_recent_decisions(limit: int = 5) -> List[Dict]:
    """获取最近的 Agent 决策记录（从 agent_decisions 表查询）"""
    try:
        from adapters.outbound.repositories.agent_intelligence_repository import AgentIntelligenceORMRepository
        repo = AgentIntelligenceORMRepository()
        return repo.get_recent_decisions(limit=limit)
    except Exception as e:
        logger.warning(f"Get recent decisions failed: {e}")
        return []


@router.get("/performance/quick", summary="快速绩效指标")
async def get_quick_performance():
    """快速获取关键绩效指标"""
    try:
        from application.services.performance_tracker import get_performance_tracker
        tracker = get_performance_tracker()
        stats = tracker.get_quick_stats()

        return {
            'success': True,
            'data': stats,
        }

    except Exception as e:
        return {'success': False, 'error': str(e)}


@router.get("/orchestrator/status", summary="编排器状态")
async def get_orchestrator_status():
    """查询日常编排器当前状态"""
    try:
        from application.services.daily_orchestrator import get_daily_orchestrator
        orchestrator = get_daily_orchestrator()
        status = orchestrator.get_status()

        return {
            'success': True,
            'data': status,
        }

    except Exception as e:
        return {'success': False, 'error': str(e)}


@router.get("/positions", summary="当前持仓")
async def get_positions():
    """查询当前持仓"""
    try:
        from live_trading.paper_trading_engine import PaperTradingEngine
        engine = PaperTradingEngine(account_name='rotation_main')
        positions = engine.get_current_positions()

        return {
            'success': True,
            'data': {
                'count': len(positions),
                'positions': positions,
            },
        }

    except Exception as e:
        return {'success': False, 'error': str(e)}


@router.get("/strategies/active", summary="活跃策略列表")
async def get_active_strategies():
    """查询当前活跃策略"""
    try:
        from adapters.outbound.repositories import StrategyORMRepository
        repo = StrategyORMRepository()
        strategies = repo.get_all(active_only=True)

        return {
            'success': True,
            'data': {
                'count': len(strategies),
                'strategies': strategies,
            },
        }

    except Exception as e:
        return {'success': False, 'error': str(e)}
