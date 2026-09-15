#!/bin/bash
# pmboard 三功能上线：延迟重启 + 重启后自检（本会话无法自我重启，故用脱离进程）
LOG=/tmp/pm-restart.log
echo "[$(date '+%F %T')] 计划重启（30s 后）" >> "$LOG"
sleep 30
launchctl kickstart -k "gui/$(id -u)/com.pi-investment.dsh" >> "$LOG" 2>&1
echo "[$(date '+%F %T')] kickstart 已发出" >> "$LOG"

CODE=000
for i in $(seq 1 45); do
  sleep 2
  CODE=$(curl -s -m 3 -o /tmp/pm-selfcheck.json -w '%{http_code}' \
    http://127.0.0.1:13080/dashboard/api/reqboard/requirements/summary 2>/dev/null)
  [ "$CODE" = "200" ] && break
done

{
  echo "=== pmboard 重启后自检 $(date '+%F %T') ==="
  echo "GET /requirements/summary → HTTP $CODE"
  if [ "$CODE" = "200" ]; then
    echo "--- 响应前 400 字节 ---"
    head -c 400 /tmp/pm-selfcheck.json
    echo
  else
    echo "!! 新接口未就绪，请检查 DSH 启动日志："
    echo "   tail -50 /Users/yunpeng/pi-investment/agent-dh/.dsh-data/profiles/agent-dh/*.log 2>/dev/null"
  fi
  PID=$(lsof -ti:13080 -sTCP:LISTEN 2>/dev/null | head -1)
  echo "监听 :13080 的 PID = ${PID:-无}"
} >> "$LOG" 2>&1
