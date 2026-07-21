#!/bin/bash
# 重构验证测试脚本
# 测试 Flask 和 FastAPI 统一策略 API

echo "=========================================="
echo "重构验证测试"
echo "=========================================="
echo ""

# 测试 Flask API
echo "📋 测试 Flask 统一 API (http://localhost:5001)"
echo "------------------------------------------"

echo "1. 列出所有策略:"
curl -s http://localhost:5001/api/strategy/list | jq .

echo ""
echo "2. V13 账户信息:"
curl -s http://localhost:5001/api/strategy/v13/account-info | jq '{success, account_name: .data.account_name, total_value: .data.total_value, positions: .data.positions_count}'

echo ""
echo "3. V14 账户信息:"
curl -s http://localhost:5001/api/strategy/v14/account-info | jq '{success, account_name: .data.account_name, total_value: .data.total_value, positions: .data.positions_count}'

echo ""
echo "4. V13 持仓明细（前3个）:"
curl -s http://localhost:5001/api/strategy/v13/positions | jq '{success, positions: (.data | length), first_3: .data[0:3]}'

echo ""
echo "5. V14 持仓明细（前3个）:"
curl -s http://localhost:5001/api/strategy/v14/positions | jq '{success, positions: (.data | length), first_3: .data[0:3]}'

echo ""
echo "=========================================="
echo "✅ Flask 测试完成"
echo "=========================================="
