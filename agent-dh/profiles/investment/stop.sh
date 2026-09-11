#!/bin/bash
# DSH Investment Agent 停止脚本（多实例安全版）
# 只停本实例（:13080，pidfile 校验），三条铁律：
#   ① 禁止 pkill -f 模糊匹配（会误杀同机其他 dsh 实例）
#   ② lsof 查端口必须 -sTCP:LISTEN（否则会把有页面连接的浏览器进程也杀掉）
#   ③ kill 前校验目标确实在监听本端口（防 PID 复用误杀）
set -e

PROFILE_DIR="$(cd "$(dirname "$0")" && pwd)"
PID_FILE="$PROFILE_DIR/state/server.pid"
PORT_FILE="$PROFILE_DIR/state/server.port"
PORT="${1:-$(cat "$PORT_FILE" 2>/dev/null || echo 13080)}"

killed=0

# 路径 0：launchd 托管分支（2026-09-11）
# KeepAlive 下 kill 只会被 launchd 立刻拉起，stop.sh 会"看起来成功"但服务仍在跑
# ——静默失效比报错更危险。真正停机必须 bootout（停止**并卸载**作业，KeepAlive 随之失效）。
LAUNCHD_LABEL="com.pi-investment.dsh"
LAUNCHD_PLIST="$HOME/Library/LaunchAgents/$LAUNCHD_LABEL.plist"
LAUNCHD_TARGET="gui/$(id -u)/$LAUNCHD_LABEL"

if launchctl print "$LAUNCHD_TARGET" >/dev/null 2>&1; then
  MANAGED_PORT=$(/usr/libexec/PlistBuddy -c "Print :ProgramArguments:2" "$LAUNCHD_PLIST" 2>/dev/null || true)
  MANAGED_PORT="${MANAGED_PORT:-13080}"
  if [ "$PORT" = "$MANAGED_PORT" ]; then
    echo "stop.sh: :$PORT 由 launchd 作业 $LAUNCHD_LABEL 托管，改用 bootout（kill 会被 KeepAlive 立刻拉起）"
    launchctl bootout "$LAUNCHD_TARGET" || { echo "stop.sh: bootout 失败" >&2; exit 1; }
    sleep 2
    if lsof -ti:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
      echo "stop.sh: 作业已卸载但 :$PORT 仍有残留监听，SIGKILL"
      lsof -ti:"$PORT" -sTCP:LISTEN | xargs kill -9 2>/dev/null || true
      sleep 1
    fi
    if lsof -ti:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
      echo "stop.sh: 停止失败，:$PORT 仍在监听" >&2
      exit 1
    fi
    echo "stop.sh: done（作业已卸载，实例已真正停止）"
    echo "stop.sh: 恢复运行: ./start.sh   （等价于 launchctl bootstrap gui/$(id -u) ${LAUNCHD_PLIST}）"
    exit 0
  fi
fi

# 路径 1：pidfile（校验该 PID 确实监听本端口，防止 PID 复用误杀）
if [ -f "$PID_FILE" ]; then
  PID=$(head -1 "$PID_FILE" | tr -d '[:space:]')
  if [ -n "$PID" ] && kill -0 "$PID" 2>/dev/null; then
    if lsof -a -p "$PID" -i ":$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
      echo "stop.sh: killing investment instance pid=$PID (port $PORT)"
      kill "$PID" 2>/dev/null || true
      killed=1
    else
      echo "stop.sh: pidfile pid=$PID 未监听 :${PORT}（PID 可能已被复用），跳过，改走端口路径"
    fi
  fi
fi

# 路径 2：端口兜底（只杀监听本端口的进程——注意 -sTCP:LISTEN，连接中的浏览器不算）
if [ "$killed" = "0" ]; then
  PIDS=$(lsof -ti:"$PORT" -sTCP:LISTEN 2>/dev/null || true)
  if [ -n "$PIDS" ]; then
    echo "stop.sh: killing listener(s) on port $PORT: $PIDS"
    echo "$PIDS" | xargs kill 2>/dev/null || true
    killed=1
  fi
fi

if [ "$killed" = "0" ]; then
  echo "stop.sh: 未发现 :$PORT 上监听的 investment 实例"
else
  sleep 2
  if lsof -ti:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
    echo "stop.sh: 进程未退出，SIGKILL"
    lsof -ti:"$PORT" -sTCP:LISTEN | xargs kill -9 2>/dev/null || true
  fi
  echo "stop.sh: done"
fi
