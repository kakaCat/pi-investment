#!/bin/bash
# 验证连接池是否正常工作
# 测试场景：发送并发请求，检查连接数是否控制在 DB_POOL_MAX 以内

set -e

echo "=== 连接池验证测试 ==="
echo "测试时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

# 检查服务是否启动
if ! curl -s http://127.0.0.1:5001/api/health > /dev/null; then
    echo "❌ 错误: quantsys-v2 服务未启动"
    echo "请先运行: cd quantsys-v2 && python api/server.py"
    exit 1
fi

echo "✅ 服务已启动"
echo ""

# 1. 记录初始连接数
echo "📊 步骤 1: 记录初始连接数"
INITIAL_CONN=$(psql -h 127.0.0.1 -U mac -d quant_investment -t -c "SELECT count(*) FROM pg_stat_activity WHERE datname = 'quant_investment';" | xargs)
INITIAL_IDLE=$(psql -h 127.0.0.1 -U mac -d quant_investment -t -c "SELECT count(*) FROM pg_stat_activity WHERE datname = 'quant_investment' AND state = 'idle';" | xargs)
echo "初始连接数: $INITIAL_CONN (空闲: $INITIAL_IDLE)"
echo ""

# 2. 发送并发请求
echo "📊 步骤 2: 发送 50 个并发请求"
echo "请求 URL: http://127.0.0.1:5001/api/health"
for i in {1..50}; do
    curl -s http://127.0.0.1:5001/api/health > /dev/null &
done

echo "等待请求完成..."
wait
echo "✅ 请求完成"
echo ""

# 3. 检查峰值连接数
echo "📊 步骤 3: 检查峰值连接数"
sleep 2  # 等待连接稳定
PEAK_CONN=$(psql -h 127.0.0.1 -U mac -d quant_investment -t -c "SELECT count(*) FROM pg_stat_activity WHERE datname = 'quant_investment';" | xargs)
PEAK_IDLE=$(psql -h 127.0.0.1 -U mac -d quant_investment -t -c "SELECT count(*) FROM pg_stat_activity WHERE datname = 'quant_investment' AND state = 'idle';" | xargs)
echo "峰值连接数: $PEAK_CONN (空闲: $PEAK_IDLE)"
echo ""

# 4. 等待连接回收
echo "📊 步骤 4: 等待连接回收 (10秒)"
sleep 10
FINAL_CONN=$(psql -h 127.0.0.1 -U mac -d quant_investment -t -c "SELECT count(*) FROM pg_stat_activity WHERE datname = 'quant_investment';" | xargs)
FINAL_IDLE=$(psql -h 127.0.0.1 -U mac -d quant_investment -t -c "SELECT count(*) FROM pg_stat_activity WHERE datname = 'quant_investment' AND state = 'idle';" | xargs)
echo "最终连接数: $FINAL_CONN (空闲: $FINAL_IDLE)"
echo ""

# 5. 验证结果
echo "=== 验证结果 ==="
DB_POOL_MAX=${DB_POOL_MAX:-20}
DB_POOL_MIN=${DB_POOL_MIN:-5}

PASS=0

# 验证 1: 峰值连接数应 ≤ DB_POOL_MAX
if [ "$PEAK_CONN" -le "$DB_POOL_MAX" ]; then
    echo "✅ 测试通过: 峰值连接数 ($PEAK_CONN) ≤ DB_POOL_MAX ($DB_POOL_MAX)"
    ((PASS++))
else
    echo "❌ 测试失败: 峰值连接数 ($PEAK_CONN) > DB_POOL_MAX ($DB_POOL_MAX)"
fi

# 验证 2: 最终连接数应回落到 DB_POOL_MIN 附近（允许误差±2）
if [ "$FINAL_CONN" -le $((DB_POOL_MIN + 2)) ] && [ "$FINAL_CONN" -ge $((DB_POOL_MIN - 2)) ]; then
    echo "✅ 测试通过: 最终连接数 ($FINAL_CONN) 回落到 DB_POOL_MIN ($DB_POOL_MIN) 附近"
    ((PASS++))
else
    echo "⚠️  警告: 最终连接数 ($FINAL_CONN) 偏离 DB_POOL_MIN ($DB_POOL_MIN)"
fi

# 验证 3: 不应有连接泄漏（最终连接数应接近初始连接数）
LEAK=$((FINAL_CONN - INITIAL_CONN))
if [ "$LEAK" -le 2 ]; then
    echo "✅ 测试通过: 无明显连接泄漏 (增量: $LEAK)"
    ((PASS++))
else
    echo "❌ 测试失败: 检测到连接泄漏 (增量: $LEAK)"
fi

echo ""
echo "=== 总结 ==="
echo "通过测试: $PASS / 3"

if [ "$PASS" -eq 3 ]; then
    echo "🎉 连接池工作正常！"
    exit 0
else
    echo "⚠️  连接池可能存在问题，请检查配置"
    exit 1
fi
