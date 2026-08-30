#!/usr/bin/env tsx
/**
 * 重新测试之前失败的工具
 */

import { existsSync } from 'fs';
import { join } from 'path';

interface ToolInfo {
  name: string;
  package: string;
  issue: string;
}

// 之前失败的工具列表
const FAILED_TOOLS: ToolInfo[] = [
  // genome 包 - 缺少工厂函数
  { name: 'genome_list', package: 'genome', issue: '缺少工厂函数' },
  { name: 'genome_read', package: 'genome', issue: '缺少工厂函数' },
  { name: 'genome_update', package: 'genome', issue: '缺少工厂函数' },
  { name: 'genome_rollback', package: 'genome', issue: '缺少工厂函数' },
  { name: 'genome_promote', package: 'genome', issue: '缺少工厂函数' },
  { name: 'genome_history', package: 'genome', issue: '缺少工厂函数' },
  
  // learning 包 - 缺少工厂函数
  { name: 'learning_track', package: 'learning', issue: '缺少工厂函数' },
  { name: 'learning_distill', package: 'learning', issue: '缺少工厂函数' },
  { name: 'learning_analyze', package: 'learning', issue: '缺少工厂函数' },
  { name: 'learning_apply', package: 'learning', issue: '缺少工厂函数' },
  
  // lifecycle 包 - 缺少工厂函数
  { name: 'self_status', package: 'lifecycle', issue: '缺少工厂函数' },
  { name: 'self_restart', package: 'lifecycle', issue: '缺少工厂函数' },
  { name: 'self_finalize', package: 'lifecycle', issue: '缺少工厂函数' },
  
  // scheduler 包 - 缺少工厂函数
  { name: 'scheduler_manage', package: 'scheduler', issue: '缺少工厂函数' },
];

function toClassName(toolName: string): string {
  return toolName
    .split('_')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1))
    .join('') + 'Tool';
}

function toDirName(toolName: string): string {
  return toolName
    .split('_')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1))
    .join('') + 'Tool';
}

interface TestResult {
  tool: ToolInfo;
  passed: boolean;
  errors: string[];
  warnings: string[];
  fixed: boolean;
}

async function testTool(tool: ToolInfo): Promise<TestResult> {
  const result: TestResult = {
    tool,
    passed: true,
    errors: [],
    warnings: [],
    fixed: false,
  };

  const packageRoot = join(process.cwd(), 'packages', tool.package);
  const toolDir = join(packageRoot, 'src', 'tools', toDirName(tool.name));
  const className = toClassName(tool.name);

  // 1. 检查目录结构
  if (!existsSync(toolDir)) {
    result.passed = false;
    result.errors.push(`工具目录不存在: ${toolDir}`);
    return result;
  }

  // 2. 检查必需文件
  const requiredFiles = [
    'index.ts',
    `${className}.ts`,
    'prompt.ts',
  ];

  for (const file of requiredFiles) {
    const filePath = join(toolDir, file);
    if (!existsSync(filePath)) {
      result.passed = false;
      result.errors.push(`缺少必需文件: ${file}`);
    }
  }

  if (!result.passed) return result;

  // 3. 尝试导入工具类
  try {
    const toolModule = await import(join(toolDir, `${className}.ts`));
    if (!toolModule[className]) {
      result.passed = false;
      result.errors.push(`工具类 ${className} 未正确导出`);
    }
  } catch (error) {
    result.passed = false;
    result.errors.push(`导入工具类失败: ${error instanceof Error ? error.message : String(error)}`);
  }

  // 4. 尝试导入 prompt
  try {
    const promptModule = await import(join(toolDir, 'prompt.ts'));
    const expectedPromptName = tool.name
      .split('_')
      .map(word => word.charAt(0).toUpperCase() + word.slice(1))
      .join('') + 'Prompt';
    
    const lowerCasePromptName = expectedPromptName.charAt(0).toLowerCase() + expectedPromptName.slice(1);
    
    if (!promptModule[lowerCasePromptName]) {
      result.warnings.push(`Prompt 导出名可能不标准，期望: ${lowerCasePromptName}`);
    }
  } catch (error) {
    result.passed = false;
    result.errors.push(`导入 prompt 失败: ${error instanceof Error ? error.message : String(error)}`);
  }

  // 5. 检查工厂函数 (关键测试)
  try {
    const indexModule = await import(join(toolDir, 'index.ts'));
    const expectedFactoryName = 'create' + className;
    
    if (!indexModule[expectedFactoryName]) {
      result.passed = false;
      result.errors.push(`工厂函数 ${expectedFactoryName} 未正确导出`);
    } else {
      // 工厂函数存在，说明已修复
      result.fixed = true;
    }
  } catch (error) {
    result.passed = false;
    result.errors.push(`导入工厂函数失败: ${error instanceof Error ? error.message : String(error)}`);
  }

  return result;
}

async function runTests() {
  console.log('🔄 重新测试之前失败的工具...\n');
  console.log(`总计: ${FAILED_TOOLS.length} 个之前失败的工具\n`);

  const results: TestResult[] = [];
  
  // 按 package 分组
  const byPackage = new Map<string, ToolInfo[]>();
  for (const tool of FAILED_TOOLS) {
    if (!byPackage.has(tool.package)) {
      byPackage.set(tool.package, []);
    }
    byPackage.get(tool.package)!.push(tool);
  }

  for (const [pkg, tools] of byPackage.entries()) {
    console.log(`\n${'='.repeat(70)}`);
    console.log(`📦 ${pkg} (${tools.length} 个工具)`);
    console.log('='.repeat(70));

    for (const tool of tools) {
      process.stdout.write(`  测试 ${tool.name.padEnd(30)} ... `);
      const result = await testTool(tool);
      results.push(result);

      if (result.passed) {
        if (result.fixed) {
          console.log('✅ 通过 (已修复)');
        } else {
          console.log('✅ 通过');
        }
      } else {
        console.log('❌ 仍然失败');
        result.errors.forEach(err => console.log(`      ❌ ${err}`));
      }

      if (result.warnings.length > 0) {
        result.warnings.forEach(warn => console.log(`      ⚠️  ${warn}`));
      }
    }
  }

  // 生成测试报告
  console.log('\n\n' + '='.repeat(70));
  console.log('📊 重测报告');
  console.log('='.repeat(70));

  const totalTests = results.length;
  const passedTests = results.filter(r => r.passed).length;
  const failedTests = totalTests - passedTests;
  const fixedTests = results.filter(r => r.fixed).length;
  const passRate = ((passedTests / totalTests) * 100).toFixed(2);
  const fixRate = ((fixedTests / totalTests) * 100).toFixed(2);

  console.log(`\n总计: ${totalTests} 个工具`);
  console.log(`✅ 通过: ${passedTests} 个 (${passRate}%)`);
  console.log(`🔧 已修复: ${fixedTests} 个 (${fixRate}%)`);
  console.log(`❌ 仍失败: ${failedTests} 个`);

  // 按 package 统计
  console.log('\n按 Package 统计:');
  const pkgStats = new Map<string, { total: number; passed: number; fixed: number }>();
  
  for (const result of results) {
    const pkg = result.tool.package;
    if (!pkgStats.has(pkg)) {
      pkgStats.set(pkg, { total: 0, passed: 0, fixed: 0 });
    }
    const stats = pkgStats.get(pkg)!;
    stats.total++;
    if (result.passed) stats.passed++;
    if (result.fixed) stats.fixed++;
  }

  for (const [pkg, stats] of Array.from(pkgStats.entries()).sort()) {
    const pkgPassRate = ((stats.passed / stats.total) * 100).toFixed(0);
    const status = stats.passed === stats.total ? '✅' : '❌';
    const fixInfo = stats.fixed > 0 ? ` (${stats.fixed} 已修复)` : '';
    console.log(`  ${status} ${pkg.padEnd(25)} ${stats.passed}/${stats.total} (${pkgPassRate}%)${fixInfo}`);
  }

  // 仍失败的工具
  const stillFailedResults = results.filter(r => !r.passed);
  if (stillFailedResults.length > 0) {
    console.log('\n\n❌ 仍然失败的工具:');
    for (const result of stillFailedResults) {
      console.log(`\n  ${result.tool.package}/${result.tool.name}:`);
      result.errors.forEach(err => console.log(`    - ${err}`));
    }
  } else {
    console.log('\n\n🎉 所有之前失败的工具都已修复并通过测试！');
  }

  // 对比
  console.log('\n' + '='.repeat(70));
  console.log('📈 修复进度对比');
  console.log('='.repeat(70));
  console.log(`\n之前: ❌ ${totalTests} 个工具失败`);
  console.log(`现在: ✅ ${passedTests} 个工具通过, ❌ ${failedTests} 个仍失败`);
  console.log(`进度: ${fixRate}% 的问题已解决`);

  console.log('\n' + '='.repeat(70));
  
  // 返回退出码
  process.exit(failedTests > 0 ? 1 : 0);
}

// 运行测试
runTests().catch(error => {
  console.error('❌ 测试执行失败:', error);
  process.exit(1);
});
