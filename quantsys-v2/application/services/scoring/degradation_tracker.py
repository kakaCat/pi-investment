"""
降级追踪器 - 记录评分过程中的所有降级/回退/数据缺失

用法：
    tracker = DegradationTracker()
    tracker.record('technical_factors', 'rsi14', 'TA-Lib not available', 
                   'used base score 50', 'warning')
    degradations = tracker.get_degradations()
"""
from typing import List, Dict, Optional, Literal
from dataclasses import dataclass, asdict
from enum import Enum


class Severity(str, Enum):
    """降级严重程度"""
    INFO = 'info'          # 信息提示（不影响置信度）
    WARNING = 'warning'    # 部分降级（-10% 置信度）
    ERROR = 'error'        # 严重降级（-30% 置信度）
    CRITICAL = 'critical'  # 不可用（拒绝返回结果）


@dataclass
class Degradation:
    """降级记录"""
    component: str      # 组件名（technical_factors / kline_data / fundamental_data）
    reason: str         # 降级原因（TA-Lib not available / backfill failed）
    fallback: str       # 回退策略（used base score 50 / used cached data）
    severity: Severity  # 严重程度
    factor: Optional[str] = None  # 具体因子（rsi14 / macd）
    details: Optional[Dict] = None  # 额外细节


class DegradationTracker:
    """降级追踪器"""
    
    def __init__(self):
        self._degradations: List[Degradation] = []
    
    def record(
        self,
        component: str,
        reason: str,
        fallback: str,
        severity: Literal['info', 'warning', 'error', 'critical'] = 'warning',
        factor: Optional[str] = None,
        details: Optional[Dict] = None
    ):
        """记录一次降级
        
        Args:
            component: 组件名（technical_factors / kline_data / fundamental_data）
            reason: 降级原因
            fallback: 回退策略
            severity: 严重程度（info / warning / error / critical）
            factor: 具体因子名（可选）
            details: 额外细节（可选）
        """
        self._degradations.append(Degradation(
            component=component,
            reason=reason,
            fallback=fallback,
            severity=Severity(severity),
            factor=factor,
            details=details or {}
        ))
    
    def get_degradations(self) -> List[Dict]:
        """获取所有降级记录（字典格式）"""
        return [asdict(d) for d in self._degradations]
    
    def has_degradations(self) -> bool:
        """是否有降级"""
        return len(self._degradations) > 0
    
    def has_critical(self) -> bool:
        """是否有严重降级"""
        return any(d.severity == Severity.CRITICAL for d in self._degradations)
    
    def get_confidence_penalty(self) -> float:
        """计算置信度惩罚（0-1）
        
        Returns:
            惩罚系数（1.0 = 无惩罚，0.7 = -30%）
        """
        penalty = 0.0
        for d in self._degradations:
            if d.severity == Severity.WARNING:
                penalty += 0.1
            elif d.severity == Severity.ERROR:
                penalty += 0.3
            elif d.severity == Severity.CRITICAL:
                return 0.0  # 严重降级直接置信度归零
        
        return max(0.0, 1.0 - penalty)
    
    def get_summary(self) -> Dict:
        """获取降级摘要
        
        Returns:
            {
                'total': 3,
                'by_severity': {'warning': 2, 'error': 1},
                'by_component': {'technical_factors': 2, 'kline_data': 1},
                'confidence_penalty': 0.5
            }
        """
        by_severity = {}
        by_component = {}
        
        for d in self._degradations:
            # 按严重程度统计
            severity_key = d.severity.value
            by_severity[severity_key] = by_severity.get(severity_key, 0) + 1
            
            # 按组件统计
            by_component[d.component] = by_component.get(d.component, 0) + 1
        
        return {
            'total': len(self._degradations),
            'by_severity': by_severity,
            'by_component': by_component,
            'confidence_penalty': self.get_confidence_penalty()
        }
    
    def clear(self):
        """清空所有记录"""
        self._degradations = []
