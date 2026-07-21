#!/bin/bash

# 指标管理 API 测试脚本

BASE_URL="${QUANTSYS_API_URL:-http://127.0.0.1:5001}"

echo "=========================================="
echo "测试指标管理 API"
echo "=========================================="
echo ""

# 1. 测试获取指标列表
echo "1. 测试 GET /api/indicators/list"
curl -s "${BASE_URL}/api/indicators/list" | jq '.'
echo ""
echo ""

# 2. 测试创建指标
echo "2. 测试 POST /api/indicators/create"
INDICATOR_RESPONSE=$(curl -s -X POST "${BASE_URL}/api/indicators/create" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "测试双均线指标",
    "code": "def calculate(df):\n    df[\"ma5\"] = df[\"close\"].rolling(5).mean()\n    df[\"ma20\"] = df[\"close\"].rolling(20).mean()\n    df[\"buy\"] = df[\"ma5\"] > df[\"ma20\"]\n    df[\"sell\"] = df[\"ma5\"] < df[\"ma20\"]\n    return df",
    "description": "简单的双均线交叉指标"
  }')

echo "$INDICATOR_RESPONSE" | jq '.'
INDICATOR_ID=$(echo "$INDICATOR_RESPONSE" | jq -r '.data.strategyId // .data.strategy_id // empty')
echo ""
echo "创建的指标ID: $INDICATOR_ID"
echo ""

# 如果创建成功，继续测试其他接口
if [ -n "$INDICATOR_ID" ] && [ "$INDICATOR_ID" != "null" ]; then

  # 3. 测试获取指标详情
  echo "3. 测试 GET /api/indicators/detail/${INDICATOR_ID}"
  curl -s "${BASE_URL}/api/indicators/detail/${INDICATOR_ID}" | jq '.'
  echo ""
  echo ""

  # 4. 测试更新指标
  echo "4. 测试 POST /api/indicators/update/${INDICATOR_ID}"
  curl -s -X POST "${BASE_URL}/api/indicators/update/${INDICATOR_ID}" \
    -H "Content-Type: application/json" \
    -d '{
      "description": "更新后的描述",
      "isActive": true
    }' | jq '.'
  echo ""
  echo ""

  # 5. 测试运行指标
  echo "5. 测试 POST /api/indicators/run/${INDICATOR_ID}"
  curl -s -X POST "${BASE_URL}/api/indicators/run/${INDICATOR_ID}" \
    -H "Content-Type: application/json" \
    -d '{
      "symbol": "000001.SZ",
      "limit": 100
    }' | jq '.'
  echo ""
  echo ""

  # 6. 测试回测指标
  echo "6. 测试 POST /api/indicators/backtest"
  curl -s -X POST "${BASE_URL}/api/indicators/backtest" \
    -H "Content-Type: application/json" \
    -d "{
      \"indicatorId\": ${INDICATOR_ID},
      \"symbol\": \"000001.SZ\",
      \"startDate\": \"2024-01-01\",
      \"endDate\": \"2024-12-31\",
      \"initialCash\": 1000000
    }" | jq '.'
  echo ""
  echo ""

  # 7. 测试删除指标
  echo "7. 测试 POST /api/indicators/delete/${INDICATOR_ID}"
  curl -s -X POST "${BASE_URL}/api/indicators/delete/${INDICATOR_ID}" | jq '.'
  echo ""
  echo ""

else
  echo "指标创建失败，跳过后续测试"
fi

echo "=========================================="
echo "测试完成"
echo "=========================================="
