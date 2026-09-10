#!/bin/bash
# Agent-DH OOM 频繁重启一键修复脚本
# 2026-09-11

set -e

echo "========================================"
echo "  Agent-DH OOM 重启修复"
echo "========================================"
echo ""

# Step 1: 停止所有 agent-dh 相关进程
echo "Step 1: 停止运行中的进程..."
pkill -f "dsh.*investment" || echo "  未找到运行中的进程"
sleep 2

# Step 2: 清理历史会话（减少启动内存压力）
echo ""
echo "Step 2: 清理历史会话..."
DSH_HOME="$HOME/.dsh"
if [ -d "$DSH_HOME/sessions" ]; then
  BACKUP_DIR="$DSH_HOME/sessions-backup-$(date +%Y%m%d-%H%M%S)"
  echo "  备份到: $BACKUP_DIR"
  cp -r "$DSH_HOME/sessions" "$BACKUP_DIR"

  # 只保留最近 3 天的会话
  echo "  删除 3 天前的会话..."
  find "$DSH_HOME/sessions" -type f -mtime +3 -delete 2>/dev/null || true

  SESSION_COUNT=$(find "$DSH_HOME/sessions" -type f 2>/dev/null | wc -l | tr -d ' ')
  echo "  剩余会话文件: $SESSION_COUNT"
fi

# Step 3: 清理 DSH 缓存
echo ""
echo "Step 3: 清理 DSH 缓存..."
if [ -d "$DSH_HOME/.cache" ]; then
  CACHE_SIZE=$(du -sh "$DSH_HOME/.cache" 2>/dev/null | awk '{print $1}')
  echo "  缓存大小: $CACHE_SIZE"
  rm -rf "$DSH_HOME/.cache" 2>/dev/null || true
  echo "  ✓ 缓存已清理"
fi

# Step 4: 验证修复
echo ""
echo "Step 4: 验证配置..."
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if grep -q "DSH_MAX_OLD_SPACE.*16384" "$SCRIPT_DIR/start.sh"; then
  echo "  ✓ start.sh 堆上限已设置为 16GB"
else
  echo "  ✗ 警告: start.sh 配置可能有误"
fi

# Step 5: 重启 agent-dh
echo ""
echo "Step 5: 重启 agent-dh..."
cd "$SCRIPT_DIR"
bash start.sh > /tmp/agent-dh-start.log 2>&1 &
AGENT_PID=$!

echo "  启动进程 PID: $AGENT_PID"
echo "  等待服务启动..."
sleep 5

# Step 6: 验证
echo ""
echo "Step 6: 验证启动状态..."
if ps -p $AGENT_PID > /dev/null 2>&1; then
  echo "  ✓ 进程运行中 (PID: $AGENT_PID)"

  # 检查内存
  RSS=$(ps -o rss= -p $AGENT_PID 2>/dev/null | awk '{printf "%.1f", $1/1024}')
  echo "  当前内存: ${RSS}MB"

  # 检查端口
  sleep 2
  if lsof -i :3080 > /dev/null 2>&1; then
    echo "  ✓ 端口 3080 已监听"
  else
    echo "  ! 端口尚未监听（可能还在初始化）"
  fi

  echo ""
  echo "启动日志:"
  tail -20 /tmp/agent-dh-start.log
else
  echo "  ✗ 进程启动失败"
  echo ""
  echo "错误日志:"
  cat /tmp/agent-dh-start.log
  exit 1
fi

echo ""
echo "========================================"
echo "修复完成！"
echo ""
echo "监控命令:"
echo "  查看进程: ps aux | grep 'dsh.*investment'"
echo "  查看内存: watch 'ps -o pid,rss,vsz,comm -p $AGENT_PID'"
echo "  查看日志: tail -f /tmp/agent-dh-start.log"
echo ""
echo "如果还有问题，检查:"
echo "  1. 内存是否持续增长（应该稳定在 3-4GB 以下）"
echo "  2. 进程是否频繁重启（查看 PID 变化）"
echo "  3. 日志中是否有 OOM 错误"
echo "========================================"
