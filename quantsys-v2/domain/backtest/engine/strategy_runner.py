"""
策略运行器

从数据库加载策略配置，对指定股票的K线数据运行所有活跃策略，
返回排序后的信号列表。

DDD 架构:
- 依赖 IStrategyRepository 接口，不依赖具体实现
- Application 层负责注入具体的 Repository

使用方式:
    # Application 层创建并注入
    strategy_repo = StrategyORMRepository()
    runner = StrategyRunner(strategy_repo=strategy_repo)

    signals = runner.run(symbol="000001.SZ", klines=klines)
    top_signals = runner.get_top_signals(symbol="000001.SZ", klines=klines, top_n=5)
"""
from typing import Dict, List, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from domain.ports import IStrategyRepository
from domain.backtest.engine.ma_cross import MACrossStrategy
from domain.backtest.engine.rsi_reversal import RSIReversalStrategy
from domain.backtest.engine.bollinger_breakout import BollingerBreakoutStrategy
from domain.backtest.engine.turtle_strategy import TurtleStrategy
from domain.backtest.engine.donchian_channel_strategy import DonchianChannelStrategy
from domain.backtest.engine.mean_reversion_strategy import MeanReversionStrategy
from domain.backtest.engine.pairs_correlation_strategy import PairsCorrelationStrategy
from domain.backtest.engine.momentum_strategy import MomentumStrategy
from domain.backtest.engine.breakout_strategy import BreakoutStrategy
from domain.backtest.engine.volatility_breakout_strategy import VolatilityBreakoutStrategy
from domain.backtest.engine.pe_momentum_ma60_strategy import PEMomentumMA60Strategy
from domain.backtest.engine.strategy_combiner import StrategyCombiner


# 策略类型到策略类的映射
STRATEGY_REGISTRY: Dict[str, type] = {
    'ma_cross': MACrossStrategy,
    'rsi_reversal': RSIReversalStrategy,
    'bollinger_breakout': BollingerBreakoutStrategy,
    'turtle': TurtleStrategy,
    'donchian_channel': DonchianChannelStrategy,
    'mean_reversion': MeanReversionStrategy,
    'pairs_correlation': PairsCorrelationStrategy,
    'momentum': MomentumStrategy,
    'breakout': BreakoutStrategy,
    'volatility_breakout': VolatilityBreakoutStrategy,
    'pe_momentum_ma60': PEMomentumMA60Strategy,
}


class StrategyRunner:
    """
    策略运行器

    负责:
    1. 从数据库加载策略配置
    2. 用配置实例化策略对象
    3. 对给定K线数据运行策略
    4. 返回排序后的信号列表
    """

    def __init__(self, strategy_repo: Optional[IStrategyRepository] = None, max_workers: int = 4):
        """
        初始化策略运行器

        Args:
            strategy_repo: 策略Repository接口实例（由 Application 层注入）
            max_workers: 并行执行策略的最大线程数，默认4

        Raises:
            ValueError: strategy_repo 未注入。domain 层不再自行创建具体仓储
                （六边形架构依赖方向），与其他 domain 类一致构造期 fail-fast。
        """
        if strategy_repo is None:
            raise ValueError(
                "StrategyRunner requires strategy_repo injection "
                "(must implement IStrategyRepository interface, "
                "wired by the Application layer)"
            )

        self.repo = strategy_repo
        self.max_workers = max_workers

    def _get_strategy_instance(self, config: Dict[str, Any]):
        """
        根据配置创建策略实例

        Args:
            config: 策略配置字典 (from strategy_configs)

        Returns:
            策略实例，或 None（不支持的类型）
        """
        strategy_type = config.get('strategy_type', '')

        # Try StrategyFactory first (covers auto-discovered strategies)
        try:
            from domain.backtest.engine.strategy_factory import StrategyFactory
            if not StrategyFactory._registry:
                StrategyFactory.auto_discover()
            return StrategyFactory.create(
                strategy_type,
                name=config.get('name', config.get('strategy_name', '')),
            )
        except ValueError:
            pass

        # Fallback to legacy STRATEGY_REGISTRY
        strategy_class = STRATEGY_REGISTRY.get(strategy_type)
        if strategy_class is None:
            return None
        return strategy_class(name=config.get(
            'name', config.get('strategy_name', '')
        ))

    def _execute_strategy(
        self,
        config: Dict[str, Any],
        klines: List[Dict[str, Any]],
        symbol: str
    ) -> Dict[str, Any]:
        """
        执行单个策略（用于并行执行）

        Args:
            config: 策略配置
            klines: K线数据
            symbol: 股票代码

        Returns:
            信号字典
        """
        strategy = self._get_strategy_instance(config)
        if strategy is None:
            return None

        # 解析参数
        parameters = config.get('parameters', {})
        if isinstance(parameters, str):
            import json
            try:
                parameters = json.loads(parameters)
            except (json.JSONDecodeError, TypeError):
                parameters = {}

        try:
            signal = strategy.generate_signal(klines, parameters)
        except Exception:
            signal = {
                'action': 'hold',
                'confidence': 0.0,
                'reason': f'策略 {config["name"]} 执行异常'
            }

        return {
            'strategy_name': config['name'],
            'strategy_type': config.get('strategy_type', ''),
            'symbol': symbol or '',
            'action': signal['action'],
            'confidence': signal['confidence'],
            'reason': signal.get('reason', ''),
            'parameters': parameters,
        }

    def run(
        self,
        klines: List[Dict[str, Any]],
        symbol: str = None,
        active_only: bool = True
    ) -> List[Dict[str, Any]]:
        """
        运行所有活跃策略（并行执行）

        Args:
            klines: K线数据列表
            symbol: 股票代码（可选，用于日志）
            active_only: 是否只运行活跃策略

        Returns:
            信号列表，按置信度降序排列，每个元素包含:
            {
                'strategy_name': str,
                'strategy_type': str,
                'symbol': str,
                'action': 'buy'|'sell'|'hold',
                'confidence': float,
                'reason': str,
                'parameters': dict,
            }
        """
        configs = self.repo.get_all(active_only=active_only)
        signals = []

        # 并行执行策略
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # 提交所有任务
            future_to_config = {
                executor.submit(self._execute_strategy, config, klines, symbol): config
                for config in configs
            }

            # 收集结果
            for future in as_completed(future_to_config):
                try:
                    signal = future.result()
                    if signal is not None:
                        signals.append(signal)
                except Exception:
                    # 异常已在 _execute_strategy 中处理，这里捕获意外错误
                    config = future_to_config[future]
                    signals.append({
                        'strategy_name': config.get('name', 'unknown'),
                        'strategy_type': config.get('strategy_type', ''),
                        'symbol': symbol or '',
                        'action': 'hold',
                        'confidence': 0.0,
                        'reason': '策略执行失败',
                        'parameters': {},
                    })

        # 按置信度降序、action 优先级排序 (BUY > SELL > HOLD)
        action_priority = {'BUY': 2, 'SELL': 1, 'HOLD': 0, 'buy': 2, 'sell': 1, 'hold': 0}  # 兼容旧数据

        signals.sort(
            key=lambda s: (s['confidence'], action_priority.get(s['action'], 0)),
            reverse=True
        )

        return signals

    def get_top_signals(
        self,
        klines: List[Dict[str, Any]],
        symbol: str = None,
        top_n: int = 5
    ) -> List[Dict[str, Any]]:
        """
        获取置信度最高的前 N 个信号

        Args:
            klines: K线数据列表
            symbol: 股票代码
            top_n: 返回数量

        Returns:
            前 N 个信号
        """
        all_signals = self.run(klines, symbol=symbol)
        return all_signals[:top_n]

    def _execute_strategy_for_combine(
        self,
        config: Dict[str, Any],
        klines: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        执行单个策略用于信号组合（并行执行）

        Args:
            config: 策略配置
            klines: K线数据

        Returns:
            原始信号字典
        """
        strategy = self._get_strategy_instance(config)
        if strategy is None:
            return None

        parameters = config.get('parameters', {})
        if isinstance(parameters, str):
            import json
            try:
                parameters = json.loads(parameters)
            except (json.JSONDecodeError, TypeError):
                parameters = {}

        try:
            signal = strategy.generate_signal(klines, parameters)
        except Exception:
            signal = {
                'action': 'hold',
                'confidence': 0.0,
                'reason': f'策略 {config["name"]} 执行异常'
            }

        return signal

    def combine_signals(
        self,
        klines: List[Dict[str, Any]],
        config_ids: List[int] = None,
        mode: str = 'majority',
        weights: List[float] = None
    ) -> Dict[str, Any]:
        """
        组合多个指定策略的信号（并行执行）

        Args:
            klines: K线数据列表
            config_ids: 要组合的策略ID列表，为空则使用所有活跃策略
            mode: 组合模式 ('and', 'or', 'majority', 'weighted')
            weights: 权重列表（weighted 模式使用）

        Returns:
            合并后的信号
        """
        if config_ids:
            configs = [self.repo.get_by_id(cid) for cid in config_ids]
            configs = [c for c in configs if c is not None]
        else:
            configs = self.repo.get_all(active_only=True)

        strategy_signals = []

        # 并行执行策略
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_config = {
                executor.submit(self._execute_strategy_for_combine, config, klines): config
                for config in configs
            }

            for future in as_completed(future_to_config):
                try:
                    signal = future.result()
                    if signal is not None:
                        strategy_signals.append(signal)
                except Exception:
                    config = future_to_config[future]
                    strategy_signals.append({
                        'action': 'hold',
                        'confidence': 0.0,
                        'reason': f'策略 {config.get("name", "unknown")} 执行异常'
                    })

        combiner = StrategyCombiner(mode=mode)
        return combiner.combine(strategy_signals, weights=weights)

    def close(self):
        """关闭数据库连接"""
        self.repo.close()
