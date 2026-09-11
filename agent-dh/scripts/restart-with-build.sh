#!/bin/bash
# Agent-DH 重启脚本（含客户端包构建）
# 用法: ./scripts/restart-with-build.sh
#
# 2026-09-11 修正：原实现 `lsof -ti:13080 | xargs kill -9` + `./start.sh &` 在 launchd
# 托管（KeepAlive）下有两处错：
#   ① kill 只触发 launchd 立刻重生（ThrottleInterval 从"上次拉起"起算），旧实例被杀的
#      瞬间新实例已经起来 —— 后续 start 必然 EADDRINUSE；
#   ② 顺序错了：kill 之后 launchd 立刻用**旧代码**把服务拉起来，构建发生在之后，
#      等于"编译了但没部署"，跑的还是老代码。
# 正确顺序：bootout（真正停）→ 构建 → bootstrap（再拉起）。另：`lsof -ti:13080` 缺
# -sTCP:LISTEN 会把持有连接的浏览器进程一并算进来（见 stop.sh 铁律②）。

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

LAUNCHD_LABEL="com.pi-investment.dsh"
LAUNCHD_PLIST="$HOME/Library/LaunchAgents/$LAUNCHD_LABEL.plist"
LAUNCHD_TARGET="gui/$(id -u)/$LAUNCHD_LABEL"
PORT=13080

echo "========================================"
echo "  Agent-DH 重启（含构建）"
echo "========================================"

# 1. 停止服务（托管时必须 bootout，kill 会被 KeepAlive 立刻拉起）
echo "[1/4] 停止 Agent-DH 服务..."
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
if [ "$MANAGED" = "1" ]; then
  # 恢复托管，保住 KeepAlive 兜底（exec 掉 start.sh 会起一个没有自动重启的裸实例）
  launchctl bootstrap "gui/$(id -u)" "$LAUNCHD_PLIST"
else
  cd ~/.dsh/profiles/investment
  ./start.sh &
fi

sleep 3

# 4. 验证服务
if lsof -ti:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  echo ""
  echo "✅ Agent-DH 已重启"
  echo "   端口: $PORT"
  echo "   日志: tail -f ~/.dsh-agent-dh/logs/dsh.log"
else
  echo ""
  echo "❌ 启动失败，请检查日志"
  exit 1
fi
