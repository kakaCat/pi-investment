#!/bin/bash
# 系统健康检查脚本

set -e

echo "🔍 QuantSys-V2 系统健康检查"
echo "======================================"
echo ""

# 1. 检查进程状态
echo "📋 1. 进程状态"
if pgrep -f "fastapi_app/main.py" > /dev/null; then
    PID=$(pgrep -f "fastapi_app/main.py")
    echo "   ✅ FastAPI 服务运行中 (PID: $PID)"
else
    echo "   ❌ FastAPI 服务未运行"
fi
echo ""

# 2. 检查端口监听
echo "📋 2. 端口监听"
if lsof -i :5001 > /dev/null 2>&1; then
    echo "   ✅ 端口 5001 正在监听"
else
    echo "   ❌ 端口 5001 未监听"
fi
echo ""

# 3. 检查数据库连接
echo "📋 3. 数据库连接状态"
psql -d quant_investment -c "
SELECT
    state,
    count(*) as count,
    max(EXTRACT(EPOCH FROM (now() - state_change))::int) as max_idle_seconds
FROM pg_stat_activity
WHERE datname='quant_investment'
GROUP BY state
ORDER BY count DESC;
" 2>/dev/null || echo "   ❌ 无法连接数据库"
echo ""

# 4. 检查 idle in transaction
echo "📋 4. 检查挂起事务 (idle in transaction)"
IDLE_COUNT=$(psql -d quant_investment -t -c "SELECT count(*) FROM pg_stat_activity WHERE state = 'idle in transaction' AND datname='quant_investment' AND EXTRACT(EPOCH FROM (now() - state_change)) > 60;" 2>/dev/null || echo "0")
if [ "$IDLE_COUNT" -gt 0 ]; then
    echo "   ⚠️ 发现 $IDLE_COUNT 个超过 60 秒的挂起事务"
    psql -d quant_investment -c "
    SELECT
        pid,
        EXTRACT(EPOCH FROM (now() - state_change))::int as idle_seconds,
        left(query, 80) as query
    FROM pg_stat_activity
    WHERE state = 'idle in transaction'
      AND datname='quant_investment'
      AND EXTRACT(EPOCH FROM (now() - state_change)) > 60;
    " 2>/dev/null
else
    echo "   ✅ 没有长时间挂起的事务"
fi
echo ""

# 5. 检查连接池使用情况
echo "📋 5. 连接池使用情况"
TOTAL_CONN=$(psql -d quant_investment -t -c "SELECT count(*) FROM pg_stat_activity WHERE datname='quant_investment';" 2>/dev/null || echo "0")
echo "   当前连接数: $TOTAL_CONN / 50 (pool_size=20 + max_overflow=30)"
if [ "$TOTAL_CONN" -gt 40 ]; then
    echo "   ⚠️ 连接数过高，可能即将耗尽"
else
    echo "   ✅ 连接池健康"
fi
echo ""

# 6. 测试 API 响应
echo "📋 6. API 响应测试"
if curl -s -o /dev/null -w "%{http_code}" http://localhost:5001/api/health --max-time 5 | grep -q "200"; then
    echo "   ✅ API 响应正常"
else
    echo "   ❌ API 无响应或超时"
fi
echo ""

# 7. 检查日志中的错误
echo "📋 7. 最近日志错误 (最近 50 行)"
if [ -f ~/v2-api.log ]; then
    ERROR_COUNT=$(tail -50 ~/v2-api.log | grep -c "error\|ERROR\|exception" || echo "0")
    if [ "$ERROR_COUNT" -gt 0 ]; then
        echo "   ⚠️ 发现 $ERROR_COUNT 条错误日志"
        tail -50 ~/v2-api.log | grep "error\|ERROR\|exception" | tail -5
    else
        echo "   ✅ 无明显错误"
    fi
else
    echo "   ⚠️ 日志文件不存在"
fi
echo ""

echo "======================================"
echo "✅ 健康检查完成"
