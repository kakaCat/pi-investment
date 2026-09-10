#!/usr/bin/env bash
# 日志轮转"是否真的跑了"的独立探针（2026-09-11 立，w-f4aa1f6a）
#
# 为什么需要它：轮转是典型的"静默失效型"任务——plist 加载了、但没跑/报错都不会有人知道，
# 直到磁盘被写满才暴露。本脚本把"没跑"翻译成**一条会进 open 队列的错误事件**，
# 让 REQ-a42aa4 的采集→处置闭环自己去兜它，而不是靠人记得去看日志。
set -uo pipefail

CHECK_OUT=$(bash /Users/yunpeng/pi-investment/scripts/rotate-logs.sh --check 2>&1)
rc=$?
if [ "$rc" -eq 0 ]; then
  echo "$CHECK_OUT"
  exit 0
fi

echo "$CHECK_OUT" >&2
# 失败 → 投递错误事件（source=os；msg 稳定以便指纹去重，detail 带原始输出）
payload=$(python3 - "$CHECK_OUT" <<'PY'
import json, sys
msg = '服务日志轮转定时任务疑似失效（rotate-logs --check 失败）'
print(json.dumps({
    'source': 'os',
    'level': 'error',
    'msg': msg,
    'detail': sys.argv[1][:2000],
    'metadata': {'probe': 'log-rotate-check', 'script': 'scripts/rotate-logs-check.sh'},
}, ensure_ascii=False))
PY
)
curl -s -X POST http://127.0.0.1:8080/api/v1/scheduler/error-events \
  -H 'Content-Type: application/json' -d "$payload" -o /dev/null -w 'error-event ingest HTTP=%{http_code}\n' || true
exit 1
