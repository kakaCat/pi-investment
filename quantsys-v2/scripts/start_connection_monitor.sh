#!/bin/bash
# WP-6 持续监控启动脚本
# 用于监控生产环境连接健康（48小时）

LOG_FILE="$HOME/pi-investment/quantsys-v2/logs/connection_health.log"
SCRIPT_DIR="$HOME/pi-investment/quantsys-v2"

echo "开始启动连接健康监控..."
echo "日志文件: $LOG_FILE"

cd "$SCRIPT_DIR" || exit 1

# 加载环境变量
export $(grep -v '^#' .env | xargs)

# 启动监控（5分钟间隔）
venv/bin/python scripts/verify_connection_health.py --continuous --interval 300 >> "$LOG_FILE" 2>&1 &
PID=$!

echo "监控已启动"
echo "PID: $PID"
echo "查看日志: tail -f $LOG_FILE"
echo "停止监控: kill $PID"
echo ""
echo "监控计划:"
echo "- T+6小时: 第一次检查"
echo "- T+12小时: 第二次检查"
echo "- T+24小时: 日运行验证"
echo "- T+48小时: 最终验证"
