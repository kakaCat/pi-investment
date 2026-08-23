"""Mixin providing factor calculation via FactorCalculatorAdapter."""
from __future__ import annotations

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
