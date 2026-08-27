#!/bin/bash
# agent-os 幂等启动脚本（唯一生命周期入口）
# 2026-08-27 w-5b8aac2a：根治"手动启动/launchd/插件重启三路并发导致端口冲突与假死"
# 设计：launchd / agent_os_restart 插件 / 人工 都必须走本脚本。
#   1. 抢端口前先清场（杀掉 8080/8081 上的残留进程，防"旧实例未死透新实例撞端口"）
#   2. exec 替换进程（launchd 监控的 PID 就是 agent-os 本体，信号传递无误）
#   3. 任何一步失败都非零退出，让 launchd ThrottleInterval 后重试
set -euo pipefail

PROJECT_ROOT="/Users/yunpeng/pi-investment/agent-os"
BIN="$PROJECT_ROOT/bin/agent-os"

echo "[serve-guard] $(date '+%F %T') starting..."

# 清场：8080（HTTP）与 8081（WebSocket）上的残留监听者
for port in 8080 8081; do
  pids=$(lsof -ti:$port -sTCP:LISTEN 2>/dev/null || true)
  if [ -n "$pids" ]; then
    echo "[serve-guard] port $port occupied by $pids, killing..."
    kill $pids 2>/dev/null || true
    sleep 2
    # 没死透则强制
    pids=$(lsof -ti:$port -sTCP:LISTEN 2>/dev/null || true)
    [ -n "$pids" ] && kill -9 $pids 2>/dev/null || true
  fi
done

cd "$PROJECT_ROOT"
echo "[serve-guard] exec $BIN serve"
exec "$BIN" serve
