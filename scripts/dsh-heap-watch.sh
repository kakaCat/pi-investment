#!/usr/bin/env bash
# DSH 实例内存看门狗（2026-09-11 立，w-f4aa1f6a）
#
# 问题：本实例是"多窗口共享单进程"，堆持续增长（实测启动即 3.6GB，稳态 3.7-3.9GB），
# V8 默认 old-space 上限 4144MB → 2026-09-11 00:51 / 01:18 两次
# "FATAL ERROR: Reached heap limit"（error_event 2a0f8617）。OOM 是**失控崩溃**：
# 发生在任意时刻、无预告、可能打断正在进行的交易/复盘工作。
#
# 本脚本把"失控崩溃"变成"可控信号"：
#   ① 超过 THRESHOLD_MB（默认 6144，低于加固后的 8192 上限，留安全余量）
#      → 投递一条 error 事件进 open 队列（可被人/agent 处置），并按需告警；
#   ② AUTO_RESTART=1 时才真正重启实例（默认 0=只告警），重启走实例自己的 stop/start，
#      避免 pkill 模糊匹配误杀其它 dsh 实例（见多实例生命周期铁律）。
set -uo pipefail

PORT=${DSH_PORT:-13080}
THRESHOLD_MB=${THRESHOLD_MB:-6144}
AUTO_RESTART=${AUTO_RESTART:-0}

PID=$(lsof -ti:"$PORT" -sTCP:LISTEN 2>/dev/null | head -1)
if [ -z "$PID" ]; then
  echo "[dsh-heap-watch] 端口 $PORT 无监听进程（实例可能正在重启）"
  exit 0
fi

# 阈值自适应（2026-09-11 w-f4aa1f6a 补）：堆上限会被各窗口调整（实证 8GB→16GB），
# 固定阈值会在**正常水位**误触发——而本看门狗已开 AUTO_RESTART=1，误触发等于打断会话。
# 故读取实例实际的 --max-old-space-size，取其 75% 作为阈值（不低于配置值）。
# FORCE_THRESHOLD=1 时跳过自适应——保留"用低阈值验证告警/重启路径"的能力（否则自适应会把测试阈值顶回去）
LIMIT_MB=""
if [ "${FORCE_THRESHOLD:-0}" != "1" ]; then
  LIMIT_MB=$(ps eww -p "$PID" 2>/dev/null | tr ' ' '\n' | grep -o 'max-old-space-size=[0-9]*' | head -1 | cut -d= -f2)
fi
if [ -n "${LIMIT_MB:-}" ] && [ "$LIMIT_MB" -gt 0 ] 2>/dev/null; then
  ADAPTIVE_MB=$((LIMIT_MB * 3 / 4))
  if [ "$ADAPTIVE_MB" -gt "$THRESHOLD_MB" ]; then
    echo "[dsh-heap-watch] 堆上限=${LIMIT_MB}MB → 阈值自适应 ${THRESHOLD_MB}MB→${ADAPTIVE_MB}MB"
    THRESHOLD_MB=$ADAPTIVE_MB
  fi
fi

RSS_KB=$(ps -o rss= -p "$PID" | tr -d ' ')
RSS_MB=$((RSS_KB / 1024))
echo "[dsh-heap-watch] pid=$PID rss=${RSS_MB}MB 阈值=${THRESHOLD_MB}MB 堆上限=${LIMIT_MB:-未知}MB"

if [ "$RSS_MB" -lt "$THRESHOLD_MB" ]; then
  exit 0
fi

DETAIL="pid=$PID rss=${RSS_MB}MB threshold=${THRESHOLD_MB}MB port=$PORT auto_restart=$AUTO_RESTART"
echo "[dsh-heap-watch] 超阈值：$DETAIL" >&2
payload=$(python3 - "$DETAIL" <<'PY'
import json, sys
print(json.dumps({
    'source': 'os', 'level': 'error',
    'msg': 'DSH 实例内存接近上限（可能再次 OOM 中断会话），需择时重启实例',
    'detail': sys.argv[1],
    'metadata': {'probe': 'dsh-heap-watch', 'script': 'scripts/dsh-heap-watch.sh'},
}, ensure_ascii=False))
PY
)
curl -s -X POST http://127.0.0.1:8080/api/v1/scheduler/error-events \
  -H 'Content-Type: application/json' -d "$payload" -o /dev/null -w 'error-event ingest HTTP=%{http_code}\n' || true

if [ "$AUTO_RESTART" = "1" ]; then
  echo "[dsh-heap-watch] AUTO_RESTART=1 → 重启实例 $PORT"
  bash ~/.dsh/profiles/investment/stop.sh "$PORT" 2>/dev/null || true
  sleep 2
  nohup bash ~/.dsh/profiles/investment/start.sh "$PORT" >/dev/null 2>&1 &
fi
exit 0
