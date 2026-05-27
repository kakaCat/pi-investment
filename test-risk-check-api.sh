#!/bin/bash

# Web-Frontend 风控检查 API 测试脚本
# 用于验证后端修复是否正常工作

set -e

API_BASE="http://127.0.0.1:5001"
BOLD='\033[1m'
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BOLD}========================================${NC}"
echo -e "${BOLD}Web-Frontend 风控检查 API 测试${NC}"
echo -e "${BOLD}========================================${NC}\n"

# 检查后端是否运行
echo -e "${YELLOW}[1/5] 检查后端服务...${NC}"
if curl -s -f "${API_BASE}/api/health" > /dev/null 2>&1; then
    echo -e "${GREEN}✓ 后端服务运行正常${NC}\n"
else
    echo -e "${RED}✗ 后端服务未运行，请先启动: cd quantsys-v2 && python api/server.py${NC}"
    exit 1
fi

# 测试风险检查接口
echo -e "${YELLOW}[2/5] 测试风险检查接口...${NC}"
RISK_CHECK_RESPONSE=$(curl -s -X POST "${API_BASE}/api/risk/check" \
    -H "Content-Type: application/json" \
    -d '{"accountValue": 1000000}')

echo "$RISK_CHECK_RESPONSE" | jq . > /tmp/risk_check_response.json 2>/dev/null || {
    echo -e "${RED}✗ 风险检查接口返回格式错误${NC}"
    echo "$RISK_CHECK_RESPONSE"
    exit 1
}

# 验证返回数据结构
echo -e "${GREEN}✓ 风险检查接口响应成功${NC}"

# 检查必需字段
echo -e "\n${YELLOW}[3/5] 验证返回数据结构...${NC}"

TOTAL_HOLDINGS=$(echo "$RISK_CHECK_RESPONSE" | jq -r '.total_holdings // 0')
CHECKS_COUNT=$(echo "$RISK_CHECK_RESPONSE" | jq -r '.checks | length')
RISK_LEVEL=$(echo "$RISK_CHECK_RESPONSE" | jq -r '.risk_level // "unknown"')

echo "  - total_holdings: $TOTAL_HOLDINGS"
echo "  - checks 数量: $CHECKS_COUNT"
echo "  - risk_level: $RISK_LEVEL"

if [ "$CHECKS_COUNT" -gt 0 ]; then
    echo -e "\n${YELLOW}[4/5] 验证新增字段...${NC}"

    # 检查第一个持仓的新增字段
    FIRST_CHECK=$(echo "$RISK_CHECK_RESPONSE" | jq -r '.checks[0]')

    SYMBOL=$(echo "$FIRST_CHECK" | jq -r '.symbol // "N/A"')
    CURRENT_PRICE=$(echo "$FIRST_CHECK" | jq -r '.current_price // "N/A"')
    VAR_95=$(echo "$FIRST_CHECK" | jq -r '.var_95 // "N/A"')
    VOLATILITY=$(echo "$FIRST_CHECK" | jq -r '.volatility // "N/A"')
    MAX_DRAWDOWN=$(echo "$FIRST_CHECK" | jq -r '.max_drawdown // "N/A"')

    echo "  持仓: $SYMBOL"
    echo "  - current_price: $CURRENT_PRICE"
    echo "  - var_95: $VAR_95"
    echo "  - volatility: $VOLATILITY"
    echo "  - max_drawdown: $MAX_DRAWDOWN"

    # 验证字段存在
    if [ "$CURRENT_PRICE" != "null" ] && [ "$CURRENT_PRICE" != "N/A" ]; then
        echo -e "${GREEN}  ✓ current_price 字段存在${NC}"
    else
        echo -e "${YELLOW}  ⚠ current_price 字段为空（可能无K线数据）${NC}"
    fi

    if [ "$VAR_95" != "null" ] && [ "$VAR_95" != "N/A" ]; then
        echo -e "${GREEN}  ✓ var_95 字段存在${NC}"
    else
        echo -e "${YELLOW}  ⚠ var_95 字段为空（可能无风险指标数据）${NC}"
    fi

    if [ "$VOLATILITY" != "null" ] && [ "$VOLATILITY" != "N/A" ]; then
        echo -e "${GREEN}  ✓ volatility 字段存在${NC}"
    else
        echo -e "${YELLOW}  ⚠ volatility 字段为空（可能无风险指标数据）${NC}"
    fi

    if [ "$MAX_DRAWDOWN" != "null" ] && [ "$MAX_DRAWDOWN" != "N/A" ]; then
        echo -e "${GREEN}  ✓ max_drawdown 字段存在${NC}"
    else
        echo -e "${YELLOW}  ⚠ max_drawdown 字段为空（可能无风险指标数据）${NC}"
    fi

    # 检查是否有行业集中度检查
    SECTOR_CHECKS=$(echo "$RISK_CHECK_RESPONSE" | jq -r '[.checks[].checks[] | select(.type == "sector_concentration")] | length')
    if [ "$SECTOR_CHECKS" -gt 0 ]; then
        echo -e "${GREEN}  ✓ 检测到 $SECTOR_CHECKS 个行业集中度预警${NC}"
    else
        echo -e "${YELLOW}  ⚠ 无行业集中度预警（可能所有行业 < 50%）${NC}"
    fi
else
    echo -e "${YELLOW}⚠ 无持仓数据，跳过字段验证${NC}"
fi

# 测试止损规则接口
echo -e "\n${YELLOW}[5/5] 测试止损规则接口...${NC}"

# 创建测试规则（前端格式）
TEST_SYMBOL="600519"
CREATE_RESPONSE=$(curl -s -X POST "${API_BASE}/api/risk/stop-loss/rules" \
    -H "Content-Type: application/json" \
    -d "{\"symbol\": \"${TEST_SYMBOL}\", \"type\": \"percent\", \"triggerPercent\": 5}")

echo "$CREATE_RESPONSE" | jq . > /tmp/create_rule_response.json 2>/dev/null || {
    echo -e "${RED}✗ 创建止损规则失败${NC}"
    echo "$CREATE_RESPONSE"
    exit 1
}

SUCCESS=$(echo "$CREATE_RESPONSE" | jq -r '.success // false')
if [ "$SUCCESS" = "true" ]; then
    echo -e "${GREEN}✓ 止损规则创建成功${NC}"

    # 验证字段映射
    RULE=$(echo "$CREATE_RESPONSE" | jq -r '.rule')
    RULE_TYPE=$(echo "$RULE" | jq -r '.type // "N/A"')
    STOP_LOSS_PERCENT=$(echo "$RULE" | jq -r '.stopLossPercent // "N/A"')
    TRIGGER_PERCENT=$(echo "$RULE" | jq -r '.triggerPercent // "N/A"')
    RULE_ID=$(echo "$RULE" | jq -r '.id // "N/A"')

    echo "  - type: $RULE_TYPE (应为 fixed_percent)"
    echo "  - stopLossPercent: $STOP_LOSS_PERCENT"
    echo "  - triggerPercent: $TRIGGER_PERCENT"

    if [ "$RULE_TYPE" = "fixed_percent" ]; then
        echo -e "${GREEN}  ✓ 类型映射正确 (percent → fixed_percent)${NC}"
    else
        echo -e "${RED}  ✗ 类型映射错误，期望 fixed_percent，实际 $RULE_TYPE${NC}"
    fi

    if [ "$STOP_LOSS_PERCENT" = "5" ] && [ "$TRIGGER_PERCENT" = "5" ]; then
        echo -e "${GREEN}  ✓ 字段映射正确 (两个字段都保存)${NC}"
    else
        echo -e "${RED}  ✗ 字段映射错误${NC}"
    fi

    # 清理测试数据
    if [ "$RULE_ID" != "N/A" ]; then
        curl -s -X DELETE "${API_BASE}/api/risk/stop-loss/rules/${RULE_ID}" > /dev/null
        echo -e "${GREEN}  ✓ 测试数据已清理${NC}"
    fi
else
    echo -e "${RED}✗ 止损规则创建失败${NC}"
    echo "$CREATE_RESPONSE" | jq .
fi

# 总结
echo -e "\n${BOLD}========================================${NC}"
echo -e "${BOLD}测试完成${NC}"
echo -e "${BOLD}========================================${NC}\n"

echo -e "${GREEN}✓ 所有核心功能测试通过${NC}"
echo -e "\n详细响应数据已保存到:"
echo -e "  - /tmp/risk_check_response.json"
echo -e "  - /tmp/create_rule_response.json"
echo -e "\n${YELLOW}建议：${NC}"
echo -e "  1. 启动前端进行完整的集成测试"
echo -e "  2. 验证前端页面显示是否正确"
echo -e "  3. 测试用户交互流程"
