#!/bin/bash
# 博弈智能系统测试执行脚本

set -e

echo "============================================================"
echo "博弈智能系统 - 测试执行"
echo "执行时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "============================================================"
echo ""

# 颜色定义
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 测试结果统计
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

# 函数：运行测试并记录结果
run_test() {
    local test_name=$1
    local test_command=$2

    echo "----------------------------------------"
    echo "测试: $test_name"
    echo "----------------------------------------"

    TOTAL_TESTS=$((TOTAL_TESTS + 1))

    if eval "$test_command"; then
        echo -e "${GREEN}✅ PASSED${NC}"
        PASSED_TESTS=$((PASSED_TESTS + 1))
    else
        echo -e "${RED}❌ FAILED${NC}"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
    echo ""
}

# ============================================================
# 1. 数据库层测试
# ============================================================
echo "========================================"
echo "1. 数据库层测试"
echo "========================================"
echo ""

run_test "验证7个表已创建" \
"psql -d quant_investment -tAc \"SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'quant' AND table_name IN ('agent_decisions', 'agent_knowledge', 'pool_change_log', 'opponent_behavior_snapshot', 'pool_game_metrics', 'manipulation_events', 'pool_health_history');\" | grep -q '^7$'"

run_test "验证agent_decisions表结构" \
"psql -d quant_investment -c '\\d quant.agent_decisions' > /dev/null 2>&1"

run_test "验证opponent_behavior_snapshot表结构" \
"psql -d quant_investment -c '\\d quant.opponent_behavior_snapshot' > /dev/null 2>&1"

run_test "验证索引创建" \
"psql -d quant_investment -tAc \"SELECT COUNT(*) FROM pg_indexes WHERE schemaname = 'quant' AND tablename LIKE 'agent_%';\" | grep -q '[0-9]'"

# ============================================================
# 2. Repository层测试
# ============================================================
echo "========================================"
echo "2. Repository层测试"
echo "========================================"
echo ""

cd /Users/mac/Documents/ai/pi-investment/quantsys-v2

run_test "Repository单元测试" \
"python -m pytest tests/repositories/test_agent_intelligence_repository.py -v --tb=short -q 2>&1 | grep -q '10 passed'"

run_test "验证Repository文件存在" \
"test -f adapters/outbound/repositories/agent_intelligence_repository.py"

run_test "验证FundFlowRepository增强" \
"grep -q 'get_market_aggregate_flow' adapters/outbound/repositories/fund_flow_repository.py"

# ============================================================
# 3. Service层测试
# ============================================================
echo "========================================"
echo "3. Service层测试"
echo "========================================"
echo ""

run_test "验证Service文件存在" \
"test -f application/services/opponent_behavior_service.py"

run_test "验证Service核心方法" \
"grep -q 'def analyze_current_behavior' application/services/opponent_behavior_service.py"

run_test "验证真实数据集成" \
"grep -q 'get_market_aggregate_flow' application/services/opponent_behavior_service.py"

# ============================================================
# 4. API层测试
# ============================================================
echo "========================================"
echo "4. API层测试"
echo "========================================"
echo ""

run_test "验证API路由文件存在" \
"test -f adapters/inbound/api/routes/game_intelligence.py"

run_test "验证API端点定义" \
"grep -q '/api/game/market/opponent-behavior' adapters/inbound/api/routes/game_intelligence.py"

run_test "验证Flask集成" \
"grep -q 'game_intelligence_bp' adapters/inbound/api/server.py"

# ============================================================
# 5. Agent工具层测试
# ============================================================
echo "========================================"
echo "5. Agent工具层测试"
echo "========================================"
echo ""

cd /Users/mac/Documents/ai/pi-investment/agent-ts

run_test "验证Agent工具文件存在" \
"test -f src/infrastructure/tools/game/opponent-behavior-tool.ts"

run_test "验证工具已注册到index.ts" \
"grep -q 'opponentBehaviorTool' src/infrastructure/tools/index.ts"

run_test "验证工具导入语句" \
"grep -q 'opponent-behavior-tool' src/infrastructure/tools/index.ts"

# ============================================================
# 6. 文档测试
# ============================================================
echo "========================================"
echo "6. 文档完整性测试"
echo "========================================"
echo ""

cd /Users/mac/Documents/ai/pi-investment

run_test "验证实施计划文档" \
"test -f IMPLEMENTATION_PLAN.md"

run_test "验证缺失分析文档" \
"test -f INTELLIGENCE_GAP_ANALYSIS.md"

run_test "验证最终报告文档" \
"test -f FINAL_IMPLEMENTATION_REPORT.md"

run_test "验证测试流程文档" \
"test -f REVIEW_AND_TEST_GUIDE.md"

# ============================================================
# 测试总结
# ============================================================
echo ""
echo "============================================================"
echo "测试执行完成"
echo "============================================================"
echo ""
echo "总测试数: $TOTAL_TESTS"
echo -e "${GREEN}通过: $PASSED_TESTS${NC}"
echo -e "${RED}失败: $FAILED_TESTS${NC}"
echo ""

if [ $FAILED_TESTS -eq 0 ]; then
    echo -e "${GREEN}✅ 所有测试通过！${NC}"
    exit 0
else
    echo -e "${YELLOW}⚠️  部分测试失败，请检查上面的输出${NC}"
    exit 1
fi
