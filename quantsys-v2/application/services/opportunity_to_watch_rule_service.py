"""
机会到盯盘规则转换服务

职责：
1. 将 opportunity_scan 的高分机会自动转换为盯盘规则
2. 避免重复创建（同一 symbol 已存在启用规则则跳过）
3. 设置合理的触发条件和预案

触发条件：
- score >= 80（A级机会）
- signal_type == 'buy'
- 同一 symbol 没有已启用的买入规则

创建的规则：
- trigger_level: L1（观察提醒）
- action_hint: observe（不自动买入）
- escalation_policy: 默认（价格偏差>5%或触发频率异常时升级L2）
- expires_at: 30天后
"""
import json
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import structlog
from sqlalchemy import text

from adapters.outbound.repositories.watch_rule_repository import WatchRuleRepository
from domain.watch.models import EscalationPolicy
from infrastructure.persistence.database.engine import get_engine

logger = structlog.get_logger(__name__)


class OpportunityToWatchRuleService:
    """机会→盯盘规则转换服务"""
    
    # 创建规则的最低分数阈值
    MIN_SCORE = 80
    
    # 默认有效期（天）
    DEFAULT_EXPIRY_DAYS = 30
    
    # 止损比例
    STOP_LOSS_PCT = 5.0
    
    # 止盈比例
    TAKE_PROFIT_PCT = 10.0
    
    def __init__(self, rule_repo: Optional[WatchRuleRepository] = None):
        self.rule_repo = rule_repo or WatchRuleRepository()
    
    def auto_create_rules(self, opportunities: List[Dict]) -> List[Dict]:
        """为高分机会自动创建盯盘规则
        
        Args:
            opportunities: 机会列表（来自 opportunity_scan）
        
        Returns:
            List[Dict]: 创建结果列表（成功/跳过/失败）
        """
        results = []
        
        for opp in opportunities:
            result = self._process_single_opportunity(opp)
            results.append(result)
        
        return results
    
    def _process_single_opportunity(self, opp: Dict) -> Dict:
        """处理单个机会"""
        symbol = opp.get('symbol', '')
        score = opp.get('score', 0)
        signal_type = opp.get('signal_type', '')
        
        # 1. 检查分数阈值
        if score < self.MIN_SCORE:
            return {
                'symbol': symbol,
                'action': 'skipped',
                'reason': f'分数{score}低于阈值{self.MIN_SCORE}',
            }
        
        # 2. 检查信号类型
        if signal_type != 'buy':
            return {
                'symbol': symbol,
                'action': 'skipped',
                'reason': f'信号类型{signal_type}非buy',
            }
        
        # 3. 检查是否已存在启用规则
        existing_rules = self.rule_repo.list_rules(symbol=symbol, enabled=True)
        if existing_rules:
            return {
                'symbol': symbol,
                'action': 'skipped',
                'reason': f'已存在{len(existing_rules)}条启用规则',
            }
        
        # 4. 创建规则
        try:
            rule = self._create_watch_rule(opp)
            if rule is None:
                return {
                    'symbol': symbol,
                    'action': 'skipped',
                    'reason': '无法确定入场价（载荷无价格且数据库无该标的K线），未创建空条件规则',
                }
            return {
                'symbol': symbol,
                'action': 'created',
                'rule_id': rule.id,
                'reason': f'分数{score}，自动创建规则#{rule.id}',
            }
        except Exception as e:
            logger.error('自动创建规则失败', symbol=symbol, error=str(e))
            return {
                'symbol': symbol,
                'action': 'failed',
                'reason': f'创建失败: {str(e)}',
            }
    
    def _create_watch_rule(self, opp: Dict):
        """创建盯盘规则"""
        symbol = opp.get('symbol', '')
        name = opp.get('name', symbol)
        score = opp.get('score', 0)
        reasons = opp.get('reasons', [])
        score_breakdown = opp.get('score_breakdown', {})
        
        # 获取当前价格：先试载荷内字段，再回落数据库最新收盘
        # 2026-09-11 修复（REQ-342799，w-c8cae280）：实测 opportunity_scan 载荷**根本不含价格字段**
        #（键为 symbol/name/score/.../scoring_method），而 _extract_current_price 只找
        # score_breakdown.technical.details.latest_price 与 reasons 里的『当前价 X』——两者都不存在，
        # 于是 current_price 恒为 None、conditions 恒为空、却照样 create_rule，
        # 造成 09-10 起累计 13 条 conditions=[] 的『永不触发』规则（假监控覆盖）。
        current_price = self._extract_current_price(opp)
        if not current_price:
            current_price = self._latest_close_from_db(symbol)
        
        # 计算买入区和止损止盈价
        if current_price:
            entry_price = round(current_price * 0.98, 2)  # 比当前价低 2% 作为买入区上沿
            stop_loss = round(current_price * (1 - self.STOP_LOSS_PCT / 100), 2)
            take_profit = round(current_price * (1 + self.TAKE_PROFIT_PCT / 100), 2)
        else:
            entry_price = None
            stop_loss = None
            take_profit = None
        
        # 构建条件
        conditions = []
        if entry_price:
            conditions.append({
                'type': 'price_break',
                'params': {'price': entry_price, 'direction': 'below'},
                'cooldown_sec': 1800,
            })
        
        # 没有可执行条件就不建规则：宁可显式跳过（并留日志/计数），也不生产空壳规则。
        # 这是『不产生假数据』纪律在盯盘链路上的落地——空条件规则的危害是让人误以为有监控覆盖。
        if not conditions:
            logger.warning(
                '跳过自动创建盯盘规则：无法确定入场价',
                symbol=symbol,
                score=score,
            )
            return None

        # 构建 context（预案）
        context = self._build_context(opp, entry_price, stop_loss, take_profit)
        
        # 构建 action_hint
        action_hint = {
            'trigger_level': 'L1',
            'action_on_trigger': 'observe',
            'requires_agent': False,
        }
        
        # 构建 escalation_policy
        escalation_policy = EscalationPolicy.default()
        
        # 创建规则
        rule = self.rule_repo.create_rule(
            symbol=symbol,
            conditions=conditions,
            context=context,
            expires_at=datetime.now() + timedelta(days=self.DEFAULT_EXPIRY_DAYS),
            created_by='opportunity_scan',
        )
        
        # 更新 action_hint 和 escalation_policy（create_rule 不支持这些字段，需要额外更新）
        # 注意：这里假设 rule_repo 有 update 方法，或者通过 SQL 直接更新
        self._update_rule_meta(rule.id, action_hint, escalation_policy)
        
        logger.info(
            '自动创建盯盘规则',
            symbol=symbol,
            rule_id=rule.id,
            score=score,
            entry_price=entry_price,
        )
        
        return rule
    
    def _latest_close_from_db(self, symbol: str) -> Optional[float]:
        """从日K线库取该标的最新收盘价（2026-09-11 新增：载荷本身不含价格字段）"""
        if not symbol:
            return None
        try:
            with get_engine().connect() as conn:
                row = conn.execute(
                    text(
                        'SELECT close FROM quant.daily_klines WHERE symbol = :s '
                        'ORDER BY trade_date DESC LIMIT 1'
                    ),
                    {'s': symbol},
                ).fetchone()
            if row and row[0] is not None:
                return float(row[0])
            return None
        except Exception as e:  # noqa: BLE001
            logger.warning('读取最新收盘价失败', symbol=symbol, error=str(e))
            return None

    def _extract_current_price(self, opp: Dict) -> Optional[float]:
        """从机会数据中提取当前价格"""
        # 尝试从 score_breakdown 中提取
        breakdown = opp.get('score_breakdown', {})
        technical = breakdown.get('technical', {})
        details = technical.get('details', {})
        
        # 尝试从 details 中获取最新价格
        if 'latest_price' in details:
            return float(details['latest_price'])
        
        # 尝试从 reasons 中提取（如"当前价 5.13"）
        for reason in opp.get('reasons', []):
            match = re.search(r'当前价\s+([\d.]+)', reason)
            if match:
                return float(match.group(1))
        
        return None
    
    def _build_context(self, opp: Dict, entry_price, stop_loss, take_profit) -> str:
        """构建规则预案文本"""
        symbol = opp.get('symbol', '')
        name = opp.get('name', symbol)
        score = opp.get('score', 0)
        reasons = opp.get('reasons', [])
        
        lines = [
            f'{name}({symbol}) 机会扫描自动监控（评分{score}）',
            '',
            '触发条件：',
        ]
        
        if entry_price:
            lines.append(f'① 跌破 {entry_price} = 进入买入区，评估建仓')
        
        lines.extend([
            '',
            '评分依据：',
        ])
        
        for i, reason in enumerate(reasons[:5], 1):  # 最多显示5条原因
            lines.append(f'{i}. {reason}')
        
        if stop_loss and take_profit:
            lines.extend([
                '',
                '风控：',
                f'• 止损：-{self.STOP_LOSS_PCT}%（≈{stop_loss}）',
                f'• 止盈：+{self.TAKE_PROFIT_PCT}%（≈{take_profit}）',
            ])
        
        lines.extend([
            '',
            f'有效期：{self.DEFAULT_EXPIRY_DAYS}天',
            '来源：opportunity_scan 自动创建',
        ])
        
        return '\n'.join(lines)
    
    def _update_rule_meta(self, rule_id: int, action_hint: Dict, escalation_policy: EscalationPolicy):
        """更新规则的 action_hint 和 escalation_policy"""
        engine = get_engine()
        
        # 统一序列化 escalation_policy（支持 dataclass 和 dict）
        if isinstance(escalation_policy, dict):
            ep_dict = escalation_policy
        else:
            ep_dict = {
                'auto_escalate': escalation_policy.auto_escalate,
                'max_triggers_per_window': escalation_policy.max_triggers_per_window,
                'price_deviation_pct': escalation_policy.price_deviation_pct,
                'volume_ratio_multiplier': escalation_policy.volume_ratio_multiplier,
                'multi_rule_confluence': escalation_policy.multi_rule_confluence,
            }
        
        with engine.begin() as conn:
            conn.execute(text(
                "UPDATE quant.watch_rules "
                "SET action_hint = :ah, escalation_policy = :ep, updated_at = NOW() "
                "WHERE id = :rid"
            ), {
                'rid': rule_id,
                'ah': json.dumps(action_hint),
                'ep': json.dumps(ep_dict),
            })
