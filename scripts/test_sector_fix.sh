#!/bin/bash
# 测试 sector_analysis 修复

echo "=== 测试 sector_analysis 修复 ==="
echo ""

# 1. 验证 Python 文件中的 sys 导入
echo "1. 检查 analysis.py 中的 sys 导入..."
if grep -q "^import sys" quantsys-v2/adapters/inbound/api/routes/analysis.py; then
    echo "   ✓ sys 已导入"
else
    echo "   ✗ sys 未导入"
fi

# 2. 验证 TypeScript 文件中的友好错误提示
echo ""
echo "2. 检查 sector-analysis-tool.ts 中的错误处理..."
if grep -q "userFriendlyMsg" agent-ts/src/infrastructure/tools/analysis/sector-analysis-tool.ts; then
    echo "   ✓ 友好错误提示已添加"
else
    echo "   ✗ 友好错误提示未添加"
fi

# 3. 测试 API 端点
echo ""
echo "3. 测试 API 端点..."
response=$(curl -s -X POST http://localhost:5001/api/portfolio/sector-aggregate \
  -H "Content-Type: application/json" \
  -d '{"sector_field": "sector", "limit": 3}')

if echo "$response" | grep -q '"success":true\|"sectors"'; then
    echo "   ✓ API 正常工作"
    echo "$response" | jq . 2>/dev/null || echo "$response"
elif echo "$response" | grep -q "name 'sys' is not defined"; then
    echo "   ✗ 仍然报 sys 未定义错误"
    echo "   可能原因:"
    echo "   - Python 字节码缓存未清除"
    echo "   - 服务未重启"
    echo "   - 错误来自其他未修复的模块"
else
    echo "   ⚠ 其他错误:"
    echo "$response" | jq . 2>/dev/null || echo "$response"
fi

echo ""
echo "=== 修复验证完成 ==="
