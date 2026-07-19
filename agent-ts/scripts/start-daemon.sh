#!/bin/bash
# 启动调度器守护进程并保存日志

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG_DIR="$PROJECT_DIR/.pi-invest/logs"
LOG_FILE="$LOG_DIR/scheduler-daemon.log"

# 创建日志目录
mkdir -p "$LOG_DIR"

# 检查是否已有守护进程在运行
if pgrep -f "start-scheduler-daemon.ts" > /dev/null; then
    echo "⚠️  调度器守护进程已在运行"
    echo "进程列表:"
    ps aux | grep "start-scheduler-daemon" | grep -v grep
    exit 1
fi

# 启动守护进程
echo "🚀 启动调度器守护进程..."
echo "📝 日志文件: $LOG_FILE"

cd "$PROJECT_DIR"
nohup npx tsx scripts/start-scheduler-daemon.ts > "$LOG_FILE" 2>&1 &

PID=$!
echo "✅ 守护进程已启动，PID: $PID"
echo ""
echo "💡 查看日志："
echo "   tail -f $LOG_FILE"
echo ""
echo "🛑 停止守护进程："
echo "   kill $PID"
echo "   或运行: pkill -f 'start-scheduler-daemon.ts'"
