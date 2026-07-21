#!/bin/bash
# 端到端集成测试脚本

set -e

echo "=== 指标工具系统端到端测试 ==="

# 1. 启动 API 服务
echo "1. 启动 API 服务..."
cd /Users/mac/Documents/ai/pi-investment/quantsys-v2
python api/server.py &
API_PID=$!
sleep 3

# 2. 测试健康检查
echo "2. 测试健康检查..."
curl -f http://127.0.0.1:5001/api/health || { echo "API 服务未启动"; kill $API_PID; exit 1; }

# 3. 创建测试指标
echo "3. 创建测试指标..."
INDICATOR_ID=$(python cli/main.py indicators create \
  --name "测试RSI策略" \
  --code "df['buy'] = df['rsi'] < 30; df['sell'] = df['rsi'] > 70" \
  --description "简单RSI策略" \
  --format json | jq -r '.id')

echo "创建的指标ID: $INDICATOR_ID"

# 4. 列出指标
echo "4. 列出指标..."
python cli/main.py indicators list --type my --format json | jq '.items | length'

# 5. 运行指标
echo "5. 运行指标..."
python cli/main.py indicators run --id $INDICATOR_ID --symbol 000001.SH --limit 100 --format json | jq '.signals | length'

# 6. 回测指标（验证包含summary）
echo "6. 回测指标..."
python cli/main.py indicators backtest \
  --id $INDICATOR_ID \
  --symbol 000001.SH \
  --start 2024-01-01 \
  --end 2024-12-31 \
  --format json > /tmp/backtest_result.json

# 验证 summary 字段存在
if jq -e '.summary' /tmp/backtest_result.json > /dev/null; then
  echo "✓ 回测结果包含 summary 字段"
else
  echo "✗ 回测结果缺少 summary 字段"
  kill $API_PID
  exit 1
fi

# 7. 测试沙箱列探查
echo "7. 测试沙箱列探查..."
curl -s "http://127.0.0.1:5001/api/indicators/sandbox-columns?symbol=000001.SH" | jq '.data.columns | keys | length'

# 8. 创建第二个指标用于对比
echo "8. 创建第二个指标..."
INDICATOR_ID_2=$(python cli/main.py indicators create \
  --name "测试RSI策略v2" \
  --code "df['buy'] = (df['rsi'] < 30) & (df['debt_ratio_q'] < 60); df['sell'] = df['rsi'] > 70" \
  --format json | jq -r '.id')

# 9. 测试双策略对比
echo "9. 测试双策略对比..."
curl -s -X POST http://127.0.0.1:5001/api/indicators/compare \
  -H "Content-Type: application/json" \
  -d "{
    \"indicatorIdA\": $INDICATOR_ID,
    \"indicatorIdB\": $INDICATOR_ID_2,
    \"symbol\": \"000001.SH\",
    \"startDate\": \"2024-01-01\",
    \"endDate\": \"2024-12-31\"
  }" | jq '.data.comparison.filteredByBOnly'

# 10. 清理
echo "10. 清理..."
kill $API_PID

echo "=== 所有测试通过 ==="
