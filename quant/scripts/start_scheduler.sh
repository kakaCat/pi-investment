#!/bin/bash
# 快速启动量化系统定时任务调度器

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=================================="
echo "量化系统定时任务调度器"
echo "=================================="
echo ""

# 检查依赖
echo "检查依赖..."
if ! python3 -c "import apscheduler" 2>/dev/null; then
    echo "⚠️  未安装 apscheduler，正在安装..."
    pip install apscheduler
fi

echo "✅ 依赖检查完成"
echo ""

# 创建日志目录
mkdir -p "$PROJECT_DIR/logs"

# 启动调度器
echo "启动调度器..."
echo "日志文件: $PROJECT_DIR/logs/scheduler.log"
echo ""
echo "按 Ctrl+C 停止调度器"
echo ""

cd "$PROJECT_DIR"
python3 "$SCRIPT_DIR/scheduler.py"
