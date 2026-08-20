"""
V14策略实现

基于V14 P0优化模型的量化策略
- 训练样本: 233,456条
- 有效因子: 75个
- 预期年化: 41.2%
- IC/IR: 0.065 / 2.5
"""
import sys
import os

from typing import List
from domain.strategies.base_strategy import BaseStrategy, Signal, StrategyConfig
from live_trading.simulation_trader import SimulationTrader


class V14Strategy(BaseStrategy):
    """V14量化策略（P0优化版）"""

    def __init__(self):
        self.trader = None
        super().__init__()

    def get_config(self) -> StrategyConfig:
        """返回V14策略配置（参数优化版 - 适应牛市）"""
        return StrategyConfig(
            name="V14 XGBoost Multi-Factor Optimized",
            version="2.1.0",
            description="V14参数优化版：15只持仓，30天调仓，适应牛市环境",
            rebalance_days=30,  # 优化: 7→30天，减少交易捕捉趋势
            max_positions=15,   # 优化: 5→15只，分散风险捕捉板块
            max_position_pct=0.95,  # 优化: 90→95%，提高仓位
            model_path="live_trading/models/v14_p0_model.json",
            params={
                'top_n': 15,
                'position_scale': 0.95,
                'min_score': 0.5,
                'single_stock_weight': 0.08,  # 优化: 18→8%，降低集中
                'single_stock_stop_loss': -0.15,  # 优化: -12→-15%，放宽止损
                'portfolio_stop_loss': -0.20,
                'version': 'v14_optimized',
                'training_samples': 233456,
                'factors': 75,
                'expected_annual_return': 0.35,  # 目标: 35-40%
                'expected_sharpe': 3.5
            }
        )

    def initialize(self):
        """初始化策略（加载V14 P0模型）"""
        if not self.trader:
            self.trader = SimulationTrader()
            # 确保加载V14 P0模型
            self.trader.model_path = "live_trading/models/v14_p0_model.json"
            self.trader.factors_path = "live_trading/models/v14_p0_valid_factors.json"
            self.trader.load_model()
        self.is_initialized = True

    def calculate_signals(self, date: str, account_name: str = 'default') -> List[Signal]:
        """
        计算V14交易信号

        V14策略特点:
        - 7日调仓周期（降低交易成本）
        - 5只集中持仓（提高Alpha）
        - 18%单股权重（Kelly准则）
        - -12%止损（V13为-15%）
        - 移动止损机制

        Args:
            date: 交易日期
            account_name: 账户名称

        Returns:
            List[Signal]: 交易信号列表
        """
        if not self.is_initialized:
            self.initialize()

        # V14使用SimulationTrader的完整流程
        # 但应用V14的配置参数
        signals = []

        # 这里应该调用trader的选股逻辑
        # 由于SimulationTrader是完整流程，这里返回空列表
        # 实际交易通过 strategy_trading_job（统一入口）执行

        return signals

    def on_trading_day(self, date: str, account_name: str = 'default') -> dict:
        """
        V14每日交易检查

        Returns:
            dict: 执行结果
        """
        if not self.is_initialized:
            self.initialize()

        try:
            # 1. 检查止损
            stop_loss_result = self.trader.check_stop_loss()

            # 2. 判断是否到调仓日
            should_rebalance = self.trader.should_rebalance()

            # 3. 执行调仓（如需要）
            rebalance_result = None
            if should_rebalance:
                rebalance_result = self.trader.rebalance()

            return {
                'success': True,
                'date': date,
                'stop_loss': stop_loss_result,
                'rebalance': rebalance_result,
                'should_rebalance': should_rebalance
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
