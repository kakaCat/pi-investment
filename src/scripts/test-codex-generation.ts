/**
 * 测试 Codex 代码生成流程
 *
 * 验证：
 * 1. Codex 能否生成工具代码
 * 2. 沙箱验证是否通过
 * 3. 完整流程是否正常
 */

import { generateToolCode, writeGeneratedCode } from '../services/intelligence/code-generator.js';
import { validateInSandbox, allValidationsPassed, formatValidationResults } from '../services/intelligence/sandbox-validator.js';
import type { ToolAddition } from '../types/evolution.js';
import * as fs from 'fs/promises';
import * as path from 'path';

async function testCodexGeneration() {
  console.log('🧪 测试 Codex 代码生成流程\n');

  // 1. 定义一个简单的测试工具规格
  const testSpec: ToolAddition = {
    name: 'test-simple-calculator',
    description: '简单计算器工具，用于测试代码生成',
    reason: '测试 Codex 代码生成和沙箱验证流程',
    expectedImpact: '验证架构重构是否成功',
    data: {
      toolName: 'test-simple-calculator',
      name: 'test-simple-calculator',
    }
  };

  try {
    // 2. 使用 Codex 生成代码
    console.log('📝 步骤 1: 调用 Codex 生成代码...\n');
    const generatedCode = await generateToolCode(testSpec);

    console.log('\n✅ 代码生成成功！');
    console.log(`  - 工具代码: ${generatedCode.toolCode.length} 字符`);
    console.log(`  - 测试代码: ${generatedCode.testCode.length} 字符\n`);

    // 3. 写入临时目录
    console.log('📝 步骤 2: 写入临时文件...\n');
    const tempDir = path.join(process.cwd(), '.tmp-test');
    await fs.mkdir(tempDir, { recursive: true });

    const { toolPath, testPath } = await writeGeneratedCode(generatedCode, tempDir);

    // 4. 沙箱验证
    console.log('\n📝 步骤 3: 沙箱验证...\n');
    const validationResults = await validateInSandbox(toolPath, testPath);

    console.log('\n' + formatValidationResults(validationResults));

    // 5. 检查结果
    const allPassed = allValidationsPassed(validationResults);

    if (allPassed) {
      console.log('🎉 测试成功！Codex 代码生成 + 沙箱验证流程正常工作\n');
    } else {
      console.log('⚠️  部分验证失败，但这可能是正常的（测试工具可能不完整）\n');
    }

    // 6. 清理临时文件
    console.log('🧹 清理临时文件...');
    await fs.rm(tempDir, { recursive: true, force: true });

    console.log('\n✅ 测试完成！');

    return allPassed;
  } catch (error: any) {
    console.error('\n❌ 测试失败:', error.message);
    console.error('\n详细错误:', error);

    // 清理临时文件
    try {
      const tempDir = path.join(process.cwd(), '.tmp-test');
      await fs.rm(tempDir, { recursive: true, force: true });
    } catch {
      // 忽略清理失败
    }

    return false;
  }
}

// 运行测试
testCodexGeneration()
  .then(success => {
    process.exit(success ? 0 : 1);
  })
  .catch(error => {
    console.error('未捕获的错误:', error);
    process.exit(1);
  });
