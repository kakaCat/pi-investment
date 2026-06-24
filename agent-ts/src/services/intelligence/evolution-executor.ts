/**
 * Evolution Executor - 进化建议执行器（效应器/Actuator）
 *
 * 根据补偿器生成的优化建议，自动应用可执行的改动。
 *
 * 自动执行：
 * - update_experience: 更新经验库
 * - add_tool: 动态注册新工具到工具列表
 * - remove_tool: 从工具列表移除低效工具
 * - adjust_parameter: 自动调整配置参数
 * - update_prompt: 修改提示词文件
 * - update_code: 修改代码文件
 *
 * 特性：
 * - 执行前验证（schema检查、参数范围验证）
 * - 执行日志记录
 * - 回滚机制（保存变更前状态）
 * - 错误恢复
 */

import * as fs from 'fs/promises';
import * as path from 'path';
import { existsSync } from 'fs';
import { Type } from '@sinclair/typebox';
import { addExperience } from './experience-manager.js';
import type { OptimizationSuggestion, Experience, ToolAddition, ToolRemoval, PromptUpdate, CodeUpdate } from '../../types/evolution.js';
import { generateToolCode, writeGeneratedCode } from './code-generator.js';
import { validateInSandbox, allValidationsPassed, formatValidationResults } from './sandbox-validator.js';
import { createEvolutionBranch, commitChanges, mergeToBranch, rollbackToBranch, getCurrentBranch } from './evolution-branch-manager.js';
import { evolutionConfig } from '../../config/config.js';

interface DynamicToolDefinition {
  name: string;
  description: string;
  parameters: any;
}

export interface ExecutionResult {
  applied: Array<{
    suggestionId: string;
    type: string;
    status: 'success' | 'skipped' | 'error';
    message: string;
    rollbackData?: any;
    details?: any;
  }>;
  manualTasks: Array<{
    suggestionId: string;
    type: string;
    description: string;
    reason: string;
    implementation: string;
  }>;
}

export interface ExecutionLog {
  timestamp: string;
  suggestionId: string;
  type: string;
  action: 'execute' | 'rollback';
  status: 'success' | 'error' | 'skipped';
  details: any;
  error?: string;
}

export interface ActuatorConfig {
  autoExecute: boolean;
  requireApproval: string[];
  maxRollbackHistory: number;
  parameterRanges: Record<string, { min: number; max: number }>;
}

const DEFAULT_CONFIG: ActuatorConfig = {
  autoExecute: true,
  requireApproval: [],
  maxRollbackHistory: 10,
  parameterRanges: {
    stop_loss_threshold: { min: 0.03, max: 0.15 },
    position_size_ratio: { min: 0.05, max: 0.3 },
    risk_preference: { min: 0.1, max: 1.0 },
  },
};

let executionLogs: ExecutionLog[] = [];

/**
 * 执行优化建议（主入口）
 */
export async function executeOptimizationSuggestions(
  suggestions: OptimizationSuggestion[],
  piDir: string,
  config: Partial<ActuatorConfig> = {}
): Promise<ExecutionResult> {
  const actuatorConfig = { ...DEFAULT_CONFIG, ...config };
  const result: ExecutionResult = {
    applied: [],
    manualTasks: [],
  };

  const evolutionDir = path.join(piDir, 'evolution');
  await fs.mkdir(evolutionDir, { recursive: true });

  for (const suggestion of suggestions) {
    const requiresApproval = actuatorConfig.requireApproval.includes(suggestion.type);

    if (requiresApproval || !actuatorConfig.autoExecute) {
      generateManualTask(suggestion, result);
      continue;
    }

    switch (suggestion.type) {
      case 'update_experience':
        await executeExperienceUpdate(suggestion, piDir, result);
        break;

      case 'add_tool':
        await executeToolAddition(suggestion, piDir, result);
        break;

      case 'remove_tool':
        await executeToolRemoval(suggestion, piDir, result);
        break;

      case 'adjust_parameter':
        await executeParameterAdjustment(suggestion, piDir, result, actuatorConfig);
        break;

      case 'update_prompt':
        await executePromptUpdate(suggestion, piDir, result);
        break;

      case 'update_code':
        await executeCodeUpdate(suggestion, piDir, result);
        break;

      default:
        result.applied.push({
          suggestionId: suggestion.id,
          type: suggestion.type,
          status: 'skipped',
          message: `未知建议类型: ${suggestion.type}`,
        });
    }
  }

  await saveExecutionLogs(evolutionDir);
  return result;
}

/**
 * 执行经验更新（自动）
 */
async function executeExperienceUpdate(
  suggestion: OptimizationSuggestion,
  piDir: string,
  result: ExecutionResult
): Promise<void> {
  const logEntry: ExecutionLog = {
    timestamp: new Date().toISOString(),
    suggestionId: suggestion.id,
    type: 'update_experience',
    action: 'execute',
    status: 'success',
    details: {},
  };

  try {
    // 从建议数据中提取经验模式
    const pattern = (suggestion as any).data?.pattern;
    if (!pattern) {
      logEntry.status = 'error';
      logEntry.error = '缺少经验模式数据';
      executionLogs.push(logEntry);

      result.applied.push({
        suggestionId: suggestion.id,
        type: 'update_experience',
        status: 'skipped',
        message: '缺少经验模式数据',
      });
      return;
    }

    // 构造经验条目
    const experience: Experience = {
      id: `exp_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      scenario: pattern.pattern || suggestion.description,
      pattern: {
        conditions: pattern.conditions || [],
        action: pattern.action || 'hold',
      },
      outcomes: {
        total_cases: pattern.count || 1,
        win_rate: pattern.winRate || 0.5,
        avg_return: pattern.avgReturn || 0,
      },
      recommendation: pattern.winRate > 0.6 ? 'aggressive' : pattern.winRate > 0.4 ? 'moderate' : 'cautious',
      reason: suggestion.reason,
      examples: [],
      confidence: pattern.winRate || 0.5,
      last_updated: new Date().toISOString(),
    };

    // 添加到经验库
    addExperience(experience, piDir);

    logEntry.details = { experienceId: experience.id, scenario: experience.scenario };
    executionLogs.push(logEntry);

    result.applied.push({
      suggestionId: suggestion.id,
      type: 'update_experience',
      status: 'success',
      message: `已添加经验: ${experience.scenario}`,
    });
  } catch (e) {
    logEntry.status = 'error';
    logEntry.error = e instanceof Error ? e.message : String(e);
    executionLogs.push(logEntry);

    result.applied.push({
      suggestionId: suggestion.id,
      type: 'update_experience',
      status: 'error',
      message: `执行失败: ${e instanceof Error ? e.message : String(e)}`,
    });
  }
}

/**
 * 执行工具添加（自动生成代码版本）
 */
async function executeToolAddition(
  suggestion: OptimizationSuggestion,
  piDir: string,
  result: ExecutionResult
): Promise<void> {
  const logEntry: ExecutionLog = {
    timestamp: new Date().toISOString(),
    suggestionId: suggestion.id,
    type: 'add_tool',
    action: 'execute',
    status: 'success',
    details: {},
  };

  let branchName: string | null = null;
  const originalBranch = await getCurrentBranch();

  try {
    const toolData = (suggestion as any).data as ToolAddition;
    if (!toolData?.name || !toolData?.description) {
      throw new Error('缺少工具名称或描述');
    }

    console.log(`\n🚀 开始执行工具添加: ${toolData.name}`);

    // 检查是否启用代码生成
    if (!evolutionConfig.enableCodeGeneration) {
      console.log('⚠️  自动代码生成已禁用（Codex 余额不足或配置关闭）');
      console.log('💡 建议：手动实现工具或充值 Codex 账户后启用');

      logEntry.status = 'skipped';
      logEntry.details = {
        toolName: toolData.name,
        description: toolData.description,
        reason: toolData.reason,
        expectedImpact: toolData.expectedImpact,
        message: '自动代码生成已禁用，需要手动实现'
      };

      result.applied.push({
        suggestionId: suggestion.id,
        type: 'add_tool',
        status: 'skipped',
        message: '自动代码生成已禁用，需要手动实现',
      });

      return;
    }

    // 1. 创建进化分支
    const evolutionId = new Date().toISOString().split('T')[0];
    branchName = await createEvolutionBranch(evolutionId);

    // 2. 生成工具代码
    console.log('📝 生成工具代码...');
    const generatedCode = await generateToolCode(toolData);

    // 3. 写入文件
    const toolsDir = path.join(process.cwd(), 'src/infrastructure/tools');
    const { toolPath, testPath } = await writeGeneratedCode(generatedCode, toolsDir);

    // 4. 沙箱验证
    console.log('🔍 沙箱验证...');
    const validationResults = await validateInSandbox(toolPath, testPath);
    const allPassed = allValidationsPassed(validationResults);

    if (!allPassed) {
      console.error('❌ 沙箱验证失败');
      console.error(formatValidationResults(validationResults));

      // 验证失败，回滚
      await rollbackToBranch(originalBranch);
      throw new Error('沙箱验证失败，已回滚更改');
    }

    console.log('✅ 沙箱验证通过');

    // 5. 注册工具到索引
    console.log('📋 注册工具到索引...');
    await registerToolToIndex(toolData.name, generatedCode.toolFileName);

    // 6. 提交到分支
    const commitMessage = `feat: add ${toolData.name} tool\n\n${toolData.reason}\n\n预期效果: ${toolData.expectedImpact}`;
    const filesToCommit = [
      toolPath,
      testPath,
      path.join(toolsDir, 'index.ts')
    ];

    const commitHash = await commitChanges(commitMessage, filesToCommit);

    // 7. 自动合并到 main（根据设计文档，完全自动化）
    console.log('🔀 合并到 main...');
    await mergeToBranch(branchName, 'main');

    console.log(`✅ 工具添加完成: ${toolData.name}`);

    logEntry.details = {
      toolName: toolData.name,
      branchName,
      commitHash,
      validationResults
    };
    executionLogs.push(logEntry);

    result.applied.push({
      suggestionId: suggestion.id,
      type: 'add_tool',
      status: 'success',
      message: `已生成并合并工具: ${toolData.name} (commit: ${commitHash})`,
      rollbackData: {
        branchName,
        commitHash,
        files: [toolPath, testPath]
      },
      details: {
        validationResults: formatValidationResults(validationResults)
      }
    });

  } catch (e) {
    console.error(`❌ 工具添加失败: ${e instanceof Error ? e.message : String(e)}`);

    // 如果创建了分支但失败了，回滚
    if (branchName) {
      try {
        await rollbackToBranch(originalBranch);
        console.log('↩️  已回滚到原分支');
      } catch (rollbackError) {
        console.error('⚠️  回滚失败:', rollbackError);
      }
    }

    logEntry.status = 'error';
    logEntry.error = e instanceof Error ? e.message : String(e);
    executionLogs.push(logEntry);

    result.applied.push({
      suggestionId: suggestion.id,
      type: 'add_tool',
      status: 'error',
      message: `执行失败: ${e instanceof Error ? e.message : String(e)}`,
    });
  }
}

/**
 * 注册工具到 index.ts
 */
async function registerToolToIndex(toolName: string, toolFileName: string): Promise<void> {
  const indexPath = path.join(process.cwd(), 'src/infrastructure/tools/index.ts');
  let content = await fs.readFile(indexPath, 'utf-8');

  // 生成导入语句（转换为 camelCase）
  const toolVarName = `${toolName}Tool`;
  const importStatement = `import { ${toolVarName} } from './${toolFileName.replace('.ts', '.js')}';\n`;

  // 检查是否已经导入
  if (content.includes(importStatement.trim())) {
    console.log('  ℹ️  工具已在索引中注册');
    return;
  }

  // 在文件开头添加导入（在其他导入之后）
  const lastImportIndex = content.lastIndexOf('import ');
  const nextLineIndex = content.indexOf('\n', lastImportIndex);
  content = content.slice(0, nextLineIndex + 1) + importStatement + content.slice(nextLineIndex + 1);

  // 在 allCustomTools 数组中添加工具
  const toolsArrayMatch = content.match(/export const allCustomTools: ToolDefinition\[\] = \[([\s\S]*?)\];/);
  if (!toolsArrayMatch) {
    throw new Error('未找到 allCustomTools 数组定义');
  }

  const toolRegistration = `  ${toolVarName},\n`;
  content = content.replace(
    /export const allCustomTools: ToolDefinition\[\] = \[/,
    `export const allCustomTools: ToolDefinition[] = [\n${toolRegistration}`
  );

  // 写回文件
  await fs.writeFile(indexPath, content, 'utf-8');
  console.log(`  ✅ 已注册到 index.ts`);
}

/**
 * 执行工具移除（自动）
 */
async function executeToolRemoval(
  suggestion: OptimizationSuggestion,
  piDir: string,
  result: ExecutionResult
): Promise<void> {
  const logEntry: ExecutionLog = {
    timestamp: new Date().toISOString(),
    suggestionId: suggestion.id,
    type: 'remove_tool',
    action: 'execute',
    status: 'success',
    details: {},
  };

  try {
    const toolData = (suggestion as any).data as ToolRemoval;
    if (!toolData?.name) {
      throw new Error('缺少工具名称');
    }

    const evolutionDir = path.join(piDir, 'evolution');
    const toolsRegistryPath = path.join(evolutionDir, 'dynamic-tools.json');

    const rollbackData = await removeDynamicTool(toolsRegistryPath, toolData.name);

    logEntry.details = { toolName: toolData.name, evidence: toolData.evidence };
    executionLogs.push(logEntry);

    result.applied.push({
      suggestionId: suggestion.id,
      type: 'remove_tool',
      status: 'success',
      message: `已移除工具: ${toolData.name}`,
      rollbackData,
    });

    await logToolChange('remove', toolData.name, toolData.evidence, evolutionDir);
  } catch (e) {
    logEntry.status = 'error';
    logEntry.error = e instanceof Error ? e.message : String(e);
    executionLogs.push(logEntry);

    result.applied.push({
      suggestionId: suggestion.id,
      type: 'remove_tool',
      status: 'error',
      message: `执行失败: ${e instanceof Error ? e.message : String(e)}`,
    });
  }
}

/**
 * 执行参数调整（自动）
 */
async function executeParameterAdjustment(
  suggestion: OptimizationSuggestion,
  piDir: string,
  result: ExecutionResult,
  config: ActuatorConfig
): Promise<void> {
  const logEntry: ExecutionLog = {
    timestamp: new Date().toISOString(),
    suggestionId: suggestion.id,
    type: 'adjust_parameter',
    action: 'execute',
    status: 'success',
    details: {},
  };

  try {
    const paramData = (suggestion as any).data;
    if (!paramData?.paramName || paramData?.newValue === undefined) {
      throw new Error('缺少参数名称或新值');
    }

    const { paramName, newValue } = paramData;

    if (!validateParameterRange(paramName, newValue, config)) {
      throw new Error(`参数值 ${newValue} 超出允许范围`);
    }

    const evolutionDir = path.join(piDir, 'evolution');
    const configPath = path.join(evolutionDir, 'runtime-config.json');

    const rollbackData = await updateRuntimeConfig(configPath, paramName, newValue);

    logEntry.details = { paramName, oldValue: rollbackData.oldValue, newValue };
    executionLogs.push(logEntry);

    result.applied.push({
      suggestionId: suggestion.id,
      type: 'adjust_parameter',
      status: 'success',
      message: `已调整参数 ${paramName}: ${rollbackData.oldValue} → ${newValue}`,
      rollbackData,
    });

    await logParameterChange(paramName, rollbackData.oldValue, newValue, evolutionDir);
  } catch (e) {
    logEntry.status = 'error';
    logEntry.error = e instanceof Error ? e.message : String(e);
    executionLogs.push(logEntry);

    result.applied.push({
      suggestionId: suggestion.id,
      type: 'adjust_parameter',
      status: 'error',
      message: `执行失败: ${e instanceof Error ? e.message : String(e)}`,
    });
  }
}

/**
 * 验证工具schema
 */
function validateToolSchema(toolDef: DynamicToolDefinition): boolean {
  if (!toolDef.name || typeof toolDef.name !== 'string') return false;
  if (!toolDef.description || typeof toolDef.description !== 'string') return false;
  if (!toolDef.parameters) return false;
  return true;
}

/**
 * 验证参数范围
 */
function validateParameterRange(
  paramName: string,
  value: number,
  config: ActuatorConfig
): boolean {
  const range = config.parameterRanges[paramName];
  if (!range) return true;
  return value >= range.min && value <= range.max;
}

/**
 * 保存动态工具到注册表
 */
async function saveDynamicTool(
  registryPath: string,
  toolDef: DynamicToolDefinition
): Promise<any> {
  let registry: { tools: DynamicToolDefinition[] } = { tools: [] };

  try {
    const content = await fs.readFile(registryPath, 'utf-8');
    registry = JSON.parse(content);
  } catch (e) {
    // 文件不存在，使用空注册表
  }

  const rollbackData = { registry: JSON.parse(JSON.stringify(registry)) };

  const existingIndex = registry.tools.findIndex(t => t.name === toolDef.name);
  if (existingIndex >= 0) {
    registry.tools[existingIndex] = toolDef;
  } else {
    registry.tools.push(toolDef);
  }

  await fs.writeFile(registryPath, JSON.stringify(registry, null, 2), 'utf-8');
  return rollbackData;
}

/**
 * 从注册表移除动态工具
 */
async function removeDynamicTool(
  registryPath: string,
  toolName: string
): Promise<any> {
  let registry: { tools: DynamicToolDefinition[] } = { tools: [] };

  try {
    const content = await fs.readFile(registryPath, 'utf-8');
    registry = JSON.parse(content);
  } catch (e) {
    throw new Error('工具注册表不存在');
  }

  const rollbackData = { registry: JSON.parse(JSON.stringify(registry)) };

  const existingIndex = registry.tools.findIndex(t => t.name === toolName);
  if (existingIndex < 0) {
    throw new Error(`工具 ${toolName} 不存在`);
  }

  registry.tools.splice(existingIndex, 1);

  await fs.writeFile(registryPath, JSON.stringify(registry, null, 2), 'utf-8');
  return rollbackData;
}

/**
 * 更新运行时配置
 */
async function updateRuntimeConfig(
  configPath: string,
  paramName: string,
  newValue: any
): Promise<any> {
  let config: Record<string, any> = {};

  try {
    const content = await fs.readFile(configPath, 'utf-8');
    config = JSON.parse(content);
  } catch (e) {
    // 文件不存在，使用空配置
  }

  const oldValue = config[paramName];
  const rollbackData = { paramName, oldValue };

  config[paramName] = newValue;
  config.last_updated = new Date().toISOString();

  await fs.writeFile(configPath, JSON.stringify(config, null, 2), 'utf-8');
  return rollbackData;
}

/**
 * 记录工具变更历史
 */
async function logToolChange(
  action: 'add' | 'remove',
  toolName: string,
  data: any,
  evolutionDir: string
): Promise<void> {
  const historyPath = path.join(evolutionDir, 'tool-changes.jsonl');
  const logLine = JSON.stringify({
    timestamp: new Date().toISOString(),
    action,
    toolName,
    data,
  }) + '\n';

  await fs.appendFile(historyPath, logLine, 'utf-8');
}

/**
 * 记录参数变更历史
 */
async function logParameterChange(
  paramName: string,
  oldValue: any,
  newValue: any,
  evolutionDir: string
): Promise<void> {
  const historyPath = path.join(evolutionDir, 'parameter-changes.jsonl');
  const logLine = JSON.stringify({
    timestamp: new Date().toISOString(),
    paramName,
    oldValue,
    newValue,
  }) + '\n';

  await fs.appendFile(historyPath, logLine, 'utf-8');
}

/**
 * 保存执行日志
 */
async function saveExecutionLogs(evolutionDir: string): Promise<void> {
  const logPath = path.join(evolutionDir, 'execution-log.json');

  let allLogs: ExecutionLog[] = [];
  try {
    const content = await fs.readFile(logPath, 'utf-8');
    allLogs = JSON.parse(content);
  } catch (e) {
    // 文件不存在
  }

  allLogs.push(...executionLogs);

  const maxLogs = 1000;
  if (allLogs.length > maxLogs) {
    allLogs = allLogs.slice(-maxLogs);
  }

  await fs.writeFile(logPath, JSON.stringify(allLogs, null, 2), 'utf-8');
  executionLogs = [];
}

/**
 * 回滚执行
 */
export async function rollbackExecution(
  suggestionId: string,
  rollbackData: any,
  piDir: string
): Promise<void> {
  const evolutionDir = path.join(piDir, 'evolution');

  if (rollbackData.registry) {
    const toolsRegistryPath = path.join(evolutionDir, 'dynamic-tools.json');
    await fs.writeFile(
      toolsRegistryPath,
      JSON.stringify(rollbackData.registry, null, 2),
      'utf-8'
    );
  }

  if (rollbackData.paramName) {
    const configPath = path.join(evolutionDir, 'runtime-config.json');
    const content = await fs.readFile(configPath, 'utf-8');
    const config = JSON.parse(content);
    config[rollbackData.paramName] = rollbackData.oldValue;
    config.last_updated = new Date().toISOString();
    await fs.writeFile(configPath, JSON.stringify(config, null, 2), 'utf-8');
  }

  const logEntry: ExecutionLog = {
    timestamp: new Date().toISOString(),
    suggestionId,
    type: 'rollback',
    action: 'rollback',
    status: 'success',
    details: rollbackData,
  };

  executionLogs.push(logEntry);
  await saveExecutionLogs(evolutionDir);
}

/**
 * 生成手动任务（降级处理）
 */
function generateManualTask(
  suggestion: OptimizationSuggestion,
  result: ExecutionResult
): void {
  const taskMap: Record<string, string> = {
    add_tool: '新增工具',
    remove_tool: '移除工具',
    adjust_parameter: '调整参数',
    update_experience: '更新经验',
  };

  result.manualTasks.push({
    suggestionId: suggestion.id,
    type: suggestion.type,
    description: `${taskMap[suggestion.type] || suggestion.type}: ${suggestion.description}`,
    reason: suggestion.reason,
    implementation: `
## 实施步骤

${suggestion.description}

## 预期效果

${suggestion.expectedImpact}

## 原因

${suggestion.reason}
`,
  });

  result.applied.push({
    suggestionId: suggestion.id,
    type: suggestion.type,
    status: 'skipped',
    message: '需要人工审核',
  });
}

/**
 * 保存执行结果到文件
 */
export async function saveExecutionResult(
  result: ExecutionResult,
  evolutionDir: string
): Promise<string> {
  // 使用日期 + 时间戳，避免同一天多次运行时覆盖
  const date = new Date();
  const dateStr = date.toISOString().split('T')[0];
  const timeStr = date.toTimeString().split(' ')[0].replace(/:/g, '');
  const resultPath = path.join(evolutionDir, `execution-${dateStr}-${timeStr}.json`);

  await fs.writeFile(
    resultPath,
    JSON.stringify(result, null, 2),
    "utf-8"
  );

  return resultPath;
}

/**
 * 获取执行历史
 */
export async function getExecutionHistory(
  piDir: string,
  limit: number = 10
): Promise<ExecutionLog[]> {
  const evolutionDir = path.join(piDir, "evolution");
  const logPath = path.join(evolutionDir, "execution-log.json");

  try {
    const content = await fs.readFile(logPath, "utf-8");
    const logs: ExecutionLog[] = JSON.parse(content);
    return logs.slice(-limit);
  } catch (e) {
    return [];
  }
}

/**
 * 执行提示词更新（自动）
 */
async function executePromptUpdate(
  suggestion: OptimizationSuggestion,
  piDir: string,
  result: ExecutionResult
): Promise<void> {
  const logEntry: ExecutionLog = {
    timestamp: new Date().toISOString(),
    suggestionId: suggestion.id,
    type: 'update_prompt',
    action: 'execute',
    status: 'success',
    details: {},
  };

  try {
    const promptUpdate = suggestion.promptUpdate;
    if (!promptUpdate) {
      throw new Error('缺少 promptUpdate 数据');
    }

    const bootstrapDir = path.join(piDir, 'bootstrap');
    const promptFilePath = path.join(bootstrapDir, promptUpdate.file);

    // 检查文件是否存在
    if (!existsSync(promptFilePath)) {
      throw new Error(`提示词文件不存在: ${promptUpdate.file}`);
    }

    // 备份原文件
    const backupPath = `${promptFilePath}.backup-${Date.now()}`;
    await fs.copyFile(promptFilePath, backupPath);
    logEntry.details.backupPath = backupPath;

    // 读取原文件
    const originalContent = await fs.readFile(promptFilePath, 'utf-8');

    // 如果指定了 section，尝试替换该章节
    let newContent: string;
    if (promptUpdate.section) {
      // 查找章节标题（支持 ## 和 # 格式）
      const sectionRegex = new RegExp(
        `(#{1,3}\\s+${promptUpdate.section}[^\\n]*\\n)([\\s\\S]*?)(?=\\n#{1,3}\\s+|$)`,
        'i'
      );
      const match = originalContent.match(sectionRegex);

      if (match) {
        // 替换该章节内容
        newContent = originalContent.replace(
          sectionRegex,
          `$1\n${promptUpdate.newContent}\n`
        );
        logEntry.details.modification = 'section_replace';
      } else {
        // 章节不存在，追加到文件末尾
        newContent = `${originalContent}\n\n${promptUpdate.newContent}\n`;
        logEntry.details.modification = 'section_append';
      }
    } else {
      // 没有指定章节，追加到文件末尾
      newContent = `${originalContent}\n\n${promptUpdate.newContent}\n`;
      logEntry.details.modification = 'file_append';
    }

    // 写入新内容
    await fs.writeFile(promptFilePath, newContent, 'utf-8');

    logEntry.details.file = promptUpdate.file;
    logEntry.details.section = promptUpdate.section;
    logEntry.details.reason = promptUpdate.reason;
    executionLogs.push(logEntry);

    result.applied.push({
      suggestionId: suggestion.id,
      type: 'update_prompt',
      status: 'success',
      message: `已更新提示词: ${promptUpdate.file}${promptUpdate.section ? ` (${promptUpdate.section})` : ''}`,
      details: {
        file: promptUpdate.file,
        backupPath,
      },
    });

    console.log(`[执行器] ✓ 提示词更新成功: ${promptUpdate.file}`);
  } catch (error: any) {
    logEntry.status = 'error';
    logEntry.error = error.message;
    executionLogs.push(logEntry);

    result.applied.push({
      suggestionId: suggestion.id,
      type: 'update_prompt',
      status: 'error',
      message: `提示词更新失败: ${error.message}`,
    });

    console.error(`[执行器] ✗ 提示词更新失败:`, error);
  }
}

/**
 * 执行代码更新（自动）
 */
async function executeCodeUpdate(
  suggestion: OptimizationSuggestion,
  piDir: string,
  result: ExecutionResult
): Promise<void> {
  const logEntry: ExecutionLog = {
    timestamp: new Date().toISOString(),
    suggestionId: suggestion.id,
    type: 'update_code',
    action: 'execute',
    status: 'success',
    details: {},
  };

  try {
    const codeUpdate = suggestion.codeUpdate;
    if (!codeUpdate) {
      throw new Error('缺少 codeUpdate 数据');
    }

    // 注意：代码修改需要更谨慎，这里生成详细的修改计划
    // 实际修改由 Agent 自身完成（通过调用自己的编辑能力）

    const modificationPlan = {
      file: codeUpdate.file,
      function: codeUpdate.function,
      issue: codeUpdate.issue,
      modification: codeUpdate.modification,
      reason: codeUpdate.reason,
      suggestedApproach: generateCodeModificationApproach(codeUpdate),
    };

    // 保存修改计划到文件
    const evolutionDir = path.join(piDir, 'evolution');
    const planPath = path.join(
      evolutionDir,
      `code-modification-${suggestion.id}.md`
    );

    const planContent = `# 代码修改计划

## 目标文件
\`${codeUpdate.file}\`

## 问题描述
${codeUpdate.issue}

## 修改内容
${codeUpdate.modification}

## 原因
${codeUpdate.reason}

## 建议方案
${modificationPlan.suggestedApproach}

## 执行步骤
1. 备份原文件
2. 阅读当前实现
3. 识别问题根源
4. 实施修改
5. 运行测试验证
6. 提交修改

---
生成时间: ${new Date().toISOString()}
建议ID: ${suggestion.id}
`;

    await fs.writeFile(planPath, planContent, 'utf-8');

    logEntry.details.file = codeUpdate.file;
    logEntry.details.planPath = planPath;
    executionLogs.push(logEntry);

    result.applied.push({
      suggestionId: suggestion.id,
      type: 'update_code',
      status: 'success',
      message: `已生成代码修改计划: ${codeUpdate.file}`,
      details: {
        file: codeUpdate.file,
        planPath,
      },
    });

    console.log(`[执行器] ✓ 代码修改计划已生成: ${planPath}`);
  } catch (error: any) {
    logEntry.status = 'error';
    logEntry.error = error.message;
    executionLogs.push(logEntry);

    result.applied.push({
      suggestionId: suggestion.id,
      type: 'update_code',
      status: 'error',
      message: `代码修改计划生成失败: ${error.message}`,
    });

    console.error(`[执行器] ✗ 代码修改计划生成失败:`, error);
  }
}

/**
 * 生成代码修改建议方案
 */
function generateCodeModificationApproach(codeUpdate: CodeUpdate): string {
  const approaches: string[] = [];

  // 根据问题类型生成不同的建议
  if (codeUpdate.issue.includes('胜率低') || codeUpdate.issue.includes('准确性')) {
    approaches.push('- 检查数据源是否准确、及时');
    approaches.push('- 审查计算逻辑是否存在错误');
    approaches.push('- 验证结果解读是否合理');
    approaches.push('- 考虑增加数据验证和异常处理');
  }

  if (codeUpdate.issue.includes('性能') || codeUpdate.issue.includes('效率')) {
    approaches.push('- 分析性能瓶颈（CPU、内存、I/O）');
    approaches.push('- 优化算法复杂度');
    approaches.push('- 添加缓存机制');
    approaches.push('- 考虑异步处理');
  }

  if (codeUpdate.issue.includes('误报') || codeUpdate.issue.includes('触发')) {
    approaches.push('- 调整触发阈值');
    approaches.push('- 增加过滤条件');
    approaches.push('- 添加二次确认机制');
    approaches.push('- 优化判断逻辑');
  }

  if (approaches.length === 0) {
    approaches.push('- 仔细阅读当前实现');
    approaches.push('- 识别问题根源');
    approaches.push('- 设计修改方案');
    approaches.push('- 实施并测试');
  }

  return approaches.join('\n');
}

