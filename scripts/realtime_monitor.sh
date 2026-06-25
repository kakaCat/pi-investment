#!/bin/bash
# 实时监控脚本 - 每5分钟执行

API_BASE="http://localhost:5001"
LOG_FILE="/tmp/quantsys_monitor.log"

# 检查预警（只记录有预警的情况）
ALERTS=$(curl -s "${API_BASE}/api/alerts/check")

# 检查是否有紧急预警
if echo "$ALERTS" | grep -q '"level":"critical"'; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') [CRITICAL] 发现紧急预警！" >> $LOG_FILE
    echo "$ALERTS" >> $LOG_FILE

    # TODO: 发送通知（飞书/邮件）
fi
