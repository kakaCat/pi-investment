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
import math
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

from live_trading.simulation_trader import SimulationTrader
from domain.ports import ISimulationRepository

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# 策略参数单一来源（REQ-261004154902-a7cd · FR-5 · t-979319）
#
# 声明源（唯一）：live_trading/configs/strategies/<name>.yaml
# 执行环境       ：live_trading/config_simulation.yaml（SimulationTrader 实际加载的那份）
#
# 修的旧 bug：`_create_trader` 只覆盖 `rebalance_days` 与 `single_stop_loss`，
# 其余策略参数静默沿用执行环境 —— 账户实际持 **5** 只，而 v13.yaml / 文档 / 代码常量
# 一律声明 **8** 只；单股权重、仓位上限同理。现在改为**全量覆盖**，并把
# 「声明值 / 执行环境(覆盖前) / 生效值」逐项打进日志（不一致时 warning 说明以声明源为准）。
# ─────────────────────────────────────────────────────────────────────────────

#: 受本链路约束、必须由声明源决定的运行时键（顺序即日志顺序）
DECLARED_RUNTIME_KEYS = (
    'rebalance_days',
    'top_n',
    'single_stock_stop_loss',
    'portfolio_stop_loss',
    'max_position',
    'min_position',
    'max_single_weight',
)

#: 声明源里的键名 → 运行时键名。左右不同名处一律注明，勿凭名字猜。
_DECLARED_KEY_SOURCES = {
    'rebalance_days': ('trading', 'rebalance_days'),
    'top_n': ('trading', 'top_n'),
    'max_positions': ('trading', 'max_positions'),          # 与 top_n 同义；二者不一致时以 top_n 为准并告警
    'single_stock_stop_loss': ('risk', 'single_stock_stop_loss'),
    'portfolio_stop_loss': ('risk', 'portfolio_stop_loss'),
    'max_position': ('trading', 'max_position_pct'),        # 运行时 max_position ← 声明的 trading.max_position_pct
    'min_position': ('risk', 'min_position'),
    'max_single_weight': ('risk', 'single_stock_weight'),   # 运行时 max_single_weight ← 声明的 single_stock_weight
}

#: 以比例表示的参数（日志里同时给百分比，便于人读）
_RATIO_KEYS = frozenset({
    'single_stock_stop_loss', 'portfolio_stop_loss',
    'max_position', 'min_position', 'max_single_weight',
})

#: 运行时键 → RiskController 上的**实际属性名**。
#: ⚠️ RiskController 构造时就把执行环境的值拷进属性，之后只改 `trader.config` 是**不生效**的
#: ——这正是旧 bug 只有 `single_stop_loss` 真正生效的原因（它当时是直接写属性）。
_RISK_CONTROLLER_ATTRS = {
    'top_n': 'top_n',
    'single_stock_stop_loss': 'single_stop_loss',
    'portfolio_stop_loss': 'portfolio_stop_loss',
    'max_position': 'max_position',
    'min_position': 'min_position',
    'max_single_weight': 'max_single_weight',
}

#: 死参数：API 与调度任务一直在传，全仓没有任何读取点（"以为能关掉，其实关不掉"）
_DEAD_KWARGS = ('enable_stop_loss', 'enable_rebalance')


def _fmt_param(key, value) -> str:
    """参数值的可读形式（比例同时给百分比）。"""
    if value is None:
        return 'None'
    if key in _RATIO_KEYS and isinstance(value, (int, float)):
        return f"{value:g} ({value:.1%})"
    if isinstance(value, (int, float)):
        return f"{value:g}"
    return str(value)


def _runtime_read(trader_config: Dict, key: str):
    """读运行时配置里的实际取值位置（trader 真正读的地方）。"""
    if key == 'rebalance_days':
        return (trader_config.get('strategy') or {}).get('rebalance_days')
    return (trader_config.get('risk_control') or {}).get(key)


def _runtime_write(trader_config: Dict, key: str, value) -> None:
    """写运行时配置里 trader 真正读的位置。"""
    if key == 'rebalance_days':
        trader_config.setdefault('strategy', {})['rebalance_days'] = value
    else:
        trader_config.setdefault('risk_control', {})[key] = value


class StrategyService:
    """策略服务（统一管理所有策略版本）

    P2-1: 支持依赖注入，保持向后兼容
    """

    @staticmethod
    def _sanitize_float(value):
        """清理浮点数：将 NaN/Inf 转换为 None，避免 JSON 序列化错误"""
        if isinstance(value, (int, float)):
            if math.isnan(value) or math.isinf(value):
                return None
        return value

    def __init__(self, repo: Optional[ISimulationRepository] = None):
        """初始化服务

        Args:
            repo: 模拟仓库（可选）

        P2-1: 推荐通过 ServiceFactory 获取实例
        """
        self.config_dir = Path(__file__).parent.parent.parent / 'live_trading' / 'configs' / 'strategies'
        self.repo = repo
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
        from infrastructure.services.service_factory import ServiceFactory
        repo = ServiceFactory.resolve(ISimulationRepository)
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

        # 2026-10-04（REQ-261004154902-a7cd t2）：手动调仓同样不许无条件报成功
        ok = isinstance(result, dict) and bool(result.get('success'))
        if not ok:
            error = (result or {}).get('error') if isinstance(result, dict) else str(result)
            logger.error(f"❌ {strategy_name} 手动调仓未成功: {error}")
        else:
            logger.info(f"✅ {strategy_name} 调仓完成")

        return {
            'strategy': strategy_name,
            'status': 'success' if ok else 'failed',
            'ok': ok,
            'error': None if ok else ((result or {}).get('error') if isinstance(result, dict) else str(result)),
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
            # 2026-10-04（REQ-261004154902-a7cd t2）：三态映射。
            # 此前只认 executed 布尔 → 「跳过」与「失败」都被压成 success（空转剧场）。
            # 现在以契约自带的 status 为准（success / skipped / failed），缺失时回退旧口径。
            'status': (check or {}).get('status')
            or ('success' if (check or {}).get('executed', True) else 'skipped'),
            'ok': (check or {}).get('ok'),
            'reason': (check or {}).get('reason'),
            'error': (check or {}).get('error'),
            'check': check,
            'account_name': trader.account_name,
            'timestamp': datetime.now().isoformat(),
            'initial_value': self._sanitize_float(round(initial_value, 2)),
            'final_value': self._sanitize_float(round(final_value, 2)),
            'cash': self._sanitize_float(round(trader.cash, 2)),
            'positions_count': len(trader.portfolio),
            'cumulative_return': self._sanitize_float(round(final_value / config.get('initial_capital', 100000) - 1, 4))
        }

        logger.info(f"\n执行结果:")
        logger.info(f"  策略: {strategy_name}")
        logger.info(f"  状态: {result['status']}（reason={result['reason']}）")
        logger.info(f"  最终资产: ¥{result['final_value']:,.2f}")
        logger.info(f"  持仓数量: {result['positions_count']}只")
        logger.info(f"{'='*70}")
        if result['status'] == 'failed':
            logger.error(
                f"❌ {strategy_name.upper()} 每日检查失败: {result['error']}"
            )
        elif result['status'] == 'skipped':
            logger.info(
                f"⏭️ {strategy_name.upper()} 每日检查跳过（{result['reason']}）——不算成功"
            )
        else:
            logger.info(f"✅ {strategy_name.upper()} 每日检查完成")
        logger.info(f"{'='*70}")

        return result

    @staticmethod
    def declared_params(config: Dict, overrides: Optional[Dict] = None) -> Dict:
        """从**声明源**（策略 yaml）提取受约束的策略参数。

        Args:
            config: 策略声明配置（v13.yaml 之类）
            overrides: 调用方显式覆盖（优先级最高；None 值忽略）

        Returns:
            Dict: 扁平字典，键为运行时键名；**声明源缺失的键为 None**（不猜默认值）
        """
        extracted: Dict = {}
        for runtime_key, (section, yaml_key) in _DECLARED_KEY_SOURCES.items():
            section_cfg = config.get(section) or {}
            extracted[runtime_key] = section_cfg.get(yaml_key)

        for key, value in (overrides or {}).items():
            if key in extracted and value is not None:
                extracted[key] = value
        return extracted

    @staticmethod
    def apply_declared_overrides(trader_config: Dict, declared: Dict,
                                 keys=None) -> Dict:
        """把声明值**全量写入** trader 的运行时配置，并回报覆盖前后取值。

        纯函数（只操作传入的 dict，不碰 IO/DB），因此一致性检查器与单测可直接调用它，
        不必构造真实的 SimulationTrader —— 口径与生产路径同一份实现。

        Args:
            trader_config: trader 的运行时配置（即 config_simulation.yaml 加载结果）
            declared: `declared_params()` 的产出
            keys: 只覆盖这些键（缺省 = 全量）。仅供检查器/单测复现「覆盖不全」的历史形态

        Returns:
            Dict: {'before': {...}, 'effective': {...}, 'applied': [...], 'skipped': [...]}
        """
        covered = DECLARED_RUNTIME_KEYS if keys is None else tuple(keys)
        before, effective, applied, skipped = {}, {}, [], []

        for key in DECLARED_RUNTIME_KEYS:
            before[key] = _runtime_read(trader_config, key)
            value = declared.get(key)
            if key not in covered or value is None:
                effective[key] = before[key]
                skipped.append(key)
                continue
            _runtime_write(trader_config, key, value)
            effective[key] = value
            applied.append(key)

        return {'before': before, 'effective': effective,
                'applied': applied, 'skipped': skipped}

    @staticmethod
    def _push_effective_to_trader(trader, effective: Dict) -> None:
        """把生效值同步到 trader **真正读取**的位置。

        `rebalance_days` 由 trader 每次实时读 `config['strategy']`，故只需写 config；
        其余风控参数由 `RiskController` 在**构造时**拷进属性，必须回写属性才真正生效。
        （漏掉这一步 = 日志说 8 只、实际仍 5 只，即本卡要消灭的「假声明」。）
        """
        risk_controller = getattr(trader, 'risk_controller', None)
        for runtime_key, attr in _RISK_CONTROLLER_ATTRS.items():
            value = effective.get(runtime_key)
            if risk_controller is not None and value is not None:
                setattr(risk_controller, attr, value)

    @staticmethod
    def _log_effective_params(declared: Dict, resolution: Dict) -> None:
        """逐项打印「声明值 vs 生效值」，不一致处说明以哪份为准。"""
        logger.info("策略参数单一来源核对（声明源 vs 生效值）：")
        logger.info(f"  {'参数':<24}{'声明值':>16}{'执行环境(覆盖前)':>20}{'生效值':>16}  来源")
        for key in DECLARED_RUNTIME_KEYS:
            declared_value = declared.get(key)
            before_value = resolution['before'][key]
            effective_value = resolution['effective'][key]
            if key in resolution['applied']:
                source = '声明源'
            elif declared_value is None:
                source = '未声明→执行环境'
            else:
                source = '未覆盖→执行环境(异常)'
            logger.info(
                f"  {key:<24}{_fmt_param(key, declared_value):>16}"
                f"{_fmt_param(key, before_value):>20}{_fmt_param(key, effective_value):>16}  {source}"
            )
            if declared_value is not None and before_value is not None and before_value != declared_value:
                logger.warning(
                    f"  ⚠️ {key}: 执行环境 {_fmt_param(key, before_value)} ≠ 声明 "
                    f"{_fmt_param(key, declared_value)} → **以声明源为准**（生效 "
                    f"{_fmt_param(key, effective_value)}）"
                )

        missing = [k for k in DECLARED_RUNTIME_KEYS if declared.get(k) is None]
        if missing:
            logger.warning(
                f"  ⚠️ 声明源未声明这些策略参数，沿用执行环境值：{', '.join(missing)}"
            )

    @staticmethod
    def _warn_dead_kwargs(kwargs: Dict) -> None:
        """死参数响亮化：要求的行为与实际行为不符时必须说出来。"""
        for dead in _DEAD_KWARGS:
            if dead in kwargs and not kwargs[dead]:
                logger.warning(
                    f"  ⚠️ 死参数 {dead}={kwargs[dead]!r} 不生效：全仓无任何读取点"
                    f"（REQ-261004154902-a7cd FR-5）——本次仍会照常执行；"
                    f"要真正关闭请改策略配置或停用对应调度任务。"
                )

    def _create_trader(self, config: Dict, **kwargs) -> SimulationTrader:
        """
        创建配置驱动的交易器

        Args:
            config: 策略配置（**唯一声明源**）
            **kwargs: 可选覆盖参数（优先级：kwargs > 声明源 > 执行环境）

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

        # 2026-10-04（REQ-261004154902-a7cd FR-5）：全量覆盖 + 生效值可见。
        # 历史 bug：只覆盖 rebalance_days / single_stop_loss → top_n、仓位、权重静默沿用
        # 执行环境（账户实际 5 只 vs 声明 8 只）。
        overrides = {k: v for k, v in kwargs.items() if k in _DECLARED_KEY_SOURCES}
        if 'stop_loss_pct' in kwargs and kwargs['stop_loss_pct'] is not None:
            overrides['single_stock_stop_loss'] = kwargs['stop_loss_pct']  # 历史参数名
        declared = self.declared_params(config, overrides)

        # top_n 与 max_positions 同义：不一致时以 top_n 为准并告警
        if declared['top_n'] is None and declared['max_positions'] is not None:
            declared['top_n'] = declared['max_positions']
        elif (declared['top_n'] is not None and declared['max_positions'] is not None
              and declared['top_n'] != declared['max_positions']):
            logger.warning(
                f"⚠️ 声明源自相矛盾：top_n={declared['top_n']} ≠ "
                f"max_positions={declared['max_positions']} → 以 top_n 为准"
            )

        resolution = self.apply_declared_overrides(trader.config, declared)
        self._push_effective_to_trader(trader, resolution['effective'])
        self._log_effective_params(declared, resolution)
        self._warn_dead_kwargs(kwargs)

        # 加载模型
        trader.load_model()

        logger.info(f"交易器已配置:")
        logger.info(f"  账户: {trader.account_name}")
        logger.info(f"  模型: {trader.model_path}")
        logger.info(f"  调仓周期: {resolution['effective']['rebalance_days']}天")
        logger.info(f"  持仓上限: {resolution['effective']['top_n']}只")
        logger.info(
            f"  单股止损: {_fmt_param('single_stock_stop_loss', resolution['effective']['single_stock_stop_loss'])}"
        )

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
