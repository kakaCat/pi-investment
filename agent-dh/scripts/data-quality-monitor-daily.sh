#!/bin/sh
# 数据质量每日检查 —— 免 agent 执行包装（2026-09-05）
# 由 Agent OS scheduler 的 command 路径直接调用（不再经 webhook→agent 投递）。
# launchd 环境 PATH 不含 node，必须在此显式补齐；脚本定位用绝对路径，不依赖调用方 cwd。
export PATH="/Users/yunpeng/.local/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
cd /Users/yunpeng/pi-investment/agent-dh || exit 1
exec node_modules/.bin/tsx scripts/data-quality-monitor.ts
