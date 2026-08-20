#!/bin/bash
# DSH Investment Agent 启动脚本
# 2026-08-19 起从 npm 发布的 @deepseek-ai/dsh 启动（运行时与 deepseek-harness 源码仓解耦，
# 不再依赖 /Volumes/ORICO 母体；Node ≥22.18 原生类型擦除可直接加载 TS 插件入口）
#
# 用法:
#   ./start.sh [端口] [web 子命令额外参数]
#   ./start.sh                    # 默认端口 13080
#   ./start.sh 13081              # 指定端口
#   ./start.sh 13081 --dump-config  # 打印组合后的 profile 配置并退出
set -e

# 独立 DSH_HOME：与主实例（~/.dsh，:3080）隔离，避免两个 dsh web 进程共享
# 单写者存储（session_projcache 为每进程全量内存 + 整文件覆盖写，
# 共享会导致投影缓存行互相抹除，表现为侧边栏"找不到 session 信息"）。
# 注意：在 dsh 会话内调用本脚本会继承父进程的 DSH_HOME=~/.dsh，必须显式覆盖；
# 仅当用户故意设为其它非默认值时才予以尊重。
if [ -z "$DSH_HOME" ] || [ "$DSH_HOME" = "$HOME/.dsh" ]; then
  export DSH_HOME="$HOME/.dsh-agent-dh"
fi

# 加载环境变量（可选；dsh 自身 credentials 体系也可提供 key）
PROFILE_DIR="$(cd "$(dirname "$0")" && pwd)"
if [ -f "$PROFILE_DIR/.env" ]; then
  export $(cat "$PROFILE_DIR/.env" | grep -v '^#' | xargs)
fi

if [ -z "$DEEPSEEK_API_KEY" ] && [ -z "$OPENAI_API_KEY" ]; then
  echo "警告: 未设置 DEEPSEEK_API_KEY / OPENAI_API_KEY（若已在 dsh 设置中配置可忽略）"
fi

# 与 agent-dh/package.json 的 @deepseek-ai/dsh-* 依赖对齐
DSH_VERSION="0.1.0-rc.7"
PORT="${1:-13080}"

echo "========================================"
echo "  PI Investment Agent-DH 启动"
echo "========================================"
echo "Profile: investment"
echo "Port: $PORT"
echo "Runtime: @deepseek-ai/dsh@$DSH_VERSION (npx)"
echo ""

# 插件入口为 TS 源码（main: ./src/index.ts）且内部用 .js 说明符互引，
# 原生类型擦除不会改写说明符，必须挂 tsx 加载器（与旧 ORICO 启动方式同理）
DSH_BIN="$PROFILE_DIR/node_modules/@deepseek-ai/dsh/lib/bin.js"
cd "$PROFILE_DIR"

if [[ " $* " == *" --dump-config "* ]]; then
  exec node --import tsx/esm "$DSH_BIN" --profile investment --dump-config
fi

exec node --import tsx/esm "$DSH_BIN" --profile investment --port "$PORT" "${@:2}"
