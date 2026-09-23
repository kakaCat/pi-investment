#!/usr/bin/env bash
# quick-restart.sh —— :13080 轻量重启编排器（RFC 016）
#
# 定位：web-liveness 的 quick_restart 工具的 detached 执行体。
# **只编排、不实现**：杀与起全部委托 scripts/stop.sh + scripts/start.sh
# （2026-09-22 裁定的唯一重启入口，42159f56）。本脚本不含任何 kill/lsof 逻辑，
# 不产生第二份重启实现，避免历史上海量重复重启路径相互漂移的问题。
#
# 与 lifecycle self_restart 的分工：本脚本不动 git、不建 wip、不回滚、不续跑。
# 失败只写结果文件，**绝不自动重试**（2026-09-23 tmp-restart 死循环事故教训：
# 2512 轮 × 15s 把实例杀了 10.7 小时）。
#
# 用法：quick-restart.sh [reason]（通常由 web-liveness host spawn，detached）
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENT_DH="$(cd "$SCRIPT_DIR/.." && pwd)"
STATE_DIR="$AGENT_DH/.dsh-data/state"
LOG="$STATE_DIR/quick-restart.log"
RESULT="$STATE_DIR/quick-restart-result.json"
PORT=13080
PRE_KILL_DELAY="${QUICK_RESTART_PRE_KILL_DELAY:-10}"
HEALTH_TIMEOUT="${QUICK_RESTART_HEALTH_TIMEOUT:-120}"
REASON="${1:-（未填写）}"

mkdir -p "$STATE_DIR"

log() { echo "[$(date '+%F %T')] $*" >> "$LOG"; }

write_result() { # $1=status(ok|failed) $2=detail
  # 结果文件供 web-liveness host 在下一次调用时透给 agent；原子写防半文件。
  local tmp="$RESULT.tmp.$$"
  printf '{"status":"%s","reason":"%s","detail":"%s","at":"%s"}\n' \
    "$1" "$(echo "$REASON" | tr -d '"\\')" "$(echo "$2" | tr -d '"\\')" \
    "$(date '+%Y-%m-%dT%H:%M:%S%z')" > "$tmp"
  mv "$tmp" "$RESULT"
}

log "quick-restart begin: reason=$REASON pid4kill=$(cat "$STATE_DIR/server.pid" 2>/dev/null || echo unknown)"

# 给 agent 留时间说完话、落盘会话（同 self_restart 的 preKillDelay 语义）
sleep "$PRE_KILL_DELAY"

if ! ( cd "$AGENT_DH" && ./scripts/stop.sh ) >> "$LOG" 2>&1; then
  log "stop.sh 失败"
  write_result failed "stop.sh 失败，见 $LOG"
  exit 1
fi

# 拉起（nohup + </dev/null：调用方会话退出不能带走新进程——2026-09-17 冻进程教训）
( cd "$AGENT_DH" && nohup ./scripts/start.sh --port "$PORT" --no-open </dev/null >> "$LOG" 2>&1 & )
log "start.sh 已拉起（后台），开始健康检查（${HEALTH_TIMEOUT}s 上限）"

deadline=$(( $(date +%s) + HEALTH_TIMEOUT ))
while [ "$(date +%s)" -lt "$deadline" ]; do
  code=$(curl -s -o /dev/null -w '%{http_code}' -m 3 "http://127.0.0.1:$PORT/" 2>/dev/null || echo 000)
  if [ "$code" != "000" ]; then
    log "health ok (HTTP $code)"
    write_result ok "HTTP $code"
    exit 0
  fi
  sleep 2
done

log "health check 超时（${HEALTH_TIMEOUT}s），服务未起来——不重试，等人工"
write_result failed "健康检查 ${HEALTH_TIMEOUT}s 超时，见 $LOG"
exit 1
