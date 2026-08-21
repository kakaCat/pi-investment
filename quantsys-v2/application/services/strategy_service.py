"""
统一策略服务

提供配置驱动的策略管理，支持 V13/V14/V15... 所有策略版本
避免重复代码，实现 DRY 原则

使用方式：
    service = StrategyService()

    # 列出所有策略
    strategies = service.list_strategies()  # ['v13', 'v14', ...]

    # 获取账户信息
    account = service.get_account_info('v13')

    # 手动调仓
    result = service.manual_rebalance('v14')

    # 每日检查
    result = service.daily_check('v13')
"""
import yaml
import logging
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

from live_trading.simulation_trader import SimulationTrader
from domain.ports import ISimulationRepository

logger = logging.getLogger(__name__)


class StrategyService:
    """策略服务（统一管理所有策略版本）"""

    def __init__(self):
        self.config_dir = Path(__file__).parent.parent.parent / 'live_trading' / 'configs' / 'strategies'
        self.repo = ISimulationRepository()
        self._configs_cache = {}

    def list_strategies(self) -> List[str]:
        """
        列出所有可用策略

        Returns:
            List[str]: 策略名称列表 ['v13', 'v14', 'v15', ...]
        """
        if not self.config_dir.exists():
            logger.warning(f"配置目录不存在: {self.config_dir}")
            return []

        configs = list(self.config_dir.glob('*.yaml'))
        strategies = [c.stem for c in configs]

        # 校验策略账户存在于注册表（simulation_account），缺失则告警并剔除
        from domain.ports.repository_ports_extended import (
            ISimulationRepository,
        )
        repo = ISimulationRepository()
        valid = []
        for name in strategies:
            account_name = self.get_config(name)['strategy'].get('account_name')
            if account_name and repo.get_account(account_name):
                valid.append(name)
            else:
                logger.warning(f"策略 {name} 的账户 {account_name} 不存在于注册表，已禁用")

        logger.info(f"发现 {len(valid)} 个策略: {valid}")
        return sorted(valid)

    def get_config(self, strategy_name: str) -> Dict:
        """
        获取策略配置

        Args:
            strategy_name: 策略名称（如 'v13', 'v14'）

        Returns:
            Dict: 策略配置字典

        Raises:
            ValueError: 策略配置不存在
        """
        # 使用缓存避免重复读取
        if strategy_name in self._configs_cache:
            return self._configs_cache[strategy_name]

        config_path = self.config_dir / f'{strategy_name}.yaml'
        if not config_path.exists():
            available = self.list_strategies()
            raise ValueError(
                f"策略配置不存在: {strategy_name}\n"
                f"可用策略: {available}"
            )

        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        # 缓存配置
        self._configs_cache[strategy_name] = config

        logger.info(f"加载配置: {strategy_name} ({config['strategy']['name']})")
        return config

    def get_account_info(self, strategy_name: str) -> Dict:
        """
        获取策略账户信息

        Args:
            strategy_name: 策略名称

        Returns:
            Dict: 账户信息
                - strategy_name: 策略名称
                - account_name: 账户名称
                - total_value: 总资产
                - cash: 现金
                - position_value: 持仓市值
                - positions_count: 持仓数量
                - cumulative_return: 累计收益率
                - last_rebalance_date: 最后调仓日期
                - config: 策略配置摘要
        """
        config = self.get_config(strategy_name)
        account_name = config['strategy']['account_name']

        logger.info(f"查询账户信息: {strategy_name} (account={account_name})")

        # 从数据库查询账户
        account = self.repo.get_account(account_name)
        if not account:
            raise ValueError(f"账户不存在: {account_name} (策略: {strategy_name})")

        # 查询持仓
        positions = self.repo.get_all_positions(account_name)

        # 计算总资产
        position_value = sum(
            float(p.shares_total) * float(p.current_price or p.avg_cost or 0)
            for p in positions
        )

        cash = float(account.cash_available or 0) + float(account.cash_frozen or 0)
        total_value = cash + position_value
        initial_capital = float(account.initial_capital or 0) or config.get('initial_capital', 100000)

        return {
            'strategy_name': strategy_name,
            'account_name': account_name,
            'total_value': round(total_value, 2),
            'cash': round(cash, 2),
            'position_value': round(position_value, 2),
            'positions_count': len(positions),
            'cumulative_return': round(total_value / initial_capital - 1, 4),
            'last_rebalance_date': str(account.last_rebalance_date) if account.last_rebalance_date else None,
            'peak_value': float(account.peak_value) if hasattr(account, 'peak_value') else total_value,
            'config': {
                'name': config['strategy']['name'],
                'version': config['strategy']['version'],
                'rebalance_days': config['trading']['rebalance_days'],
                'max_positions': config['trading']['max_positions'],
            }
        }

    def get_positions(self, strategy_name: str) -> List[Dict]:
        """
        获取策略持仓明细

        Args:
            strategy_name: 策略名称

        Returns:
            List[Dict]: 持仓列表
        """
        config = self.get_config(strategy_name)
        account_name = config['strategy']['account_name']

        logger.info(f"查询持仓明细: {strategy_name} (account={account_name})")

        positions = self.repo.get_all_positions(account_name)

        return [self._position_to_dict(p) for p in positions]

    def manual_rebalance(self, strategy_name: str, **kwargs) -> Dict:
        """
        手动触发调仓

        Args:
            strategy_name: 策略名称
            **kwargs: 可选参数（覆盖配置）

        Returns:
            Dict: 调仓结果
        """
        config = self.get_config(strategy_name)

        logger.info(f"{'='*70}")
        logger.info(f"手动调仓: {strategy_name}")
        logger.info(f"{'='*70}")

        # 创建交易器
        trader = self._create_trader(config, **kwargs)

        # 执行调仓
        result = trader.rebalance(current_date=datetime.now().strftime('%Y-%m-%d'))

        logger.info(f"✅ {strategy_name} 调仓完成")

        return {
            'strategy': strategy_name,
            'status': 'success',
            'account_name': trader.account_name,
            'timestamp': datetime.now().isoformat(),
            'result': result
        }

    def daily_check(self, strategy_name: str, **kwargs) -> Dict:
        """
        执行每日检查

        Args:
            strategy_name: 策略名称
            **kwargs: 可选参数
                - enable_stop_loss: 是否启用止损检查
                - enable_rebalance: 是否启用调仓

        Returns:
            Dict: 执行结果
        """
        config = self.get_config(strategy_name)

        # 策略休眠开关（2026-08-12 新增）：enabled=false 的策略拒绝执行，
        # 不创建交易器、不触碰账户。v14 因 -52.86% 历史战绩被显式休眠。
        if not config['strategy'].get('enabled', True):
            logger.warning(f"{strategy_name.upper()} 策略已禁用（enabled=false），跳过每日检查")
            return {
                'strategy': strategy_name,
                'status': 'disabled',
                'account_name': config['strategy'].get('account_name'),
                'timestamp': datetime.now().isoformat(),
            }

        logger.info(f"{'='*70}")
        logger.info(f"{strategy_name.upper()} 模拟交易每日检查")
        logger.info(f"{'='*70}")

        # 创建交易器
        trader = self._create_trader(config, **kwargs)

        # 记录初始状态
        initial_value = trader._calculate_total_value_from_portfolio()

        # 执行每日检查（返回结构化结果，区分 executed / skipped）
        check = trader.run_daily_check()

        # 记录最终状态
        final_value = trader._calculate_total_value_from_portfolio()

        result = {
            'strategy': strategy_name,
            'status': 'success' if (check or {}).get('executed', True) else 'skipped',
            'check': check,
            'account_name': trader.account_name,
            'timestamp': datetime.now().isoformat(),
            'initial_value': round(initial_value, 2),
            'final_value': round(final_value, 2),
            'cash': round(trader.cash, 2),
            'positions_count': len(trader.portfolio),
            'cumulative_return': round(final_value / config.get('initial_capital', 100000) - 1, 4)
        }

        logger.info(f"\n执行结果:")
        logger.info(f"  策略: {strategy_name}")
        logger.info(f"  状态: 成功")
        logger.info(f"  最终资产: ¥{result['final_value']:,.2f}")
        logger.info(f"  持仓数量: {result['positions_count']}只")
        logger.info(f"{'='*70}")
        logger.info(f"✅ {strategy_name.upper()} 每日检查完成")
        logger.info(f"{'='*70}")

        return result

    def _create_trader(self, config: Dict, **kwargs) -> SimulationTrader:
        """
        创建配置驱动的交易器

        Args:
            config: 策略配置
            **kwargs: 可选覆盖参数

        Returns:
            SimulationTrader: 配置好的交易器实例
        """
        # 账户与因子计算器必须在构造时注入（账户状态在 __init__ 内加载）
        trader = SimulationTrader(
            account_name=config['strategy']['account_name'],
            factor_calculator=config['model'].get('factor_calculator', 'v13'),
        )

        # 模型文件路径（load_model 读取实例属性）
        trader.model_path = config['model']['model_path']
        trader.factors_path = config['model']['factors_path']

        # 调仓周期：should_rebalance 读 config['strategy']['rebalance_days']
        trader.config['strategy']['rebalance_days'] = kwargs.get(
            'rebalance_days', config['trading']['rebalance_days'])

        # 止损阈值：check_single_stock_stop_loss 读 risk_controller.single_stop_loss
        if 'risk' in config:
            trader.risk_controller.single_stop_loss = kwargs.get(
                'stop_loss_pct', config['risk']['single_stock_stop_loss'])

        # 加载模型
        trader.load_model()

        logger.info(f"交易器已配置:")
        logger.info(f"  账户: {trader.account_name}")
        logger.info(f"  模型: {trader.model_path}")
        logger.info(f"  调仓周期: {trader.config['strategy']['rebalance_days']}天")
        logger.info(f"  单股止损: {trader.risk_controller.single_stop_loss:.0%}")

        return trader

    def _position_to_dict(self, position) -> Dict:
        """
        持仓对象转字典

        Args:
            position: 持仓对象（ORM）

        Returns:
            Dict: 持仓字典
        """
        shares = float(position.shares_total or 0)
        cost = float(position.avg_cost or 0)
        current_price = float(position.current_price or position.avg_cost or 0)
        market_value = shares * current_price
        profit = (current_price - cost) * shares
        profit_pct = (current_price / cost - 1) if cost > 0 else 0

        return {
            'symbol': position.symbol,
            'name': getattr(position, 'name', position.symbol),
            'shares': round(shares, 2),
            'shares_available': position.shares_available,
            'cost': round(cost, 2),
            'current_price': round(current_price, 2),
            'market_value': round(market_value, 2),
            'profit': round(profit, 2),
            'profit_pct': round(profit_pct, 4),
            'weight': 0  # 需要从账户总资产计算
        }
