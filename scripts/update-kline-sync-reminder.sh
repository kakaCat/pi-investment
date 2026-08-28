#!/bin/bash
# 更新 K线同步 reminder
# 用途：将旧的文字描述 reminder 改为调用 kline_daily_sync 工具

set -e

echo "=========================================="
echo "更新 K线同步 Reminder"
echo "=========================================="

# 检查 Agent OS 是否在线
echo "检查 Agent OS 状态..."
if ! curl -s http://localhost:8080/api/health > /dev/null 2>&1; then
    echo "❌ Agent OS 不在线 (http://localhost:8080)"
    echo "请先启动 Agent OS：cd agent-os && ./agent-os"
    exit 1
fi
echo "✓ Agent OS 在线"

# 查看当前 reminders
echo ""
echo "当前 reminders:"
curl -s http://localhost:8080/api/reminders | jq '.reminders[] | {id, name, cron, enabled}' || true

echo ""
echo "----------------------------------------"
echo "准备更新 reminder..."
echo "旧 ID: 5a0b9df8 (文字描述)"
echo "新 prompt: 直接调用 kline_daily_sync 工具"
echo "----------------------------------------"

# 删除旧 reminder（如果存在）
echo ""
echo "1. 删除旧 reminder (5a0b9df8)..."
curl -s -X DELETE http://localhost:8080/api/reminders/5a0b9df8 && echo "✓ 已删除" || echo "⚠️ 未找到或已删除"

# 创建新 reminder
echo ""
echo "2. 创建新 reminder..."

NEW_PROMPT=$(cat << 'EOF'
执行每日K线同步任务：

1. 调用 kline_daily_sync 工具同步昨日数据
2. 检查结果：
   - success=true 且 success_count ≥ 4000：记录成功日志
   - success=false 或 success_count < 4000：飞书高优告警
     • 标题：【K线同步失败】{sync_date}
     • 内容：成功 {success_count}/{total_stocks}，失败 {failed_count}，耗时 {elapsed_time}s
     • 失败股票（前10）：{failed_symbols}
3. 将结果写入 memory_write：
   - namespace: 'operation'
   - tags: ['data-sync', 'kline', sync_date]
   - content: 包含完整同步结果的 JSON
   - importance: 成功 0.3，失败 0.8
EOF
)

curl -s -X POST http://localhost:8080/api/reminders \
  -H "Content-Type: application/json" \
  -d @- << EOF
{
  "name": "daily-kline-sync",
  "cron": "0 21 * * 1-5",
  "window": "w-6807aa37",
  "prompt": $(echo "$NEW_PROMPT" | jq -Rs .)
}
EOF

echo ""
echo "✓ 新 reminder 已创建"

# 验证结果
echo ""
echo "3. 验证新 reminder..."
NEW_ID=$(curl -s http://localhost:8080/api/reminders | jq -r '.reminders[] | select(.name == "daily-kline-sync") | .id')

if [ -n "$NEW_ID" ]; then
    echo "✓ 新 reminder ID: $NEW_ID"
    echo ""
    curl -s http://localhost:8080/api/reminders | jq ".reminders[] | select(.id == \"$NEW_ID\")"
else
    echo "❌ 未找到新 reminder"
    exit 1
fi

echo ""
echo "=========================================="
echo "✅ Reminder 更新完成"
echo "=========================================="
echo "下次触发时间: 今晚 21:00（工作日）"
echo "手动测试命令: 在 DSH 会话中执行"
echo "  kline_daily_sync({ date: '2026-08-28' })"
echo "=========================================="
