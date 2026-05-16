/**
 * 真实集成测试 - 测试重试机制
 * 使用实际的 Python 调用
 */

import { callPythonResilient } from './dist/infrastructure/tools/shared/python-caller-resilient.js';

console.log('🧪 真实集成测试 - 重试机制\n');
console.log('='.repeat(60));

// 测试 1: 正常调用（应该成功，无需重试）
console.log('\n📋 测试 1: 正常调用 - get_stock_info');
console.log('预期: 成功获取数据，无需重试\n');

const start1 = Date.now();
try {
  const result = await callPythonResilient('get_stock_info', { symbol: '000001' });
  const elapsed = ((Date.now() - start1) / 1000).toFixed(2);
  const parsed = JSON.parse(result);

  console.log(`✅ 成功 (${elapsed}秒)`);
  console.log(`   股票名称: ${parsed.name || '未知'}`);
  console.log(`   股票代码: ${parsed.code || '000001'}`);

  if (parsed._via_python_fallback) {
    console.log('   ⚠️  使用了 Python 降级');
  }
} catch (error) {
  const elapsed = ((Date.now() - start1) / 1000).toFixed(2);
  console.log(`❌ 失败 (${elapsed}秒): ${error.message}`);
}

console.log('\n' + '='.repeat(60));

// 测试 2: 快速接口（15秒超时）
console.log('\n📋 测试 2: 快速接口 - get_stock_realtime_price');
console.log('预期: 15秒超时，如果失败会重试\n');

const start2 = Date.now();
try {
  const result = await callPythonResilient('get_stock_realtime_price', { symbol: '000001' });
  const elapsed = ((Date.now() - start2) / 1000).toFixed(2);
  const parsed = JSON.parse(result);

  console.log(`✅ 成功 (${elapsed}秒)`);
  console.log(`   当前价格: ${parsed.price || '未知'}`);
  console.log(`   涨跌幅: ${parsed.change_pct || '未知'}%`);

  if (parsed._from_fallback_cache) {
    console.log(`   ℹ️  使用降级缓存 (${parsed._cache_age_minutes} 分钟前)`);
  }
} catch (error) {
  const elapsed = ((Date.now() - start2) / 1000).toFixed(2);
  console.log(`❌ 失败 (${elapsed}秒): ${error.message}`);

  // 检查是否包含重试信息
  if (error.message.includes('failed after')) {
    console.log('   ✅ 重试机制已触发');
  }
}

console.log('\n' + '='.repeat(60));

// 测试 3: 无效参数（应该立即失败，不重试）
console.log('\n📋 测试 3: 无效参数 - 不应该重试');
console.log('预期: 立即失败，不触发重试\n');

const start3 = Date.now();
try {
  const result = await callPythonResilient('get_stock_info', { symbol: 'INVALID_CODE_12345' });
  const elapsed = ((Date.now() - start3) / 1000).toFixed(2);
  const parsed = JSON.parse(result);

  if (parsed.error) {
    console.log(`✅ 正确返回错误 (${elapsed}秒)`);
    console.log(`   错误信息: ${parsed.error}`);
  } else {
    console.log(`⚠️  意外成功 (${elapsed}秒)`);
  }
} catch (error) {
  const elapsed = ((Date.now() - start3) / 1000).toFixed(2);
  console.log(`✅ 正确失败 (${elapsed}秒): ${error.message}`);

  // 检查是否触发了重试（不应该）
  if (error.message.includes('failed after')) {
    console.log('   ⚠️  意外触发了重试机制');
  } else {
    console.log('   ✅ 没有触发重试（符合预期）');
  }
}

console.log('\n' + '='.repeat(60));

// 测试 4: 检查 NaN 处理
console.log('\n📋 测试 4: NaN 处理 - get_stock_realtime_price');
console.log('预期: 返回的 JSON 不包含 NaN 值\n');

const start4 = Date.now();
try {
  const result = await callPythonResilient('get_stock_realtime_price', { symbol: '600000' });
  const elapsed = ((Date.now() - start4) / 1000).toFixed(2);

  // 检查原始字符串是否包含 NaN
  if (result.includes('NaN') || result.includes('Infinity')) {
    console.log(`❌ 失败 (${elapsed}秒): 返回值包含 NaN/Infinity`);
    console.log(`   原始数据: ${result.substring(0, 200)}...`);
  } else {
    const parsed = JSON.parse(result);
    console.log(`✅ 成功 (${elapsed}秒): JSON 解析正常`);
    console.log(`   股票代码: ${parsed.code || '600000'}`);
    console.log(`   价格: ${parsed.price || 'null'}`);
  }
} catch (error) {
  const elapsed = ((Date.now() - start4) / 1000).toFixed(2);

  if (error.message.includes('not valid JSON')) {
    console.log(`❌ JSON 解析失败 (${elapsed}秒)`);
    console.log('   ⚠️  NaN 清理机制可能未生效');
  } else {
    console.log(`ℹ️  其他错误 (${elapsed}秒): ${error.message}`);
  }
}

console.log('\n' + '='.repeat(60));
console.log('\n✨ 测试完成\n');

process.exit(0);
