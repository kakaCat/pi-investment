#!/bin/bash
# Agent-DH 重启脚本（含客户端包构建）
# 用法: ./scripts/restart-with-build.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "========================================"
echo "  Agent-DH 重启（含构建）"
echo "========================================"

# 1. 停止服务
echo "[1/4] 停止 Agent-DH 服务..."
if lsof -ti:13080 >/dev/null 2>&1; then
  lsof -ti:13080 | xargs kill -9
  echo "✓ 服务已停止"
else
  echo "✓ 服务未运行"
fi

sleep 2

# 2. 构建客户端包
echo ""
echo "[2/4] 构建 agent-os-client..."
cd "$PROJECT_ROOT/../agent-os-client"
pnpm build

echo ""
echo "[3/4] 构建 quantsys-v2-client..."
cd "$PROJECT_ROOT/../quantsys-v2-client"
pnpm build

# 3. 启动服务
echo ""
echo "[4/4] 启动 Agent-DH 服务..."
cd ~/.dsh/profiles/investment
./start.sh &

sleep 3

# 4. 验证服务
if lsof -ti:13080 >/dev/null 2>&1; then
  echo ""
  echo "✅ Agent-DH 已重启"
  echo "   端口: 13080"
  echo "   日志: tail -f ~/.dsh-agent-dh/logs/dsh.log"
else
  echo ""
  echo "❌ 启动失败，请检查日志"
  exit 1
fi
