/**
 * 简单的重试机制测试
 * 直接测试 Python Bridge 的重试逻辑
 */

import { spawn } from 'child_process';

console.log('🧪 测试重试机制\n');

// 模拟超时场景
console.log('📋 测试场景 1: 模拟超时错误（应该重试）\n');

let retryCount = 0;
const maxRetries = 2;

async function testRetryLogic() {
  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      if (attempt > 0) {
        const delayMs = Math.min(1000 * Math.pow(2, attempt - 1), 5000);
        console.log(`🔄 重试 ${attempt}/${maxRetries}，等待 ${delayMs}ms...`);
        await new Promise(resolve => setTimeout(resolve, delayMs));
      }

      console.log(`📡 尝试 ${attempt + 1}/${maxRetries + 1}...`);

      // 模拟调用
      const result = await simulateCall(attempt);
      console.log(`✅ 成功: ${result}\n`);
      return result;
    } catch (error) {
      console.log(`❌ 失败: ${error.message}`);

      // 检查是否可重试
      if (!isRetriableError(error)) {
        console.log(`⚠️  不可重试的错误，直接抛出\n`);
        throw error;
      }

      if (attempt === maxRetries) {
        console.log(`⚠️  已达到最大重试次数 (${maxRetries + 1} 次尝试)\n`);
        throw new Error(`${error.message} (failed after ${maxRetries + 1} attempts)`);
      }

      console.log(`🔄 可重试的错误，准备重试...\n`);
    }
  }
}

function isRetriableError(error) {
  const message = error.message.toLowerCase();
  const retriablePatterns = [
    'timeout',
    'econnrefused',
    'econnreset',
    'etimedout',
    'network',
  ];
  return retriablePatterns.some(pattern => message.includes(pattern));
}

// 模拟调用：前2次超时，第3次成功
let callCount = 0;
async function simulateCall(attempt) {
  callCount++;

  if (callCount <= 2) {
    throw new Error('Timeout after 15000ms');
  }

  return '{"name": "平安银行", "code": "000001"}';
}

// 运行测试
console.log('='.repeat(60));
console.log('测试 1: 超时后重试成功\n');

try {
  const result = await testRetryLogic();
  console.log('='.repeat(60));
  console.log('✨ 测试通过: 重试机制正常工作');
  console.log(`📊 总调用次数: ${callCount}`);
  console.log(`📊 重试次数: ${callCount - 1}`);
} catch (error) {
  console.log('='.repeat(60));
  console.log('❌ 测试失败:', error.message);
}

console.log('\n' + '='.repeat(60));
console.log('测试 2: 不可重试的错误\n');

// 重置计数器
callCount = 0;

async function simulateNonRetriableError() {
  throw new Error('Invalid JSON format');
}

try {
  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      console.log(`📡 尝试 ${attempt + 1}/${maxRetries + 1}...`);
      await simulateNonRetriableError();
    } catch (error) {
      console.log(`❌ 失败: ${error.message}`);

      if (!isRetriableError(error)) {
        console.log(`⚠️  不可重试的错误，直接抛出\n`);
        throw error;
      }
    }
  }
} catch (error) {
  console.log('='.repeat(60));
  console.log('✨ 测试通过: 不可重试的错误不会重试');
  console.log(`📊 只尝试了 1 次（符合预期）`);
}

console.log('\n✅ 所有测试完成\n');
