#!/usr/bin/env bash
# 一次性运维编排（REQ-260927202051-f6df / t-e77b06 解锁，2026-09-27）
#
# 为什么需要它：quick_restart 的顺序是「sleep 10s → stop.sh → start.sh」。
# 旧进程活着时对台账的任何文件改写都会被它内存态覆盖（mutate 落盘的是整册 draft），
# 所以修复只有落在「旧进程已死、新进程尚未 load()」的窗口里才算数。
# 本脚本 detached 常驻：等到旧 pid 消失 → 立即跑修复 → 记日志。
# 旧进程 120s 内没死（例如 quick_restart 被限流拒绝）→ **不写**，只记日志。
set -u
AGENT_DH=/Users/yunpeng/pi-investment/agent-dh
LEDGER="$AGENT_DH/.dsh-data/dsh-reqboard.json"
PIDFILE="$AGENT_DH/.dsh-data/state/server.pid"
REPAIR="$AGENT_DH/docs/requirements/REQ-260927202051-f6df/notes/ops-repair/req-lock-repair.py"
LOG=/tmp/req-lock-repair.log

PID=$(cat "$PIDFILE" 2>/dev/null || echo "")
echo "[$(date '+%F %T')] armed; target pid=${PID:-?}; ledger=$LEDGER" >> "$LOG"
if [ -z "$PID" ]; then
  echo "[$(date '+%F %T')] 拿不到 pidfile → 中止" >> "$LOG"
  exit 1
fi

i=0
while [ "$i" -lt 600 ]; do
  kill -0 "$PID" 2>/dev/null || break
  sleep 0.2
  i=$((i + 1))
done

if kill -0 "$PID" 2>/dev/null; then
  echo "[$(date '+%F %T')] pid $PID 仍存活（120s 超时）→ 不写，避免在活进程下改台账" >> "$LOG"
  exit 1
fi

echo "[$(date '+%F %T')] pid $PID 已退出（等待 ${i} 轮 ×0.2s）→ 立即修复" >> "$LOG"
python3 "$REPAIR" "$LEDGER" >> "$LOG" 2>&1
rc=$?
echo "[$(date '+%F %T')] repair exit=$rc" >> "$LOG"
echo "[$(date '+%F %T')] 观测（不再改文件）listener=$(lsof -nP -iTCP:13080 -sTCP:LISTEN 2>/dev/null | tail -1)" >> "$LOG"
exit "$rc"
