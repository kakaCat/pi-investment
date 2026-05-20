#!/usr/bin/env python3
"""Run the agent-assisted IPO subscription watch pipeline."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from quantsys.watch import (
    AgentDecision,
    AkShareIpoSource,
    CliConfirmationChannel,
    DecisionAgentClient,
    FeishuNotifier,
    HttpDecisionAgentClient,
    InMemoryDecisionJournal,
    IpoWatchPipeline,
    IpoWatchPipelineConfig,
)


class ConservativeIpoAgent(DecisionAgentClient):
    """Local placeholder agent used until a remote IPO agent endpoint is wired in."""

    def __init__(self, auto_subscribe: bool = False) -> None:
        self.auto_subscribe = auto_subscribe

    def decide(self, opportunity):
        if not self.auto_subscribe:
            return AgentDecision(
                action="wait",
                confidence=0.5,
                reason="发现今日可申购新股，默认保守等待；使用 --auto-subscribe 才允许本地测试确认",
            )

        return AgentDecision(
            action="subscribe",
            confidence=0.75,
            reason=f"本地测试规则确认: {opportunity.reason}",
        )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    target_date = date.fromisoformat(args.date) if args.date else date.today()

    agent = (
        HttpDecisionAgentClient(args.agent_endpoint, timeout=args.agent_timeout)
        if args.agent_endpoint
        else ConservativeIpoAgent(auto_subscribe=args.auto_subscribe)
    )

    pipeline = IpoWatchPipeline(
        config=IpoWatchPipelineConfig(min_confidence_to_confirm=args.min_confidence),
        source=AkShareIpoSource(board=args.board),
        agent=agent,
        confirmation_channel=CliConfirmationChannel(),
        notifier=FeishuNotifier(webhook_url=args.feishu_webhook or os.getenv("FEISHU_WEBHOOK_URL")),
        journal=InMemoryDecisionJournal(),
    )

    results = pipeline.scan_once(target_date=target_date)
    emit_results(results)
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Agent-assisted IPO subscription watch pipeline")
    parser.add_argument("--date", help="Subscription date in YYYY-MM-DD format; defaults to today")
    parser.add_argument(
        "--board",
        default="全部股票",
        choices=["全部股票", "沪市主板", "科创板", "深市主板", "创业板", "北交所"],
        help="EastMoney IPO board filter",
    )
    parser.add_argument("--min-confidence", type=float, default=0.7)
    parser.add_argument("--feishu-webhook")
    parser.add_argument("--agent-endpoint", help="HTTP endpoint that returns an AgentDecision JSON payload")
    parser.add_argument("--agent-timeout", type=float, default=10.0)
    parser.add_argument("--auto-subscribe", action="store_true", help="Use the local placeholder agent to approve test subscriptions")
    return parser.parse_args(argv)


def emit_results(results) -> None:
    if not results:
        print(json.dumps({"time": datetime.now().isoformat(timespec="seconds"), "count": 0}, ensure_ascii=False))
        return

    for result in results:
        print(
            json.dumps(
                {
                    "time": datetime.now().isoformat(timespec="seconds"),
                    "symbol": result.candidate.symbol,
                    "name": result.candidate.name,
                    "subscription_code": result.candidate.subscription_code,
                    "subscription_date": result.candidate.subscription_date.isoformat(),
                    "status": result.status,
                    "action": result.decision.action,
                    "confidence": result.decision.confidence,
                    "reason": result.decision.reason,
                    "confirmed": result.confirmation.approved if result.confirmation else None,
                },
                ensure_ascii=False,
            )
        )


if __name__ == "__main__":
    raise SystemExit(main())
