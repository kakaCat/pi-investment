#!/bin/bash
# Quant 量化系统 - 快速启动指南

echo "=================================="
echo "Quant 量化系统 - 快速启动"
echo "=================================="
echo ""

# 检查当前目录
if [ ! -f "scripts/scheduler.py" ]; then
    echo "❌ 错误: 请在 quant 项目根目录运行此脚本"
    echo "   cd /Users/mac/Documents/ai/pi-investment/quant"
    exit 1
fi

echo "✅ 当前目录正确"
echo ""

# 检查 Python 版本
echo "检查 Python 版本..."
python3 --version
echo ""

# 检查依赖
echo "检查依赖..."
if ! python3 -c "import apscheduler" 2>/dev/null; then
    echo "⚠️  缺少 apscheduler，正在安装..."
    pip install apscheduler
fi

if ! python3 -c "import pandas" 2>/dev/null; then
    echo "⚠️  缺少依赖，正在安装..."
    pip install -r requirements.txt
fi

echo "✅ 依赖检查完成"
echo ""

# 检查数据库
echo "检查数据库..."
if [ ! -f "quantsys/data/stocks.db" ]; then
    echo "❌ 数据库不存在"
    echo ""
    echo "请先运行以下命令获取数据："
    echo "  python3 scripts/fetch_hs300_data.py"
    echo ""
    exit 1
fi

# 统计数据
STOCK_COUNT=$(sqlite3 quantsys/data/stocks.db "SELECT COUNT(DISTINCT symbol) FROM daily_klines;" 2>/dev/null || echo "0")
RECORD_COUNT=$(sqlite3 quantsys/data/stocks.db "SELECT COUNT(*) FROM daily_klines;" 2>/dev/null || echo "0")

echo "✅ 数据库存在"
echo "   股票数: $STOCK_COUNT"
echo "   记录数: $RECORD_COUNT"
echo ""

# 创建日志目录
mkdir -p logs
mkdir -p .pi-invest

echo "=================================="
echo "启动选项"
echo "=================================="
echo ""
echo "1. 测试核心任务（推荐首次运行）"
echo "2. 启动调度器（前台运行）"
echo "3. 启动调度器（后台运行）"
echo "4. 查看调度器状态"
echo "5. 停止调度器"
echo "6. 查看日志"
echo "7. 查看信号"
echo "8. 退出"
echo ""

read -p "请选择 [1-8]: " choice

case $choice in
    1)
        echo ""
        echo "=================================="
        echo "测试核心任务"
        echo "=================================="
        echo ""
        python3 scripts/test_core_tasks.py
        ;;
    2)
        echo ""
        echo "=================================="
        echo "启动调度器（前台运行）"
        echo "=================================="
        echo ""
        echo "按 Ctrl+C 停止"
        echo ""
        python3 scripts/scheduler.py
        ;;
    3)
        echo ""
        echo "=================================="
        echo "启动调度器（后台运行）"
        echo "=================================="
        echo ""
        nohup python3 scripts/scheduler.py > logs/scheduler.log 2>&1 &
        PID=$!
        echo "✅ 调度器已启动"
        echo "   进程ID: $PID"
        echo "   日志文件: logs/scheduler.log"
        echo ""
        echo "查看日志: tail -f logs/scheduler.log"
        echo "停止调度器: kill $PID"
        echo ""
        ;;
    4)
        echo ""
        echo "=================================="
        echo "调度器状态"
        echo "=================================="
        echo ""
        if pgrep -f "scheduler.py" > /dev/null; then
            echo "✅ 调度器正在运行"
            echo ""
            ps aux | grep scheduler.py | grep -v grep
        else
            echo "❌ 调度器未运行"
        fi
        echo ""
        ;;
    5)
        echo ""
        echo "=================================="
        echo "停止调度器"
        echo "=================================="
        echo ""
        if pgrep -f "scheduler.py" > /dev/null; then
            pkill -f scheduler.py
            echo "✅ 调度器已停止"
        else
            echo "⚠️  调度器未运行"
        fi
        echo ""
        ;;
    6)
        echo ""
        echo "=================================="
        echo "查看日志（最近50行）"
        echo "=================================="
        echo ""
        if [ -f "logs/scheduler.log" ]; then
            tail -50 logs/scheduler.log
        else
            echo "⚠️  日志文件不存在"
        fi
        echo ""
        ;;
    7)
        echo ""
        echo "=================================="
        echo "查看最新信号"
        echo "=================================="
        echo ""
        if [ -f ".pi-invest/signals.json" ]; then
            cat .pi-invest/signals.json | jq .
        else
            echo "⚠️  信号文件不存在"
            echo "   请先运行: python3 scripts/generate_signals.py"
        fi
        echo ""
        ;;
    8)
        echo ""
        echo "再见！"
        echo ""
        exit 0
        ;;
    *)
        echo ""
        echo "❌ 无效选择"
        echo ""
        exit 1
        ;;
esac
