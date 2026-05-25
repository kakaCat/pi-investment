from __future__ import annotations

from datetime import date, datetime
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from quantsys.watch import (
    AgentDecision,
    CliConfirmationChannel,
    ConfirmationResult,
    DecisionAgentClient,
    FeishuNotifier,
    InMemoryDecisionJournal,
)
from quantsys.watch.ipo import (
    AkShareIpoSource,
    IpoCandidate,
    IpoWatchPipeline,
    IpoWatchPipelineConfig,
)


class RecordingIpoAgent(DecisionAgentClient):
    def __init__(self, decision: AgentDecision):
        self.decision = decision
        self.received = []

    def decide(self, opportunity):
        self.received.append(opportunity)
        return self.decision


class RecordingConfirmation(CliConfirmationChannel):
    def __init__(self, approved: bool = True):
        self.approved = approved
        self.requests = []

    def request_confirmation(self, opportunity, decision):
        self.requests.append((opportunity, decision))
        return ConfirmationResult(approved=self.approved, approver="tester")


class RecordingFeishu(FeishuNotifier):
    def __init__(self):
        self.messages = []

    def notify(self, title: str, payload: dict) -> None:
        self.messages.append((title, payload))


class StaticIpoSource:
    def __init__(self, candidates):
        self.candidates = candidates

    def fetch_candidates(self, target_date: date):
        return list(self.candidates)


def test_ipo_watch_fetches_today_candidates_sends_to_agent_and_requires_confirmation():
    candidate = IpoCandidate(
        symbol="920218",
        name="新天力",
        subscription_code="920218",
        board="北交所",
        exchange="北京证券交易所",
        issue_price=12.19,
        subscription_date=date(2026, 5, 20),
        subscription_limit=1053800,
        required_market_value=1284.5822,
        issue_pe=14.78,
        industry_pe=30.67,
        raw={"股票简称": "新天力"},
    )
    agent = RecordingIpoAgent(
        AgentDecision(
            action="subscribe",
            confidence=0.82,
            reason="发行市盈率低于行业市盈率，允许测试申购",
        )
    )
    confirmation = RecordingConfirmation(approved=True)
    notifier = RecordingFeishu()
    journal = InMemoryDecisionJournal()
    pipeline = IpoWatchPipeline(
        config=IpoWatchPipelineConfig(min_confidence_to_confirm=0.7),
        source=StaticIpoSource([candidate]),
        agent=agent,
        confirmation_channel=confirmation,
        notifier=notifier,
        journal=journal,
    )

    results = pipeline.scan_once(target_date=date(2026, 5, 20), now=datetime(2026, 5, 20, 8, 30))

    assert len(results) == 1
    assert results[0].status == "confirmed"
    assert len(agent.received) == 1
    assert agent.received[0].symbol == "920218"
    assert agent.received[0].price == 12.19
    assert agent.received[0].quote["subscription_code"] == "920218"
    assert len(confirmation.requests) == 1
    assert notifier.messages[-1][0] == "打新确认通过"
    assert notifier.messages[-1][1]["subscription_code"] == "920218"
    assert journal.records[-1].status == "confirmed"


def test_ipo_watch_records_skipped_decision_without_confirmation_or_notification():
    candidate = IpoCandidate(
        symbol="001234",
        name="测试新股",
        subscription_code="001234",
        board="深市主板",
        exchange="深圳证券交易所",
        issue_price=20.0,
        subscription_date=date(2026, 5, 20),
        raw={},
    )
    agent = RecordingIpoAgent(AgentDecision(action="skip", confidence=0.9, reason="估值偏高"))
    confirmation = RecordingConfirmation(approved=True)
    notifier = RecordingFeishu()
    journal = InMemoryDecisionJournal()
    pipeline = IpoWatchPipeline(
        config=IpoWatchPipelineConfig(min_confidence_to_confirm=0.7),
        source=StaticIpoSource([candidate]),
        agent=agent,
        confirmation_channel=confirmation,
        notifier=notifier,
        journal=journal,
    )

    results = pipeline.scan_once(target_date=date(2026, 5, 20), now=datetime(2026, 5, 20, 8, 30))

    assert results[0].status == "skipped"
    assert confirmation.requests == []
    assert notifier.messages == []
    assert journal.records[-1].decision.reason == "估值偏高"


def test_akshare_ipo_source_normalizes_and_filters_subscription_date():
    frame = pd.DataFrame(
        [
            {
                "股票代码": "920218",
                "股票简称": "新天力",
                "申购代码": "920218",
                "交易所": "北京证券交易所",
                "板块": "北交所",
                "发行价格": 12.19,
                "申购日期": date(2026, 5, 20),
                "申购上限": 1053800,
                "顶格申购需配市值": 1284.5822,
                "发行市盈率": 14.78,
                "行业市盈率": 30.67,
            },
            {
                "股票代码": "920161",
                "股票简称": "龙辰科技",
                "申购代码": "920161",
                "交易所": "北京证券交易所",
                "板块": "北交所",
                "发行价格": 9.21,
                "申购日期": date(2026, 5, 18),
            },
        ]
    )

    source = AkShareIpoSource(fetch_fn=lambda symbol: frame, board="全部股票")
    candidates = source.fetch_candidates(date(2026, 5, 20))

    assert len(candidates) == 1
    assert candidates[0].symbol == "920218"
    assert candidates[0].name == "新天力"
    assert candidates[0].subscription_code == "920218"
    assert candidates[0].issue_price == 12.19
