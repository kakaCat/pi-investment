#!/bin/bash
# DSH Investment Agent 启动脚本
# 2026-08-19 起从 npm 发布的 @deepseek-ai/dsh 启动（运行时与 deepseek-harness 源码仓解耦，
# 不再依赖 /Volumes/ORICO 母体；Node ≥22.18 原生类型擦除可直接加载 TS 插件入口）
#
# 用法:
#   ./start.sh [端口] [web 子命令额外参数]
#   ./start.sh                    # 默认端口 13080（launchd 托管端口）
#   ./start.sh 13081              # 指定端口（脱离 launchd 的裸实例）
#   ./start.sh 13081 --dump-config  # 打印组合后的 profile 配置并退出
#
# 重启 :13080（本机 launchd 托管，唯一正确入口）:
#   launchctl kickstart -k gui/$(id -u)/com.pi-investment.dsh
# 停止 :13080:
#   ./stop.sh        （内部走 launchctl bootout；直接 kill 会被 KeepAlive 立刻拉起）
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

# 与 agent-dh/package.json 的 @deepseek-ai/dsh-* 依赖对齐。
# ⚠️ 本行**刻意**与线上不同，勿"顺手同步"：线上用 node -p 读 node_modules 里的实际版本，
# 而模板目录没有 node_modules，那句在 set -e 下会直接让脚本失败。升级 dsh 依赖时两边都要改。
DSH_VERSION="0.1.2-alpha.4"  # 2026-09-11 同步线上（原 0.1.0-rc.7 陈旧，从模板重建会降级）
PORT="${1:-13080}"

# ── launchd 托管互斥（2026-09-11）────────────────────────────────────────────
# 本机 :13080 由 launchd 作业 com.pi-investment.dsh 托管（KeepAlive + RunAtLoad，
# ProgramArguments 就是本脚本）。此时手工 `lsof -ti:13080 | xargs kill -9 && ./start.sh`
# **必然** EADDRINUSE：ThrottleInterval 从"上次拉起"起算而非从退出起算，对一个已经跑了
# 很久的实例等于立即重启，手工进程根本抢不到端口（2026-09-11 事故根因）。
# 因此：只要作业已加载、且请求的端口就是它托管的端口，本脚本不再自行 bind，而是把
# "重启"这个意图转交给 launchctl（kickstart -k 会负责先杀后拉，是唯一正确的重启入口）。
#
# 安全绳：判定"我就是 launchd 拉起的那个进程"用双保险（PPID=1 / launchd 记录的作业 pid
# 就是我）。托管实例自身必须永远不走 kickstart，否则就是自我重启死循环——KeepAlive 下
# 会无限重跑（2026-09-11 已踩过一次的坑）。
LAUNCHD_LABEL="com.pi-investment.dsh"
LAUNCHD_PLIST="$HOME/Library/LaunchAgents/$LAUNCHD_LABEL.plist"
LAUNCHD_TARGET="gui/$(id -u)/$LAUNCHD_LABEL"

_launchd_loaded() { launchctl print "$LAUNCHD_TARGET" >/dev/null 2>&1; }
_launchd_job_pid() {
  launchctl print "$LAUNCHD_TARGET" 2>/dev/null \
    | awk -F'= ' '/[[:space:]]pid = /{print $2; exit}' | tr -d '[:space:]'
}
_is_launchd_child() {
  # ① launchd 直接 fork+exec 本脚本，故 PPID=1（exec node 不改变 PID/PPID）
  if [ "${PPID:-0}" = "1" ]; then
    return 0
  fi
  # ② 兜底：作业当前记录的 pid 就是本进程（与 PPID 逻辑无关，防 PPID 判定失效）
  _jp="$(_launchd_job_pid)"
  if [ -n "$_jp" ] && [ "$_jp" = "$$" ]; then
    return 0
  fi
  return 1
}

_launchd_managed_port() {
  local p
  p=$(/usr/libexec/PlistBuddy -c "Print :ProgramArguments:2" "$LAUNCHD_PLIST" 2>/dev/null || true)
  printf '%s' "${p:-13080}"
}

if _launchd_loaded; then
  MANAGED_PORT="$(_launchd_managed_port)"
  if [ "$PORT" = "$MANAGED_PORT" ] && ! _is_launchd_child; then
    echo "注意: :$PORT 由 launchd 作业 $LAUNCHD_LABEL 托管（KeepAlive）。"
    echo "      手工 bind 会与 launchd 抢端口（必然 EADDRINUSE），已改为请求 launchctl 重启。"
    echo "      如确实要脱离 launchd 手工接管: launchctl bootout $LAUNCHD_TARGET"
    exec launchctl kickstart -k "$LAUNCHD_TARGET"
  fi
fi

# 作业文件存在但未加载（例如刚被 stop.sh bootout）时，优先恢复托管而不是起一个
# "没有 KeepAlive 兜底"的裸进程——否则 stop → start 之后实例会失去自动重启能力。
if [ "$PORT" = "13080" ] && [ -f "$LAUNCHD_PLIST" ] && ! _launchd_loaded; then
  echo "注意: launchd 作业 $LAUNCHD_LABEL 未加载，正在恢复托管（bootstrap）。"
  echo "      如确实要起脱离 launchd 的裸实例，请换端口: ./start.sh 13081"
  exec launchctl bootstrap "gui/$(id -u)" "$LAUNCHD_PLIST"
fi

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
