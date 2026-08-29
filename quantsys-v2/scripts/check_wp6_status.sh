#!/bin/bash
# WP-6 监控检查提醒
# 在 T+6h/12h/24h/48h 时运行此脚本

SCRIPT_DIR="$HOME/pi-investment/quantsys-v2"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  WP-6 定期健康检查"
echo "  时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

cd "$SCRIPT_DIR" || exit 1

# 加载环境变量
export $(grep -v '^#' .env | xargs)

echo ""
echo "1️⃣  执行连接健康检查..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
venv/bin/python scripts/verify_connection_health.py

echo ""
echo "2️⃣  查看最近监控日志（最后 30 次检查）..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [ -f logs/connection_health.log ]; then
    tail -50 logs/connection_health.log | grep -E "检查|idle in transaction:|总连接数:|✅|❌" | tail -30
else
    echo "⚠️  监控日志文件不存在"
fi

echo ""
echo "3️⃣  测试关键 API 端点..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "健康检查:"
curl -s http://127.0.0.1:5001/api/health/db | head -3

echo -e "\n股票池数量:"
curl -s http://127.0.0.1:5001/api/pools | grep -o '"id":[0-9]*' | wc -l | xargs echo "股票池总数:"

echo ""
echo "4️⃣  监控进程状态..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if ps aux | grep verify_connection_health | grep -v grep > /dev/null; then
    echo "✅ 监控进程运行中"
    ps aux | grep verify_connection_health | grep -v grep
else
    echo "❌ 监控进程已停止！需要重启！"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  检查完成"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
