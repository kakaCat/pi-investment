#!/bin/bash
# 模型训练定时任务（系统 cron 调用）
#
# 2026-09-14（REQ-a458a6 t2，w-4db568de）：**本 cron 路径已停用，脚本保留但不训练**。
#
# 停用原因：本路径不进 quant.scheduler_runs、无告警、日志只落 /tmp（系统会清理——实测
# 2026-08-24 / 08-31 的日志已不可得，连它当时"没跑"还是"跑失败"都判不出来），因此有过
# 2026-08-20 → 09-05 停训 16 天无人发现。
# 训练唯一入口 = v2 每日模型重训任务：quant.scheduler_tasks id=320（cron 30 3 * * *，
# Job=ModelTrainDailyJob）。它每次运行都落 scheduler_runs、受 scheduler-watchdog 覆盖、
# 可手动 trigger（POST /api/scheduler/tasks/320/trigger）。
#
# 待人工收尾（agent 无 /var/at/tmp 写权限，改不了 crontab）：
#   crontab -l | grep -v cron_train_model.sh | crontab -
# 需要一次性强制训练：
#   bash quantsys-v2/tools/cron_train_model_force.sh   # 需 CONFIRM_FORCE_TRAIN=1
LOG_FILE="/tmp/model-train-$(date +%Y%m%d).log"

{
  echo "=== 模型训练 cron 入口（已停用） $(date) ==="
  echo "[已停用] REQ-a458a6 t2：训练唯一入口 = v2 quant.scheduler_tasks id=320"
  echo "          本 crontab 行请人工删除：crontab -l | grep -v cron_train_model.sh | crontab -"
} >> "$LOG_FILE"

echo "[已停用] 训练唯一入口 = v2 task 320（每日 03:30，ModelTrainDailyJob）；请删除本 cron 行（详见 $LOG_FILE）"
exit 0
