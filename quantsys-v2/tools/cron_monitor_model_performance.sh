#!/bin/bash
# 模型性能监控任务（系统cron调用）
# 每天检查模型性能，低于阈值时发送告警

LOG_FILE="/tmp/model-monitor-$(date +%Y%m%d).log"
echo "=== 性能监控开始 $(date) ===" >> "$LOG_FILE"

cd /Users/yunpeng/pi-investment/quantsys-v2
source activate-py313.sh

python3 << 'PYEOF' 2>&1 | tee -a "$LOG_FILE"
from application.services.ml_train_notification import check_model_performance_alert
from datetime import datetime

print(f"\n[{datetime.now()}] 检查模型性能...")

alerted = check_model_performance_alert()

if alerted:
    print("⚠️ 性能告警已发送")
else:
    print("✓ 模型性能正常")
PYEOF

echo "=== 性能监控结束 $(date) ===" >> "$LOG_FILE"
