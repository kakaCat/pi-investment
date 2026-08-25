#!/bin/bash
# OS 提醒桥接：Agent OS scheduler 任务触发时执行，把提醒写入 OS 记忆库信箱
# 数据流：OS cron 任务 → 本脚本 → OS memory（tags: office:reminder:<window>）
#        → lifecycle 轮询（60s）→ followup 投递到窗口会话
# 用法: os-remind-bridge.sh "<task_name>"
set -euo pipefail

TASK_NAME="${1:?usage: os-remind-bridge.sh <task_name>}"
OS="${AGENT_OS_URL:-http://localhost:8080}"
export TASK_NAME OS

# 按名称查任务，取 payload.prompt / payload.window（任务名经环境变量传 python，避免插值转义问题）
TASK_JSON=$(curl -sf "$OS/api/v1/scheduler/tasks" | python3 -c "
import json, sys, os
name = os.environ['TASK_NAME']
d = json.load(sys.stdin)
tasks = d.get('tasks') or []
hit = [t for t in tasks if t.get('name') == name]
if not hit:
    sys.exit(2)
t = hit[0]
p = t.get('payload') or {}
print(json.dumps({
    'prompt': p.get('prompt', ''),
    'window': p.get('window', ''),
    'task_id': str(t.get('id', '')),
    'name': t.get('name', ''),
}, ensure_ascii=False))
")

PROMPT=$(echo "$TASK_JSON" | python3 -c "import json,sys; print(json.load(sys.stdin)['prompt'])")
if [ -z "$PROMPT" ]; then
  echo "os-remind-bridge: task '$TASK_NAME' payload 无 prompt，丢弃" >&2
  exit 1
fi

# 写入 OS 记忆库（提醒信箱）
echo "$TASK_JSON" | python3 -c "
import json, sys, datetime
t = json.load(sys.stdin)
body = {
    'title': 'reminder ' + t['name'],
    'content': json.dumps({
        'prompt': t['prompt'],
        'window': t['window'],
        'task_id': t['task_id'],
        'task': t['name'],
        'fired_at': datetime.datetime.now().astimezone().isoformat(),
        'delivered': False,
    }, ensure_ascii=False),
    'category': 'data',
    'tags': ['office:reminder', 'office:reminder:' + t['window']],
}
print(json.dumps(body, ensure_ascii=False))
" | curl -sf -X POST "$OS/api/v1/memory" -H 'Content-Type: application/json' -d @- >/dev/null

echo "os-remind-bridge: reminder '${TASK_NAME}' 已入信箱"
