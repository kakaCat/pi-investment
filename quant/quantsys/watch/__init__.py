"""Agent-assisted market watch pipeline."""

from quantsys.watch.agent import AgentDecision, DecisionAgentClient
from quantsys.watch.confirmation import (
    CliConfirmationChannel,
    ConfirmationChannel,
    ConfirmationResult,
)
from quantsys.watch.execution import OrderRequest, OrderResult, SimulatedOrderExecutor
from quantsys.watch.http_agent import HttpDecisionAgentClient
from quantsys.watch.ipo import (
    AkShareIpoSource,
    IpoCandidate,
    IpoSource,
    IpoWatchPipeline,
    IpoWatchPipelineConfig,
    IpoWatchResult,
)
from quantsys.watch.journal import DecisionRecord, InMemoryDecisionJournal
from quantsys.watch.notifier import FeishuNotifier
from quantsys.watch.pipeline import ExecutionMode, WatchPipeline, WatchPipelineConfig, WatchResult
from quantsys.watch.quote_sources import (
    AkShareRealtimeQuoteSource,
    FallbackRealtimeQuoteSource,
    SinaRealtimeQuoteSource,
)
from quantsys.watch.trigger import CandidateOpportunity, StaticThresholdTrigger

__all__ = [
    "AgentDecision",
    "CandidateOpportunity",
    "CliConfirmationChannel",
    "ConfirmationChannel",
    "ConfirmationResult",
    "DecisionAgentClient",
    "DecisionRecord",
    "ExecutionMode",
    "FeishuNotifier",
    "AkShareRealtimeQuoteSource",
    "FallbackRealtimeQuoteSource",
    "SinaRealtimeQuoteSource",
    "HttpDecisionAgentClient",
    "AkShareIpoSource",
    "InMemoryDecisionJournal",
    "IpoCandidate",
    "IpoSource",
    "IpoWatchPipeline",
    "IpoWatchPipelineConfig",
    "IpoWatchResult",
    "OrderRequest",
    "OrderResult",
    "SimulatedOrderExecutor",
    "StaticThresholdTrigger",
    "WatchPipeline",
    "WatchPipelineConfig",
    "WatchResult",
]
