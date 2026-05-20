from __future__ import annotations

from datetime import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from quantsys.watch import CandidateOpportunity
from quantsys.watch.http_agent import HttpDecisionAgentClient


class FakeHttpClient:
    def __init__(self):
        self.requests = []

    def post_json(self, url: str, payload: dict, timeout: float) -> dict:
        self.requests.append((url, payload, timeout))
        return {
            "action": "buy",
            "confidence": 0.81,
            "target_position_pct": 0.08,
            "stop_loss": 33.5,
            "take_profit": 39.0,
            "reason": "agent approved",
            "valid_seconds": 120,
        }


def test_http_decision_agent_posts_opportunity_and_parses_structured_decision():
    http = FakeHttpClient()
    client = HttpDecisionAgentClient("http://agent.local/decision", http_client=http, timeout=3.0)
    opportunity = CandidateOpportunity(
        symbol="600036",
        price=35.2,
        quote={"price": 35.2, "amount": 35000000},
        reason="price >= 35.0",
        triggered_at=datetime(2026, 5, 19, 10, 30),
    )

    decision = client.decide(opportunity)

    assert http.requests[0][0] == "http://agent.local/decision"
    assert http.requests[0][1]["symbol"] == "600036"
    assert http.requests[0][1]["quote"]["amount"] == 35000000
    assert http.requests[0][2] == 3.0
    assert decision.action == "buy"
    assert decision.confidence == 0.81
    assert decision.target_position_pct == 0.08
    assert decision.reason == "agent approved"
