#!/bin/bash

echo "🧪 测试池扫描流程"
echo "===================="

echo ""
echo "步骤1: 获取池21详情"
curl -s http://127.0.0.1:5001/api/pools/21 | python3 -c "
import sys, json
data = json.load(sys.stdin)
pool = data.get('data', {})
print(f'池ID: {pool.get(\"id\")}')
print(f'池名: {pool.get(\"name\")}')
print(f'股票: {pool.get(\"symbols\", [])[:5]}')
"

echo ""
echo "步骤2: 扫描池21生成信号"
curl -s -X POST http://127.0.0.1:5001/api/pools/21/scan \
  -H "Content-Type: application/json" \
  -d '{"strategy_ids": [430, 431, 432], "min_score": 0}' \
  > /tmp/scan-result.json

python3 << 'PYEOF'
import json

with open('/tmp/scan-result.json') as f:
    result = json.load(f)

if result.get('success'):
    summary = result.get('data', {}).get('summary', {})
    print(f"✅ 扫描成功")
    print(f"   买入: {summary.get('buy', 0)}")
    print(f"   持有: {summary.get('hold', 0)}")
    print(f"   卖出: {summary.get('sell', 0)}")
    print(f"   错误: {summary.get('error', 0)}")

    buy_signals = result.get('data', {}).get('buy_signals', [])
    if buy_signals:
        print(f"\n💰 买入信号:")
        for sig in buy_signals[:3]:
            print(f"   {sig.get('symbol')}: {sig.get('score')}分 ¥{sig.get('current_price')}")
    else:
        print(f"\n⚠️ 当前无买入信号")
else:
    print(f"❌ 扫描失败: {result.get('error')}")
PYEOF

echo ""
echo "✅ 测试完成"
