#!/bin/bash
# 测试战场评估工具

echo "============================================================"
echo "战场评估工具测试"
echo "执行时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "============================================================"
echo ""

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

TEST_PASSED=0
TEST_FAILED=0

# 测试1: TypeScript编译
echo -e "${BLUE}测试1: TypeScript编译${NC}"
echo "----------------------------------------"
cd agent-ts
if npm run build 2>&1 | grep -q "error TS"; then
    echo -e "${RED}❌ 编译失败${NC}"
    TEST_FAILED=$((TEST_FAILED + 1))
else
    echo -e "${GREEN}✅ 编译成功${NC}"
    TEST_PASSED=$((TEST_PASSED + 1))
fi
echo ""

# 测试2: 工具文件存在
echo -e "${BLUE}测试2: 工具文件验证${NC}"
echo "----------------------------------------"
if [ -f "src/infrastructure/tools/game/pool-battlefield-tool.ts" ]; then
    echo -e "${GREEN}✅ 工具文件存在${NC}"
    TEST_PASSED=$((TEST_PASSED + 1))
else
    echo -e "${RED}❌ 工具文件不存在${NC}"
    TEST_FAILED=$((TEST_FAILED + 1))
fi
echo ""

# 测试3: 工具已注册
echo -e "${BLUE}测试3: 工具注册验证${NC}"
echo "----------------------------------------"
if grep -q "poolBattlefieldTool" src/infrastructure/tools/index.ts; then
    echo -e "${GREEN}✅ 工具已注册${NC}"
    TEST_PASSED=$((TEST_PASSED + 1))
else
    echo -e "${RED}❌ 工具未注册${NC}"
    TEST_FAILED=$((TEST_FAILED + 1))
fi
echo ""

# 测试4: Service文件验证
echo -e "${BLUE}测试4: Service文件验证${NC}"
echo "----------------------------------------"
cd ../quantsys-v2
if [ -f "application/services/battlefield_assessor.py" ]; then
    echo -e "${GREEN}✅ Service文件存在${NC}"
    TEST_PASSED=$((TEST_PASSED + 1))
    
    # 验证核心方法
    if grep -q "def assess_pool" application/services/battlefield_assessor.py; then
        echo -e "${GREEN}✅ 核心方法存在${NC}"
        TEST_PASSED=$((TEST_PASSED + 1))
    else
        echo -e "${RED}❌ 核心方法缺失${NC}"
        TEST_FAILED=$((TEST_FAILED + 1))
    fi
else
    echo -e "${RED}❌ Service文件不存在${NC}"
    TEST_FAILED=$((TEST_FAILED + 2))
fi
echo ""

# 测试5: API端点验证
echo -e "${BLUE}测试5: API端点验证${NC}"
echo "----------------------------------------"
if grep -q "battlefield-assessment" adapters/inbound/api/routes/game_intelligence.py; then
    echo -e "${GREEN}✅ API端点已添加${NC}"
    TEST_PASSED=$((TEST_PASSED + 1))
else
    echo -e "${RED}❌ API端点缺失${NC}"
    TEST_FAILED=$((TEST_FAILED + 1))
fi
echo ""

# 测试总结
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
    echo -e "${GREEN}✅ 所有测试通过！${NC}"
    echo ""
    echo "📋 战场评估功能已就绪："
    echo "- BattlefieldAssessor Service ✅"
    echo "- API: GET /api/game/pools/{id}/battlefield-assessment ✅"
    echo "- Agent工具: pool_battlefield ✅"
    echo ""
    echo "下一步："
    echo "1. 启动后端测试API"
    echo "2. Agent调用工具测试"
    exit 0
else
    echo -e "${YELLOW}⚠️  部分测试失败${NC}"
    exit 1
fi
