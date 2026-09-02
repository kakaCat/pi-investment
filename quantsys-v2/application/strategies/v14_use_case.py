"""
V14 strategy use case — application-level orchestration.

Same daily workflow as V13 (:class:`XGBoostStrategyUseCase`) driven by
``V14_CONFIG``: P0-optimized model, 30-day rebalance, 15 positions. All
business logic lives in the domain ``XGBoostStrategy``; this layer only
wires it to infrastructure.
"""
from __future__ import annotations

from application.strategies.v13_use_case import XGBoostStrategyUseCase
from application.strategies.v14_config import V14_CONFIG

__all__ = ["V14StrategyUseCase"]


class V14StrategyUseCase(XGBoostStrategyUseCase):
    """V14 daily workflow: XGBoost optimized, 30-day rebalance, 15 positions."""

    CONFIG = V14_CONFIG
