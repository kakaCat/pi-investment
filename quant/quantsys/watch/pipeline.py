"""Core watch pipeline orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Protocol

from quantsys.watch.agent import AgentDecision, DecisionAgentClient
from quantsys.watch.confirmation import ConfirmationChannel, ConfirmationResult
from quantsys.watch.execution import OrderRequest, OrderResult, SimulatedOrderExecutor
from quantsys.watch.journal import DecisionRecord, InMemoryDecisionJournal
from quantsys.watch.notifier import FeishuNotifier
from quantsys.watch.trigger import CandidateOpportunity, StaticThresholdTrigger


class ExecutionMode(str, Enum):
    """Execution behavior after the agent returns a buy decision."""

    TEST = "test"
    PROD = "prod"


class MarketDataSource(Protocol):
    """Minimal realtime quote source required by the watch pipeline."""

    def fetch_realtime_quote(self, symbol: str) -> dict:
        """Return the latest quote for a symbol."""


@dataclass(frozen=True)
class WatchPipelineConfig:
    """Runtime settings for one watch pipeline."""

    mode: ExecutionMode = ExecutionMode.TEST
    total_equity: float = 100000.0
    duplicate_cooldown_seconds: int = 300
    min_confidence_to_trade: float = 0.7


@dataclass(frozen=True)
class WatchResult:
    """Result emitted for each triggered opportunity."""

    opportunity: CandidateOpportunity
    decision: AgentDecision
    status: str
    confirmation: ConfirmationResult | None = None
    order_result: OrderResult | None = None


class WatchPipeline:
    """Poll quotes, trigger opportunities, ask an agent, then execute or notify."""

    def __init__(
        self,
        config: WatchPipelineConfig,
        data_source: MarketDataSource,
        trigger: StaticThresholdTrigger,
        agent: DecisionAgentClient,
        confirmation_channel: ConfirmationChannel,
        executor: SimulatedOrderExecutor,
        notifier: FeishuNotifier,
        journal: InMemoryDecisionJournal,
    ) -> None:
        self.config = config
        self.data_source = data_source
        self.trigger = trigger
        self.agent = agent
        self.confirmation_channel = confirmation_channel
        self.executor = executor
        self.notifier = notifier
        self.journal = journal
        self._last_triggered_at: dict[str, datetime] = {}

    def scan_once(self, symbols: list[str], now: datetime | None = None) -> list[WatchResult]:
        """Fetch one quote per symbol and process triggered opportunities."""
        current_time = now or datetime.now()
        results = []

        for symbol in symbols:
            try:
                quote = self.data_source.fetch_realtime_quote(symbol)
            except Exception as exc:
                self.notifier.notify("行情获取失败", {"symbol": symbol, "error": str(exc)})
                continue

            opportunity = self.trigger.evaluate(symbol, quote, current_time)
            if not opportunity or self._is_duplicate(opportunity, current_time):
                continue

            self._last_triggered_at[opportunity.dedup_key] = current_time
            results.append(self._process_opportunity(opportunity, current_time))

        return results

    def _process_opportunity(self, opportunity: CandidateOpportunity, now: datetime) -> WatchResult:
        decision = self.agent.decide(opportunity)

        if decision.action != "buy" or decision.confidence < self.config.min_confidence_to_trade:
            return self._finish(opportunity, decision, "skipped", now)

        confirmation = None
        if self.config.mode == ExecutionMode.TEST:
            confirmation = self.confirmation_channel.request_confirmation(opportunity, decision)
            if not confirmation.approved:
                return self._finish(opportunity, decision, "rejected", now, confirmation=confirmation)

        order = self._build_order(opportunity, decision, now)
        order_result = self.executor.execute(order)
        title = "测试挂单已确认" if self.config.mode == ExecutionMode.TEST else "自动交易已执行"
        self.notifier.notify(title, self._notification_payload(opportunity, decision, order_result))
        return self._finish(opportunity, decision, "executed", now, confirmation, order_result)

    def _build_order(
        self,
        opportunity: CandidateOpportunity,
        decision: AgentDecision,
        now: datetime,
    ) -> OrderRequest:
        target_value = self.config.total_equity * decision.target_position_pct
        raw_shares = int(target_value / opportunity.price) if opportunity.price > 0 else 0
        shares = max(100, raw_shares // 100 * 100)
        return OrderRequest(
            symbol=opportunity.symbol,
            action=decision.action,
            price=opportunity.price,
            shares=shares,
            reason=decision.reason,
            created_at=now,
            stop_loss=decision.stop_loss,
            take_profit=decision.take_profit,
        )

    def _finish(
        self,
        opportunity: CandidateOpportunity,
        decision: AgentDecision,
        status: str,
        now: datetime,
        confirmation: ConfirmationResult | None = None,
        order_result: OrderResult | None = None,
    ) -> WatchResult:
        self.journal.record(
            DecisionRecord(
                timestamp=now,
                opportunity=opportunity,
                decision=decision,
                status=status,
                confirmation=confirmation,
                order_result=order_result,
            )
        )
        return WatchResult(
            opportunity=opportunity,
            decision=decision,
            status=status,
            confirmation=confirmation,
            order_result=order_result,
        )

    def _is_duplicate(self, opportunity: CandidateOpportunity, now: datetime) -> bool:
        last = self._last_triggered_at.get(opportunity.dedup_key)
        if not last:
            return False
        elapsed = (now - last).total_seconds()
        return elapsed < self.config.duplicate_cooldown_seconds

    @staticmethod
    def _notification_payload(
        opportunity: CandidateOpportunity,
        decision: AgentDecision,
        order_result: OrderResult,
    ) -> dict:
        return {
            "symbol": opportunity.symbol,
            "price": opportunity.price,
            "trigger_reason": opportunity.reason,
            "agent_action": decision.action,
            "confidence": decision.confidence,
            "order_id": order_result.order_id,
            "shares": order_result.shares,
            "mode": order_result.mode,
        }
