"""机会候选 → 结构化观察规则。

纪律（2026-11-18 反馈修复）：
* 评分只负责筛选候选，不再用 ``latest_close * 0.98`` 伪造“买入区”。
* 自动建规必须同时具有结构位、失效位、目标位和失效后动作；缺任一项即明确跳过。
* 账户归属显式建模：传入 account 时写 account + linked_account；无账户时只能是全局
  trend_observe，摘要层不得把它误报为缺账户的入场规则。

本服务只创建观察规则，不创建交易委托，也不替机会评分器编造市场结构。
"""
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import structlog

from qs_watch.domain.watch.models import EscalationPolicy
from qs_watch.domain.watch.ports import IWatchRuleRepository
from qs_watch.application.services.watch_engine._repo_resolver import watch_rule_repo

logger = structlog.get_logger(__name__)


def _positive(value: Any) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


class OpportunityToWatchRuleService:
    """把带有完整结构证据的高分机会转换为观察规则。"""

    MIN_SCORE = 80
    DEFAULT_EXPIRY_DAYS = 30

    def __init__(self, rule_repo: Optional[IWatchRuleRepository] = None):
        self.rule_repo = rule_repo or watch_rule_repo()

    def auto_create_rules(self, opportunities: List[Dict], account: Optional[str] = None) -> List[Dict]:
        """批量创建；account 为空表示全局观察，绝不猜一个默认账户。"""
        owner = str(account or '').strip() or None
        return [self._process_single_opportunity(opp, account=owner) for opp in opportunities]

    def _process_single_opportunity(self, opp: Dict, account: Optional[str] = None) -> Dict:
        symbol = str(opp.get('symbol') or '')
        score = opp.get('score', 0)
        signal_type = opp.get('signal_type', '')

        if score < self.MIN_SCORE:
            return {'symbol': symbol, 'action': 'skipped',
                    'reason': f'分数{score}低于阈值{self.MIN_SCORE}'}
        if signal_type != 'buy':
            return {'symbol': symbol, 'action': 'skipped',
                    'reason': f'信号类型{signal_type}非buy'}

        existing_rules = self.rule_repo.list_rules(symbol=symbol, enabled=True)
        if existing_rules:
            return {'symbol': symbol, 'action': 'skipped',
                    'reason': f'已存在{len(existing_rules)}条启用规则'}

        try:
            rule = self._create_watch_rule(opp, account=account)
            if rule is None:
                return {
                    'symbol': symbol,
                    'action': 'skipped',
                    'reason_code': 'missing_or_invalid_structural_entry',
                    'reason': '缺少有效结构位/失效位/目标位/失效动作，或盈亏比不足；未创建机械百分比买区',
                }
            return {'symbol': symbol, 'action': 'created', 'rule_id': rule.id,
                    'account': account, 'ownership': 'account' if account else 'global_observation',
                    'reason': f'分数{score}，按显式结构创建观察规则#{rule.id}'}
        except Exception as e:  # noqa: BLE001 - 单候选失败不阻断其他候选
            logger.error('自动创建规则失败', symbol=symbol, error=str(e))
            return {'symbol': symbol, 'action': 'failed', 'reason': f'创建失败: {str(e)}'}

    @staticmethod
    def _structure_payload(opp: Dict) -> Dict[str, Any]:
        """只读取显式结构对象；技术分/理由文本/最新价都不是入场结构。"""
        for key in ('entry_setup', 'structure', 'trade_setup'):
            value = opp.get(key)
            if isinstance(value, dict):
                return dict(value)
        direct_keys = {
            'structure_price', 'entry_price', 'invalidation_price', 'target_price',
            'invalidation_action', 'structure_basis', 'direction',
        }
        if direct_keys.intersection(opp):
            return {key: opp[key] for key in direct_keys if key in opp}
        return {}

    @staticmethod
    def _validated_structure(opp: Dict) -> Optional[Tuple[float, float, float, str, str, str]]:
        setup = OpportunityToWatchRuleService._structure_payload(opp)
        entry = _positive(setup.get('structure_price', setup.get('entry_price')))
        invalidation = _positive(setup.get('invalidation_price'))
        target = _positive(setup.get('target_price'))
        action = str(setup.get('invalidation_action') or '').strip()
        basis = str(setup.get('structure_basis') or '').strip()
        direction = str(setup.get('direction') or 'below').strip().lower()
        if not all((entry, invalidation, target, action, basis)) or direction not in ('above', 'below'):
            return None
        if action not in ('清仓', '减半', '观察'):
            return None
        risk = entry - invalidation
        reward = target - entry
        if risk <= 0 or reward < risk:
            return None
        return entry, invalidation, target, action, basis, direction

    def _create_watch_rule(self, opp: Dict, account: Optional[str] = None):
        structure = self._validated_structure(opp)
        if structure is None:
            return None
        entry, invalidation, target, invalidation_action, basis, direction = structure
        symbol = str(opp.get('symbol') or '')
        score = opp.get('score', 0)
        conditions = [{
            'type': 'price_break',
            'params': {'direction': direction, 'price': round(entry, 2)},
        }]
        context = self._build_context(
            opp, basis=basis, invalidation=invalidation,
            invalidation_action=invalidation_action, account=account,
        )
        action_hint = {
            'action_on_trigger': 'observe',
            'requires_agent': False,
            'structure_price': entry,
            'invalidation_price': invalidation,
            'invalidation_action': invalidation_action,
            'target_price': target,
            'structure_basis': basis,
            'ownership': 'account' if account else 'global_observation',
        }
        rule = self.rule_repo.create_rule(
            symbol=symbol,
            conditions=conditions,
            context=context,
            active_window=None,
            expires_at=datetime.now() + timedelta(days=self.DEFAULT_EXPIRY_DAYS),
            created_by='opportunity_scan',
            account=account,
            linked_account=account,
            intent='trend_observe',
            action_hint=action_hint,
            position_state='none',
            trigger_channel='direct',
        )
        self._update_rule_meta(rule, symbol)
        return rule

    @staticmethod
    def _build_context(opp: Dict, *, basis: str, invalidation: float,
                       invalidation_action: str, account: Optional[str]) -> str:
        symbol = str(opp.get('symbol') or '')
        name = str(opp.get('name') or symbol)
        score = opp.get('score', 0)
        reasons = '、'.join(str(x) for x in (opp.get('reasons') or [])[:3])
        data_as_of = str(opp.get('data_as_of') or '未标注')
        ownership = f'账户观察：{account}' if account else '全局观察：不关联账户、不允许交易'
        return (
            f'{name}({symbol}) | 评分{score} | {ownership}\n'
            f'机会理由：{reasons or "未提供"}\n'
            f'结构位依据：{basis}\n'
            f'失效位：{invalidation}；失效后动作：{invalidation_action}\n'
            f'数据时点：{data_as_of}\n'
            f'[opportunity_scan 自动创建 · 显式结构证据 · 非买入指令]'
        )

    def _update_rule_meta(self, rule, symbol: str) -> None:
        policy = EscalationPolicy(auto_escalate=True)
        self.rule_repo.update_fields(
            rule.id,
            lifecycle_stage='watching',
            scope='symbol',
            target=symbol,
            review_interval_days=7,
            next_action_hint='结构触发后复核数据时点与账户归属；观察不等于入场',
            escalation_policy={'auto_escalate': policy.auto_escalate},
        )
