"""Mixin providing factor calculation via FactorCalculatorAdapter."""
from __future__ import annotations

# 2026-09-11（investor / w-8f2c4cc5）修复：cd952915 盲改为 domain.quantlib.adapters，
# 但该路径从未存在（domain/quantlib/adapters/ 是空目录，无 __init__.py）→ ImportError，
# 本文件位于 domain.backtest.engine 包初始化链上（enhanced_strategy_base → mixins），
# 导入即炸；StrategyCodeService 初始化失败的下一颗雷（错误看板事件 236ff599）。
# get_factor_adapter 的真实定义在 infrastructure.quantlib.adapters（factor_calculator_adapter.py）。
from infrastructure.quantlib.adapters import get_factor_adapter


class FactorMixin:
    """Mixin that gives strategies access to factor calculations."""

    def __init__(self):
        self.factor_adapter = get_factor_adapter()

    def calculate_factors(
        self, klines: list[dict], factor_names: list[str] | None = None
    ) -> dict[str, float | None]:
        if factor_names is None:
            factor_names = self.factor_adapter.names(category='technical')
        if not factor_names:
            return {}
        return self.factor_adapter.calculate_batch(factor_names, klines)

    def get_factor_categories(self) -> dict[str, str]:
        return {f['name']: f['category'] for f in self.factor_adapter.list_all()}
