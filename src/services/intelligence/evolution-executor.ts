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
 *
 * 特性：
 * - 执行前验证（schema检查、参数范围验证）
 * - 执行日志记录
 * - 回滚机制（保存变更前状态）
 * - 错误恢复
 */

import * as fs from 'fs/promises';
import * as path from 'path';
import { Type } from '@sinclair/typebox';
import { addExperience } from './experience-manager.js';
import type { OptimizationSuggestion, Experience, ToolAddition, ToolRemoval } from '../../types/evolution.js';

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
  status: 'success' | 'error';
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
    const pattern = suggestion.data?.pattern;
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
 * 执行工具添加（自动）
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

  try {
    const toolData = suggestion.data as ToolAddition;
    if (!toolData?.name || !toolData?.description) {
      throw new Error('缺少工具名称或描述');
    }

    const toolDef: DynamicToolDefinition = {
      name: toolData.name,
      description: toolData.description,
      parameters: Type.Object({}),
    };

    if (!validateToolSchema(toolDef)) {
      throw new Error('工具schema验证失败');
    }

    const evolutionDir = path.join(piDir, 'evolution');
    const toolsRegistryPath = path.join(evolutionDir, 'dynamic-tools.json');

    const rollbackData = await saveDynamicTool(toolsRegistryPath, toolDef);

    logEntry.details = { toolName: toolData.name, toolDef };
    executionLogs.push(logEntry);

    result.applied.push({
      suggestionId: suggestion.id,
      type: 'add_tool',
      status: 'success',
      message: `已添加工具: ${toolData.name}`,
      rollbackData,
    });

    await logToolChange('add', toolData.name, toolDef, evolutionDir);
  } catch (e) {
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
    const toolData = suggestion.data as ToolRemoval;
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
    const paramData = suggestion.data;
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
  const timestamp = new Date().toISOString().split("T")[0];
  const resultPath = path.join(evolutionDir, `execution-${timestamp}.json`);

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

