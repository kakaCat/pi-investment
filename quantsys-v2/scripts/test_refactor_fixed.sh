#!/bin/bash
# 重构完整测试脚本（修复版）
# 使用虚拟环境

cd /Users/mac/Documents/ai/pi-investment/quantsys-v2
source venv/bin/activate

echo "=============================================="
echo "V13/V14 重构完整测试"
echo "时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "Python: $(which python)"
echo "=============================================="
echo ""

PASS_COUNT=0
FAIL_COUNT=0
TEST_COUNT=0

# 测试函数
test_api() {
    TEST_COUNT=$((TEST_COUNT + 1))
    local name=$1
    local url=$2
    local expected_key=$3

    echo -n "[$TEST_COUNT] $name ... "
    result=$(curl -s "$url")

    if echo "$result" | jq -e ".$expected_key" > /dev/null 2>&1; then
        echo "✅ PASS"
        PASS_COUNT=$((PASS_COUNT + 1))
        return 0
    else
        echo "❌ FAIL"
        FAIL_COUNT=$((FAIL_COUNT + 1))
        return 1
    fi
}

# ========== Flask 统一 API 测试 ==========
echo "📋 Part 1: Flask 统一 API 测试"
echo "----------------------------------------------"

test_api "列出所有策略" \
    "http://localhost:5001/api/strategy/list" \
    "data.strategies"

test_api "V13 账户信息" \
    "http://localhost:5001/api/strategy/v13/account-info" \
    "data.total_value"

test_api "V14 账户信息" \
    "http://localhost:5001/api/strategy/v14/account-info" \
    "data.total_value"

test_api "V13 持仓明细" \
    "http://localhost:5001/api/strategy/v13/positions" \
    "data"

test_api "V14 持仓明细" \
    "http://localhost:5001/api/strategy/v14/positions" \
    "data"

echo ""

# ========== 向后兼容测试 ==========
echo "📋 Part 2: 向后兼容测试"
echo "----------------------------------------------"

test_api "V14 旧接口 - 账户信息" \
    "http://localhost:5001/api/v14/account-info" \
    "success"

test_api "V14 旧接口 - 持仓" \
    "http://localhost:5001/api/v14/positions" \
    "success"

echo ""

# ========== 数据一致性测试 ==========
echo "📋 Part 3: 数据一致性测试"
echo "----------------------------------------------"

echo -n "[$((TEST_COUNT + 1))] V14 新旧接口数据一致性 ... "
TEST_COUNT=$((TEST_COUNT + 1))

old_total=$(curl -s "http://localhost:5001/api/v14/account-info" | jq -r '.data.total_value // .totalValue // empty' 2>/dev/null)
new_total=$(curl -s "http://localhost:5001/api/strategy/v14/account-info" | jq -r '.data.total_value' 2>/dev/null)

if [ -n "$old_total" ] && [ -n "$new_total" ]; then
    diff=$(echo "$old_total - $new_total" | bc -l 2>/dev/null | awk '{print ($1<0)?-$1:$1}')
    if (( $(echo "$diff < 0.01" | bc -l) )); then
        echo "✅ PASS (旧=$old_total, 新=$new_total)"
        PASS_COUNT=$((PASS_COUNT + 1))
    else
        echo "❌ FAIL (差异=$diff)"
        FAIL_COUNT=$((FAIL_COUNT + 1))
    fi
else
    echo "⚠️  WARNING (无法获取数据)"
fi

echo ""

# ========== 配置文件测试 ==========
echo "📋 Part 4: 配置文件测试"
echo "----------------------------------------------"

echo -n "[$((TEST_COUNT + 1))] V13 配置文件存在 ... "
TEST_COUNT=$((TEST_COUNT + 1))
if [ -f "live_trading/configs/strategies/v13.yaml" ]; then
    echo "✅ PASS"
    PASS_COUNT=$((PASS_COUNT + 1))
else
    echo "❌ FAIL"
    FAIL_COUNT=$((FAIL_COUNT + 1))
fi

echo -n "[$((TEST_COUNT + 1))] V14 配置文件存在 ... "
TEST_COUNT=$((TEST_COUNT + 1))
if [ -f "live_trading/configs/strategies/v14.yaml" ]; then
    echo "✅ PASS"
    PASS_COUNT=$((PASS_COUNT + 1))
else
    echo "❌ FAIL"
    FAIL_COUNT=$((FAIL_COUNT + 1))
fi

echo -n "[$((TEST_COUNT + 1))] V13 配置格式正确 ... "
TEST_COUNT=$((TEST_COUNT + 1))
if python -c "import yaml; yaml.safe_load(open('live_trading/configs/strategies/v13.yaml'))" 2>/dev/null; then
    echo "✅ PASS"
    PASS_COUNT=$((PASS_COUNT + 1))
else
    echo "❌ FAIL"
    FAIL_COUNT=$((FAIL_COUNT + 1))
fi

echo -n "[$((TEST_COUNT + 1))] V14 配置格式正确 ... "
TEST_COUNT=$((TEST_COUNT + 1))
if python -c "import yaml; yaml.safe_load(open('live_trading/configs/strategies/v14.yaml'))" 2>/dev/null; then
    echo "✅ PASS"
    PASS_COUNT=$((PASS_COUNT + 1))
else
    echo "❌ FAIL"
    FAIL_COUNT=$((FAIL_COUNT + 1))
fi

echo ""

# ========== Python 服务层测试 ==========
echo "📋 Part 5: Python 服务层测试"
echo "----------------------------------------------"

echo -n "[$((TEST_COUNT + 1))] StrategyService 导入 ... "
TEST_COUNT=$((TEST_COUNT + 1))
if python -c "from application.services.strategy_service import StrategyService" 2>/dev/null; then
    echo "✅ PASS"
    PASS_COUNT=$((PASS_COUNT + 1))
else
    echo "❌ FAIL"
    FAIL_COUNT=$((FAIL_COUNT + 1))
fi

echo -n "[$((TEST_COUNT + 1))] StrategyService.list_strategies() ... "
TEST_COUNT=$((TEST_COUNT + 1))
result=$(python -c "from application.services.strategy_service import StrategyService; s = StrategyService(); print(','.join(s.list_strategies()))" 2>/dev/null)
if [ "$result" = "v13,v14" ]; then
    echo "✅ PASS"
    PASS_COUNT=$((PASS_COUNT + 1))
else
    echo "❌ FAIL (结果: $result)"
    FAIL_COUNT=$((FAIL_COUNT + 1))
fi

echo ""

# ========== 代码质量检查 ==========
echo "📋 Part 6: 代码质量检查"
echo "----------------------------------------------"

echo -n "[$((TEST_COUNT + 1))] strategy_service.py 语法 ... "
TEST_COUNT=$((TEST_COUNT + 1))
if python -m py_compile application/services/strategy_service.py 2>/dev/null; then
    echo "✅ PASS"
    PASS_COUNT=$((PASS_COUNT + 1))
else
    echo "❌ FAIL"
    FAIL_COUNT=$((FAIL_COUNT + 1))
fi

echo -n "[$((TEST_COUNT + 1))] strategy_trading.py 语法 ... "
TEST_COUNT=$((TEST_COUNT + 1))
if python -m py_compile adapters/inbound/api/routes/strategy_trading.py 2>/dev/null; then
    echo "✅ PASS"
    PASS_COUNT=$((PASS_COUNT + 1))
else
    echo "❌ FAIL"
    FAIL_COUNT=$((FAIL_COUNT + 1))
fi

echo -n "[$((TEST_COUNT + 1))] strategy_trading_async.py 语法 ... "
TEST_COUNT=$((TEST_COUNT + 1))
if python -m py_compile adapters/inbound/fastapi_app/routes/strategy_trading_async.py 2>/dev/null; then
    echo "✅ PASS"
    PASS_COUNT=$((PASS_COUNT + 1))
else
    echo "❌ FAIL"
    FAIL_COUNT=$((FAIL_COUNT + 1))
fi

echo -n "[$((TEST_COUNT + 1))] strategy_trading_job.py 语法 ... "
TEST_COUNT=$((TEST_COUNT + 1))
if python -m py_compile infrastructure/jobs/strategy_trading_job.py 2>/dev/null; then
    echo "✅ PASS"
    PASS_COUNT=$((PASS_COUNT + 1))
else
    echo "❌ FAIL"
    FAIL_COUNT=$((FAIL_COUNT + 1))
fi

echo ""

# ========== 测试总结 ==========
echo "=============================================="
echo "测试完成"
echo "=============================================="
echo "总测试数: $TEST_COUNT"
echo "✅ 通过: $PASS_COUNT"
echo "❌ 失败: $FAIL_COUNT"
echo ""

if [ $FAIL_COUNT -eq 0 ]; then
    echo "🎉 所有测试通过！"
    exit 0
else
    echo "⚠️  有 $FAIL_COUNT 个测试失败"
    exit 1
fi
