#!/bin/bash

# 测试修复后的工具
# 使用方式: ./test_fixed_tools.sh

set -e

echo "======================================"
echo "测试修复后的工具"
echo "======================================"
echo ""

cd "$(dirname "$0")/agent-ts"

echo "1️⃣  测试 market.opponent_behavior"
echo "--------------------------------------"
node -e "
const { runQuantV2 } = require('./dist/infrastructure/adapters/quant/quant-v2-client.js');
runQuantV2('market.opponent_behavior', {})
  .then(r => {
    console.log('✅ 成功:', r.ok);
    console.log('数据:', JSON.stringify(r.data, null, 2));
  })
  .catch(e => {
    console.error('❌ 失败:', e.message);
    process.exit(1);
  });
" || echo "❌ market.opponent_behavior 失败"

echo ""
echo "2️⃣  测试 market.sentiment"
echo "--------------------------------------"
node -e "
const { runQuantV2 } = require('./dist/infrastructure/adapters/quant/quant-v2-client.js');
runQuantV2('market.sentiment', {})
  .then(r => {
    console.log('✅ 成功:', r.ok);
    console.log('数据:', JSON.stringify(r.data, null, 2));
  })
  .catch(e => {
    console.error('❌ 失败:', e.message);
    process.exit(1);
  });
" || echo "❌ market.sentiment 失败"

echo ""
echo "3️⃣  测试 opportunity_scan"
echo "--------------------------------------"
node -e "
const { scanOpportunities } = require('./dist/infrastructure/adapters/quant/quant-v2-client.js');
scanOpportunities({ limit: 5 })
  .then(r => {
    console.log('✅ 成功');
    console.log('机会数量:', r.length);
    console.log('数据:', JSON.stringify(r, null, 2));
  })
  .catch(e => {
    console.error('❌ 失败:', e.message);
    process.exit(1);
  });
" || echo "❌ opportunity_scan 失败"

echo ""
echo "======================================"
echo "测试完成"
echo "======================================"
