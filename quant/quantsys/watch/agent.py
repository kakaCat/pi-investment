"""Agent decision interface for watch opportunities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from quantsys.watch.trigger import CandidateOpportunity


@dataclass(frozen=True)
class AgentDecision:
    """Structured response returned by the decision agent."""

    action: str
    confidence: float
    reason: str
    target_position_pct: float = 0.0
    stop_loss: float | None = None
    take_profit: float | None = None
    valid_seconds: int = 300


class DecisionAgentClient(Protocol):
    """Interface used by the watch pipeline to ask an agent for a decision."""

    def decide(self, opportunity: CandidateOpportunity) -> AgentDecision:
        """Return buy, skip, or wait for one candidate opportunity."""
