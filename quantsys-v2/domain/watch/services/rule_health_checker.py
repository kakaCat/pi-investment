"""
规则健康度检查器领域服务

每天收盘后评估所有启用规则的健康度，自动禁用过期/失效规则。
"""
import re
from typing import List, Optional
from datetime import datetime, timedelta

from domain.watch.models import WatchRule, RuleHealthReport, TriggerLevel
from domain.watch.ports import IWatchRuleRepository, ITriggerHistoryRepository, IQuoteProvider


class RuleHealthChecker:
    """规则健康度检查器
    
    职责：
    1. 检查所有启用规则的健康度
    2. 自动禁用过期/失效规则
    3. 标记长期未触发规则供人工审查
    
    健康度状态：
    - HEALTHY: 正常，继续监控
    - EXPIRED: 已过有效期，自动禁用
    - STALE: 价格偏差 >20%，自动禁用（位置失效）
    - OUTDATED: 预案日期已过期，自动禁用
    - INACTIVE: 30天未触发，标记审查（不自动禁用）
    """
    
    # 价格偏差阈值（%）
    PRICE_DEVIATION_THRESHOLD = 20.0
    
    # 未触发天数阈值
    INACTIVE_DAYS_THRESHOLD = 30
    
    def __init__(
        self,
        rule_repo: IWatchRuleRepository,
        trigger_repo: ITriggerHistoryRepository,
        quote_provider: IQuoteProvider,
    ):
        self.rule_repo = rule_repo
        self.trigger_repo = trigger_repo
        self.quote_provider = quote_provider
    
    def check_all_rules(self) -> List[RuleHealthReport]:
        """检查所有启用规则的健康度
        
        Returns:
            List[RuleHealthReport]: 健康度报告列表
        """
        reports = []
        rules = self.rule_repo.get_all_enabled()
        
        for rule in rules:
            report = self._check_rule(rule)
            reports.append(report)
            
            # 自动处理
            if report.status == 'EXPIRED':
                self.rule_repo.disable(rule.id, reason="已过有效期")
            elif report.status == 'STALE':
                self.rule_repo.disable(rule.id, reason=f"价格偏差{report.deviation_pct:.1f}%")
            elif report.status == 'OUTDATED':
                self.rule_repo.disable(rule.id, reason="预案日期已过期")
            # INACTIVE 不自动禁用，只标记审查
        
        return reports
    
    def _check_rule(self, rule: WatchRule) -> RuleHealthReport:
        """检查单条规则健康度"""
        
        # 1. 检查有效期
        if rule.is_expired():
            return RuleHealthReport(
                rule_id=rule.id,
                status='EXPIRED',
                reason=f'已过有效期（{rule.expires_at.strftime("%Y-%m-%d")}）'
            )
        
        # 2. 检查价格偏差
        deviation_report = self._check_price_deviation(rule)
        if deviation_report:
            return deviation_report
        
        # 3. 检查预案日期
        outdated_report = self._check_context_date(rule)
        if outdated_report:
            return outdated_report
        
        # 4. 检查触发活跃度
        inactive_report = self._check_trigger_activity(rule)
        if inactive_report:
            return inactive_report
        
        return RuleHealthReport(
            rule_id=rule.id,
            status='HEALTHY',
            reason='正常'
        )
    
    def _check_price_deviation(self, rule: WatchRule) -> Optional[RuleHealthReport]:
        """检查价格偏差"""
        current_price = self.quote_provider.get_current_price(rule.symbol)
        if current_price is None:
            return None
        
        trigger_price = self._extract_trigger_price(rule.conditions)
        if trigger_price is None or trigger_price <= 0:
            return None
        
        deviation_pct = abs(current_price - trigger_price) / trigger_price * 100
        
        if deviation_pct > self.PRICE_DEVIATION_THRESHOLD:
            return RuleHealthReport(
                rule_id=rule.id,
                status='STALE',
                reason=f'价格偏差{deviation_pct:.1f}%（当前{current_price} vs 设定{trigger_price}）',
                deviation_pct=deviation_pct
            )
        
        return None
    
    def _check_context_date(self, rule: WatchRule) -> Optional[RuleHealthReport]:
        """检查预案日期是否已过期
        
        从 context 文本中提取日期（如"9/2买点"），检查是否已过期。
        """
        if not rule.context:
            return None
        
        # 提取日期模式：M/D 或 MM/DD
        date_patterns = [
            r'(\d{1,2})/(\d{1,2})',  # 9/2, 12/31
            r'(\d{4})-(\d{2})-(\d{2})',  # 2026-09-02
        ]
        
        for pattern in date_patterns:
            matches = re.findall(pattern, rule.context)
            for match in matches:
                try:
                    if len(match) == 2:  # M/D
                        month, day = int(match[0]), int(match[1])
                        year = datetime.now().year
                        date_obj = datetime(year, month, day)
                    else:  # YYYY-MM-DD
                        year, month, day = int(match[0]), int(match[1]), int(match[2])
                        date_obj = datetime(year, month, day)
                    
                    # 如果日期在未来 7 天内或已过去，认为是有效日期
                    # 如果日期已过去超过 7 天，标记为过期
                    days_diff = (datetime.now() - date_obj).days
                    if days_diff > 7:
                        return RuleHealthReport(
                            rule_id=rule.id,
                            status='OUTDATED',
                            reason=f'预案日期已过期（{date_obj.strftime("%m/%d")}，已过去{days_diff}天）'
                        )
                except (ValueError, IndexError):
                    continue
        
        return None
    
    def _check_trigger_activity(self, rule: WatchRule) -> Optional[RuleHealthReport]:
        """检查触发活跃度"""
        last_trigger = self.trigger_repo.get_last_trigger(rule.id)
        
        if last_trigger is None:
            # 从未触发过，检查创建时间
            if rule.created_at:
                days_since_created = (datetime.now() - rule.created_at).days
                if days_since_created > self.INACTIVE_DAYS_THRESHOLD:
                    return RuleHealthReport(
                        rule_id=rule.id,
                        status='INACTIVE',
                        reason=f'创建后{days_since_created}天从未触发'
                    )
            return None
        
        days_since_trigger = (datetime.now() - last_trigger).days
        
        if days_since_trigger > self.INACTIVE_DAYS_THRESHOLD:
            return RuleHealthReport(
                rule_id=rule.id,
                status='INACTIVE',
                reason=f'{days_since_trigger}天未触发（上次：{last_trigger.strftime("%Y-%m-%d")}）'
            )
        
        return None
    
    def _extract_trigger_price(self, conditions: List[dict]) -> Optional[float]:
        """从条件列表中提取触发价格"""
        for cond in conditions:
            ctype = cond.get('type')
            params = cond.get('params', {})
            
            if ctype == 'price_break':
                return params.get('price')
            elif ctype == 'combined':
                # 递归提取复合条件中的价格
                sub_conditions = params.get('conditions', [])
                price = self._extract_trigger_price(sub_conditions)
                if price is not None:
                    return price
        
        return None
