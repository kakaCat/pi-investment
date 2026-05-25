"""Human confirmation channels for test-mode execution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from quantsys.watch.agent import AgentDecision
from quantsys.watch.trigger import CandidateOpportunity


@dataclass(frozen=True)
class ConfirmationResult:
    """Result of a human approval request."""

    approved: bool
    approver: str = "cli"
    reason: str | None = None


class ConfirmationChannel(Protocol):
    """Manual approval interface used before test-mode order placement."""

    def request_confirmation(
        self,
        opportunity: CandidateOpportunity,
        decision: AgentDecision,
    ) -> ConfirmationResult:
        """Ask a human to approve or reject a proposed order."""


class CliConfirmationChannel:
    """Simple interactive CLI confirmation channel."""

    def request_confirmation(
        self,
        opportunity: CandidateOpportunity,
        decision: AgentDecision,
    ) -> ConfirmationResult:
        prompt = (
            f"{opportunity.symbol} {decision.action} "
            f"confidence={decision.confidence:.2f} "
            "approve? [y/N]: "
        )
        answer = input(prompt).strip().lower()
        approved = answer in {"y", "yes"}
        return ConfirmationResult(approved=approved, approver="cli")
