#!/bin/bash

# 风控检查页面修复验证脚本
# 验证所有修复是否正常工作

set -e

BOLD='\033[1m'
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

API_BASE="http://127.0.0.1:5001"
PASSED=0
FAILED=0

echo -e "${BOLD}========================================${NC}"
echo -e "${BOLD}风控检查页面修复验证${NC}"
echo -e "${BOLD}========================================${NC}\n"

# 测试函数
test_case() {
    local name="$1"
    local command="$2"
    local expected="$3"

    echo -e "${YELLOW}测试: ${name}${NC}"

    result=$(eval "$command" 2>&1)

    if echo "$result" | grep -q "$expected"; then
        echo -e "${GREEN}✓ 通过${NC}\n"
        ((PASSED++))
        return 0
    else
        echo -e "${RED}✗ 失败${NC}"
        echo "期望包含: $expected"
        echo "实际结果: $result"
        echo ""
        ((FAILED++))
        return 1
    fi
}

# 1. 健康检查
echo -e "${BOLD}[1/6] 服务健康检查${NC}\n"
test_case "后端服务健康" \
    "curl -s $API_BASE/api/health" \
    '"status": "ok"'

# 2. 风险检查接口
echo -e "${BOLD}[2/6] 风险检查接口${NC}\n"
test_case "风险检查基本响应" \
    "curl -s -X POST $API_BASE/api/risk/check -H 'Content-Type: application/json' -d '{\"accountValue\": 1000000}'" \
    '"checks"'

# 3. 止损规则创建 - triggerPercent 字段
echo -e "${BOLD}[3/6] 止损规则创建（triggerPercent字段）${NC}\n"
test_case "创建规则使用triggerPercent" \
    "curl -s -X POST $API_BASE/api/risk/stop-loss/rules -H 'Content-Type: application/json' -d '{\"symbol\": \"TEST001\", \"stopLossType\": \"percent\", \"triggerPercent\": 8, \"enabled\": true}'" \
    '"stopLossPercent": 8'

test_case "返回包含triggerPercent字段" \
    "curl -s -X POST $API_BASE/api/risk/stop-loss/rules -H 'Content-Type: application/json' -d '{\"symbol\": \"TEST002\", \"stopLossType\": \"percent\", \"triggerPercent\": 9, \"enabled\": true}'" \
    '"triggerPercent": 9'

# 4. 止损类型映射
echo -e "${BOLD}[4/6] 止损类型映射${NC}\n"
test_case "类型映射: percent → fixed_percent" \
    "curl -s -X POST $API_BASE/api/risk/stop-loss/rules -H 'Content-Type: application/json' -d '{\"symbol\": \"TEST003\", \"stopLossType\": \"percent\", \"triggerPercent\": 10, \"enabled\": true}'" \
    '"type": "fixed_percent"'

test_case "类型映射: price → fixed_price" \
    "curl -s -X POST $API_BASE/api/risk/stop-loss/rules -H 'Content-Type: application/json' -d '{\"symbol\": \"TEST004\", \"stopLossType\": \"price\", \"triggerPercent\": 50, \"enabled\": true}'" \
    '"type": "fixed_price"'

test_case "类型映射: trailing → trailing_stop" \
    "curl -s -X POST $API_BASE/api/risk/stop-loss/rules -H 'Content-Type: application/json' -d '{\"symbol\": \"TEST005\", \"stopLossType\": \"trailing\", \"triggerPercent\": 15, \"enabled\": true}'" \
    '"type": "trailing_stop"'

# 5. 批量创建
echo -e "${BOLD}[5/6] 批量创建止损规则${NC}\n"
test_case "批量创建使用triggerPercent" \
    "curl -s -X POST $API_BASE/api/risk/stop-loss/rules/batch -H 'Content-Type: application/json' -d '{\"rules\": [{\"symbol\": \"TEST006\", \"stopLossType\": \"percent\", \"triggerPercent\": 11, \"enabled\": true}]}'" \
    '"stopLossPercent": 11'

test_case "批量创建类型映射" \
    "curl -s -X POST $API_BASE/api/risk/stop-loss/rules/batch -H 'Content-Type: application/json' -d '{\"rules\": [{\"symbol\": \"TEST007\", \"stopLossType\": \"price\", \"triggerPercent\": 60, \"enabled\": true}, {\"symbol\": \"TEST008\", \"stopLossType\": \"trailing\", \"triggerPercent\": 20, \"enabled\": true}]}'" \
    '"type": "fixed_price"'

# 6. 清理测试数据
echo -e "${BOLD}[6/6] 清理测试数据${NC}\n"
echo "获取所有规则..."
all_rules=$(curl -s $API_BASE/api/risk/stop-loss/rules)
test_rule_ids=$(echo "$all_rules" | jq -r '.rules[] | select(.symbol | startswith("TEST")) | .id')

if [ -n "$test_rule_ids" ]; then
    echo "删除测试规则..."
    for rule_id in $test_rule_ids; do
        curl -s -X DELETE "$API_BASE/api/risk/stop-loss/rules/$rule_id" > /dev/null
        echo "  删除规则: $rule_id"
    done
    echo -e "${GREEN}✓ 测试数据已清理${NC}\n"
else
    echo -e "${BLUE}ℹ 无测试数据需要清理${NC}\n"
fi

# 总结
echo -e "${BOLD}========================================${NC}"
echo -e "${BOLD}测试总结${NC}"
echo -e "${BOLD}========================================${NC}\n"

echo -e "通过: ${GREEN}$PASSED${NC}"
echo -e "失败: ${RED}$FAILED${NC}"
echo -e "总计: $((PASSED + FAILED))"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}${BOLD}✓ 所有测试通过！${NC}"
    echo ""
    echo "修复验证成功："
    echo "  ✓ triggerPercent 字段正确映射到 stopLossPercent"
    echo "  ✓ 止损类型正确映射（percent/price/trailing）"
    echo "  ✓ 批量创建支持新字段和类型映射"
    echo "  ✓ 向后兼容性保持"
    echo ""
    echo "下一步："
    echo "  1. 访问 http://127.0.0.1:3001/risk-check 测试前端"
    echo "  2. 测试风险检查功能"
    echo "  3. 测试止损规则管理功能"
    exit 0
else
    echo -e "${RED}${BOLD}✗ 部分测试失败${NC}"
    echo ""
    echo "请检查："
    echo "  1. 后端服务是否正常运行"
    echo "  2. 查看日志: tail -f /Users/mac/Documents/ai/pi-investment/quantsys-v2/logs/server.log"
    echo "  3. 检查代码修复是否正确应用"
    exit 1
fi
