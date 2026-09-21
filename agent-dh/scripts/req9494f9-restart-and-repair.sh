#!/bin/bash
# REQ-9494f9 一次性「停实例 → 修 session 日志 → 启动 → 健康检查」编排（t-f0dcf2 / plan.md §5）
#
# 为什么需要独立编排进程：本脚本要停掉 :13080 的 DSH 进程，而发起它的那个会话就活在该进程里
#   ——前后两步必须由一个"进程外"的执行者完成，否则 kill 会把发起者自己一并带走。
#
# 为什么不用 lifecycle 的 self_restart：
#   self_restart 在重启前会把**整个 agent-dh/ 未提交改动**提交到 agent-self/* wip 分支
#   （restart-planner.ts:111 createWipBranch('agent-self', ['agent-dh/'], ...)）。本仓工作区
#   此刻有多个窗口的未提交改动（dsh-pmboard 等），回到干线时这些只存在于 wip 的改动会从
#   磁盘消失（2026-09-10 已发生过的静默抹除事故）。故本脚本**只做运行期操作，不含任何 git 命令**。
#
# 顺序（先停后改，避免与在线写入器的 seq 竞争；见 plan.md §5）：
#   1. stop.sh（pidfile + 端口双重校验，多实例安全）
#   2. 等 :13080 释放（最多 30s）
#   3. 备份 session 文件（cp -p，保留 mtime）
#   4. node scripts/req9494f9-repair-inbox.mjs --apply（追加修正帧，回读校验）
#   5. start.sh 拉起 + 健康检查（最多 120s）
set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"

PORT="${1:-13080}"
SESS="$ROOT/.dsh-data/sessions/--Users-yunpeng-pi-investment-agent-dh--/session-6faac762-d721-4942-ae9a-f6463ab7cf79/session.v3.jsonl.zstd"
LOG="$ROOT/.dsh-data/state/req9494f9-repair.log"

exec >>"$LOG" 2>&1
ts() { date '+%Y-%m-%d %H:%M:%S'; }
echo ""
echo "=== $(ts) 编排开始 (pid $$) port=$PORT ==="

if [ ! -f "$SESS" ]; then
  echo "$(ts) FATAL 找不到目标 session 文件：$SESS"
  exit 1
fi

# ── 1. 停实例 ──────────────────────────────────────────────────────────
./scripts/stop.sh "$PORT" || echo "$(ts) stop.sh rc=$?"

# ── 2. 等端口释放 ──────────────────────────────────────────────────────
freed=0
for _i in $(seq 1 30); do
  if ! lsof -ti:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then freed=1; break; fi
  sleep 1
done
if [ "$freed" != "1" ]; then
  echo "$(ts) FATAL :$PORT 30s 内未释放，放弃（未做任何写入）"
  exit 1
fi
echo "$(ts) 实例已停止，:$PORT 已释放"

# ── 3. 备份 ────────────────────────────────────────────────────────────
BAK="$SESS.bak-req9494f9-$(date +%Y%m%d%H%M%S)"
if cp -p "$SESS" "$BAK"; then
  echo "$(ts) 已备份 → $(basename "$BAK")"
else
  echo "$(ts) FATAL 备份失败，放弃（未写入）"
  exit 1
fi

# ── 4. 写入修正帧 ──────────────────────────────────────────────────────
echo "$(ts) repair: 开始"
node scripts/req9494f9-repair-inbox.mjs --file "$SESS" --apply
repair_rc=$?
echo "$(ts) repair rc=$repair_rc"

# ── 5. 启动 + 健康检查 ─────────────────────────────────────────────────
nohup ./scripts/start.sh --port "$PORT" >>"$LOG" 2>&1 &
start_pid=$!
echo "$(ts) 已拉起 start.sh pid=$start_pid"

healthy=0
for _i in $(seq 1 60); do
  if curl -sf -o /dev/null "http://127.0.0.1:$PORT/"; then healthy=1; break; fi
  sleep 2
done

if [ "$healthy" = "1" ]; then
  echo "$(ts) 健康检查通过 :$PORT"
else
  echo "$(ts) FATAL 健康检查 120s 未通过——请人工检查日志"
fi

# ── 6. 复验：折叠投影 + 全量扫描（AC-4 / AC-6 证据）────────────────────
echo "$(ts) 复验 dry-run（应报「无需修复」）："
node scripts/req9494f9-repair-inbox.mjs --file "$SESS" 2>&1 | tail -12

hits=0; scanned=0
while IFS= read -r f; do
  scanned=$((scanned + 1))
  if zstd -d -c "$f" 2>/dev/null | grep -q 'inserted":\["'; then
    hits=$((hits + 1)); echo "  HIT $f"
  fi
done < <(find "$ROOT/.dsh-data/sessions" -name 'session.v3.jsonl.zstd')
echo "$(ts) 全量扫描：scanned=$scanned hits=$hits"

echo "=== $(ts) 编排结束 healthy=$healthy repair_rc=$repair_rc hits=$hits ==="
