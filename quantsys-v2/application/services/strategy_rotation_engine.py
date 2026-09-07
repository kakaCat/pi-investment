"""
策略自适应轮动引擎 (Strategy Rotation Engine)

闭环流程：市场风格检测 → 策略表现评估 → 轮动方案生成 → Agent决策 → 执行

核心规则：
- 冷却期：策略切换后至少运行 5 天再评估
- 最大活跃策略数：3 个
- 淘汰条件：连续 10 天跑输基准 5% 以上
- 新策略上线：必须经过回测验证 + 小仓位试跑

使用方式：
    engine = StrategyRotationEngine()
    proposal = engine.evaluate()  # 每日盘前调用
    engine.execute_rotation(proposal)  # Agent 确认后执行
"""
from __future__ import annotations

from domain.ports import IAgentIntelligenceRepository, ISimulationRepository, IStrategyPerformanceRepository, IStrategyRepository

import structlog
from typing import Dict, Any, Optional, List
from datetime import datetime, date, timedelta

from application.services.market_style_detector import MarketStyleDetector
from application.services.strategy_weight_adjuster import StrategyWeightAdjuster
from application.services.agent_notification_service import agent_service

logger = structlog.get_logger(__name__)


# ============================================================
# 配置
# ============================================================

ROTATION_CONFIG = {
    'max_active_strategies': 3,        # 最大活跃策略数
    'cooldown_days': 5,                # 切换后冷却期（天）
    'underperform_days': 10,           # 连续跑输天数阈值
    'underperform_threshold': -0.05,   # 跑输基准阈值（-5%）
    'style_switch_confidence': 0.7,    # 风格切换置信度阈值
    'min_trial_days': 5,              # 新策略最小试跑天数
}

# 市场风格 → 推荐策略类型映射
STYLE_STRATEGY_MAP = {
    'bull': ['trend_following', 'momentum', 'multi_factor'],
    'bear': ['mean_reversion', 'defensive', 'indicator'],
    'oscillation': ['mean_reversion', 'indicator', 'multi_factor'],
    'value': ['indicator', 'multi_factor', 'mean_reversion'],
    'growth': ['trend_following', 'momentum', 'multi_factor'],
    'cycle': ['momentum', 'indicator', 'trend_following'],
}


# ============================================================
# 轮动引擎
# ============================================================

class StrategyRotationEngine:
    """策略自适应轮动引擎

    每日盘前调用 evaluate()，生成轮动建议。
    Agent 确认后调用 execute_rotation() 执行。
    """

    def __init__(self, config: Optional[Dict] = None, strategy_repo=None):
        self.config = {**ROTATION_CONFIG, **(config or {})}
        self.style_detector = MarketStyleDetector()
        self.weight_adjuster = StrategyWeightAdjuster()
        if strategy_repo is None:
            from infrastructure.services.enhanced_service_factory import EnhancedServiceFactory
            self.strategy_repo = EnhancedServiceFactory.resolve(IStrategyRepository)
        else:
            self.strategy_repo = strategy_repo

        # 上次轮动记录（内存缓存，重启从 DB 恢复）
        self._last_rotation_date: Optional[date] = None
        self._last_market_style: Optional[str] = None

    # ==================== 主流程 ====================

    def evaluate(self) -> Dict[str, Any]:
        """每日盘前评估，生成轮动建议

        Returns:
            {
                'needs_rotation': bool,
                'market_style': str,
                'style_changed': bool,
                'proposal': {...} or None,
                'reason': str,
            }
        """
        today = date.today()

        # 1. 检测市场风格
        style_result = self.style_detector.detect_market_style()
        current_style = style_result.get('style', 'unknown')
        confidence = style_result.get('confidence', 0)

        logger.info(
            "rotation_evaluate",
            style=current_style,
            confidence=confidence,
        )

        # 2. 检查冷却期
        if self._in_cooldown(today):
            return {
                'needs_rotation': False,
                'market_style': current_style,
                'style_changed': False,
                'proposal': None,
                'reason': f'冷却期内（上次轮动: {self._last_rotation_date}）',
            }

        # 3. 判断是否需要轮动（使用自适应阈值）
        adaptive_threshold = self._adaptive_confidence_threshold()
        style_changed = (
            self._last_market_style is not None
            and current_style != self._last_market_style
            and confidence >= adaptive_threshold
        )

        # 4. 检查策略表现衰减
        underperformers = self._check_underperformers()

        # 5. [反馈闭环] 检查历史验证反馈（verdict=negative 未处理）
        negative_feedback = self._get_negative_feedback()

        # 6. 生成轮动方案
        if style_changed or underperformers or negative_feedback:
            proposal = self._generate_proposal(
                current_style=current_style,
                confidence=confidence,
                style_changed=style_changed,
                underperformers=underperformers,
            )

            # [反馈闭环] 纳入回滚建议
            if negative_feedback:
                proposal['actions'].append({
                    'action': 'rollback_candidate',
                    'strategy_id': None,
                    'reason': f"上次轮动效果不佳(收益{negative_feedback.get('actual_return', 0):.2%})，建议评估回滚",
                    'original_decision_id': negative_feedback.get('decision_id'),
                })
                proposal['trigger'] = 'negative_verification'

            # 7. 通知 Agent 做最终决策
            self._notify_agent_for_decision(proposal)

            reason = self._build_reason(style_changed, underperformers)
            if negative_feedback:
                reason += f'；上次轮动验证为负面({negative_feedback.get("lesson", "")})'

            return {
                'needs_rotation': True,
                'market_style': current_style,
                'style_changed': style_changed,
                'proposal': proposal,
                'reason': reason,
            }

        # 无需轮动
        self._last_market_style = current_style
        return {
            'needs_rotation': False,
            'market_style': current_style,
            'style_changed': False,
            'proposal': None,
            'reason': '市场风格稳定，策略表现正常',
        }

    def execute_rotation(self, proposal: Dict[str, Any]) -> Dict[str, Any]:
        """执行轮动方案（Agent 确认后调用）

        Args:
            proposal: 轮动方案（来自 evaluate() 或 Agent 调整后）

        Returns:
            执行结果
        """
        actions = proposal.get('actions', [])
        executed = []
        errors = []

        for action in actions:
            try:
                strategy_id = action.get('strategy_id')
                # 2026-09-01：action 归一化（容忍 BUY/Deactivate 等大小写）
                action_type = (action.get('action') or '').strip().lower()  # activate / deactivate / adjust_weight

                if action_type == 'activate':
                    self.strategy_repo.update_strategy(strategy_id, {'is_active': True})
                elif action_type == 'deactivate':
                    self.strategy_repo.update_strategy(strategy_id, {'is_active': False})
                elif action_type == 'adjust_weight':
                    new_weight = action.get('new_weight', 1.0)
                    self.strategy_repo.update_strategy(strategy_id, {'weight': new_weight})
                else:
                    raise ValueError(f"未知轮动动作: '{action.get('action')}'（支持 activate/deactivate/adjust_weight）")

                executed.append(action)
                logger.info(
                    "rotation_action_executed",
                    strategy_id=strategy_id,
                    action=action_type,
                )

            except Exception as e:
                errors.append({'action': action, 'error': str(e)})
                logger.error(f"Rotation action failed: {e}")

        # 更新轮动记录
        self._last_rotation_date = date.today()
        self._last_market_style = proposal.get('target_style')

        result = {
            'success': len(errors) == 0,
            'executed': len(executed),
            'errors': len(errors),
            'error_details': errors,
            'rotation_date': str(date.today()),
        }

        logger.info("rotation_executed", **result)
        return result

    # ==================== 内部方法 ====================

    def _in_cooldown(self, today: date) -> bool:
        """检查是否在冷却期内"""
        if self._last_rotation_date is None:
            return False
        days_since = (today - self._last_rotation_date).days
        return days_since < self.config['cooldown_days']

    def _check_underperformers(self) -> List[Dict[str, Any]]:
        """检查表现衰减的策略

        Returns:
            表现差的策略列表 [{strategy_id, strategy_name, underperform_days, cumulative_return}]
        """
        underperformers = []

        try:
            strategies = self.strategy_repo.get_all(active_only=True)

            for strategy in strategies:
                strategy_id = strategy.get('id')
                strategy_name = strategy.get('strategy_name', '')

                # 获取最近 N 天的表现
                perf = self._get_recent_performance(
                    strategy_name,
                    days=self.config['underperform_days']
                )

                if perf and perf.get('cumulative_return', 0) < self.config['underperform_threshold']:
                    underperformers.append({
                        'strategy_id': strategy_id,
                        'strategy_name': strategy_name,
                        'cumulative_return': perf['cumulative_return'],
                        'days': perf.get('days', 0),
                    })

        except Exception as e:
            logger.error(f"Check underperformers failed: {e}")

        return underperformers

    def _get_recent_performance(self, strategy_name: str, days: int) -> Optional[Dict]:
        """获取策略最近 N 天的表现"""
        try:
            from infrastructure.services.enhanced_service_factory import EnhancedServiceFactory
            perf_repo = EnhancedServiceFactory.resolve(IStrategyPerformanceRepository)
            stats = perf_repo.get_statistics(strategy_name)

            if stats is None:
                return None

            return {
                'cumulative_return': stats.get('avg_pnl_pct', 0) * stats.get('total_trades', 0),
                'win_rate': stats.get('win_rate', 0),
                'total_trades': stats.get('total_trades', 0),
                'days': days,
            }

        except Exception as e:
            logger.warning(f"Get performance failed for {strategy_name}: {e}")
            return None

    def _generate_proposal(
        self,
        current_style: str,
        confidence: float,
        style_changed: bool,
        underperformers: List[Dict],
    ) -> Dict[str, Any]:
        """生成轮动方案"""
        actions = []

        # 获取当前活跃策略
        active_strategies = self.strategy_repo.get_all(active_only=True)
        active_ids = {s['id'] for s in active_strategies}

        # 获取所有策略（含非活跃）
        all_strategies = self.strategy_repo.get_all(active_only=False)

        # 推荐策略类型
        recommended_types = STYLE_STRATEGY_MAP.get(current_style, [])

        # 1. 停用表现差的策略
        for underperformer in underperformers:
            if underperformer['strategy_id'] in active_ids:
                actions.append({
                    'strategy_id': underperformer['strategy_id'],
                    'strategy_name': underperformer['strategy_name'],
                    'action': 'deactivate',
                    'reason': f"连续跑输: {underperformer['cumulative_return']:.2%}",
                })
                active_ids.discard(underperformer['strategy_id'])

        # 2. 根据市场风格调整权重
        for strategy in active_strategies:
            if strategy['id'] not in active_ids:
                continue  # 已被停用

            strategy_type = strategy.get('strategy_type', 'indicator')
            weight_result = self.weight_adjuster.get_weight(
                strategy_name=strategy.get('strategy_name', ''),
                strategy_type=strategy_type,
                market_style=current_style,
            )

            new_weight = weight_result.get('weight_adjustment', 1.0)

            # 如果权重变化超过 20%，建议调整
            current_weight = strategy.get('weight', 1.0) or 1.0
            if abs(new_weight - current_weight) / current_weight > 0.2:
                actions.append({
                    'strategy_id': strategy['id'],
                    'strategy_name': strategy.get('strategy_name', ''),
                    'action': 'adjust_weight',
                    'new_weight': round(new_weight, 2),
                    'old_weight': current_weight,
                    'reason': f"风格适配: {current_style} → 权重 {current_weight:.2f} → {new_weight:.2f}",
                })

        # 3. 启用推荐类型的备选策略（如果活跃数不足）
        if len(active_ids) < self.config['max_active_strategies']:
            candidates = [
                s for s in all_strategies
                if s['id'] not in active_ids
                and s.get('strategy_type') in recommended_types
                and s.get('status') != 'deprecated'
            ]

            # 按历史表现排序
            candidates.sort(key=lambda s: s.get('win_rate', 0) or 0, reverse=True)

            slots_available = self.config['max_active_strategies'] - len(active_ids)
            for candidate in candidates[:slots_available]:
                actions.append({
                    'strategy_id': candidate['id'],
                    'strategy_name': candidate.get('strategy_name', ''),
                    'action': 'activate',
                    'reason': f"风格匹配: {candidate.get('strategy_type')} 适合 {current_style}",
                })

        proposal = {
            'date': str(date.today()),
            'trigger': 'style_change' if style_changed else 'underperformance',
            'current_style': self._last_market_style,
            'target_style': current_style,
            'confidence': confidence,
            'actions': actions,
            'summary': self._summarize_actions(actions),
        }

        logger.info("rotation_proposal_generated", actions=len(actions))
        return proposal

    def _summarize_actions(self, actions: List[Dict]) -> str:
        """生成方案摘要"""
        activates = sum(1 for a in actions if a['action'] == 'activate')
        deactivates = sum(1 for a in actions if a['action'] == 'deactivate')
        adjustments = sum(1 for a in actions if a['action'] == 'adjust_weight')

        parts = []
        if activates:
            parts.append(f"启用{activates}个")
        if deactivates:
            parts.append(f"停用{deactivates}个")
        if adjustments:
            parts.append(f"调权{adjustments}个")

        return '、'.join(parts) if parts else '无变更'

    def _build_reason(self, style_changed: bool, underperformers: List) -> str:
        """构建轮动原因说明"""
        reasons = []
        if style_changed:
            reasons.append(f"市场风格切换: {self._last_market_style} → 新风格")
        if underperformers:
            names = [u['strategy_name'] for u in underperformers]
            reasons.append(f"策略表现衰减: {', '.join(names)}")
        return '；'.join(reasons)

    def _notify_agent_for_decision(self, proposal: Dict[str, Any]):
        """通知 Agent 做轮动决策"""
        try:
            agent_service.notify_agent('strategy_rotation', {
                'date': proposal['date'],
                'trigger': proposal['trigger'],
                'current_style': proposal.get('current_style'),
                'target_style': proposal.get('target_style'),
                'confidence': proposal.get('confidence'),
                'actions': proposal['actions'],
                'summary': proposal['summary'],
                'instructions': (
                    '策略轮动建议已生成，请做最终决策：\n'
                    '1. 同意轮动 → 调用 V2 API 执行\n'
                    '2. 部分同意 → 调整后执行\n'
                    '3. 否决 → 保持现状（记录原因）\n'
                    '决策结果将写入 agent_decisions 表。'
                ),
            })
        except Exception as e:
            logger.warning(f"Failed to notify agent for rotation: {e}")

    # ==================== Agent 工具链支持 ====================

    def get_proposal_context(self) -> Dict[str, Any]:
        """获取富数据轮动方案（供 /api/agent/rotation/proposal 调用）

        返回完整上下文供 Agent 多步推理：
        - 市场风格 + 置信度 + 历史
        - 当前策略组合 + 近期表现
        - 轮动建议 + 预期影响
        - 约束条件（冷却期等）
        - 下一步建议
        """
        today = date.today()

        # 1. 市场风格检测
        style_result = self.style_detector.detect_market_style()
        current_style = style_result.get('style', 'unknown')
        confidence = style_result.get('confidence', 0)

        # 风格历史（从 DB 或内存）
        style_history = self._get_style_history(limit=5)
        style_duration = self._get_style_duration_days(current_style)

        # 2. 当前活跃策略 + 表现
        active_strategies = self.strategy_repo.get_all(active_only=True)
        enriched_strategies = []
        for s in active_strategies:
            perf = self._get_recent_performance(
                s.get('strategy_name', ''), days=30
            ) or {}
            enriched_strategies.append({
                'id': s.get('id'),
                'name': s.get('strategy_name', ''),
                'type': s.get('strategy_type', 'indicator'),
                'weight': s.get('weight', 1.0),
                'recent_return_7d': perf.get('cumulative_return', 0) * 0.23,  # 近似7天
                'recent_return_30d': perf.get('cumulative_return', 0),
                'win_rate': perf.get('win_rate', 0),
                'total_trades': perf.get('total_trades', 0),
            })

        # 3. 生成轮动建议
        underperformers = self._check_underperformers()
        style_changed = (
            self._last_market_style is not None
            and current_style != self._last_market_style
            and confidence >= self.config['style_switch_confidence']
        )
        in_cooldown = self._in_cooldown(today)

        proposal_data = None
        if not in_cooldown and (style_changed or underperformers):
            raw_proposal = self._generate_proposal(
                current_style=current_style,
                confidence=confidence,
                style_changed=style_changed,
                underperformers=underperformers,
            )
            # 估算影响
            actions = raw_proposal.get('actions', [])
            position_change = len([a for a in actions if a['action'] in ('activate', 'deactivate')])
            estimated_cost = position_change * 800  # 粗略估算每次换仓成本
            proposal_data = {
                'needs_rotation': True,
                'trigger': raw_proposal.get('trigger', 'unknown'),
                'actions': actions,
                'summary': raw_proposal.get('summary', ''),
                'expected_impact': {
                    'position_change_count': position_change,
                    'estimated_cost': estimated_cost,
                    'risk_change': 'moderate' if position_change <= 1 else 'significant',
                },
            }
        else:
            proposal_data = {
                'needs_rotation': False,
                'trigger': None,
                'actions': [],
                'summary': '无需轮动' if not in_cooldown else '冷却期内',
                'expected_impact': None,
            }

        # 4. 约束条件
        cooldown_strategies = self._get_cooldown_strategies()

        # [反馈闭环] 读取近期被 Agent 拒绝的方案
        recent_rejects = self._get_reject_constraints()

        return {
            'market_style': current_style,
            'style_confidence': confidence,
            'style_duration_days': style_duration,
            'style_history': style_history,
            'active_strategies': enriched_strategies,
            'proposal': proposal_data,
            'constraints': {
                'cooldown_strategies': cooldown_strategies,
                'max_active': self.config['max_active_strategies'],
                'in_cooldown': in_cooldown,
                'last_rotation_date': str(self._last_rotation_date) if self._last_rotation_date else None,
                'recent_rejects': recent_rejects,
            },
            'next_steps': [
                '调用 rotation_simulate 查看模拟执行结果',
                '调用 portfolio_status 确认当前持仓',
                '调用 market_style_detect 独立验证风格判断',
            ],
        }

    def simulate_rotation(self, actions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """模拟执行轮动方案（不真正执行）

        计算：
        - 需要卖出哪些持仓（策略停用导致的清仓）
        - 交易成本估算
        - 执行后的组合状态
        - 风险指标变化
        """
        simulated_trades = []
        warnings = []

        # 获取当前持仓
        positions = self._get_current_positions()
        portfolio_before = self._get_portfolio_snapshot()

        # 分析每个 action 的影响
        deactivated_strategies = set()
        for action in actions:
            # 2026-09-01：action 归一化（容忍 BUY/Deactivate 等大小写，避免契约不匹配被静默忽略）
            action_type = (action.get('action') or action.get('type') or '').strip().lower()
            strategy_id = action.get('strategy_id')
            strategy_name = action.get('strategy_name', '')

            if action_type == 'deactivate':
                deactivated_strategies.add(strategy_name)
                # 查找该策略关联的持仓
                for pos in positions:
                    if pos.get('strategy') == strategy_name or pos.get('reason', '').find(strategy_name) >= 0:
                        pnl = pos.get('profit', 0)
                        simulated_trades.append({
                            'symbol': pos.get('symbol'),
                            'action': 'sell',
                            'shares': pos.get('shares', 0),
                            'price': pos.get('current_price', 0),
                            'reason': f'策略停用清仓: {strategy_name}',
                            'estimated_pnl': pnl,
                        })
                        if pnl < 0:
                            warnings.append(
                                f"卖出 {pos.get('symbol')} 将实现亏损 {pnl:.0f} 元"
                            )

            elif action_type == 'adjust_weight':
                old_w = action.get('old_weight', 1.0)
                new_w = action.get('new_weight', 1.0)
                if new_w < old_w * 0.7:
                    warnings.append(
                        f"策略 {strategy_name} 权重大幅下调 ({old_w:.2f}→{new_w:.2f})，"
                        f"相关持仓可能需要减仓"
                    )
            elif action_type not in ('activate',):
                # 2026-09-01：未知 action 不再静默忽略，给出可见告警
                warnings.append(
                    f"忽略无法识别的轮动动作: '{action.get('action') or action.get('type')}' "
                    f"（支持 activate/deactivate/adjust_weight）"
                )

        # 估算交易成本
        total_trade_value = sum(
            t.get('shares', 0) * t.get('price', 0) for t in simulated_trades
        )
        estimated_cost = total_trade_value * 0.0013  # 手续费万3 + 印花税千1

        # 计算执行后状态
        cash_freed = sum(
            t.get('shares', 0) * t.get('price', 0) for t in simulated_trades
        )
        portfolio_after = {
            'cash': portfolio_before.get('cash', 0) + cash_freed - estimated_cost,
            'positions': portfolio_before.get('positions', 0) - len(simulated_trades),
            'total': portfolio_before.get('total', 0) - estimated_cost,
        }

        # 风险指标变化
        risk_before = self._calculate_risk_metrics(positions)
        remaining_positions = [
            p for p in positions
            if p.get('symbol') not in {t['symbol'] for t in simulated_trades}
        ]
        risk_after = self._calculate_risk_metrics(remaining_positions)

        return {
            'simulated_trades': simulated_trades,
            'portfolio_before': portfolio_before,
            'portfolio_after': portfolio_after,
            'estimated_cost': round(estimated_cost, 2),
            'risk_metrics_change': {
                'max_position_pct': {
                    'before': risk_before.get('max_position_pct', 0),
                    'after': risk_after.get('max_position_pct', 0),
                },
                'sector_concentration': {
                    'before': risk_before.get('sector_concentration', 0),
                    'after': risk_after.get('sector_concentration', 0),
                },
            },
            'warnings': warnings,
            'next_steps': [
                '确认无误后调用 rotation_execute 真正执行',
                '如有顾虑可修改 actions 后重新模拟',
            ],
        }

    def verify_rotation(self, rotation_date: Optional[str] = None) -> Dict[str, Any]:
        """验证轮动效果（对比预期 vs 实际）

        Args:
            rotation_date: 轮动执行日期（默认取最近一次）
        """
        # 确定轮动日期
        target_date = rotation_date or (
            str(self._last_rotation_date) if self._last_rotation_date else None
        )
        if not target_date:
            return {
                'success': False,
                'error': '未找到轮动记录',
                'recommendation': '暂无轮动历史可验证',
            }

        try:
            from datetime import datetime as dt
            rot_date = dt.strptime(target_date, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            rot_date = self._last_rotation_date or date.today()

        days_since = (date.today() - rot_date).days

        # 获取轮动后的实际表现
        actual_return = 0.0
        max_drawdown = 0.0
        try:
            from infrastructure.services.enhanced_service_factory import EnhancedServiceFactory
            sim_repo = EnhancedServiceFactory.resolve(ISimulationRepository)
            snapshots_raw = sim_repo.get_equity_snapshots(
                account_name='rotation_main',
                limit=90,
            )
            # 转为 dict 并过滤轮动日期之后的快照（按日期正序）
            snapshots = sorted(
                [s.to_dict() for s in (snapshots_raw or [])
                 if s.snapshot_date and str(s.snapshot_date) >= str(rot_date)],
                key=lambda x: x.get('date', '')
            )
            if snapshots and len(snapshots) >= 2:
                first_value = snapshots[0].get('total_value', 1)
                last_value = snapshots[-1].get('total_value', 1)
                actual_return = (last_value - first_value) / first_value if first_value else 0
                # 计算最大回撤
                peak = first_value
                for snap in snapshots:
                    v = snap.get('total_value', 0)
                    if v > peak:
                        peak = v
                    dd = (v - peak) / peak if peak else 0
                    if dd < max_drawdown:
                        max_drawdown = dd
        except Exception as e:
            logger.warning(f"Verify rotation: get snapshots failed: {e}")

        # 新策略表现
        new_strategies_perf = []
        active_strategies = self.strategy_repo.get_all(active_only=True)
        for s in active_strategies:
            perf = self._get_recent_performance(s.get('strategy_name', ''), days=days_since)
            if perf:
                new_strategies_perf.append({
                    'name': s.get('strategy_name', ''),
                    'type': s.get('strategy_type', ''),
                    'return': perf.get('cumulative_return', 0),
                    'win_rate': perf.get('win_rate', 0),
                })

        # 判定
        expected_return = 0.02  # 默认预期 2%
        if actual_return >= expected_return * 0.7:
            verdict = 'positive'
            recommendation = '轮动效果符合预期，建议保持当前组合'
        elif actual_return >= 0:
            verdict = 'neutral'
            recommendation = '轮动效果一般，继续观察，暂不调整'
        else:
            verdict = 'negative'
            recommendation = '轮动后表现为负，建议重新评估策略组合'

        # [反馈闭环] 将验证结果写回决策记录
        self._persist_verification(rot_date, verdict, actual_return, max_drawdown)

        return {
            'rotation_date': target_date,
            'days_since': days_since,
            'expected': {'return_7d': expected_return, 'risk_level': 'moderate'},
            'actual': {
                'return': round(actual_return, 4),
                'max_drawdown': round(max_drawdown, 4),
            },
            'verdict': verdict,
            'new_strategies_performance': new_strategies_perf,
            'recommendation': recommendation,
        }

    # ==================== 辅助方法（工具链支持） ====================

    def _get_style_history(self, limit: int = 5) -> List[Dict]:
        """获取最近 N 次风格变化记录"""
        try:
            from infrastructure.persistence.orm import get_session
            from sqlalchemy import text
            session = get_session()
            # 注意：表里没有 detected_at 列（实际为 created_at），用错列名会被
            # 下面 except 吞掉导致风格历史恒为空——2026-08-04 修复
            rows = session.execute(text(
                "SELECT style, confidence, created_at FROM quant.market_style_state "
                "ORDER BY created_at DESC LIMIT :limit"
            ), {'limit': limit}).fetchall()
            return [
                {'style': r[0], 'confidence': float(r[1]) if r[1] else 0, 'date': str(r[2])}
                for r in rows
            ]
        except Exception:
            return []

    def _get_style_duration_days(self, current_style: str) -> int:
        """当前风格持续天数"""
        history = self._get_style_history(limit=10)
        if not history:
            return 0
        # 找到最近一次风格变化的日期
        for i, h in enumerate(history):
            if h.get('style') != current_style:
                # 第 i 条是不同风格，说明 current_style 从第 i-1 条开始
                try:
                    from datetime import datetime as dt
                    change_date = dt.fromisoformat(history[i]['date'].replace(' ', 'T')).date()
                    return (date.today() - change_date).days
                except (ValueError, TypeError, IndexError):
                    return 0
        return len(history) * 2  # 粗略估计

    def _get_cooldown_strategies(self) -> List[int]:
        """获取冷却中的策略ID列表"""
        # 简化实现：最近 cooldown_days 内被激活/停用的策略
        cooldown = []
        if self._last_rotation_date:
            days_since = (date.today() - self._last_rotation_date).days
            if days_since < self.config['cooldown_days']:
                # 所有活跃策略都在冷却中
                active = self.strategy_repo.get_all(active_only=True)
                cooldown = [s['id'] for s in active]
        return cooldown

    def _get_current_positions(self) -> List[Dict]:
        """获取当前持仓"""
        try:
            from infrastructure.services.enhanced_service_factory import EnhancedServiceFactory
            sim_repo = EnhancedServiceFactory.resolve(ISimulationRepository)
            positions = sim_repo.get_all_positions(account_name='rotation_main')
            return positions or []
        except Exception:
            return []

    def _get_portfolio_snapshot(self) -> Dict[str, Any]:
        """获取当前组合快照"""
        try:
            from infrastructure.services.enhanced_service_factory import EnhancedServiceFactory
            sim_repo = EnhancedServiceFactory.resolve(ISimulationRepository)
            account = sim_repo.get_account('rotation_main')
            if account:
                return {
                    'cash': account.get('cash_available', 0),
                    'positions': account.get('position_count', 0),
                    'total': account.get('total_value', 0),
                }
        except Exception:
            pass
        return {'cash': 0, 'positions': 0, 'total': 0}

    def _calculate_risk_metrics(self, positions: List[Dict]) -> Dict[str, float]:
        """计算持仓风险指标"""
        if not positions:
            return {'max_position_pct': 0, 'sector_concentration': 0}

        total_value = sum(p.get('market_value', 0) for p in positions)
        if total_value == 0:
            return {'max_position_pct': 0, 'sector_concentration': 0}

        # 最大单票占比
        max_pct = max(
            (p.get('market_value', 0) / total_value for p in positions),
            default=0
        )

        # 行业集中度（简化：按 symbol 前缀分组）
        sectors: Dict[str, float] = {}
        for p in positions:
            sector = p.get('sector', p.get('symbol', '')[:3])
            sectors[sector] = sectors.get(sector, 0) + p.get('market_value', 0)
        max_sector = max((v / total_value for v in sectors.values()), default=0)

        return {
            'max_position_pct': round(max_pct, 3),
            'sector_concentration': round(max_sector, 3),
        }

    # ==================== 状态恢复 ====================

    def load_state(self):
        """从 DB 恢复轮动状态（进程重启后调用）"""
        try:
            # 从 strategy_weight_config 或专门的轮动日志表恢复
            # 简化实现：从最近的策略更新时间推断
            strategies = self.strategy_repo.get_all(active_only=True)
            if strategies:
                # 使用最新的 updated_at 作为上次轮动时间
                latest_update = max(
                    (s.get('updated_at') for s in strategies if s.get('updated_at')),
                    default=None
                )
                if latest_update:
                    if isinstance(latest_update, str):
                        self._last_rotation_date = datetime.fromisoformat(latest_update).date()
                    elif isinstance(latest_update, datetime):
                        self._last_rotation_date = latest_update.date()

            logger.info(
                "rotation_state_loaded",
                last_rotation=str(self._last_rotation_date),
            )

        except Exception as e:
            logger.warning(f"Failed to load rotation state: {e}")

    # ==================== 反馈闭环方法 ====================

    def _get_negative_feedback(self) -> Optional[Dict]:
        """查找近期 verdict=negative 且未处理的轮动验证"""
        try:
            from infrastructure.services.enhanced_service_factory import EnhancedServiceFactory
            repo = EnhancedServiceFactory.resolve(IAgentIntelligenceRepository)
            recent = repo.get_recent_decisions(limit=10)
            for d in recent:
                eval_result = d.get('evaluation_result') or {}
                if (d.get('decision_type') == 'rotation'
                        and eval_result.get('verdict') == 'negative'
                        and not eval_result.get('action_taken')):
                    return {
                        'decision_id': d['decision_id'],
                        'verdict': 'negative',
                        'actual_return': eval_result.get('actual_return', 0),
                        'lesson': d.get('learned_lesson', ''),
                        'original_actions': d.get('parameters', {}).get('actions', []),
                    }
            return None
        except Exception as e:
            logger.warning(f"Get negative feedback failed: {e}")
            return None

    def _persist_verification(self, rot_date, verdict: str, actual_return: float, max_drawdown: float):
        """将验证结果写入 agent_decisions 的 evaluation 字段"""
        try:
            from infrastructure.services.enhanced_service_factory import EnhancedServiceFactory
            repo = EnhancedServiceFactory.resolve(IAgentIntelligenceRepository)
            decisions = repo.get_recent_decisions(limit=20)
            for d in decisions:
                if (d.get('decision_type') == 'rotation'
                        and str(rot_date) in str(d.get('created_at', ''))):
                    repo.update_evaluation(d['decision_id'], {
                        'verdict': verdict,
                        'actual_return': actual_return,
                        'max_drawdown': max_drawdown,
                        'success': verdict == 'positive',
                        'learned_lesson': self._generate_lesson(verdict, actual_return),
                    })
                    logger.info("verification_persisted", decision_id=d['decision_id'], verdict=verdict)
                    break
        except Exception as e:
            logger.warning(f"Persist verification failed: {e}")

    def _generate_lesson(self, verdict: str, actual_return: float) -> str:
        """根据验证结果生成经验教训"""
        if verdict == 'positive':
            return f'轮动成功，收益{actual_return:.2%}，当前策略组合有效'
        elif verdict == 'negative':
            return f'轮动失败，收益{actual_return:.2%}，需重新审视策略选择逻辑'
        return f'轮动效果中性，收益{actual_return:.2%}，继续观察'

    def _get_reject_constraints(self) -> List[Dict]:
        """获取近期被 Agent 拒绝的方案，避免重复推荐"""
        try:
            from infrastructure.services.enhanced_service_factory import EnhancedServiceFactory
            repo = EnhancedServiceFactory.resolve(IAgentIntelligenceRepository)
            recent = repo.get_recent_decisions(limit=20)
            rejects = []
            for d in recent:
                if d.get('decision_type') == 'rotation_reject':
                    created = d.get('created_at', '')
                    if created and (datetime.now() - datetime.fromisoformat(created)).days <= 14:
                        rejects.append({
                            'rejected_actions': d.get('context', {}).get('actions', []),
                            'reason': d.get('reasoning'),
                            'date': created[:10],
                        })
            return rejects
        except Exception as e:
            logger.warning(f"Get reject constraints failed: {e}")
            return []

    def _adaptive_confidence_threshold(self) -> float:
        """根据历史决策成功率动态调整风格切换置信度阈值"""
        try:
            from infrastructure.services.enhanced_service_factory import EnhancedServiceFactory
            repo = EnhancedServiceFactory.resolve(IAgentIntelligenceRepository)
            recent = repo.get_recent_decisions(limit=30)
            rotations = [
                d for d in recent
                if d.get('decision_type') == 'rotation' and d.get('success') is not None
            ]
            if len(rotations) >= 3:
                success_rate = sum(1 for d in rotations if d['success']) / len(rotations)
                # 成功率高 → 降低阈值（更敢切）；成功率低 → 提高阈值（更谨慎）
                base = self.config['style_switch_confidence']  # 0.7
                adjusted = base - (success_rate - 0.5) * 0.2  # 范围 0.6~0.8
                logger.info("adaptive_threshold", base=base, success_rate=success_rate, adjusted=adjusted)
                return max(0.5, min(0.9, adjusted))
            return self.config['style_switch_confidence']
        except Exception:
            return self.config['style_switch_confidence']


# ============================================================
# 全局单例
# ============================================================

_rotation_engine: Optional[StrategyRotationEngine] = None


def get_rotation_engine() -> StrategyRotationEngine:
    """获取全局轮动引擎实例"""
    global _rotation_engine
    if _rotation_engine is None:
        _rotation_engine = StrategyRotationEngine()
        _rotation_engine.load_state()
    return _rotation_engine
