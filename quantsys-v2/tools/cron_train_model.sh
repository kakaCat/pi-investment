#!/bin/bash
# 模型训练定时任务（系统cron调用）
# 每周一凌晨3点执行

LOG_FILE="/tmp/model-train-$(date +%Y%m%d).log"
echo "=== 模型训练开始 $(date) ===" >> "$LOG_FILE"

cd /Users/yunpeng/pi-investment/quantsys-v2
source activate-py313.sh

python3 << 'PYEOF' 2>&1 | tee -a "$LOG_FILE"
from application.services.scheduler_tasks import handle_model_train_auto
import json
from datetime import datetime

print(f"\n[{datetime.now()}] 调用 handle_model_train_auto")

result = handle_model_train_auto({
    "model_type": "lightgbm",
    "symbols_limit": 500,
    "lookback_days": 350,
    "force_train": False,  # 智能判断
    "auto_switch": True,   # 性能提升时自动切换
    "test_size": 0.2,
})

print(f"\n[{datetime.now()}] 训练结果:")
print(json.dumps(result, indent=2, ensure_ascii=False))

if result.get("status") == "success":
    print(f"\n✓ 训练成功: {result.get('version')}")
    print(f"  训练准确率: {result.get('train_accuracy')}")
    print(f"  测试准确率: {result.get('test_accuracy')}")
    print(f"  自动切换: {result.get('auto_switched')}")
elif result.get("status") == "skipped":
    print(f"\n⊙ 跳过训练: {result.get('reason')}")
else:
    print(f"\n✗ 训练失败: {result.get('error')}")
    exit(1)
PYEOF

echo "=== 模型训练结束 $(date) ===" >> "$LOG_FILE"
