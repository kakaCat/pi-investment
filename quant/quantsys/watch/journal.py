"""Decision journal for watch pipeline auditing."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from quantsys.watch.agent import AgentDecision
from quantsys.watch.confirmation import ConfirmationResult
from quantsys.watch.execution import OrderResult
from quantsys.watch.trigger import CandidateOpportunity


@dataclass(frozen=True)
class DecisionRecord:
    """One audited watch pipeline decision."""

    timestamp: datetime
    opportunity: CandidateOpportunity
    decision: AgentDecision
    status: str
    confirmation: ConfirmationResult | None = None
    order_result: OrderResult | None = None


class InMemoryDecisionJournal:
    """Append-only in-memory journal, suitable for tests and local dry runs."""

    def __init__(self) -> None:
        self.records: list[DecisionRecord] = []

    def record(self, record: DecisionRecord) -> None:
        self.records.append(record)
