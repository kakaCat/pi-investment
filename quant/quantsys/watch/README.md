# Agent Watch Pipeline

This package implements the first agent-assisted watch loop:

1. Poll realtime quote snapshots.
2. Convert matched trigger rules into candidate opportunities.
3. Send each opportunity to a decision agent.
4. In `test` mode, require human confirmation through CLI before simulated execution.
5. In `prod` mode, execute directly and notify Feishu/CLI.
6. Journal every trigger, decision, confirmation, and order result.

## Current Safety Boundary

`scripts/watch_agent_pipeline.py` uses `SimulatedOrderExecutor`, so it does not place real broker orders yet. Replacing that executor is the handoff point for broker integration.

The bundled `ConservativeRuleAgent` returns `wait` by default. Use `--auto-buy` only for local pipeline testing.

## Example

```bash
python scripts/watch_agent_pipeline.py \
  --thresholds '{"600036": 35.0}' \
  --symbols 600036 \
  --mode test \
  --once
```

With Feishu notification:

```bash
FEISHU_WEBHOOK_URL='https://open.feishu.cn/open-apis/bot/v2/hook/...' \
python scripts/watch_agent_pipeline.py \
  --thresholds '{"600036": 35.0}' \
  --symbols 600036 \
  --mode test \
  --auto-buy
```

## Production Switch

Before using `--mode prod`, replace `SimulatedOrderExecutor` with a broker executor and keep the same `OrderRequest` / `OrderResult` contract.

## IPO Subscription Watch

The IPO watch pipeline reuses the same decision, confirmation, notification, and journal boundaries. It fetches today's IPO subscription candidates from AkShare/EastMoney, sends each candidate to the agent, and only asks for CLI confirmation plus Feishu notification when the agent returns `subscribe` or `buy` with sufficient confidence.

```bash
FEISHU_WEBHOOK_URL='https://open.feishu.cn/open-apis/bot/v2/hook/...' \
python scripts/ipo_watch_pipeline.py \
  --agent-endpoint http://agent.local/decision \
  --min-confidence 0.7
```

For local dry runs without a remote agent, the built-in conservative agent returns `wait` by default:

```bash
python scripts/ipo_watch_pipeline.py --date 2026-05-20
```

Use `--auto-subscribe` only to test the CLI confirmation and Feishu notification path.

Example daily cron entry:

```cron
30 8 * * 1-5 cd /Users/mac/Documents/ai/pi-investment/quant && FEISHU_WEBHOOK_URL='...' python scripts/ipo_watch_pipeline.py --agent-endpoint http://agent.local/decision >> logs/ipo_watch.log 2>&1
```
