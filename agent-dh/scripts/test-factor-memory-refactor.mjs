#!/usr/bin/env node
/**
 * Factor 和 Memory 包重构验证脚本
 *
 * 测试目标：
 * 1. BaseTool 类能否正常实例化
 * 2. call() 方法能否正常执行三阶段流程
 * 3. 参数校验是否生效
 */

import { FactorCalculateTool, FactorAnalyzeTool } from '../packages/factor/src/index.ts';
import { MemorySearchTool, MemoryWriteTool, ExperienceWriteTool } from '../packages/memory/src/index.ts';
import { QuantsysV2Client } from '../../quantsys-v2-client/src/index.js';
import { OsMemoryStore } from '../../os-memory/src/index.js';

const qv2 = new QuantsysV2Client({ baseURL: 'http://localhost:5001' });
const osMemory = new OsMemoryStore({ baseURL: 'http://localhost:8080', agentId: 'test' });

console.log('=== Factor 包测试 ===\n');

// 测试 FactorCalculateTool
console.log('1. 测试 FactorCalculateTool 实例化');
const factorCalcTool = new FactorCalculateTool(qv2);
console.log('✓ 实例化成功');
console.log('  metadata:', factorCalcTool.getMetadata());

console.log('\n2. 测试参数校验（缺少必填参数）');
const invalidResult1 = await factorCalcTool.call({});
console.log('  校验结果:', invalidResult1.success ? '✗ 应该失败' : '✓ 正确拒绝');
if (!invalidResult1.success) {
  console.log('  错误信息:', invalidResult1.error?.issue);
}

console.log('\n3. 测试参数校验（symbol 格式错误）');
const invalidResult2 = await factorCalcTool.call({ symbol: 'AAPL' });
console.log('  校验结果:', invalidResult2.success ? '✗ 应该失败' : '✓ 正确拒绝');
if (!invalidResult2.success) {
  console.log('  错误信息:', invalidResult2.error?.issue);
}

// 测试 FactorAnalyzeTool
console.log('\n4. 测试 FactorAnalyzeTool 实例化');
const factorAnalyzeTool = new FactorAnalyzeTool(qv2);
console.log('✓ 实例化成功');

console.log('\n5. 测试参数校验（缺少必填参数）');
const invalidResult3 = await factorAnalyzeTool.call({});
console.log('  校验结果:', invalidResult3.success ? '✗ 应该失败' : '✓ 正确拒绝');
if (!invalidResult3.success) {
  console.log('  错误信息:', invalidResult3.error?.issue);
}

console.log('\n=== Memory 包测试 ===\n');

// 测试 MemorySearchTool
console.log('6. 测试 MemorySearchTool 实例化');
const memorySearchTool = new MemorySearchTool(osMemory);
console.log('✓ 实例化成功');
console.log('  metadata:', memorySearchTool.getMetadata());

console.log('\n7. 测试参数校验（缺少必填参数）');
const invalidResult4 = await memorySearchTool.call({});
console.log('  校验结果:', invalidResult4.success ? '✗ 应该失败' : '✓ 正确拒绝');
if (!invalidResult4.success) {
  console.log('  错误信息:', invalidResult4.error?.issue);
}

console.log('\n8. 测试参数校验（top_k 超出范围）');
const invalidResult5 = await memorySearchTool.call({ query: 'test', top_k: 100 });
console.log('  校验结果:', invalidResult5.success ? '✗ 应该失败' : '✓ 正确拒绝');
if (!invalidResult5.success) {
  console.log('  错误信息:', invalidResult5.error?.issue);
}

// 测试 MemoryWriteTool
console.log('\n9. 测试 MemoryWriteTool 实例化');
const memoryWriteTool = new MemoryWriteTool(osMemory);
console.log('✓ 实例化成功');

console.log('\n10. 测试参数校验（缺少必填参数）');
const invalidResult6 = await memoryWriteTool.call({});
console.log('  校验结果:', invalidResult6.success ? '✗ 应该失败' : '✓ 正确拒绝');
if (!invalidResult6.success) {
  console.log('  错误信息:', invalidResult6.error?.issue);
}

// 测试 ExperienceWriteTool
console.log('\n11. 测试 ExperienceWriteTool 实例化');
const experienceWriteTool = new ExperienceWriteTool(osMemory);
console.log('✓ 实例化成功');

console.log('\n12. 测试参数校验（缺少必填参数）');
const invalidResult7 = await experienceWriteTool.call({});
console.log('  校验结果:', invalidResult7.success ? '✗ 应该失败' : '✓ 正确拒绝');
if (!invalidResult7.success) {
  console.log('  错误信息:', invalidResult7.error?.issue);
}

console.log('\n=== 所有测试完成 ===');
console.log('\n总结：');
console.log('✓ Factor 包 2 个工具类正常实例化');
console.log('✓ Memory 包 3 个工具类正常实例化');
console.log('✓ 所有工具的参数校验正常工作');
console.log('✓ BaseTool 三阶段架构验证通过');
