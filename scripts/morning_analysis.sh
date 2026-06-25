#!/bin/bash
# 系统Cron方案 - Shell脚本示例

API_BASE="http://localhost:5001"
LOG_FILE="/tmp/quantsys_morning.log"

echo "========================================" >> $LOG_FILE
echo "$(date '+%Y-%m-%d %H:%M:%S') [INFO] 开始早盘分析" >> $LOG_FILE
echo "========================================" >> $LOG_FILE

# 1. 分析对手行为
echo "$(date '+%Y-%m-%d %H:%M:%S') [INFO] 分析对手行为..." >> $LOG_FILE
curl -s "${API_BASE}/api/game/market/opponent-behavior" >> $LOG_FILE 2>&1

# 2. 检查预警
echo "$(date '+%Y-%m-%d %H:%M:%S') [INFO] 检查博弈预警..." >> $LOG_FILE
curl -s "${API_BASE}/api/alerts/check" >> $LOG_FILE 2>&1

# 3. 评估所有池子（假设有3个池子）
for pool_id in 1 2 3; do
    echo "$(date '+%Y-%m-%d %H:%M:%S') [INFO] 评估池子#${pool_id}..." >> $LOG_FILE
    curl -s "${API_BASE}/api/game/pools/${pool_id}/battlefield-assessment" >> $LOG_FILE 2>&1
done

echo "$(date '+%Y-%m-%d %H:%M:%S') [INFO] 早盘分析完成" >> $LOG_FILE
echo "" >> $LOG_FILE
