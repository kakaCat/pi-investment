#!/bin/bash
# 模型强制训练任务（系统 cron 调用）
#
# 2026-09-14（REQ-a458a6 t2，w-4db568de）：**本 cron 路径已停用**（同 cron_train_model.sh）：
# 不进 quant.scheduler_runs、无告警、日志只落 /tmp，且它的产出（2026-09-01 那次）从未被
# 人工审核、也从未落库（DB 里没有该 version 的行），等价白训。
# 训练唯一入口 = v2 quant.scheduler_tasks id=320。
# 本脚本保留**手工强制训练**能力，但必须显式确认（防止 crontab 里的残留行继续偷偷训练）：
#   CONFIRM_FORCE_TRAIN=1 bash tools/cron_train_model_force.sh
# 待人工收尾：crontab -l | grep -v cron_train_model_force.sh | crontab -
LOG_FILE="/tmp/model-train-force-$(date +%Y%m%d).log"

if [ "${CONFIRM_FORCE_TRAIN:-0}" != "1" ]; then
  {
    echo "=== 强制训练入口（已停用） $(date) ==="
    echo "[已停用] REQ-a458a6 t2：需人工显式确认才会执行。"
    echo "          训练唯一入口 = v2 quant.scheduler_tasks id=320"
    echo "          本 crontab 行请人工删除：crontab -l | grep -v cron_train_model_force.sh | crontab -"
  } >> "$LOG_FILE"
  echo "[已停用] 需强制训练请显式确认：CONFIRM_FORCE_TRAIN=1 bash tools/cron_train_model_force.sh"
  exit 0
fi

echo "=== 强制训练开始 $(date) ===" >> "$LOG_FILE"

cd /Users/yunpeng/pi-investment/quantsys-v2
source activate-py313.sh

python3 << 'PYEOF' 2>&1 | tee -a "$LOG_FILE"
from application.services.scheduler_tasks import handle_model_train_auto
import json
from datetime import datetime

print(f"\n[{datetime.now()}] 强制训练模式")

result = handle_model_train_auto({
    "model_type": "lightgbm",
    "symbols_limit": 500,
    "lookback_days": 350,
    "force_train": True,   # 强制训练
    "auto_switch": False,  # 不自动切换，需人工审核
    "test_size": 0.2,
})

print(f"\n[{datetime.now()}] 训练结果:")
print(json.dumps(result, indent=2, ensure_ascii=False))

if result.get("status") == "success":
    print(f"\n✓ 训练成功: {result.get('version')}")
    print(f"  训练准确率: {result.get('train_accuracy')}")
    print(f"  测试准确率: {result.get('test_accuracy')}")
    print(f"  ⚠️ 需人工审核后切换模型")
else:
    print(f"\n✗ 训练失败: {result.get('error')}")
    exit(1)
PYEOF

echo "=== 强制训练结束 $(date) ===" >> "$LOG_FILE"
