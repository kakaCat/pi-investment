"""Strategy Factory — auto-discover, register, create, DB sync."""
from __future__ import annotations
import importlib
import inspect
import logging
import re
from typing import Type

from domain.backtest.engine.strategy_base import StrategyBase
from domain.backtest.engine.enhanced_strategy_base import EnhancedStrategyBase

logger = logging.getLogger(__name__)


class StrategyFactory:
    """Factory for auto-discovering and instantiating strategies.

    Scans quantlib.engine for StrategyBase subclasses, registers them,
    and can sync metadata to the database.
    """

    _registry: dict[str, Type[StrategyBase]] = {}
    _metadata: dict[str, dict] = {}

    # Strategy file names to scan
    _STRATEGY_MODULES = [
        'ma_cross', 'rsi_reversal', 'bollinger_breakout',
        'turtle_strategy', 'donchian_channel_strategy',
        'momentum_strategy', 'breakout_strategy',
        'mean_reversion_strategy', 'volatility_breakout_strategy',
        'pairs_correlation_strategy',
        'multi_factor_strategy', 'ml_prediction_strategy',
        'adx_trend_strategy', 'cci_reversal_strategy',
        'grid_trading_strategy',
        'config_driven_strategy',
        'multi_factor_swing_strategy',
        'ensemble_vote_strategy',
        'pe_momentum_ma60_strategy',
    ]

    @classmethod
    def auto_discover(cls, package_path: str | None = None) -> None:
        """扫描本包下的策略模块并注册。

        2026-09-13 修复（w-a9ec14d7）：原默认参数把包路径**写死为 quantlib.engine** ——
        那是索引重构前的包名，本仓早已改为 domain.backtest.engine，于是一直扫不到任何模块：
        strategy_list(source='builtin') 长期静默返回空（路由拿到空注册表就回 []，
        上层只能看到「没有内置策略」，看不到「加载失败」）。

        两处根因一起修：
          ① 包路径从本模块自身推导（__package__），以后再改名也不会失配；
          ② 失败不再静默：模块文件**存在**但导入失败 → 记入 _load_errors 并告警；
             模块文件**不存在** → 视为可选策略静默跳过（不制造噪声）。
        """
        import os
        pkg = package_path or __package__ or 'domain.backtest.engine'
        cls._load_errors = []
        pkg_dir = os.path.dirname(os.path.abspath(__file__))
        for module_name in cls._STRATEGY_MODULES:
            exists = os.path.exists(os.path.join(pkg_dir, module_name + '.py'))
            try:
                module = importlib.import_module(f'{pkg}.{module_name}')
                for name, obj in inspect.getmembers(module, inspect.isclass):
                    if not name.endswith('Strategy'):
                        continue
                    if obj in (StrategyBase, EnhancedStrategyBase):
                        continue
                    if issubclass(obj, StrategyBase):
                        strategy_type = cls.class_name_to_type(name)
                        cls.register(strategy_type, obj)
            except ModuleNotFoundError as e:
                if not exists:
                    continue  # 可选策略模块本就不存在
                cls._load_errors.append({'module': module_name, 'error': str(e)})
                logger.warning('策略模块存在但导入失败 %s.%s: %s', pkg, module_name, e)
            except Exception as e:
                cls._load_errors.append({'module': module_name, 'error': str(e)})
                logger.warning('Failed to load %s: %s', module_name, e)

    @classmethod
    def list_load_errors(cls) -> list[dict]:
        """返回最近一次 auto_discover 的加载失败清单（空注册表不再冒充「没有策略」）。"""
        return list(getattr(cls, '_load_errors', []))

    @classmethod
    def register(cls, strategy_type: str, strategy_class: Type[StrategyBase]):
        cls._registry[strategy_type] = strategy_class
        cls._metadata[strategy_type] = cls._extract_metadata(strategy_class)

    @classmethod
    def create(cls, strategy_type: str, **kwargs) -> StrategyBase:
        if strategy_type not in cls._registry:
            raise ValueError(
                f"Unknown strategy type: '{strategy_type}'. "
                f"Available: {cls.list_all()}"
            )
        return cls._registry[strategy_type](**kwargs)

    @classmethod
    def list_all(cls) -> list[str]:
        return sorted(cls._registry.keys())

    @classmethod
    def get_info(cls, strategy_type: str) -> dict | None:
        return cls._metadata.get(strategy_type)

    @classmethod
    def _extract_metadata(cls, strategy_class: Type[StrategyBase]) -> dict:
        return {
            'class_name': strategy_class.__name__,
            'description': (strategy_class.__doc__ or '').strip().split('\n')[0],
            'category': cls._infer_category(strategy_class.__name__),
            'default_params': getattr(strategy_class, 'DEFAULT_PARAMS', {}),
            'param_schema': getattr(strategy_class, 'PARAM_SCHEMA', {}),
        }

    @staticmethod
    def class_name_to_type(class_name: str) -> str:
        name = class_name.replace('Strategy', '')
        s1 = re.sub(r'(.)([A-Z][a-z]+)', r'\1_\2', name)
        return re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', s1).lower()

    @staticmethod
    def _infer_category(class_name: str) -> str:
        lower = class_name.lower()
        if any(x in lower for x in ['trend', 'ma', 'adx', 'turtle', 'donchian']):
            return 'trend_following'
        if any(x in lower for x in ['reversal', 'rsi', 'cci', 'mean']):
            return 'mean_reversion'
        if any(x in lower for x in ['grid']):
            return 'arbitrage'
        if any(x in lower for x in ['ml', 'prediction']):
            return 'machine_learning'
        if any(x in lower for x in ['factor', 'multi']):
            return 'multi_factor'
        if any(x in lower for x in ['volatility', 'breakout', 'bollinger']):
            return 'volatility'
        return 'other'

    @classmethod
    def sync_to_database(cls, repo) -> int:
        """
        Sync registered strategies to database

        Args:
            repo: Strategy repository interface (injected by caller, e.g.
                  StrategyORMRepository wired by the Adapters/Application layer)

        Raises:
            ValueError: repo 未注入。domain 层不再自行创建 adapters 具体仓储
                (六边形架构依赖方向)。
        """
        if repo is None:
            raise ValueError(
                "StrategyFactory.sync_to_database requires a strategy repository "
                "injection (e.g. StrategyORMRepository from "
                "adapters.outbound.repositories, wired by the caller)"
            )

        count = 0
        for strategy_type, metadata in cls._metadata.items():
            try:
                repo.upsert_metadata({
                    'strategy_type': strategy_type,
                    'class_name': metadata['class_name'],
                    'description': metadata['description'],
                    'category': metadata['category'],
                    'default_params': metadata.get('default_params', {}),
                    'param_schema': metadata.get('param_schema', {}),
                    'is_available': True,
                })
                count += 1
            except Exception as e:
                logger.warning("Failed to sync %s: %s", strategy_type, e)
        logger.info("Synced %d strategies to database", count)
        return count
