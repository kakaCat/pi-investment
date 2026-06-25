#!/bin/bash
# 端到端流程测试

echo "============================================================"
echo "博弈智能系统 - 端到端流程测试"
echo "执行时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "============================================================"
echo ""

GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

API_BASE="http://localhost:5001"
TEST_PASSED=0
TEST_FAILED=0

# ==================== 测试准备 ====================
echo -e "${BLUE}==================== 测试准备 ====================${NC}"
echo ""

echo "检查API服务状态..."
if curl -s "${API_BASE}/health" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ API服务运行正常${NC}"
    TEST_PASSED=$((TEST_PASSED + 1))
else
    echo -e "${RED}❌ API服务未启动${NC}"
    echo ""
    echo -e "${YELLOW}请先启动API服务：${NC}"
    echo "cd quantsys-v2"
    echo "python start_all.py &"
    exit 1
fi

echo ""

# ==================== 流程1: 早盘分析流程 ====================
echo -e "${BLUE}==================== 流程1: 早盘分析 ====================${NC}"
echo ""

echo "Step 1: 分析对手行为..."
OPPONENT_RESULT=$(curl -s "${API_BASE}/api/game/market/opponent-behavior")
if echo "$OPPONENT_RESULT" | grep -q '"success":true'; then
    echo -e "${GREEN}✅ 对手行为分析成功${NC}"
    # 提取关键信息
    RETAIL=$(echo "$OPPONENT_RESULT" | grep -o '"retail":{[^}]*}' | head -1)
    echo "   散户行为: $(echo $RETAIL | grep -o '"behavior":"[^"]*"' | cut -d'"' -f4)"
    TEST_PASSED=$((TEST_PASSED + 1))
else
    echo -e "${RED}❌ 对手行为分析失败${NC}"
    TEST_FAILED=$((TEST_FAILED + 1))
fi

echo ""
echo "Step 2: 检查博弈预警..."
ALERT_RESULT=$(curl -s "${API_BASE}/api/alerts/check")
if echo "$ALERT_RESULT" | grep -q '"success":true'; then
    echo -e "${GREEN}✅ 预警检查成功${NC}"
    ALERT_COUNT=$(echo "$ALERT_RESULT" | grep -o '"alert_id"' | wc -l)
    echo "   发现预警: ${ALERT_COUNT}条"
    TEST_PASSED=$((TEST_PASSED + 1))
else
    echo -e "${RED}❌ 预警检查失败${NC}"
    TEST_FAILED=$((TEST_FAILED + 1))
fi

echo ""
echo "Step 3: 检测市场操纵..."
MANIP_RESULT=$(curl -s "${API_BASE}/api/game/market/manipulation-detect")
if echo "$MANIP_RESULT" | grep -q '"success":true'; then
    echo -e "${GREEN}✅ 操纵检测成功${NC}"
    TEST_PASSED=$((TEST_PASSED + 1))
else
    echo -e "${RED}❌ 操纵检测失败${NC}"
    TEST_FAILED=$((TEST_FAILED + 1))
fi

echo ""

# ==================== 流程2: 决策记录流程 ====================
echo -e "${BLUE}==================== 流程2: 决策记录 ====================${NC}"
echo ""

echo "Step 1: 记录决策..."
DECISION_DATA='{
  "decision_type": "auto_assessment",
  "context": {
    "market_phase": "accumulation",
    "test": true
  },
  "parameters": {},
  "reasoning": "端到端测试决策",
  "related_entity_type": "test",
  "related_entity_id": "1"
}'

DECISION_RESULT=$(curl -s -X POST "${API_BASE}/api/decisions/record" \
  -H "Content-Type: application/json" \
  -d "$DECISION_DATA")

if echo "$DECISION_RESULT" | grep -q '"success":true'; then
    echo -e "${GREEN}✅ 决策记录成功${NC}"
    DECISION_ID=$(echo "$DECISION_RESULT" | grep -o '"decision_id":"[^"]*"' | cut -d'"' -f4)
    echo "   决策ID: ${DECISION_ID}"
    TEST_PASSED=$((TEST_PASSED + 1))
else
    echo -e "${RED}❌ 决策记录失败${NC}"
    TEST_FAILED=$((TEST_FAILED + 1))
fi

echo ""
echo "Step 2: 查询决策历史..."
HISTORY_RESULT=$(curl -s "${API_BASE}/api/decisions/history?limit=5")
if echo "$HISTORY_RESULT" | grep -q '"success":true'; then
    echo -e "${GREEN}✅ 决策历史查询成功${NC}"
    HISTORY_COUNT=$(echo "$HISTORY_RESULT" | grep -o '"decision_id"' | wc -l)
    echo "   历史决策: ${HISTORY_COUNT}条"
    TEST_PASSED=$((TEST_PASSED + 1))
else
    echo -e "${RED}❌ 决策历史查询失败${NC}"
    TEST_FAILED=$((TEST_FAILED + 1))
fi

echo ""

# ==================== 流程3: 知识库流程 ====================
echo -e "${BLUE}==================== 流程3: 知识库 ====================${NC}"
echo ""

echo "Step 1: 查询活跃知识..."
KNOWLEDGE_RESULT=$(curl -s "${API_BASE}/api/knowledge/active")
if echo "$KNOWLEDGE_RESULT" | grep -q '"success":true'; then
    echo -e "${GREEN}✅ 知识查询成功${NC}"
    KNOWLEDGE_COUNT=$(echo "$KNOWLEDGE_RESULT" | grep -o '"id":"know_' | wc -l)
    echo "   知识数量: ${KNOWLEDGE_COUNT}条"
    TEST_PASSED=$((TEST_PASSED + 1))
else
    echo -e "${RED}❌ 知识查询失败${NC}"
    TEST_FAILED=$((TEST_FAILED + 1))
fi

echo ""
echo "Step 2: 获取知识统计..."
SUMMARY_RESULT=$(curl -s "${API_BASE}/api/knowledge/summary")
if echo "$SUMMARY_RESULT" | grep -q '"success":true'; then
    echo -e "${GREEN}✅ 知识统计成功${NC}"
    TEST_PASSED=$((TEST_PASSED + 1))
else
    echo -e "${RED}❌ 知识统计失败${NC}"
    TEST_FAILED=$((TEST_FAILED + 1))
fi

echo ""

# ==================== 流程4: 学习流程 ====================
echo -e "${BLUE}==================== 流程4: 学习系统 ====================${NC}"
echo ""

echo "Step 1: 学习报告..."
LEARNING_RESULT=$(curl -s "${API_BASE}/api/learning/report")
if echo "$LEARNING_RESULT" | grep -q '"success":true'; then
    echo -e "${GREEN}✅ 学习报告生成成功${NC}"
    TEST_PASSED=$((TEST_PASSED + 1))
else
    echo -e "${RED}❌ 学习报告生成失败${NC}"
    TEST_FAILED=$((TEST_FAILED + 1))
fi

echo ""

# ==================== 流程5: Shell脚本流程 ====================
echo -e "${BLUE}==================== 流程5: Shell脚本执行 ====================${NC}"
echo ""

echo "Step 1: 执行早盘分析脚本..."
./scripts/morning_analysis.sh > /dev/null 2>&1
if [ -f "/tmp/quantsys_morning.log" ]; then
    echo -e "${GREEN}✅ 早盘分析脚本执行成功${NC}"
    echo "   日志文件: /tmp/quantsys_morning.log"
    LOG_LINES=$(wc -l < /tmp/quantsys_morning.log)
    echo "   日志行数: ${LOG_LINES}"
    TEST_PASSED=$((TEST_PASSED + 1))
else
    echo -e "${RED}❌ 早盘分析脚本执行失败${NC}"
    TEST_FAILED=$((TEST_FAILED + 1))
fi

echo ""
echo "Step 2: 执行学习脚本..."
./scripts/daily_learning.sh > /dev/null 2>&1
if [ -f "/tmp/quantsys_learning.log" ]; then
    echo -e "${GREEN}✅ 学习脚本执行成功${NC}"
    echo "   日志文件: /tmp/quantsys_learning.log"
    TEST_PASSED=$((TEST_PASSED + 1))
else
    echo -e "${RED}❌ 学习脚本执行失败${NC}"
    TEST_FAILED=$((TEST_FAILED + 1))
fi

echo ""

# ==================== 测试总结 ====================
echo ""
echo "============================================================"
echo "测试完成"
echo "============================================================"
echo ""

echo "总测试数: $((TEST_PASSED + TEST_FAILED))"
echo -e "${GREEN}通过: $TEST_PASSED${NC}"
echo -e "${RED}失败: $TEST_FAILED${NC}"
echo ""

if [ $TEST_FAILED -eq 0 ]; then
    echo -e "${GREEN}╔═══════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║                                                       ║${NC}"
    echo -e "${GREEN}║   ✅ 端到端流程测试全部通过！系统可用！          ║${NC}"
    echo -e "${GREEN}║                                                       ║${NC}"
    echo -e "${GREEN}╚═══════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${YELLOW}📋 测试覆盖：${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  ✅ API服务健康检查"
    echo "  ✅ 对手行为分析"
    echo "  ✅ 博弈预警检查"
    echo "  ✅ 操纵检测"
    echo "  ✅ 决策记录"
    echo "  ✅ 决策历史查询"
    echo "  ✅ 知识库查询"
    echo "  ✅ 知识统计"
    echo "  ✅ 学习报告"
    echo "  ✅ Shell脚本执行（早盘）"
    echo "  ✅ Shell脚本执行（学习）"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo -e "${GREEN}整个学习闭环流程已验证可用！${NC}"
    echo ""
    exit 0
else
    echo -e "${YELLOW}⚠️  部分测试失败${NC}"
    echo ""
    echo "可能原因："
    echo "1. API服务未完全启动"
    echo "2. 数据库连接问题"
    echo "3. 部分Service实现未完成"
    echo ""
    exit 1
fi
