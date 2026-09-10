#!/usr/bin/env bash
# 重启后自动验收（2026-09-11，w-f4aa1f6a）
#
# 为什么要这个：重启会杀掉发起会话的进程，验收动作没有执行者。
# 本脚本由 launchd 托管（不随 DSH 进程死亡），在端口恢复后自动跑一遍关键检查并落盘。
#
# 验收目标（本轮 ②③① 的 agent-dh TS 改动需 DSH 重启才生效）：
#   ① 实例是否带着 8GB 堆上限起来；
#   ② 插件树是否**仍然加载成功**（新增模块若 import 失败会在这里暴露，
#      而不是等到 08:30 熔断触发才炸）；
#   ③ 两个新模块与单测是否就位、测试是否仍绿；
#   ④ v2 / agent-os 健康 + 事件队列。
set -uo pipefail

LOG=/Users/yunpeng/pi-investment/logs/postrestart-verify-w-f4aa1f6a.log
REPO=/Users/yunpeng/pi-investment
PSQL=/opt/homebrew/opt/postgresql@14/bin/psql

log() { printf '%s | %s\n' "$(date '+%H:%M:%S')" "$*" >> "$LOG"; }

: > "$LOG"
BASE_PID=$(lsof -ti:13080 -sTCP:LISTEN 2>/dev/null | head -1)
log "=== 重启后验收开始（基线 pid=${BASE_PID}，等待实例更替） ==="

# 必须等到"端口换成另一个 pid"才继续——否则会在旧实例上验收并得出假通过。
# （首版缺这一步，脚本一装上就立刻对旧实例跑完了。）
UP=0
for n in $(seq 1 150); do
  CUR=$(lsof -ti:13080 -sTCP:LISTEN 2>/dev/null | head -1)
  if [ -n "$CUR" ] && [ "$CUR" != "$BASE_PID" ]; then UP=1; log "实例已更替：${BASE_PID} → ${CUR}"; break; fi
  sleep 2
done
[ "$UP" = "1" ] || { log "FAIL: 300s 内实例未更替（重启未发生或失败），需人工介入"; exit 1; }

sleep 8  # 等插件树加载完
PID=$(lsof -ti:13080 -sTCP:LISTEN | head -1)
log "新实例 pid=$PID start=$(ps -o lstart= -p "$PID" | tr -s ' ')"
RSS_MB=$(ps -o rss= -p "$PID" | tr -d ' '); log "RSS=$((RSS_MB / 1024))MB"
LIMIT=$(ps eww -p "$PID" 2>/dev/null | tr ' ' '\n' | grep -c 'max-old-space-size')
log "堆上限参数命中数=$LIMIT（>=1 表示 8GB 上限已生效）"

# ① 插件树是否加载成功（关键：新模块 import 失败会在这里现形）
PROFILE=~/.dsh/profiles/investment
ERR_LOG="$PROFILE/state/launchd.err.log"
if [ -f "$ERR_LOG" ]; then
  BAD=$(tail -400 "$ERR_LOG" | grep -cE "plugin tree failed to load|Failed to load plugin|Cannot find module|SyntaxError")
  log "插件加载错误行数=$BAD（0 为佳）"
  tail -400 "$ERR_LOG" | grep -E "plugin tree failed to load|Cannot find module|SyntaxError" | tail -3 >> "$LOG"
else
  log "未找到 $ERR_LOG（跳过插件加载检查）"
fi

# ② 新模块与单测
for f in "$REPO/agent-dh/packages/trading/src/tools/M4CircuitBreakerTool/drawdownTrust.ts" \
         "$REPO/agent-dh/packages/risk/src/tools/RiskMetricsTool/attributionAlignment.ts"; do
  [ -f "$f" ] && log "存在: ${f#$REPO/}" || log "缺失: $f"
done
cd "$REPO/agent-dh" || exit 1
VT=$(npx vitest run tests/drawdown-trust.test.ts tests/attribution-alignment.test.ts 2>&1 | grep -E "Tests +[0-9]" | tail -1)
log "vitest: ${VT:-未取到结果}"

# ③ 服务健康 + 事件队列
V2=$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:5001/api/health)
AOS=$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8080/health)
OPEN=$($PSQL -d quant_investment -t -A -c "select count(*) from public.error_events where status='open';" 2>/dev/null)
log "v2=${V2} agent-os=${AOS} open_events=${OPEN:-查询失败}"

# ④ 归因对齐是否已切到按日期（工具侧验证留给人/agent 调 risk_metrics 复核）
log "=== 验收结束；下一步由会话复核 risk_metrics 的 attribution.alignment 是否含 date-aligned ==="
