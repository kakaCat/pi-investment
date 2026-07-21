"""
通用策略基类

所有模拟交易策略必须继承此类并实现抽象方法
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass, field


@dataclass
class Signal:
    """交易信号"""
    symbol: str
    action: str  # 'BUY' or 'SELL'
    weight: float  # 目标权重 (0-1)
    score: float  # 预测分数
    reason: str  # 信号原因
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StrategyConfig:
    """策略配置"""
    name: str
    version: str
    description: str
    rebalance_days: int = 5
    max_positions: int = 8
    max_position_pct: float = 0.85
    model_path: Optional[str] = None
    params: Dict[str, Any] = field(default_factory=dict)


class BaseStrategy(ABC):
    """策略基类"""
    
    def __init__(self):
        self.config = self.get_config()
        self.is_initialized = False
    
    @abstractmethod
    def get_config(self) -> StrategyConfig:
        """返回策略配置"""
        pass
    
    @abstractmethod
    def calculate_signals(self, date: str, account_name: str = 'default') -> List[Signal]:
        """计算交易信号"""
        pass
    
    def should_rebalance(self, last_rebalance_date: Optional[str], current_date: str, has_positions: bool = True) -> bool:
        """
        判断是否需要调仓

        优化逻辑：
        - 空仓时：每天都可以调仓（灵活捕捉机会）
        - 有持仓时：遵循固定调仓周期（避免过度交易）

        Args:
            last_rebalance_date: 最后调仓日期
            current_date: 当前日期
            has_positions: 是否有持仓（默认True保持兼容性）

        Returns:
            是否应该调仓
        """
        if not last_rebalance_date:
            return True

        # 空仓时：每天都检查买入机会
        if not has_positions:
            return True

        # 有持仓时：遵循固定调仓周期
        last_date = datetime.strptime(last_rebalance_date, '%Y-%m-%d')
        curr_date = datetime.strptime(current_date, '%Y-%m-%d')
        days_diff = (curr_date - last_date).days

        return days_diff >= self.config.rebalance_days
    
    def initialize(self):
        """初始化策略"""
        self.is_initialized = True
    
    def validate_signals(self, signals: List[Signal]) -> List[Signal]:
        """验证和过滤信号"""
        valid_signals = [s for s in signals if s.symbol and s.action in ['BUY', 'SELL']]
        
        buy_signals = [s for s in valid_signals if s.action == 'BUY']
        if len(buy_signals) > self.config.max_positions:
            buy_signals = sorted(buy_signals, key=lambda x: x.score, reverse=True)[:self.config.max_positions]
            valid_signals = buy_signals + [s for s in valid_signals if s.action == 'SELL']
        
        total_weight = sum(s.weight for s in buy_signals)
        if total_weight > self.config.max_position_pct:
            scale = self.config.max_position_pct / total_weight
            for s in buy_signals:
                s.weight *= scale
        
        return valid_signals
    
    def get_metadata(self) -> Dict[str, Any]:
        """获取策略元数据"""
        return {
            'name': self.config.name,
            'version': self.config.version,
            'description': self.config.description,
            'rebalance_days': self.config.rebalance_days,
            'max_positions': self.config.max_positions,
            'max_position_pct': self.config.max_position_pct,
            'model_path': self.config.model_path,
            'params': self.config.params
        }
