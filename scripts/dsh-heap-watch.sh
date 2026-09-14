#!/usr/bin/env bash
# DSH 实例内存看门狗（2026-09-11 立，w-f4aa1f6a；2026-09-14 REQ-dfd8b6 加固退避与告警）
#
# 问题：本实例是"多窗口共享单进程"，堆持续增长（实测启动即 3.6GB，稳态 3.7-3.9GB），
# V8 默认 old-space 上限 4144MB → 2026-09-11 00:51 / 01:18 两次
# "FATAL ERROR: Reached heap limit"（error_event 2a0f8617）。OOM 是**失控崩溃**：
# 发生在任意时刻、无预告、可能打断正在进行的交易/复盘工作。
#
# 本脚本把"失控崩溃"变成"可控信号"：
#   ① 超过 THRESHOLD_MB（默认 6144，低于加固后的上限，留安全余量）
#      → 投递一条 error 事件进 open 队列（可被人/agent 处置），并按需告警；
#   ② AUTO_RESTART=1 时才真正重启实例（默认 0=只告警）。重启走 launchd 原生的
#      `launchctl kickstart -k`（2026-09-11 修）：既不 pkill 模糊匹配误杀其它 dsh 实例
#      （见多实例生命周期铁律），也不会像旧版那样「杀了却起不来」——详见文末注释。
#
# ── 2026-09-14 REQ-dfd8b6 修复：10 分钟无退避重启循环 ───────────────────────────
# 事故现场：22:45:31 / 22:55:35 / 23:05:40 连续三次 kickstart 全部由本脚本触发，
#   触发值 RSS=7632 / 7717 / 7674MB（堆上限 8192MB）。根因是重启后 DSH 重建
#   session projection cache（22:56 一次写 62 个投影，对应压缩会话 714.8MB），
#   重建峰值贴着 V8 上限；而旧版「超阈值就重启」既无退避、也无有效性判定，
#   且只投 error-event（Agent OS 侧不外发通知）——对用户全程静默，肉眼只见"反复重启"。
# 本次加固（三条，均可关/可调）：
#   ① 台账 + 每小时上限：$STATE_DIR/dsh-heap-watch-restarts.tsv 记录每次真实重启；
#      滚动 1 小时内达到 MAX_RESTARTS_PER_HOUR（默认 3）仍超阈值 → **退避**：
#      只告警不再重启（避免「重启→重建→再超阈值」无限循环；此时再重启已无收益）。
#      MAX_RESTARTS_PER_HOUR<=0 表示不限（退回旧行为）。
#   ② 告警升级：单次重启 = error 事件（原行为）；1 小时内第 2 次起 → alerts 群 high，
#      内容带近一小时重启轨迹 + 最重的几个会话（人拿到就能直接处置）。
#   ③ 恢复即清零：任一时刻 RSS 回落到阈值以下 → 台账窗口作废，下次重新计数。
# 验证钩子：HEAP_WATCH_DRY_RUN=1 只打印将执行的动作，不重启、不发通知、不写台账
#   （故障注入/部署后核验用；配合 HEAP_WATCH_STATE_DIR 指向临时目录可完全旁路线上状态）。
set -uo pipefail

PORT=${DSH_PORT:-13080}
THRESHOLD_MB=${THRESHOLD_MB:-6144}
AUTO_RESTART=${AUTO_RESTART:-0}

MAX_RESTARTS_PER_HOUR=${MAX_RESTARTS_PER_HOUR:-3}
DRY_RUN=${HEAP_WATCH_DRY_RUN:-0}
STATE_DIR=${HEAP_WATCH_STATE_DIR:-/Users/yunpeng/pi-investment/logs}
LEDGER="$STATE_DIR/dsh-heap-watch-restarts.tsv"
GUARD_LOG="$STATE_DIR/dsh-heap-watch-guard.log"
ALERT_STAMP="$STATE_DIR/dsh-heap-watch-alert.stamp"
AGENT_OS=${AGENT_OS_BASE_URL:-http://127.0.0.1:8080}
SESSIONS_DIR=${DSH_SESSIONS_DIR:-/Users/yunpeng/pi-investment/agent-dh/.dsh-data/sessions}
ALERT_COOLDOWN=${HEAP_WATCH_ALERT_COOLDOWN:-1800}

NOW=$(date +%s)
mkdir -p "$STATE_DIR" 2>/dev/null || true

_log() {  # 落 guard 台账 + stdout（launchd 收集到 launchd.out.log）
  echo "[dsh-heap-watch] $*"
  echo "$(date -u +%FT%TZ) $*" >> "$GUARD_LOG" 2>/dev/null || true
}

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

# 台账保留 24 小时，避免无限增长
if [ -f "$LEDGER" ]; then
  awk -F'\t' -v now="$NOW" -v win=86400 '$1 >= now-win' "$LEDGER" > "$LEDGER.tmp" 2>/dev/null && mv "$LEDGER.tmp" "$LEDGER" 2>/dev/null || true
fi

if [ "$RSS_MB" -lt "$THRESHOLD_MB" ]; then
  # ③ 恢复即清零：窗口里还有记录说明刚刚重启过，现在回到阈值以下 = 重启有效
  if [ -s "$LEDGER" ]; then
    RECENT=$(awk -F'\t' -v now="$NOW" -v win=3600 '$1 >= now-win' "$LEDGER" 2>/dev/null | wc -l | tr -d ' ')
    if [ "${RECENT:-0}" -gt 0 ]; then
      _log "内存已回落（rss=${RSS_MB}MB < ${THRESHOLD_MB}MB）：近 1 小时 ${RECENT} 次重启判定为**有效**，台账清零"
    fi
    if [ "$DRY_RUN" != "1" ]; then rm -f "$LEDGER" "$ALERT_STAMP" 2>/dev/null || true; fi
  fi
  exit 0
fi

DETAIL="pid=$PID rss=${RSS_MB}MB threshold=${THRESHOLD_MB}MB port=$PORT auto_restart=$AUTO_RESTART"
echo "[dsh-heap-watch] 超阈值：$DETAIL" >&2

RECENT=$(awk -F'\t' -v now="$NOW" -v win=3600 '$1 >= now-win' "$LEDGER" 2>/dev/null | wc -l | tr -d ' ')
[ -n "$RECENT" ] || RECENT=0
TRACE=$(tail -5 "$LEDGER" 2>/dev/null | awk -F'\t' '{printf "  - %s rss=%sMB pid=%s\n", strftime("%H:%M:%S", $1), $2, $3}' || true)

# 重灾区会话（只读诊断，给告警用；不做任何删除）
_top_sessions() {
  [ -d "$SESSIONS_DIR" ] || return 0
  find "$SESSIONS_DIR" -name 'session*.zstd' -size +20M -print0 2>/dev/null \
    | xargs -0 du -m 2>/dev/null | sort -rn | head -5 \
    | sed "s|$SESSIONS_DIR/||; s|^|  - |"
}

_notify() {  # $1=title $2=content
  if [ "$DRY_RUN" = "1" ]; then
    echo "[dsh-heap-watch] [dry-run] 将发通知 channel=alerts urgency=high title=$1"
    return 0
  fi
  if [ -f "$ALERT_STAMP" ]; then
    LAST=$(cat "$ALERT_STAMP" 2>/dev/null || echo 0)
    if [ "$((NOW - LAST))" -lt "$ALERT_COOLDOWN" ]; then
      _log "告警冷却中（距上次 $((NOW - LAST))s < ${ALERT_COOLDOWN}s），本次只记 error 事件不再外发"
      return 0
    fi
  fi
  local payload
  payload=$(python3 - "$1" "$2" <<'PY'
import json, sys
print(json.dumps({"channel": "alerts", "title": sys.argv[1], "content": sys.argv[2], "urgency": "high"}, ensure_ascii=False))
PY
)
  curl -s -X POST "$AGENT_OS/api/v1/notifications/send" \
    -H 'Content-Type: application/json' -d "$payload" -o /dev/null \
    -w 'notify HTTP=%{http_code}\n' || true
  echo "$NOW" > "$ALERT_STAMP" 2>/dev/null || true
}

_alert_text() {  # $1=场景
  echo "场景: $1"
  echo ""
  echo "实例: :$PORT pid=$PID rss=${RSS_MB}MB 阈值=${THRESHOLD_MB}MB 堆上限=${LIMIT_MB:-未知}MB"
  echo "近 1 小时自动重启次数: ${RECENT}（上限 ${MAX_RESTARTS_PER_HOUR}）"
  if [ -n "${TRACE:-}" ]; then echo ""; echo "最近重启轨迹:"; echo "$TRACE"; fi
  echo ""
  echo "最重的会话（投影重建时全量解压，是内存峰值的主要来源）:"
  _top_sessions
  echo ""
  echo "排查入口: tail -50 /Users/yunpeng/pi-investment/logs/dsh-heap-watch.{log,guard.log}"
  echo "判别口径: 每 10 分钟整点重启 = 本看门狗超阈值，不是崩溃；见 agent-dh/docs/guides/dsh-heap-watch-and-restart-loop.md"
}

# 投 error 事件（原行为，保持不变；Agent OS 侧不会外发通知，故另有 _notify 升级）
if [ "$DRY_RUN" != "1" ]; then
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
  curl -s -X POST "$AGENT_OS/api/v1/scheduler/error-events" \
    -H 'Content-Type: application/json' -d "$payload" -o /dev/null -w 'error-event ingest HTTP=%{http_code}\n' || true
fi

# ── ① 退避围栏：滚动 1 小时内的重启次数达到上限 → 不再重启，转人工 ──────────────
if [ "$MAX_RESTARTS_PER_HOUR" -gt 0 ] 2>/dev/null && [ "$RECENT" -ge "$MAX_RESTARTS_PER_HOUR" ]; then
  _log "退避触发：近 1 小时已重启 ${RECENT} 次（上限 ${MAX_RESTARTS_PER_HOUR}）且仍超阈值 → 本次**不重启**，只告警（再重启已无收益，疑似重建/泄漏型高水位）"
  _notify "【DSH 内存看门狗】退避：1 小时内第 ${RECENT} 次超阈值，已停止自动重启" "$(_alert_text "看门狗退避（重启不再有收益）")"
  if [ "${ALLOW_RESTART_BEYOND_CAP:-0}" = "1" ]; then
    _log "ALLOW_RESTART_BEYOND_CAP=1 → 逃生阀生效，继续执行重启"
  else
    exit 0
  fi
fi

# ── AUTO_RESTART：先确认「重启通道可用」再动手，绝不制造宕机 ─────────────────
# 旧版（2026-09-11 修复前）是 stop.sh 杀实例 + `nohup start.sh` 起新的，两个缺陷：
#   ① 它被 launchd 以精简 PATH（/usr/bin:/bin:/usr/sbin:/sbin）拉起，而本机 node 在
#      ~/.local/bin → start.sh 直接 `node: command not found`：**实例杀了却起不来**；
#   ② 绕过 launchd 手动起进程，会与 plist 的 KeepAlive respawn 抢同一端口——这正是
#      pi-services.sh 里针对 v2/web 记下的血泪教训。
# 现在统一走 launchd 原生 `launchctl kickstart -k`：杀旧起新由 launchd 内部完成，
# PATH 与 KeepAlive 全程有效，不存在抢端口。且**通道不可用就只告警、绝不 kill**。
if [ "$AUTO_RESTART" = "1" ]; then
  LABEL=${DSH_LAUNCHD_LABEL:-com.pi-investment.dsh}
  GUI="gui/$(id -u)"
  export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"

  if ! launchctl print "$GUI/$LABEL" >/dev/null 2>&1; then
    # 关键：没有可用重启通道时绝不能 kill。宁可让高内存实例多活一会儿（可能自然回落），
    # 也好过看门狗把唯一实例杀掉却拉不起来。error 事件上面已投递，这里只补明细。
    _log "重启通道不可用（$LABEL 不在 launchd 域内）→ 跳过自动重启，仅告警"
    exit 0
  fi

  if [ "$DRY_RUN" = "1" ]; then
    echo "[dsh-heap-watch] [dry-run] 将执行: launchctl kickstart -k $GUI/$LABEL（台账将记 1 条：近 1 小时 ${RECENT} → $((RECENT + 1))）"
    exit 0
  fi

  _log "AUTO_RESTART=1 → launchctl kickstart -k $GUI/$LABEL（近 1 小时第 $((RECENT + 1)) 次）"
  if ! launchctl kickstart -k "$GUI/$LABEL"; then
    _log "FAIL: kickstart 失败，未 kill 任何进程（实例保持原样）"
    exit 1
  fi

  # 重启后必须确认实例真的回来了，否则就是「看门狗把实例看死了」，要吵出来而不是静默
  BACK=0
  for n in $(seq 1 60); do
    if lsof -ti:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then BACK=1; break; fi
    sleep 1
  done
  if [ "$BACK" = "1" ]; then
    NEWPID=$(lsof -ti:"$PORT" -sTCP:LISTEN 2>/dev/null | head -1)
    printf '%s\t%s\t%s\t%s\n' "$NOW" "$RSS_MB" "$PID" "$NEWPID" >> "$LEDGER" 2>/dev/null || true
    _log "重启完成，新 pid=$NEWPID（${n}s 内恢复）"
    # ② 告警升级：1 小时内第 2 次起 → 高优外发（单次静默重启是正常运维，不值得打扰）
    if [ "$RECENT" -ge 1 ]; then
      _notify "【DSH 内存看门狗】1 小时内第 $((RECENT + 1)) 次重启（rss=${RSS_MB}MB）" "$(_alert_text "反复超阈值重启，疑似内存重建/泄漏型高水位")"
    fi
  else
    _log "FAIL: 重启后 ${n}s 内 $PORT 仍未监听，需人工介入"
    _notify "【DSH 内存看门狗】重启失败：$PORT 未恢复监听" "$(_alert_text "看门狗重启后端口未恢复，需人工介入")"
    exit 1
  fi
fi
exit 0
