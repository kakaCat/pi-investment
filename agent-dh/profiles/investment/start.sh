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
DSH_VERSION="0.1.2-alpha.4"  # 2026-09-11 同步线上（原 0.1.0-rc.7 陈旧，从模板重建会降级）
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

# 堆上限（2026-09-11）：本实例是"多窗口共享单进程"，堆持续增长（实测稳态 RSS 3.7-3.9GB，
# 并随时间爬升），而 Node 默认 V8 old-space 上限仅 4144MB —— 2026-09-11 00:51 / 01:18
# 两次 `FATAL ERROR: Reached heap limit`（error_event 2a0f8617）就是撞在这个默认值上。
# 故显式提到 8192MB（机器 64GB 内存，余量充足），可用 DSH_MAX_OLD_SPACE 覆盖。
#
# 生效性已实测确认（2026-09-11 11:2x 复核）：活进程环境里能看到
# `NODE_OPTIONS=--max-old-space-size=8192`，参数确实传到了 node。
#
# ⚠️ 本文件是**模板**：launchd（com.pi-investment.dsh）实际执行的是
# ~/.dsh/profiles/investment/start.sh。只改这里而不部署 = 什么都没发生。
# 历史上本修复就曾"看起来没生效"，原因是**部署漂移**而非参数本身：00:58 它先落在
# ~/.dsh-agent-dh/profiles/investment/start.sh，而 launchd 执行的是 ~/.dsh/... 那份，
# 直到 01:20 才补上（见该文件 w-f4aa1f6a 的注释）。两份 profile 需保持同步。
#
# 这仍是治标：真正的增长源（多窗口会话记录常驻堆）需上游 DSH 修。
DSH_MAX_OLD_SPACE="${DSH_MAX_OLD_SPACE:-8192}"
export NODE_OPTIONS="--max-old-space-size=${DSH_MAX_OLD_SPACE}${NODE_OPTIONS:+ $NODE_OPTIONS}"

# 多实例隔离（2026-08-21）：写本实例 pidfile（exec 保持 PID 不变，$$ 即最终 node 进程 PID）。
# 停止本实例只能走 stop.sh（pidfile + 端口双重校验），禁止 pkill -f 模糊匹配。
# 2026-09-11 同步线上：模板此前缺本段，从模板重建会丢失精确停机能力。
mkdir -p "$PROFILE_DIR/state"
echo $$ > "$PROFILE_DIR/state/server.pid"
echo $PORT > "$PROFILE_DIR/state/server.port"

if [[ " $* " == *" --dump-config "* ]]; then
  exec node --import tsx/esm "$DSH_BIN" --profile investment --dump-config
fi

exec node --import tsx/esm "$DSH_BIN" --profile investment --port "$PORT" "${@:2}"
