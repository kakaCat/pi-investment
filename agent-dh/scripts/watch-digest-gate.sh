#!/usr/bin/env bash
# 盯盘摘要门（REQ-f08def Phase 2 · RFC 014 §4.5/§6）
#
# 唯一职责：让 agent 唤醒次数与触发数解耦。
#   · 队列空            → 静默退出，零 LLM
#   · 距上次唤醒太近     → 静默退出（最小间隔，防同一批被反复唤醒）
#   · 当日唤醒已达上限   → 静默退出（日上限）
#   · 否则              → 只唤醒一次，处理「自上次水位线以来的全部」待处置项
#
# 用法：watch-digest-gate.sh [since_iso]  # 不传时用水位线文件
# 环境：WATCH_API / AGENT_HOOK / MIN_INTERVAL_SEC(1500) / DAILY_CAP(8) / DRY_RUN=1
set -uo pipefail

WATCH_API="${WATCH_API:-http://127.0.0.1:5001}"
AGENT_HOOK="${AGENT_HOOK:-http://127.0.0.1:13080/agent-os-trigger}"
MIN_INTERVAL_SEC="${MIN_INTERVAL_SEC:-1500}"
DAILY_CAP="${DAILY_CAP:-8}"
STATE_DIR="${STATE_DIR:-$HOME/.dsh-agent-dh/profiles/investment/state}"
MARK="${STATE_DIR}/watch-digest-watermark"
CNT="${STATE_DIR}/watch-digest-count"
mkdir -p "${STATE_DIR}" 2>/dev/null || true

now_epoch() { date +%s; }
today() { date +%Y-%m-%d; }

# ── 闸门 1：最小间隔（防同一批待处置被反复唤醒）──
LAST_WAKE="$(cat "${MARK}" 2>/dev/null || echo 0)"
if [ "${LAST_WAKE}" -gt 0 ] 2>/dev/null; then
  ELAPSED=$(( $(now_epoch) - LAST_WAKE ))
  if [ "${ELAPSED}" -lt "${MIN_INTERVAL_SEC}" ]; then
    echo "[watch-digest] 距上次唤醒 ${ELAPSED}s < ${MIN_INTERVAL_SEC}s，静默退出"; exit 0
  fi
fi

# ── 闸门 2：当日唤醒上限 ──
C_TODAY="$(cut -d' ' -f1 "${CNT}" 2>/dev/null || echo '')"
C_N="$(cut -d' ' -f2 "${CNT}" 2>/dev/null || echo 0)"
[ "${C_TODAY}" = "$(today)" ] || C_N=0
if [ "${C_N}" -ge "${DAILY_CAP}" ] 2>/dev/null; then
  echo "[watch-digest] 当日唤醒已达上限 ${C_N}/${DAILY_CAP}，静默退出"; exit 0
fi

# ── 闸门 3：队列空 ──
SINCE="${1:-}"
if [ -z "${SINCE}" ] && [ -f "${MARK}.iso" ]; then SINCE="$(cat "${MARK}.iso")"; fi
if [ -z "${SINCE}" ]; then SINCE="$(date -v-1d +%Y-%m-%dT%H:%M:%S 2>/dev/null || date -d '1 day ago' +%Y-%m-%dT%H:%M:%S)"; fi
URL="${WATCH_API}/api/watch/triggers/digest?since=${SINCE}"
RESP="$(curl -s --max-time 15 "${URL}" || true)"
if [ -z "${RESP}" ]; then echo "[watch-digest] 摘要接口不可达，跳过"; exit 0; fi
GATE="$(printf %s "${RESP}" | python3 -c "import json,sys
try: d=json.load(sys.stdin)['data']
except Exception: print('FALSE'); raise SystemExit
print('TRUE' if d.get('gate') else 'FALSE')" 2>/dev/null || echo FALSE)"
if [ "${GATE}" != "TRUE" ]; then echo "[watch-digest] 自 ${SINCE} 起无待处置触发，静默退出（零 LLM）"; exit 0; fi
PAYLOAD="$(printf %s "${RESP}" | python3 -c "import json,sys
d=json.load(sys.stdin)['data']
head=('【盯盘待处置摘要】共 {n} 条触发、{g} 个标的（自上次摘要以来）。请按标的处置，不要逐条发通知：'+chr(10)+
 '1) 可自决的：执行后 PATCH /api/watch/triggers/{{id}} 置 handled，reason 写动作与结果；'+chr(10)+
 '2) 判不动的：置 ignored，reason 必须含「为什么不动 + 下次什么条件下才动(NEXT)」；'+chr(10)+
 '3) 需用户决策的（超授权/资金/不可逆/置信不足）：不要替用户决定，留在待决策队列，由交互会话用 ask_user_question 拉起；'+chr(10)+
 '4) 本次不要再发逐条飞书；遵守 R-001~R-009 与交易宪法。'+chr(10)+chr(10)).format(n=d['count'],g=d['group_count'])
print(json.dumps({'prompt': head+d.get('text','')}, ensure_ascii=False))" 2>/dev/null)"
if [ -z "${PAYLOAD}" ]; then echo "[watch-digest] 载荷构建失败，跳过"; exit 0; fi
if [ "${DRY_RUN:-}" = "1" ]; then echo "[dry-run] 将要唤醒 agent（不发送）："; echo "${PAYLOAD}"; exit 0; fi
if curl -s --max-time 15 -X POST "${AGENT_HOOK}" -H 'Content-Type: application/json' -d "${PAYLOAD}" >/dev/null; then
  now_epoch > "${MARK}"
  date +%Y-%m-%dT%H:%M:%S > "${MARK}.iso"
  echo "$(today) $(( C_N + 1 ))" > "${CNT}"
  echo "[watch-digest] 已唤醒 agent 处理待处置项（今日第 $(( C_N + 1 )) 次）"
else
  echo "[watch-digest] 唤醒失败（不写水位线，下次重试）"
fi
