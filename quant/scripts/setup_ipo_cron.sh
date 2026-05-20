#!/bin/bash
# 设置打新盯盘定时任务 - 每个交易日早上自动检查今日可申购新股

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
QUANT_DIR="$SCRIPT_DIR/.."
LOG_DIR="$QUANT_DIR/logs"
IPO_SCRIPT="$SCRIPT_DIR/ipo_watch_pipeline.py"
AGENT_ENDPOINT="${IPO_AGENT_ENDPOINT:-}"
FEISHU_WEBHOOK="${FEISHU_WEBHOOK_URL:-}"

mkdir -p "$LOG_DIR"

if [ -z "$AGENT_ENDPOINT" ]; then
    echo "缺少 IPO_AGENT_ENDPOINT 环境变量"
    echo "示例："
    echo "  IPO_AGENT_ENDPOINT='http://agent.local/decision' FEISHU_WEBHOOK_URL='https://...' $0"
    exit 1
fi

CRON_MARKER="ipo_watch_pipeline.py"
CRON_JOB="30 8 * * 1-5 cd $QUANT_DIR && FEISHU_WEBHOOK_URL='$FEISHU_WEBHOOK' python $IPO_SCRIPT --agent-endpoint '$AGENT_ENDPOINT' >> $LOG_DIR/ipo_watch.log 2>&1"

echo "="
echo "打新盯盘定时任务设置工具"
echo "="
echo ""
echo "将添加以下定时任务："
echo "  时间: 每周一至周五 08:30"
echo "  脚本: $IPO_SCRIPT"
echo "  Agent: $AGENT_ENDPOINT"
echo "  日志: $LOG_DIR/ipo_watch.log"
echo ""

if crontab -l 2>/dev/null | grep -q "$CRON_MARKER"; then
    echo "打新盯盘定时任务已存在，跳过添加"
    echo ""
    echo "当前任务："
    crontab -l | grep "$CRON_MARKER"
else
    (crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -
    echo "打新盯盘定时任务添加成功"
    echo ""
    echo "当前任务："
    crontab -l | grep "$CRON_MARKER"
fi

echo ""
echo "手动测试："
echo "  cd $QUANT_DIR && python $IPO_SCRIPT --agent-endpoint '$AGENT_ENDPOINT'"
echo ""
echo "查看日志："
echo "  tail -f $LOG_DIR/ipo_watch.log"
