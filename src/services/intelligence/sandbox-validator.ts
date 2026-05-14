/**
 * Sandbox Validator - 沙箱验证器
 *
 * 对生成的代码进行三级验证：
 * 1. 编译验证 - TypeScript 类型检查
 * 2. 单元测试 - Jest 测试执行
 * 3. 集成测试 - 实际加载和调用工具
 */

import { exec } from 'child_process';
import { promisify } from 'util';
import * as path from 'path';

const execAsync = promisify(exec);

export interface ValidationResult {
  passed: boolean;
  level: 'compile' | 'unit_test' | 'integration_test';
  errors: string[];
  warnings: string[];
  duration: number;
}

/**
 * 在沙箱中验证生成的代码
 */
export async function validateInSandbox(
  toolFilePath: string,
  testFilePath?: string
): Promise<ValidationResult[]> {
  const results: ValidationResult[] = [];

  console.log('🔍 开始沙箱验证...');

  // Level 1: 编译验证
  const compileResult = await validateCompilation(toolFilePath);
  results.push(compileResult);
  console.log(`  ${compileResult.passed ? '✅' : '❌'} 编译验证: ${compileResult.passed ? '通过' : '失败'}`);

  if (!compileResult.passed) {
    console.log('  ⚠️  编译失败，跳过后续验证');
    return results;
  }

  // Level 2: 单元测试（如果提供了测试文件）
  if (testFilePath) {
    const testResult = await validateUnitTests(testFilePath);
    results.push(testResult);
    console.log(`  ${testResult.passed ? '✅' : '❌'} 单元测试: ${testResult.passed ? '通过' : '失败'}`);

    if (!testResult.passed) {
      console.log('  ⚠️  单元测试失败，跳过集成测试');
      return results;
    }
  }

  // Level 3: 集成测试
  const integrationResult = await validateIntegration(toolFilePath);
  results.push(integrationResult);
  console.log(`  ${integrationResult.passed ? '✅' : '❌'} 集成测试: ${integrationResult.passed ? '通过' : '失败'}`);

  return results;
}

/**
 * Level 1: 编译验证
 * 运行 TypeScript 编译器检查类型错误
 */
async function validateCompilation(filePath: string): Promise<ValidationResult> {
  const startTime = Date.now();
  const result: ValidationResult = {
    passed: false,
    level: 'compile',
    errors: [],
    warnings: [],
    duration: 0
  };

  try {
    // 使用 tsc --noEmit 只检查类型，不生成文件
    const { stdout, stderr } = await execAsync(
      `npx tsc --noEmit ${filePath}`,
      { cwd: process.cwd() }
    );

    // 如果没有错误输出，说明编译通过
    if (!stderr || stderr.trim() === '') {
      result.passed = true;
    } else {
      result.errors.push(stderr);
    }

    if (stdout && stdout.trim() !== '') {
      result.warnings.push(stdout);
    }
  } catch (error: any) {
    // tsc 返回非零退出码时会抛出错误
    result.errors.push(error.stdout || error.stderr || error.message);
  }

  result.duration = Date.now() - startTime;
  return result;
}

/**
 * Level 2: 单元测试验证
 * 运行 Jest 测试
 */
async function validateUnitTests(testPath: string): Promise<ValidationResult> {
  const startTime = Date.now();
  const result: ValidationResult = {
    passed: false,
    level: 'unit_test',
    errors: [],
    warnings: [],
    duration: 0
  };

  try {
    // 运行指定的测试文件
    const { stdout, stderr } = await execAsync(
      `npm test -- ${testPath} --passWithNoTests`,
      { cwd: process.cwd() }
    );

    // 检查测试是否通过
    if (stdout.includes('PASS') || stdout.includes('Tests:') && !stdout.includes('FAIL')) {
      result.passed = true;
    }

    if (stderr && stderr.trim() !== '') {
      result.warnings.push(stderr);
    }
  } catch (error: any) {
    result.errors.push(error.stdout || error.stderr || error.message);
  }

  result.duration = Date.now() - startTime;
  return result;
}

/**
 * Level 3: 集成测试验证
 * 尝试动态加载工具并验证其结构
 */
async function validateIntegration(toolPath: string): Promise<ValidationResult> {
  const startTime = Date.now();
  const result: ValidationResult = {
    passed: false,
    level: 'integration_test',
    errors: [],
    warnings: [],
    duration: 0
  };

  try {
    // 动态导入工具模块
    const absolutePath = path.resolve(toolPath);
    const toolModule = await import(absolutePath);

    // 查找导出的工具定义
    const toolExport = Object.values(toolModule).find(
      (exp: any) => exp && typeof exp === 'object' && 'name' in exp && 'execute' in exp
    );

    if (!toolExport) {
      result.errors.push('未找到符合 ToolDefinition 接口的导出');
      result.duration = Date.now() - startTime;
      return result;
    }

    const tool = toolExport as any;

    // 验证必需字段
    const requiredFields = ['name', 'description', 'parameters', 'execute'];
    const missingFields = requiredFields.filter(field => !(field in tool));

    if (missingFields.length > 0) {
      result.errors.push(`缺少必需字段: ${missingFields.join(', ')}`);
      result.duration = Date.now() - startTime;
      return result;
    }

    // 验证 execute 是函数
    if (typeof tool.execute !== 'function') {
      result.errors.push('execute 必须是一个函数');
      result.duration = Date.now() - startTime;
      return result;
    }

    // 验证 parameters 是对象
    if (typeof tool.parameters !== 'object') {
      result.errors.push('parameters 必须是一个对象');
      result.duration = Date.now() - startTime;
      return result;
    }

    result.passed = true;
  } catch (error: any) {
    result.errors.push(`动态加载失败: ${error.message}`);
  }

  result.duration = Date.now() - startTime;
  return result;
}

/**
 * 检查所有验证是否通过
 */
export function allValidationsPassed(results: ValidationResult[]): boolean {
  return results.every(r => r.passed);
}

/**
 * 格式化验证结果为可读文本
 */
export function formatValidationResults(results: ValidationResult[]): string {
  const lines: string[] = ['## 验证结果\n'];

  for (const result of results) {
    const icon = result.passed ? '✅' : '❌';
    const levelName = {
      compile: '编译验证',
      unit_test: '单元测试',
      integration_test: '集成测试'
    }[result.level];

    lines.push(`${icon} **${levelName}**: ${result.passed ? '通过' : '失败'} (${result.duration}ms)`);

    if (result.errors.length > 0) {
      lines.push('\n错误:');
      result.errors.forEach(err => {
        lines.push(`  - ${err.split('\n')[0]}`); // 只显示第一行
      });
    }

    if (result.warnings.length > 0) {
      lines.push('\n警告:');
      result.warnings.forEach(warn => {
        lines.push(`  - ${warn.split('\n')[0]}`);
      });
    }

    lines.push('');
  }

  return lines.join('\n');
}
