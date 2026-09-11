#!/bin/bash
# Agent-DH 发版/重启脚本（校验插件链接 + 构建客户端包 + 重启）
# 用法: ./scripts/restart-with-build.sh
#
# 2026-09-11 两轮修正：
#
# ① 原实现 `lsof -ti:13080 | xargs kill -9` + `./start.sh &` 在 launchd 托管
#    （KeepAlive）下有两处错：kill 只触发 launchd 立刻重生（ThrottleInterval 从"上次
#    拉起"起算），旧实例被杀的瞬间新实例已经起来，后续 start 必然 EADDRINUSE；更要命
#    的是顺序错了 —— kill 之后 launchd 立刻用**旧代码**把服务拉起来，构建发生在之后，
#    等于"编译了但没部署"。正确顺序：bootout（真正停）→ 构建 → bootstrap（再拉起）。
#    另：`lsof -ti:13080` 缺 -sTCP:LISTEN，会把持有连接的浏览器进程也算进来（stop.sh 铁律②）。
#
# ② `pnpm build` 从来就不等于部署，本脚本以前也没做任何部署。profile 的插件依赖由
#    pnpm 装成**硬链接副本**，文件一旦被编辑就断链、静默停在旧版本（2026-09-11 事故：
#    全天 RFC 015 工作全部没生效）。现在加了 relink 步骤把依赖统一成指向仓库的符号链接。

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PROFILE_DIR="$HOME/.dsh/profiles/investment"

LAUNCHD_LABEL="com.pi-investment.dsh"
LAUNCHD_PLIST="$HOME/Library/LaunchAgents/$LAUNCHD_LABEL.plist"
LAUNCHD_TARGET="gui/$(id -u)/$LAUNCHD_LABEL"
PORT=13080

echo "========================================"
echo "  Agent-DH 发版重启（校验链接 + 构建 + 重启）"
echo "========================================"

# 0. 前置告警：依赖是符号链接，工作区里**未提交**的改动重启后就会直接上线
echo "[0/5] 检查工作区..."
DIRTY=$(git -C "$PROJECT_ROOT" status --porcelain -- packages/ || true)
if [ -n "$DIRTY" ]; then
  echo "⚠️  packages/ 下有未提交的改动 —— 它们重启后会**直接生效**（依赖是符号链接）："
  echo "$DIRTY" | sed 's/^/      /'
  echo "      如果某个包正在被别的会话改动、不该发布，先把它隔离出去再重启。"
  echo ""
fi

# 1. 停止服务（托管时必须 bootout，kill 会被 KeepAlive 立刻拉起）
echo "[1/5] 停止 Agent-DH 服务..."
MANAGED=0
if launchctl print "$LAUNCHD_TARGET" >/dev/null 2>&1; then
  MANAGED=1
  launchctl bootout "$LAUNCHD_TARGET"
  echo "✓ 服务已停止（launchd 作业已卸载）"
else
  if lsof -ti:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
    lsof -ti:"$PORT" -sTCP:LISTEN | xargs kill 2>/dev/null || true
    echo "✓ 服务已停止"
  else
    echo "✓ 服务未运行"
  fi
fi

# 等端口真正释放（条件等待，替代拍脑袋 sleep）
for _ in $(seq 1 40); do
  lsof -ti:"$PORT" -sTCP:LISTEN >/dev/null 2>&1 || break
  sleep 0.5
done
if lsof -ti:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  lsof -ti:"$PORT" -sTCP:LISTEN | xargs kill -9 2>/dev/null || true
  sleep 1
fi

# 2. 构建客户端包（这两个的 main 指向 dist/，其余包 tsx 直载 TS，无需构建）
echo ""
echo "[2/5] 构建 agent-os-client..."
cd "$PROJECT_ROOT/../agent-os-client"
pnpm build

echo ""
echo "[3/5] 构建 quantsys-v2-client..."
cd "$PROJECT_ROOT/../quantsys-v2-client"
pnpm build

# 3. 校验并修复 profile 插件链接（防 pnpm install 把符号链接换回硬链接副本）
echo ""
echo "[4/5] 校验 DSH profile 插件链接..."
if python3 "$SCRIPT_DIR/relink-profile.py" --check; then
  echo "✓ 依赖均为指向仓库的符号链接"
else
  echo "  发现漂移，正在修复（旧副本备份到 $PROFILE_DIR/.deploy-backup/）..."
  python3 "$SCRIPT_DIR/relink-profile.py"
fi

# 4. 启动服务
echo ""
echo "[5/5] 启动 Agent-DH 服务..."
if [ "$MANAGED" = "1" ]; then
  # 恢复托管，保住 KeepAlive 兜底（直接 exec start.sh 会起一个没有自动重启的裸实例）
  launchctl bootstrap "gui/$(id -u)" "$LAUNCHD_PLIST"
else
  cd "$PROFILE_DIR"
  ./start.sh &
fi

sleep 3

# 5. 验证服务
if lsof -ti:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  echo ""
  echo "✅ Agent-DH 已重启"
  echo "   端口: $PORT"
  echo "   日志: tail -f $PROFILE_DIR/state/launchd.out.log"
else
  echo ""
  echo "❌ 启动失败，请检查日志: $PROFILE_DIR/state/launchd.err.log"
  exit 1
fi
