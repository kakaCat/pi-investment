#!/bin/bash
# DSH Investment Agent 启动脚本
# 使用 tsx 模式启动，支持 TypeScript 插件热加载
#
# 用法:
#   ./start.sh [端口] [额外参数]
#   ./start.sh              # 使用默认端口 13080
#   ./start.sh 13081        # 使用指定端口
#   ./start.sh 13081 --dump-config  # 打印配置并退出

set -e

# 加载环境变量
PROFILE_DIR="$(cd "$(dirname "$0")" && pwd)"
if [ -f "$PROFILE_DIR/.env" ]; then
  export $(cat "$PROFILE_DIR/.env" | grep -v '^#' | xargs)
fi

# 必需的 API Key
if [ -z "$DEEPSEEK_API_KEY" ] && [ -z "$OPENAI_API_KEY" ]; then
  echo "错误: 请设置 DEEPSEEK_API_KEY 或 OPENAI_API_KEY 环境变量"
  echo ""
  echo "示例:"
  echo "  export DEEPSEEK_API_KEY=sk-..."
  echo "  export OPENAI_API_KEY=sk-..."
  echo ""
  echo "或将环境变量写入 $PROFILE_DIR/.env 文件"
  exit 1
fi

# DSH 仓库路径
DSH_ROOT="/Volumes/ORICO/doc/github/deepseek-harness"

# 默认端口
PORT="${1:-13080}"

# 检查 DSH 根目录
if [ ! -d "$DSH_ROOT" ]; then
  echo "错误: DSH 根目录不存在: $DSH_ROOT"
  exit 1
fi

echo "========================================"
echo "  PI Investment Agent-DH 启动"
echo "========================================"
echo "Profile: investment"
echo "Port: $PORT"
echo "DSH Root: $DSH_ROOT"
echo ""

cd "$DSH_ROOT"

# 使用 tsx 模式启动（支持 TypeScript 插件热加载）
# 生产环境应使用: node apps/cli/lib/bin.js（需先构建插件）
exec node --import tsx/esm apps/cli/src/bin.ts \
  --profile investment \
  --port "$PORT" \
  "${@:2}"
