#!/bin/bash
# Agent OS 进程守护 - 自动重启崩溃的进程

AGENT_OS_SCRIPT="/Users/yunpeng/pi-investment/agent-os/agent-os.sh"
CHECK_INTERVAL=30  # 每30秒检查一次

echo "🔒 Agent OS 守护进程启动"
echo "   检查间隔: ${CHECK_INTERVAL}秒"
echo "   按 Ctrl+C 停止守护"
echo ""

# 首次启动
if ! $AGENT_OS_SCRIPT status | grep -q "运行中"; then
    echo "初始启动 Agent OS..."
    $AGENT_OS_SCRIPT start
fi

# 守护循环
while true; do
    sleep $CHECK_INTERVAL
    
    # 检查进程是否运行
    if ! $AGENT_OS_SCRIPT status > /dev/null 2>&1; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] ⚠️  检测到 Agent OS 崩溃，正在重启..."
        $AGENT_OS_SCRIPT start
        
        if [ $? -eq 0 ]; then
            echo "[$(date '+%Y-%m-%d %H:%M:%S')] ✅ Agent OS 重启成功"
        else
            echo "[$(date '+%Y-%m-%d %H:%M:%S')] ❌ Agent OS 重启失败"
        fi
    fi
done
