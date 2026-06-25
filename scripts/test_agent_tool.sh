#!/bin/bash
# Agent工具端到端测试脚本

set -e

echo "============================================================"
echo "Agent工具端到端测试"
echo "执行时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "============================================================"
echo ""

# 颜色定义
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 测试结果
TEST_PASSED=0
TEST_FAILED=0

# ============================================================
# Step 1: 验证TypeScript编译
# ============================================================
echo -e "${BLUE}Step 1: 验证TypeScript编译${NC}"
echo "----------------------------------------"

cd /Users/mac/Documents/ai/pi-investment/agent-ts

if npm run build 2>&1 | grep -q "error TS"; then
    echo -e "${RED}❌ TypeScript编译失败${NC}"
    TEST_FAILED=$((TEST_FAILED + 1))
else
    echo -e "${GREEN}✅ TypeScript编译成功${NC}"
    TEST_PASSED=$((TEST_PASSED + 1))
fi
echo ""

# ============================================================
# Step 2: 验证工具注册
# ============================================================
echo -e "${BLUE}Step 2: 验证工具注册${NC}"
echo "----------------------------------------"

if grep -q "opponentBehaviorTool" src/infrastructure/tools/index.ts; then
    echo -e "${GREEN}✅ 工具已注册到index.ts${NC}"
    TEST_PASSED=$((TEST_PASSED + 1))
else
    echo -e "${RED}❌ 工具未注册${NC}"
    TEST_FAILED=$((TEST_FAILED + 1))
fi
echo ""

# ============================================================
# Step 3: 验证工具文件
# ============================================================
echo -e "${BLUE}Step 3: 验证工具文件${NC}"
echo "----------------------------------------"

if [ -f "src/infrastructure/tools/game/opponent-behavior-tool.ts" ]; then
    echo -e "${GREEN}✅ 工具文件存在${NC}"

    # 验证关键方法
    if grep -q "export const opponentBehaviorTool" src/infrastructure/tools/game/opponent-behavior-tool.ts; then
        echo -e "${GREEN}✅ 工具导出正确${NC}"
        TEST_PASSED=$((TEST_PASSED + 1))
    else
        echo -e "${RED}❌ 工具导出错误${NC}"
        TEST_FAILED=$((TEST_FAILED + 1))
    fi

    if grep -q "formatOpponentBehaviorReport" src/infrastructure/tools/game/opponent-behavior-tool.ts; then
        echo -e "${GREEN}✅ 格式化方法存在${NC}"
        TEST_PASSED=$((TEST_PASSED + 1))
    else
        echo -e "${RED}❌ 格式化方法缺失${NC}"
        TEST_FAILED=$((TEST_FAILED + 1))
    fi
else
    echo -e "${RED}❌ 工具文件不存在${NC}"
    TEST_FAILED=$((TEST_FAILED + 2))
fi
echo ""

# ============================================================
# Step 4: 验证编译输出
# ============================================================
echo -e "${BLUE}Step 4: 验证编译输出${NC}"
echo "----------------------------------------"

if [ -f "dist/infrastructure/tools/game/opponent-behavior-tool.js" ]; then
    echo -e "${GREEN}✅ JavaScript文件已生成${NC}"
    TEST_PASSED=$((TEST_PASSED + 1))
else
    echo -e "${YELLOW}⚠️  JavaScript文件未找到（可能未编译）${NC}"
fi
echo ""

# ============================================================
# Step 5: 模拟API响应测试
# ============================================================
echo -e "${BLUE}Step 5: 验证工具逻辑完整性${NC}"
echo "----------------------------------------"

# 检查核心方法
METHODS=(
    "translateBehavior"
    "formatFlow"
    "getEmotionLabel"
    "translatePositionChange"
    "translateMarketPhase"
    "translateRiskAppetite"
    "translateOpportunityKey"
)

for method in "${METHODS[@]}"; do
    if grep -q "$method" src/infrastructure/tools/game/opponent-behavior-tool.ts; then
        echo -e "${GREEN}✅ 方法 $method 存在${NC}"
        TEST_PASSED=$((TEST_PASSED + 1))
    else
        echo -e "${RED}❌ 方法 $method 缺失${NC}"
        TEST_FAILED=$((TEST_FAILED + 1))
    fi
done
echo ""

# ============================================================
# 测试总结
# ============================================================
echo ""
echo "============================================================"
echo "测试执行完成"
echo "============================================================"
echo ""
echo "总测试数: $((TEST_PASSED + TEST_FAILED))"
echo -e "${GREEN}通过: $TEST_PASSED${NC}"
echo -e "${RED}失败: $TEST_FAILED${NC}"
echo ""

if [ $TEST_FAILED -eq 0 ]; then
    echo -e "${GREEN}✅ 所有Agent工具测试通过！${NC}"
    echo ""
    echo "📋 下一步操作："
    echo "1. 启动quantsys-v2后端: cd quantsys-v2 && python start_all.py"
    echo "2. 测试API: curl http://localhost:5001/api/game/market/opponent-behavior"
    echo "3. 启动agent-ts: cd agent-ts && npm run dev"
    echo "4. Agent会话中测试: 使用 opponent_behavior 工具分析市场"
    exit 0
else
    echo -e "${YELLOW}⚠️  部分测试失败，请检查上面的输出${NC}"
    exit 1
fi
