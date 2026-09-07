"""Factory for creating versioned XGBoost strategy use cases."""
from __future__ import annotations

from typing import Any, Dict, Type

from application.strategies import (
    V13StrategyUseCase,
    V14StrategyUseCase,
    XGBoostStrategyUseCase,
)

__all__ = ["StrategyFactory"]


class StrategyFactory:
    """Create the appropriate :class:`XGBoostStrategyUseCase` subclass by version."""

    VERSIONS: Dict[str, Type[XGBoostStrategyUseCase]] = {
        "V13": V13StrategyUseCase,
        "V14": V14StrategyUseCase,
    }

    @classmethod
    def create(
        cls,
        version: str,
        trader: Any,
        feishu_notifier: Any,
        position_repo: Any,
        account_name: str,
    ) -> XGBoostStrategyUseCase:
        """Build a strategy use case for ``version``.

        Args:
            version: Strategy version identifier (``"V13"`` or ``"V14"``).
            trader: Execution adapter.
            feishu_notifier: Feishu notifier instance.
            position_repo: Position repository.
            account_name: Account identifier.

        Returns:
            An instance of the requested strategy use case.

        Raises:
            ValueError: If ``version`` is not supported.
        """
        version = version.upper()
        use_case_class = cls.VERSIONS.get(version)
        if use_case_class is None:
            raise ValueError(
                f"Unknown strategy version: {version!r}. "
                f"Supported versions: {', '.join(sorted(cls.VERSIONS))}"
            )
        return use_case_class(
            trader=trader,
            feishu_notifier=feishu_notifier,
            position_repo=position_repo,
            account_name=account_name,
        )
