#!/bin/bash
# 紧急修复脚本：立即执行所有止血措施

set -e

echo "🚨 开始执行紧急修复..."

# 1. 启用数据库超时保护
echo "📋 步骤 1: 启用数据库 idle_in_transaction 超时..."
psql -d quant_investment -c "ALTER DATABASE quant_investment SET idle_in_transaction_session_timeout = '5min';" || echo "⚠️ 数据库超时设置失败（可能权限不足）"

# 2. 杀掉当前挂起的事务
echo "📋 步骤 2: 检查并终止挂起的事务..."
python scripts/fix_idle_transactions.py --check --kill --threshold 60

# 3. 增加连接池容量（需要重启服务）
echo "📋 步骤 3: 检查连接池配置..."
if grep -q "pool_size: 10" infrastructure/config/settings.yaml; then
    echo "⚠️ 检测到连接池偏小 (pool_size=10)，建议增加到 20"
    echo "   修改 infrastructure/config/settings.yaml:"
    echo "   database:"
    echo "     pool_size: 20"
    echo "     max_overflow: 30"
fi

# 4. 重启 FastAPI 服务（应用新的中间件）
echo "📋 步骤 4: 重启 FastAPI 服务..."
echo "   执行命令: launchctl kickstart -k gui/$(id -u)/com.pi-investment.v2-api"
echo "   或手动重启: pkill -f 'fastapi_app/main.py' && python adapters/inbound/fastapi_app/main.py &"

# 5. 启动监控脚本（后台）
echo "📋 步骤 5: 启动事务监控..."
nohup python scripts/fix_idle_transactions.py --monitor --kill --threshold 300 --interval 60 > logs/idle_transaction_monitor.log 2>&1 &
MONITOR_PID=$!
echo "✅ 监控脚本已启动 (PID: $MONITOR_PID)"

echo ""
echo "✅ 紧急修复完成！"
echo ""
echo "📊 验证步骤:"
echo "   1. 检查数据库连接: psql -d quant_investment -c \"SELECT count(*), state FROM pg_stat_activity WHERE datname='quant_investment' GROUP BY state;\""
echo "   2. 查看监控日志: tail -f logs/idle_transaction_monitor.log"
echo "   3. 测试 API: curl http://localhost:5001/api/health"
echo ""
echo "⚠️ 下一步:"
echo "   - 修改 infrastructure/config/settings.yaml 增加连接池"
echo "   - 重启服务以应用新配置"
echo "   - 观察监控日志，确认不再出现 idle in transaction"
