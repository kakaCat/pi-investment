#!/bin/bash
# pi-services — PI Investment 三层服务运维工具（agent / v2 / web）
#
# 用法：
#   scripts/ops/pi-services.sh status              # 三层状态总览
#   scripts/ops/pi-services.sh restart v2|web|agent|all
#   scripts/ops/pi-services.sh logs agent [行数]
#
# 设计约束（血泪教训固化）：
#   - v2 (5001) 与 web (3001) 由 launchd 托管（KeepAlive）——重启只能 launchctl kickstart -k，
#     禁止 nohup 手动起（会与 launchd respawn 抢端口，输家关闭 WatchEngine）
#   - agent 改为 headless 常驻（npm run headless：调度器+wake+feishu），
#     由本脚本 nohup 托管；TUI（npm run dev）检测到 automation.lock 会自动降级为纯交互
#   - 固定端口：v2=5001 web=3001 wake=3002，禁止漂移
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
AGENT_DIR="$REPO_ROOT/agent-ts"
AGENT_LOG="$AGENT_DIR/logs/agent-headless.log"
V2_LABEL="com.pi-investment.v2-api"
WEB_LABEL="com.pi-investment.web"
GUI="gui/$(id -u)"

green() { printf "\033[32m%s\033[0m\n" "$1"; }
red()   { printf "\033[31m%s\033[0m\n" "$1"; }
yellow(){ printf "\033[33m%s\033[0m\n" "$1"; }

port_ok() { lsof -nP -iTCP:"$1" -sTCP:LISTEN >/dev/null 2>&1; }

wait_port() { # port, timeout_s
  local port=$1 timeout=${2:-30} i=0
  while [ $i -lt "$timeout" ]; do
    if port_ok "$port"; then return 0; fi
    sleep 1; i=$((i+1))
  done
  return 1
}

status() {
  echo "=== PI Investment 服务状态 ==="
  if port_ok 5001; then green "v2 REST   5001  UP"; else red "v2 REST   5001  DOWN"; fi
  if port_ok 3001; then green "web       3001  UP"; else red "web       3001  DOWN"; fi
  if port_ok 3002; then green "wake      3002  UP"; else red "wake      3002  DOWN"; fi
  echo
  echo "--- launchd ---"
  launchctl list | grep "com.pi-investment" || yellow "(无 launchd 任务)"
  echo
  echo "--- agent 进程 ---"
  pgrep -fl "tsx src/(index|api/start-headless)\.ts" || yellow "(agent 未运行)"
  if [ -f "$AGENT_DIR/.pi-invest/automation.lock" ]; then
    echo "--- automation.lock ---"
    cat "$AGENT_DIR/.pi-invest/automation.lock"; echo
  fi
}

restart_v2() {
  yellow "重启 v2（launchctl kickstart -k $V2_LABEL）..."
  launchctl kickstart -k "$GUI/$V2_LABEL" || { red "launchctl 失败"; return 1; }
  if wait_port 5001 40; then
    local health
    health=$(curl -s --max-time 5 http://127.0.0.1:5001/api/memory/health || true)
    green "v2 已起：5001 监听中；/api/memory/health → $health"
  else
    red "v2 40s 内未监听 5001，查 logs/fastapi_5001.log"; return 1
  fi
}

restart_web() {
  yellow "重启 web（launchctl kickstart -k $WEB_LABEL）..."
  launchctl kickstart -k "$GUI/$WEB_LABEL" || { red "launchctl 失败"; return 1; }
  if wait_port 3001 40; then green "web 已起：3001 监听中"; else red "web 40s 内未监听 3001"; return 1; fi
}

restart_agent() {
  yellow "停止 agent（TUI/headless 进程树）..."
  pkill -f "tsx src/api/start-headless.ts" 2>/dev/null
  pkill -f "tsx src/index.ts" 2>/dev/null
  sleep 2
  # 残留强杀
  pkill -9 -f "tsx src/api/start-headless.ts" 2>/dev/null
  pkill -9 -f "tsx src/index.ts" 2>/dev/null
  rm -f "$AGENT_DIR/.pi-invest/automation.lock"

  yellow "启动 headless agent（nohup，日志 $AGENT_LOG）..."
  mkdir -p "$AGENT_DIR/logs"
  cd "$AGENT_DIR"
  nohup npm run headless > "$AGENT_LOG" 2>&1 &
  local pid=$!
  yellow "headless pid=$pid，等待 3002..."
  if wait_port 3002 60; then
    local health
    health=$(curl -s --max-time 5 http://127.0.0.1:3002/wake/health || true)
    green "agent 已起：3002 监听中；/wake/health → $health"
    echo "--- 启动日志尾部 ---"
    tail -15 "$AGENT_LOG"
  else
    red "agent 60s 内未监听 3002，最近日志："
    tail -30 "$AGENT_LOG"
    return 1
  fi
}

logs() {
  local target=${1:-agent} lines=${2:-50}
  case "$target" in
    agent) tail -n "$lines" "$AGENT_LOG" ;;
    v2)    tail -n "$lines" "$REPO_ROOT/quantsys-v2/logs/fastapi_5001.log" ;;
    *)     red "未知日志目标: $target（agent|v2）"; return 1 ;;
  esac
}

case "${1:-}" in
  status) status ;;
  logs)   logs "${2:-agent}" "${3:-50}" ;;
  restart)
    case "${2:-}" in
      v2)    restart_v2 ;;
      web)   restart_web ;;
      agent) restart_agent ;;
      all)   restart_v2 && restart_web && restart_agent ;;
      *)     echo "用法: $0 restart v2|web|agent|all"; exit 1 ;;
    esac ;;
  *) echo "用法: $0 status | logs [agent|v2] [行数] | restart v2|web|agent|all"; exit 1 ;;
esac
