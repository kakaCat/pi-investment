#!/bin/sh
# event-calendar-check 免 agent 执行包装（launchd PATH 无 node，必须显式补 PATH）
export PATH="/Users/yunpeng/.local/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
cd /Users/yunpeng/pi-investment/agent-dh || exit 1
exec node_modules/.bin/tsx scripts/event-calendar-check.ts
