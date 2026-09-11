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
#   ② AUTO_RESTART=1 时才真正重启实例（默认 0=只告警）。重启走 launchd 原生的
#      `launchctl kickstart -k`（2026-09-11 修）：既不 pkill 模糊匹配误杀其它 dsh 实例
#      （见多实例生命周期铁律），也不会像旧版那样「杀了却起不来」——详见文末注释。
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

# ── AUTO_RESTART：先确认「重启通道可用」再动手，绝不制造宕机 ─────────────────
# 旧版（2026-09-11 修复前）是 stop.sh 杀实例 + `nohup start.sh` 起新的，两个缺陷：
#   ① 它被 launchd 以精简 PATH（/usr/bin:/bin:/usr/sbin:/sbin）拉起，而本机 node 在
#      ~/.local/bin → start.sh 直接 `node: command not found`：**实例杀了却起不来**；
#   ② 绕过 launchd 手动起进程，会与 plist 的 KeepAlive respawn 抢同一端口——这正是
#      pi-services.sh 里针对 v2/web 记下的血泪教训。
# 现在统一走 launchd 原生 `launchctl kickstart -k`：杀旧起新由 launchd 内部完成，
# PATH 与 KeepAlive 全程有效，不存在抢端口。且**通道不可用就只告警、绝不 kill**。
if [ "$AUTO_RESTART" = "1" ]; then
  LABEL=com.pi-investment.dsh
  GUI="gui/$(id -u)"
  export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"

  if ! launchctl print "$GUI/$LABEL" >/dev/null 2>&1; then
    # 关键：没有可用重启通道时绝不能 kill。宁可让高内存实例多活一会儿（可能自然回落），
    # 也好过看门狗把唯一实例杀掉却拉不起来。error 事件上面已投递，这里只补明细。
    echo "[dsh-heap-watch] 重启通道不可用（$LABEL 不在 launchd 域内）→ 跳过自动重启，仅告警" >&2
    exit 0
  fi

  echo "[dsh-heap-watch] AUTO_RESTART=1 → launchctl kickstart -k $GUI/$LABEL"
  if ! launchctl kickstart -k "$GUI/$LABEL"; then
    echo "[dsh-heap-watch] FAIL: kickstart 失败，未 kill 任何进程（实例保持原样）" >&2
    exit 1
  fi

  # 重启后必须确认实例真的回来了，否则就是「看门狗把实例看死了」，要吵出来而不是静默
  BACK=0
  for n in $(seq 1 60); do
    if lsof -ti:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then BACK=1; break; fi
    sleep 1
  done
  if [ "$BACK" = "1" ]; then
    echo "[dsh-heap-watch] 重启完成，新 pid=$(lsof -ti:"$PORT" -sTCP:LISTEN 2>/dev/null | head -1)（${n}s 内恢复）"
  else
    echo "[dsh-heap-watch] FAIL: 重启后 ${n}s 内 $PORT 仍未监听，需人工介入" >&2
    exit 1
  fi
fi
exit 0
