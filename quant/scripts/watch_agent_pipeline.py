#!/usr/bin/env python3
"""Run the agent-assisted market watch pipeline."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from quantsys.data.data.sources.akshare_adapter import AkShareAdapter
from quantsys.watch import (
    AgentDecision,
    CandidateOpportunity,
    CliConfirmationChannel,
    DecisionAgentClient,
    ExecutionMode,
    AkShareRealtimeQuoteSource,
    FeishuNotifier,
    HttpDecisionAgentClient,
    InMemoryDecisionJournal,
    SimulatedOrderExecutor,
    SinaRealtimeQuoteSource,
    StaticThresholdTrigger,
    FallbackRealtimeQuoteSource,
    WatchPipeline,
    WatchPipelineConfig,
)


class ConservativeRuleAgent(DecisionAgentClient):
    """Local placeholder agent used until a remote agent endpoint is wired in."""

    def __init__(self, auto_buy: bool = False) -> None:
        self.auto_buy = auto_buy

    def decide(self, opportunity: CandidateOpportunity) -> AgentDecision:
        if not self.auto_buy:
            return AgentDecision(
                action="wait",
                confidence=0.5,
                reason="触发已收到，默认保守等待；使用 --auto-buy 才允许测试买入",
            )

        return AgentDecision(
            action="buy",
            confidence=0.75,
            target_position_pct=0.05,
            reason=f"测试规则确认: {opportunity.reason}",
        )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    thresholds = load_thresholds(args.thresholds)
    symbols = args.symbols.split(",") if args.symbols else list(thresholds)
    if not symbols:
        raise SystemExit("至少需要 --symbols 或 --thresholds")

    agent = (
        HttpDecisionAgentClient(args.agent_endpoint, timeout=args.agent_timeout)
        if args.agent_endpoint
        else ConservativeRuleAgent(auto_buy=args.auto_buy)
    )

    data_source = FallbackRealtimeQuoteSource([
        SinaRealtimeQuoteSource(),
        AkShareRealtimeQuoteSource(AkShareAdapter()),
    ])

    pipeline = WatchPipeline(
        config=WatchPipelineConfig(
            mode=ExecutionMode(args.mode),
            total_equity=args.total_equity,
            duplicate_cooldown_seconds=args.cooldown_seconds,
            min_confidence_to_trade=args.min_confidence,
        ),
        data_source=data_source,
        trigger=StaticThresholdTrigger(thresholds),
        agent=agent,
        confirmation_channel=CliConfirmationChannel(),
        executor=SimulatedOrderExecutor(),
        notifier=FeishuNotifier(webhook_url=args.feishu_webhook or os.getenv("FEISHU_WEBHOOK_URL")),
        journal=InMemoryDecisionJournal(),
    )

    while True:
        results = pipeline.scan_once(symbols)
        emit_results(results)
        if args.once:
            break
        time.sleep(args.interval_seconds)

    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Agent-assisted quant watch pipeline")
    parser.add_argument("--symbols", help="Comma-separated stock symbols, e.g. 600036,000001")
    parser.add_argument("--thresholds", required=True, help="JSON file or inline JSON mapping symbol to trigger price")
    parser.add_argument("--mode", choices=["test", "prod"], default="test")
    parser.add_argument("--once", action="store_true", help="Run one scan and exit")
    parser.add_argument("--interval-seconds", type=float, default=5.0)
    parser.add_argument("--cooldown-seconds", type=int, default=300)
    parser.add_argument("--total-equity", type=float, default=100000.0)
    parser.add_argument("--min-confidence", type=float, default=0.7)
    parser.add_argument("--feishu-webhook")
    parser.add_argument("--agent-endpoint", help="HTTP endpoint that returns an AgentDecision JSON payload")
    parser.add_argument("--agent-timeout", type=float, default=10.0)
    parser.add_argument("--auto-buy", action="store_true", help="Use the local placeholder agent to approve test buys")
    return parser.parse_args(argv)


def load_thresholds(value: str) -> dict[str, float]:
    path = Path(value)
    raw = path.read_text(encoding="utf-8") if path.exists() else value
    data = json.loads(raw)
    return {str(symbol): float(price) for symbol, price in data.items()}


def emit_results(results) -> None:
    for result in results:
        payload = {
            "time": datetime.now().isoformat(timespec="seconds"),
            "symbol": result.opportunity.symbol,
            "status": result.status,
            "action": result.decision.action,
            "confidence": result.decision.confidence,
            "reason": result.decision.reason,
            "order": None,
        }
        if result.order_result:
            payload["order"] = {
                "order_id": result.order_result.order_id,
                "shares": result.order_result.shares,
                "price": result.order_result.price,
                "mode": result.order_result.mode,
            }
        print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    raise SystemExit(main())
