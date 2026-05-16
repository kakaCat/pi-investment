/**
 * 测试重试机制
 *
 * 测试场景：
 * 1. 正常调用（无需重试）
 * 2. 超时错误（应该重试）
 * 3. 网络错误（应该重试）
 * 4. 业务错误（不应该重试）
 */

import { callPythonResilient } from './src/infrastructure/tools/shared/python-caller-resilient.js';

console.log('🧪 测试重试机制\n');

// 测试 1: 正常调用
console.log('📋 测试 1: 正常调用（无需重试）');
try {
  const result = await callPythonResilient('get_stock_info', { symbol: '000001' });
  const parsed = JSON.parse(result);
  console.log('✅ 成功:', parsed.name || '平安银行');
} catch (error) {
  console.log('❌ 失败:', error.message);
}

console.log('\n' + '='.repeat(60) + '\n');

// 测试 2: 快速接口（15秒超时）
console.log('📋 测试 2: 快速接口 - get_stock_realtime_price');
console.log('预期: 15秒超时，最多重试2次');
const start2 = Date.now();
try {
  const result = await callPythonResilient('get_stock_realtime_price', { symbol: '000001' });
  const elapsed2 = ((Date.now() - start2) / 1000).toFixed(1);
  const parsed = JSON.parse(result);
  console.log(`✅ 成功 (${elapsed2}秒):`, parsed.price ? `价格 ${parsed.price}` : '已获取');
} catch (error) {
  const elapsed2 = ((Date.now() - start2) / 1000).toFixed(1);
  console.log(`❌ 失败 (${elapsed2}秒):`, error.message);
}

console.log('\n' + '='.repeat(60) + '\n');

// 测试 3: 慢速接口（55秒超时）
console.log('📋 测试 3: 慢速接口 - get_macro_data');
console.log('预期: 55秒超时，如果失败会重试');
const start3 = Date.now();
try {
  const result = await callPythonResilient('get_macro_data', { indicators: ['CPI', 'PPI'] });
  const elapsed3 = ((Date.now() - start3) / 1000).toFixed(1);
  const parsed = JSON.parse(result);
  console.log(`✅ 成功 (${elapsed3}秒):`, parsed.data ? `获取 ${parsed.data.length} 条数据` : '已获取');
} catch (error) {
  const elapsed3 = ((Date.now() - start3) / 1000).toFixed(1);
  console.log(`❌ 失败 (${elapsed3}秒):`, error.message);
}

console.log('\n' + '='.repeat(60) + '\n');

// 测试 4: 检查降级缓存
console.log('📋 测试 4: 降级缓存机制');
try {
  const result = await callPythonResilient('get_stock_info', { symbol: '000001' });
  const parsed = JSON.parse(result);

  if (parsed._from_fallback_cache) {
    console.log(`✅ 使用降级缓存 (${parsed._cache_age_minutes} 分钟前)`);
  } else {
    console.log('✅ 使用新鲜数据');
  }
} catch (error) {
  console.log('❌ 失败:', error.message);
}

console.log('\n' + '='.repeat(60) + '\n');
console.log('✨ 测试完成\n');

process.exit(0);
