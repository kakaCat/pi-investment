#!/bin/bash
# 设置定时任务 - 每天18:00自动更新数据

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
DAILY_UPDATE_SCRIPT="$SCRIPT_DIR/daily_update.py"
LOG_DIR="$SCRIPT_DIR/../logs"

# 创建日志目录
mkdir -p "$LOG_DIR"

# 定时任务配置
CRON_JOB="0 18 * * 1-5 cd $SCRIPT_DIR/.. && /usr/bin/env python3 $DAILY_UPDATE_SCRIPT >> $LOG_DIR/daily_update.log 2>&1"

echo "="
echo "定时任务设置工具"
echo "="
echo ""
echo "将添加以下定时任务："
echo "  时间: 每周一至周五 18:00"
echo "  脚本: $DAILY_UPDATE_SCRIPT"
echo "  日志: $LOG_DIR/daily_update.log"
echo ""

# 检查是否已存在相同的定时任务
if crontab -l 2>/dev/null | grep -q "$DAILY_UPDATE_SCRIPT"; then
    echo "⚠️  定时任务已存在，跳过添加"
    echo ""
    echo "当前定时任务："
    crontab -l | grep "$DAILY_UPDATE_SCRIPT"
else
    # 添加定时任务
    (crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -
    echo "✅ 定时任务添加成功！"
    echo ""
    echo "当前定时任务："
    crontab -l | grep "$DAILY_UPDATE_SCRIPT"
fi

echo ""
echo "="
echo "使用说明"
echo "="
echo ""
echo "1. 查看定时任务："
echo "   crontab -l"
echo ""
echo "2. 编辑定时任务："
echo "   crontab -e"
echo ""
echo "3. 删除定时任务："
echo "   crontab -l | grep -v 'daily_update.py' | crontab -"
echo ""
echo "4. 查看执行日志："
echo "   tail -f $LOG_DIR/daily_update.log"
echo ""
echo "5. 手动运行更新："
echo "   python3 $DAILY_UPDATE_SCRIPT"
echo ""
