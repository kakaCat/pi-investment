#!/bin/bash
# 信号表现回填（硬编码盘后例程，不依赖 agent 响应）
# 数据流：Agent OS cron → 本脚本 → quantsys-v2 PUT /api/signals/track/update
# 用途：盘后自动回填 signal_tracking 的 5/10/20 日表现（price/return/hit），
#       供 signal_track report 胜率统计与 validation_gate 样本裁决使用。
# 用法: signal-perf-backfill.sh [lookback_days]   # 默认 30
set -euo pipefail

QV2="${QUANTSYS_V2_URL:-http://localhost:5001}"
LOOKBACK="${1:-30}"

# 调用后端批量回填（幂等：已回填字段不会被重复覆盖）
RESP=$(curl -sf -X PUT "$QV2/api/signals/track/update" \
  -H 'Content-Type: application/json' \
  -d "{\"lookback_days\": $LOOKBACK}" 2>&1) || {
  echo "signal-perf-backfill: FAILED ($QV2/api/signals/track/update) $RESP" >&2
  exit 1
}

echo "signal-perf-backfill: OK lookback=${LOOKBACK}d ${RESP}"
