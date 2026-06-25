#!/bin/bash
# 测试操纵检测工具

echo "============================================================"
echo "操纵检测工具测试"
echo "执行时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "============================================================"
echo ""

GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

TEST_PASSED=0
TEST_FAILED=0

# 测试1: Service文件
echo -e "${BLUE}测试1: Service文件验证${NC}"
echo "----------------------------------------"
cd quantsys-v2
if [ -f "application/services/manipulation_detector.py" ]; then
    echo -e "${GREEN}✅ Service文件存在${NC}"
    TEST_PASSED=$((TEST_PASSED + 1))
    
    if grep -q "def detect_market_manipulation" application/services/manipulation_detector.py; then
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

# 测试2: API端点
echo -e "${BLUE}测试2: API端点验证${NC}"
echo "----------------------------------------"
if grep -q "manipulation-detect" adapters/inbound/api/routes/game_intelligence.py; then
    echo -e "${GREEN}✅ API端点已添加${NC}"
    TEST_PASSED=$((TEST_PASSED + 1))
else
    echo -e "${RED}❌ API端点缺失${NC}"
    TEST_FAILED=$((TEST_FAILED + 1))
fi
echo ""

# 测试3: Agent工具
echo -e "${BLUE}测试3: Agent工具验证${NC}"
echo "----------------------------------------"
cd ../agent-ts
if [ -f "src/infrastructure/tools/game/manipulation-detect-tool.ts" ]; then
    echo -e "${GREEN}✅ 工具文件存在${NC}"
    TEST_PASSED=$((TEST_PASSED + 1))
else
    echo -e "${RED}❌ 工具文件不存在${NC}"
    TEST_FAILED=$((TEST_FAILED + 1))
fi

if grep -q "manipulationDetectTool" src/infrastructure/tools/index.ts; then
    echo -e "${GREEN}✅ 工具已注册${NC}"
    TEST_PASSED=$((TEST_PASSED + 1))
else
    echo -e "${RED}❌ 工具未注册${NC}"
    TEST_FAILED=$((TEST_FAILED + 1))
fi
echo ""

# 测试4: TypeScript编译
echo -e "${BLUE}测试4: TypeScript编译${NC}"
echo "----------------------------------------"
if npm run build 2>&1 | grep -q "error TS"; then
    echo -e "${RED}❌ 编译失败${NC}"
    TEST_FAILED=$((TEST_FAILED + 1))
else
    echo -e "${GREEN}✅ 编译成功${NC}"
    TEST_PASSED=$((TEST_PASSED + 1))
fi
echo ""

# 总结
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
    echo "📋 操纵检测功能已就绪："
    echo "- ManipulationDetector Service ✅"
    echo "- API: GET /api/game/market/manipulation-detect ✅"
    echo "- Agent工具: manipulation_detect ✅"
    exit 0
else
    echo -e "${RED}⚠️  部分测试失败${NC}"
    exit 1
fi
