"""HTTP-backed decision agent client."""

from __future__ import annotations

import json
import urllib.request

from quantsys.watch.agent import AgentDecision
from quantsys.watch.trigger import CandidateOpportunity


class UrllibJsonHttpClient:
    """Small JSON HTTP client to avoid adding a dependency for one POST."""

    def post_json(self, url: str, payload: dict, timeout: float) -> dict:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))


class HttpDecisionAgentClient:
    """Send candidate opportunities to an agent over HTTP."""

    def __init__(
        self,
        endpoint_url: str,
        http_client: UrllibJsonHttpClient | None = None,
        timeout: float = 10.0,
    ) -> None:
        self.endpoint_url = endpoint_url
        self.http_client = http_client or UrllibJsonHttpClient()
        self.timeout = timeout

    def decide(self, opportunity: CandidateOpportunity) -> AgentDecision:
        response = self.http_client.post_json(
            self.endpoint_url,
            self._payload(opportunity),
            timeout=self.timeout,
        )
        return AgentDecision(
            action=str(response.get("action", "wait")),
            confidence=float(response.get("confidence", 0.0)),
            target_position_pct=float(response.get("target_position_pct", 0.0)),
            stop_loss=_optional_float(response.get("stop_loss")),
            take_profit=_optional_float(response.get("take_profit")),
            reason=str(response.get("reason", "")),
            valid_seconds=int(response.get("valid_seconds", 300)),
        )

    @staticmethod
    def _payload(opportunity: CandidateOpportunity) -> dict:
        return {
            "symbol": opportunity.symbol,
            "price": opportunity.price,
            "quote": opportunity.quote,
            "trigger_reason": opportunity.reason,
            "triggered_at": opportunity.triggered_at.isoformat(),
        }


def _optional_float(value) -> float | None:
    if value is None:
        return None
    return float(value)
