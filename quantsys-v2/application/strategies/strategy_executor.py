"""Strategy executor — entry point for scheduled strategy execution.

This module orchestrates the versioned XGBoost strategies (V13/V14): it
resolves the immutable ``StrategyConfig`` for a version, builds the Feishu
notifier from app config, creates the matching use case via
:class:`StrategyFactory`, and runs its daily workflow.

Scheduled tasks call :meth:`StrategyExecutor.execute` for a single version
or :meth:`StrategyExecutor.execute_all` to run every active strategy.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, Optional

from application.strategies.strategy_factory import StrategyFactory
from application.strategies.v13_config import V13_CONFIG
from application.strategies.v14_config import V14_CONFIG
from domain.strategies.value_objects import StrategyConfig
from utils.feishu_notifier import create_notifier_from_config

__all__ = ["StrategyExecutor"]

logger = logging.getLogger(__name__)


class StrategyExecutor:
    """Orchestrate execution of all versioned strategies.

    Infrastructure dependencies are injected, keeping the executor free of
    construction-time side effects and testable.
    """

    #: Active strategy configs keyed by version identifier.
    CONFIGS: Dict[str, StrategyConfig] = {
        "V13": V13_CONFIG,
        "V14": V14_CONFIG,
    }

    def __init__(self, trader: Any, position_repo: Any, engine: Any) -> None:
        """
        Args:
            trader: Execution adapter forwarded to the use case.
            position_repo: Position repository forwarded to the use case.
            engine: Trading engine; when it exposes a dict ``config``
                attribute, that config provides the Feishu section for
                :func:`create_notifier_from_config`.
        """
        self.trader = trader
        self.position_repo = position_repo
        self.engine = engine

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def execute(
        self,
        version: str,
        date: str,
        account_name: str = "default",
    ) -> Dict[str, Any]:
        """Run the daily workflow for one strategy ``version``.

        Args:
            version: Strategy version identifier (``"V13"`` or ``"V14"``).
            date: Trading date (``YYYY-MM-DD``).
            account_name: Account identifier used for positions and audit.

        Returns:
            The use case result dict, annotated with ``version`` and
            ``account_name``.

        Raises:
            ValueError: If ``version`` is not supported.
        """
        version_key = version.upper()
        config = self.CONFIGS.get(version_key)
        if config is None:
            raise ValueError(
                f"Unknown strategy version: {version!r}. "
                f"Supported versions: {', '.join(sorted(self.CONFIGS))}"
            )

        notifier = self._create_notifier(config)
        use_case = StrategyFactory.create(
            version=version_key,
            trader=self.trader,
            feishu_notifier=notifier,
            position_repo=self.position_repo,
            account_name=account_name,
        )

        logger.info(
            "Executing strategy %s for %s (account=%s)",
            version_key,
            date,
            account_name,
        )
        result = use_case.execute(date)
        result.setdefault("version", version_key)
        result.setdefault("account_name", account_name)
        return result

    def execute_all(self, date: Optional[str] = None) -> Dict[str, Any]:
        """Run every active strategy (V13 + V14) for ``date``.

        A failure in one strategy is captured in that strategy's entry and
        does not block the remaining strategies.

        Args:
            date: Trading date (``YYYY-MM-DD``); defaults to today.

        Returns:
            Combined results keyed by version, plus ``date`` and an overall
            ``success`` flag.
        """
        date = date or datetime.now().strftime("%Y-%m-%d")
        results: Dict[str, Any] = {"date": date, "success": True}

        for version in sorted(self.CONFIGS):
            try:
                results[version] = self.execute(version, date)
            except Exception as exc:  # noqa: BLE001 - one strategy must not block the others
                logger.exception("Strategy %s execution failed for %s", version, date)
                results[version] = {"success": False, "error": str(exc)}
                results["success"] = False

        return results

    # ------------------------------------------------------------------
    # Infrastructure wiring
    # ------------------------------------------------------------------
    def _create_notifier(self, config: StrategyConfig) -> Any:
        """Build the Feishu notifier from the best available config source.

        Preference order: the engine's app config dict (which carries the
        ``feishu`` section), then the strategy config's ``params['feishu']``,
        then an empty config (notifier disabled).
        """
        engine_config = getattr(self.engine, "config", None)
        if isinstance(engine_config, dict):
            return create_notifier_from_config(engine_config)

        feishu_params = config.params.get("feishu") if config.params else None
        if isinstance(feishu_params, dict):
            return create_notifier_from_config({"feishu": feishu_params})

        return create_notifier_from_config({})
