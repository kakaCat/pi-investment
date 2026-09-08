"""
升级检查器领域服务

判断 L0/L1 触发是否应自动升级为 L2（agent 介入）。
纯函数，无 I/O，无外部依赖。
"""
from typing import Optional

from domain.watch.models import WatchRule, QuoteData


class EscalationChecker:
    """升级检查器
    
    职责：
    1. 检查 L0/L1 触发是否满足升级条件
    2. 返回升级原因（None=不升级）
    
    升级条件（5 类）：
    - 触发频率：近 N 分钟内触发 ≥M 次
    - 价格偏差：当前价 vs 规则设定价偏差 >X%
    - 核心区域：价格进入预设区间
    - 量能异常：实际 ratio > 阈值 ×Y 倍
    - 多规则共振：同 symbol 近 Z 秒内 ≥2 条规则触发
    """
    
    def should_escalate(
        self,
        rule: WatchRule,
        condition: dict,
        quote: QuoteData,
        result,
        recent_trigger_count: int = 0,
        concurrent_trigger_count: int = 0,
    ) -> Optional[str]:
        """检查是否应升级"""
        # 处理 dict 类型的 escalation_policy（从数据库 JSONB 读取）
        policy = rule.escalation_policy
        if isinstance(policy, dict):
            if not policy or not policy.get('auto_escalate', True):
                return None
        elif not policy or not getattr(policy, 'auto_escalate', True):
            return None
        
        # 1. 触发频率升级
        reason = self._check_trigger_frequency(policy, recent_trigger_count)
        if reason:
            return reason
        
        # 2. 价格偏差升级
        reason = self._check_price_deviation(policy, condition, quote)
        if reason:
            return reason
        
        # 3. 核心区域升级
        reason = self._check_core_zones(policy, quote)
        if reason:
            return reason
        
        # 4. 量能异常升级
        reason = self._check_volume_anomaly(policy, condition, result)
        if reason:
            return reason
        
        # 5. 多规则共振升级
        reason = self._check_multi_rule_confluence(policy, concurrent_trigger_count)
        if reason:
            return reason
        
        return None
    
    def _get_policy_value(self, policy, key, default=None):
        """统一获取 policy 值（支持 dict 和 dataclass）"""
        if isinstance(policy, dict):
            return policy.get(key, default)
        return getattr(policy, key, default)
    
    def _check_trigger_frequency(self, policy, recent_trigger_count: int) -> Optional[str]:
        """检查触发频率升级条件"""
        max_triggers = self._get_policy_value(policy, 'max_triggers_per_window')
        if not max_triggers:
            return None
        
        count = max_triggers.get('count', 3) if isinstance(max_triggers, dict) else getattr(max_triggers, 'count', 3)
        window = max_triggers.get('window_minutes', 10) if isinstance(max_triggers, dict) else getattr(max_triggers, 'window_minutes', 10)
        
        if recent_trigger_count >= count:
            return f"触发频率异常（{window}分钟内{recent_trigger_count}次），可能洗盘/真突破"
        
        return None
    
    def _check_price_deviation(self, policy, condition: dict, quote: QuoteData) -> Optional[str]:
        """检查价格偏差升级条件"""
        deviation_pct = self._get_policy_value(policy, 'price_deviation_pct')
        if not deviation_pct:
            return None
        
        params = condition.get('params', {})
        rule_price = params.get('price')
        
        if not rule_price or rule_price <= 0:
            return None
        
        deviation = abs(quote.price - rule_price) / rule_price * 100
        
        if deviation > deviation_pct:
            return f"价格偏差{deviation:.1f}%，原预案位置失效"
        
        return None
    
    def _check_core_zones(self, policy, quote: QuoteData) -> Optional[str]:
        """检查核心区域升级条件"""
        core_zones = self._get_policy_value(policy, 'core_zones')
        if not core_zones:
            return None
        
        for zone in core_zones:
            if isinstance(zone, dict):
                low = zone.get('low')
                high = zone.get('high')
                reason = zone.get('reason', '关键区域')
            else:
                low = getattr(zone, 'low', None)
                high = getattr(zone, 'high', None)
                reason = getattr(zone, 'reason', '关键区域')
            
            if low is not None and high is not None:
                if low <= quote.price <= high:
                    return f"进入核心区域 {low}-{high}（{reason}）"
        
        return None
    
    def _check_volume_anomaly(self, policy, condition: dict, result) -> Optional[str]:
        """检查量能异常升级条件"""
        multiplier = self._get_policy_value(policy, 'volume_ratio_multiplier')
        if not multiplier:
            return None
        
        if not result.value or result.value <= 0:
            return None
        
        params = condition.get('params', {})
        threshold = params.get('multiple', 1.5)
        
        if result.value > threshold * multiplier:
            return f"量能异常（{result.value:.1f}x vs 阈值{threshold}x），可能主力异动"
        
        return None
    
    def _check_multi_rule_confluence(self, policy, concurrent_trigger_count: int) -> Optional[str]:
        """检查多规则共振升级条件"""
        confluence = self._get_policy_value(policy, 'multi_rule_confluence')
        if not confluence:
            return None
        
        enabled = confluence.get('enabled', False) if isinstance(confluence, dict) else getattr(confluence, 'enabled', False)
        if not enabled:
            return None
        
        if concurrent_trigger_count >= 2:
            window = confluence.get('window_seconds', 60) if isinstance(confluence, dict) else getattr(confluence, 'window_seconds', 60)
            return f"多规则共振（{concurrent_trigger_count}条规则近{window}秒内触发），价格剧烈波动"
        
        return None
