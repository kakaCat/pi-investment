#!/bin/bash
echo "测试交易记录API"
echo "================"
echo ""

echo "1. 测试 /api/trades/list (前端实际调用的端点):"
curl -s "http://127.0.0.1:5001/api/trades/list?page=1&pageSize=2" | python3 -m json.tool

echo ""
echo "2. 测试 /api/simulation/trades (之前调试用的端点):"
curl -s "http://127.0.0.1:5001/api/simulation/trades?account_name=default&limit=2" | python3 -m json.tool

echo ""
echo "================"
echo "对比两个端点的数据结构"
