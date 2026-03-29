#!/bin/bash
# Codex 结果处理脚本
# 当检测到新的 Codex 结果时，自动读取并展示

NOTIFICATION_FILE="$1"

if [ -z "$NOTIFICATION_FILE" ]; then
  echo "用法: $0 <notification_file>"
  exit 1
fi

# 提取任务ID
TASK_ID=$(basename "$NOTIFICATION_FILE" .txt)

# 读取结果
RESULT_FILE="bridge/codex/completed/${TASK_ID}.json"

if [ -f "$RESULT_FILE" ]; then
  echo "📬 Codex 任务完成通知"
  echo "任务ID: $TASK_ID"
  echo ""
  cat "$RESULT_FILE"

  # 删除通知文件（避免重复处理）
  rm "$NOTIFICATION_FILE"
else
  echo "⚠️ 结果文件不存在: $RESULT_FILE"
fi
