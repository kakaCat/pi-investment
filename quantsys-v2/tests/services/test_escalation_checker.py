"""EscalationChecker 单元测试"""
import pytest
from datetime import datetime
from types import SimpleNamespace

from domain.watch.models import WatchRule, EscalationPolicy, TriggerLevel, ActionHint
from domain.watch.services.escalation_checker import EscalationChecker, QuoteData
from application.services.watch_engine.conditions import EvalResult


class TestEscalationChecker:
    """升级检查器测试"""
    
    def setup_method(self):
        self.checker = EscalationChecker()
        self.rule = WatchRule(
            id=1,
            symbol='600219',
            enabled=True,
            conditions=[{'type': 'price_break', 'params': {'price': 5.13, 'direction': 'above'}}],
            action_hint=ActionHint(
                trigger_level=TriggerLevel.L1_OBSERVATION,
                action_on_trigger='observe',
                requires_agent=False,
            ),
            escalation_policy=EscalationPolicy.default(),
        )
        self.quote = QuoteData(symbol='600219', price=5.15, change_pct=1.2)
        self.result = EvalResult(triggered=True, value=1.8, distance_ratio=0.1, message='突破5.13')
    
    def test_no_escalation_when_policy_disabled(self):
        """策略关闭时不升级"""
        self.rule.escalation_policy = EscalationPolicy(auto_escalate=False)
        reason = self.checker.should_escalate(self.rule, self.rule.conditions[0], self.quote, self.result)
        assert reason is None
    
    def test_no_escalation_when_no_policy(self):
        """无策略时不升级"""
        self.rule.escalation_policy = None
        reason = self.checker.should_escalate(self.rule, self.rule.conditions[0], self.quote, self.result)
        assert reason is None
    
    def test_trigger_frequency_escalation(self):
        """触发频率升级"""
        reason = self.checker.should_escalate(
            self.rule, self.rule.conditions[0], self.quote, self.result,
            recent_trigger_count=3
        )
        assert reason is not None
        assert '触发频率异常' in reason
        assert '3次' in reason
    
    def test_no_frequency_escalation_when_below_threshold(self):
        """触发次数不足时不升级"""
        reason = self.checker.should_escalate(
            self.rule, self.rule.conditions[0], self.quote, self.result,
            recent_trigger_count=2
        )
        assert reason is None
    
    def test_price_deviation_escalation(self):
        """价格偏差升级"""
        # 当前价 5.50，设定价 5.13，偏差 7.2% > 5%
        quote = QuoteData(symbol='600219', price=5.50)
        reason = self.checker.should_escalate(self.rule, self.rule.conditions[0], quote, self.result)
        assert reason is not None
        assert '价格偏差' in reason
        assert '7.2%' in reason
    
    def test_no_price_deviation_when_within_threshold(self):
        """价格偏差在阈值内不升级"""
        # 当前价 5.15，设定价 5.13，偏差 0.4% < 5%
        reason = self.checker.should_escalate(self.rule, self.rule.conditions[0], self.quote, self.result)
        assert reason is None
    
    def test_core_zone_escalation(self):
        """核心区域升级"""
        self.rule.escalation_policy = EscalationPolicy(
            auto_escalate=True,
            core_zones=[{'low': 4.65, 'high': 5.13, 'reason': '平台震荡区'}]
        )
        # 当前价 5.00，在核心区域内
        quote = QuoteData(symbol='600219', price=5.00)
        reason = self.checker.should_escalate(self.rule, self.rule.conditions[0], quote, self.result)
        assert reason is not None
        assert '核心区域' in reason
        assert '平台震荡区' in reason
    
    def test_volume_anomaly_escalation(self):
        """量能异常升级"""
        # volume_surge 阈值 1.5x，实际 3.5x，倍数 2.33 > 2.0
        result = EvalResult(triggered=True, value=3.5, distance_ratio=0.1, message='放量')
        condition = {'type': 'volume_surge', 'params': {'multiple': 1.5}}
        reason = self.checker.should_escalate(self.rule, condition, self.quote, result)
        assert reason is not None
        assert '量能异常' in reason
    
    def test_multi_rule_confluence_escalation(self):
        """多规则共振升级"""
        reason = self.checker.should_escalate(
            self.rule, self.rule.conditions[0], self.quote, self.result,
            concurrent_trigger_count=2
        )
        assert reason is not None
        assert '多规则共振' in reason
    
    def test_no_escalation_when_healthy(self):
        """健康状态不升级"""
        reason = self.checker.should_escalate(
            self.rule, self.rule.conditions[0], self.quote, self.result,
            recent_trigger_count=1,
            concurrent_trigger_count=1
        )
        assert reason is None
