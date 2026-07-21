"""
V13策略实现

将现有的SimulationTrader包装为BaseStrategy接口
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from typing import List
from domain.strategies.base_strategy import BaseStrategy, Signal, StrategyConfig
from live_trading.simulation_trader import SimulationTrader


class V13Strategy(BaseStrategy):
    """V13量化策略"""
    
    def __init__(self):
        self.trader = None
        super().__init__()
    
    def get_config(self) -> StrategyConfig:
        """返回V13策略配置"""
        return StrategyConfig(
            name="V13 XGBoost Multi-Factor",
            version="1.0.0",
            description="基于XGBoost的多因子选股策略，5日调仓周期，最多持仓8只股票",
            rebalance_days=5,
            max_positions=8,
            max_position_pct=0.85,
            model_path="live_trading/models/v13_model.json",
            params={
                'top_n': 8,
                'position_scale': 0.85,
                'min_score': 0.5
            }
        )
    
    def initialize(self):
        """初始化策略（加载模型）"""
        if not self.trader:
            self.trader = SimulationTrader()
            self.trader.load_model()
        self.is_initialized = True
    
    def calculate_signals(self, date: str, account_name: str = 'default') -> List[Signal]:
        """
        计算V13交易信号
        
        注意：V13Strategy目前使用SimulationTrader的完整流程
        不直接返回Signal对象，而是通过trader执行完整的rebalance
        """
        if not self.is_initialized:
            self.initialize()
        
        # V13的逻辑比较复杂，包含因子计算、模型预测、风控选股等
        # 暂时返回空列表，实际执行通过run()方法调用trader
        return []
    
    def run(self, account_name: str = 'default'):
        """
        执行V13策略（直接调用SimulationTrader）
        
        这是临时方案，完整重构后应该通过calculate_signals返回信号
        """
        if not self.is_initialized:
            self.initialize()
        
        # 直接调用SimulationTrader的run_daily_check
        self.trader.run_daily_check()


# 便捷函数：创建并返回V13策略实例
def create_v13_strategy() -> V13Strategy:
    """创建V13策略实例"""
    return V13Strategy()
