from __future__ import annotations

from datetime import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from quantsys.watch import (
    AgentDecision,
    CandidateOpportunity,
    CliConfirmationChannel,
    ConfirmationResult,
    DecisionAgentClient,
    ExecutionMode,
    FeishuNotifier,
    InMemoryDecisionJournal,
    SimulatedOrderExecutor,
    StaticThresholdTrigger,
    WatchPipeline,
    WatchPipelineConfig,
)


class FakeMarketDataSource:
    def __init__(self, quotes):
        self.quotes = quotes

    def fetch_realtime_quote(self, symbol: str) -> dict:
        if isinstance(self.quotes[symbol], Exception):
            raise self.quotes[symbol]
        return dict(self.quotes[symbol])


class RecordingAgent(DecisionAgentClient):
    def __init__(self, decision: AgentDecision):
        self.decision = decision
        self.received = []

    def decide(self, opportunity: CandidateOpportunity) -> AgentDecision:
        self.received.append(opportunity)
        return self.decision


class RecordingConfirmation(CliConfirmationChannel):
    def __init__(self, approved: bool = True):
        self.approved = approved
        self.requests = []

    def request_confirmation(
        self,
        opportunity: CandidateOpportunity,
        decision: AgentDecision,
    ) -> ConfirmationResult:
        self.requests.append((opportunity, decision))
        return ConfirmationResult(approved=self.approved, approver="tester")


class RecordingFeishu(FeishuNotifier):
    def __init__(self):
        self.messages = []

    def notify(self, title: str, payload: dict) -> None:
        self.messages.append((title, payload))


def test_watch_pipeline_sends_triggered_quote_to_agent_and_requires_manual_confirmation():
    quote = {
        "symbol": "600036",
        "name": "招商银行",
        "price": 35.2,
        "change_pct": 2.1,
        "volume": 1000000,
        "amount": 35000000,
    }
    source = FakeMarketDataSource({"600036": quote})
    trigger = StaticThresholdTrigger({"600036": 35.0})
    agent = RecordingAgent(
        AgentDecision(
            action="buy",
            confidence=0.82,
            target_position_pct=0.1,
            stop_loss=33.5,
            take_profit=39.0,
            reason="突破阈值且成交额放大",
        )
    )
    confirmation = RecordingConfirmation(approved=True)
    executor = SimulatedOrderExecutor()
    notifier = RecordingFeishu()
    journal = InMemoryDecisionJournal()

    pipeline = WatchPipeline(
        config=WatchPipelineConfig(mode=ExecutionMode.TEST, total_equity=100000),
        data_source=source,
        trigger=trigger,
        agent=agent,
        confirmation_channel=confirmation,
        executor=executor,
        notifier=notifier,
        journal=journal,
    )

    results = pipeline.scan_once(["600036"], now=datetime(2026, 5, 19, 10, 30))

    assert len(agent.received) == 1
    assert agent.received[0].symbol == "600036"
    assert len(confirmation.requests) == 1
    assert results[0].status == "executed"
    assert results[0].order_result is not None
    assert results[0].order_result.mode == "simulated"
    assert notifier.messages[-1][0] == "测试挂单已确认"
    assert journal.records[-1].decision.action == "buy"


def test_watch_pipeline_deduplicates_same_symbol_trigger_within_cooldown():
    source = FakeMarketDataSource({"600036": {"symbol": "600036", "price": 35.2}})
    trigger = StaticThresholdTrigger({"600036": 35.0})
    agent = RecordingAgent(AgentDecision(action="buy", confidence=0.8, target_position_pct=0.1, reason="ok"))
    pipeline = WatchPipeline(
        config=WatchPipelineConfig(mode=ExecutionMode.TEST, duplicate_cooldown_seconds=300),
        data_source=source,
        trigger=trigger,
        agent=agent,
        confirmation_channel=RecordingConfirmation(True),
        executor=SimulatedOrderExecutor(),
        notifier=RecordingFeishu(),
        journal=InMemoryDecisionJournal(),
    )

    first = pipeline.scan_once(["600036"], now=datetime(2026, 5, 19, 10, 0))
    second = pipeline.scan_once(["600036"], now=datetime(2026, 5, 19, 10, 1))

    assert len(first) == 1
    assert second == []
    assert len(agent.received) == 1


def test_watch_pipeline_skips_execution_when_agent_says_skip():
    source = FakeMarketDataSource({"600036": {"symbol": "600036", "price": 35.2}})
    trigger = StaticThresholdTrigger({"600036": 35.0})
    agent = RecordingAgent(AgentDecision(action="skip", confidence=0.4, reason="信号质量不足"))
    confirmation = RecordingConfirmation(True)
    pipeline = WatchPipeline(
        config=WatchPipelineConfig(mode=ExecutionMode.TEST),
        data_source=source,
        trigger=trigger,
        agent=agent,
        confirmation_channel=confirmation,
        executor=SimulatedOrderExecutor(),
        notifier=RecordingFeishu(),
        journal=InMemoryDecisionJournal(),
    )

    results = pipeline.scan_once(["600036"], now=datetime(2026, 5, 19, 10, 0))

    assert results[0].status == "skipped"
    assert confirmation.requests == []


def test_watch_pipeline_production_mode_executes_without_manual_confirmation_and_notifies():
    source = FakeMarketDataSource({"600036": {"symbol": "600036", "price": 35.2}})
    trigger = StaticThresholdTrigger({"600036": 35.0})
    agent = RecordingAgent(AgentDecision(action="buy", confidence=0.9, target_position_pct=0.1, reason="ok"))
    confirmation = RecordingConfirmation(True)
    notifier = RecordingFeishu()
    pipeline = WatchPipeline(
        config=WatchPipelineConfig(mode=ExecutionMode.PROD, total_equity=100000),
        data_source=source,
        trigger=trigger,
        agent=agent,
        confirmation_channel=confirmation,
        executor=SimulatedOrderExecutor(),
        notifier=notifier,
        journal=InMemoryDecisionJournal(),
    )

    results = pipeline.scan_once(["600036"], now=datetime(2026, 5, 19, 10, 0))

    assert confirmation.requests == []
    assert results[0].status == "executed"
    assert notifier.messages[-1][0] == "自动交易已执行"


def test_watch_pipeline_continues_when_one_quote_fetch_fails():
    source = FakeMarketDataSource(
        {
            "600036": RuntimeError("quote timeout"),
            "000001": {"symbol": "000001", "price": 12.5},
        }
    )
    notifier = RecordingFeishu()
    pipeline = WatchPipeline(
        config=WatchPipelineConfig(mode=ExecutionMode.TEST),
        data_source=source,
        trigger=StaticThresholdTrigger({"000001": 12.0}),
        agent=RecordingAgent(AgentDecision(action="skip", confidence=0.4, reason="wait")),
        confirmation_channel=RecordingConfirmation(True),
        executor=SimulatedOrderExecutor(),
        notifier=notifier,
        journal=InMemoryDecisionJournal(),
    )

    results = pipeline.scan_once(["600036", "000001"], now=datetime(2026, 5, 19, 10, 0))

    assert len(results) == 1
    assert results[0].opportunity.symbol == "000001"
    assert notifier.messages[0][0] == "行情获取失败"
    assert notifier.messages[0][1]["symbol"] == "600036"
