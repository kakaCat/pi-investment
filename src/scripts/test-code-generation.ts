#!/usr/bin/env tsx
/**
 * 测试代码生成功能
 */

import { generateToolCode } from '../services/intelligence/code-generator.js';
import type { ToolAddition } from '../types/evolution.js';

async function testCodeGeneration() {
  console.log('🧪 测试代码生成功能\n');

  const toolSpec: ToolAddition = {
    name: 'test_market_sentiment',
    description: '分析市场情绪指标（恐慌指数、融资融券、北向资金）',
    reason: '缺少市场情绪判断能力，需要量化市场恐慌/贪婪程度',
    expectedImpact: '提升择时能力，避免在市场极度恐慌时卖出'
  };

  try {
    console.log('📝 工具规格:');
    console.log(`  名称: ${toolSpec.name}`);
    console.log(`  描述: ${toolSpec.description}`);
    console.log(`  原因: ${toolSpec.reason}\n`);

    const result = await generateToolCode(toolSpec);

    console.log('✅ 代码生成成功!\n');
    console.log('📄 工具文件:', result.toolFileName);
    console.log('📄 测试文件:', result.testFileName);
    console.log('\n--- 工具代码预览 (前50行) ---');
    console.log(result.toolCode.split('\n').slice(0, 50).join('\n'));
    console.log('\n--- 测试代码预览 (前30行) ---');
    console.log(result.testCode.split('\n').slice(0, 30).join('\n'));

  } catch (error) {
    console.error('❌ 代码生成失败:', error instanceof Error ? error.message : String(error));
    if (error instanceof Error && error.stack) {
      console.error('\n堆栈跟踪:');
      console.error(error.stack);
    }
    process.exit(1);
  }
}

testCodeGeneration();
