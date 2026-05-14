/**
 * Evolution Executor - 进化建议执行器
 *
 * 根据补偿器生成的优化建议，自动应用可执行的改动。
 *
 * 自动执行：
 * - update_experience: 更新经验库
 *
 * 手动审核：
 * - add_tool / remove_tool: 生成实施任务，需人工实现
 * - adjust_parameter: 生成配置变更建议
 */

import * as fs from 'fs/promises';
import * as path from 'path';
import { addExperience } from './experience-manager.js';
import type { OptimizationSuggestion, Experience } from '../../types/evolution.js';

export interface ExecutionResult {
  applied: Array<{
    suggestionId: string;
    type: string;
    status: 'success' | 'skipped' | 'error';
    message: string;
  }>;
  manualTasks: Array<{
    suggestionId: string;
    type: string;
    description: string;
    reason: string;
    implementation: string;
  }>;
}

/**
 * 执行优化建议
 */
export async function executeOptimizationSuggestions(
  suggestions: OptimizationSuggestion[],
  piDir: string
): Promise<ExecutionResult> {
  const result: ExecutionResult = {
    applied: [],
    manualTasks: [],
  };

  for (const suggestion of suggestions) {
    switch (suggestion.type) {
      case 'update_experience':
        await executeExperienceUpdate(suggestion, piDir, result);
        break;

      case 'add_tool':
        generateToolAdditionTask(suggestion, result);
        break;

      case 'remove_tool':
        generateToolRemovalTask(suggestion, result);
        break;

      case 'adjust_parameter':
        generateParameterAdjustmentTask(suggestion, result);
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
  try {
    // 从建议数据中提取经验模式
    const pattern = suggestion.data?.pattern;
    if (!pattern) {
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

    result.applied.push({
      suggestionId: suggestion.id,
      type: 'update_experience',
      status: 'success',
      message: `已添加经验: ${experience.scenario}`,
    });
  } catch (e) {
    result.applied.push({
      suggestionId: suggestion.id,
      type: 'update_experience',
      status: 'error',
      message: `执行失败: ${e instanceof Error ? e.message : String(e)}`,
    });
  }
}

/**
 * 生成工具添加任务（手动）
 */
function generateToolAdditionTask(
  suggestion: OptimizationSuggestion,
  result: ExecutionResult
): void {
  const toolName = suggestion.data?.toolName || '未命名工具';
  const toolDescription = suggestion.data?.description || suggestion.description;

  result.manualTasks.push({
    suggestionId: suggestion.id,
    type: 'add_tool',
    description: `新增工具: ${toolName}`,
    reason: suggestion.reason,
    implementation: `
## 实施步骤

1. 在 src/infrastructure/tools/ 创建 ${toolName.replace(/_/g, '-')}-tool.ts
2. 实现工具逻辑：${toolDescription}
3. 在 src/infrastructure/tools/index.ts 中注册
4. 添加到 allCustomTools 数组
5. 编写测试用例

## 工具规格

- 名称: ${toolName}
- 描述: ${toolDescription}
- 预期效果: ${suggestion.expectedImpact}
`,
  });

  result.applied.push({
    suggestionId: suggestion.id,
    type: 'add_tool',
    status: 'skipped',
    message: `已生成实施任务（需手动实现）`,
  });
}

/**
 * 生成工具移除任务（手动）
 */
function generateToolRemovalTask(
  suggestion: OptimizationSuggestion,
  result: ExecutionResult
): void {
  const toolName = suggestion.data?.toolName || '未命名工具';
  const evidence = suggestion.data?.evidence;

  result.manualTasks.push({
    suggestionId: suggestion.id,
    type: 'remove_tool',
    description: `移除工具: ${toolName}`,
    reason: suggestion.reason,
    implementation: `
## 实施步骤

1. 从 src/infrastructure/tools/index.ts 的 allCustomTools 中移除
2. 可选：删除工具文件或标记为 deprecated
3. 检查是否有其他代码依赖此工具

## 移除依据

${evidence ? `
- 调用次数: ${evidence.callCount}
- 胜率: ${(evidence.winRate * 100).toFixed(0)}%
- 平均收益: ${(evidence.avgReturn * 100).toFixed(1)}%
` : ''}
`,
  });

  result.applied.push({
    suggestionId: suggestion.id,
    type: 'remove_tool',
    status: 'skipped',
    message: `已生成实施任务（需手动审核）`,
  });
}

/**
 * 生成参数调整任务（手动）
 */
function generateParameterAdjustmentTask(
  suggestion: OptimizationSuggestion,
  result: ExecutionResult
): void {
  result.manualTasks.push({
    suggestionId: suggestion.id,
    type: 'adjust_parameter',
    description: suggestion.description,
    reason: suggestion.reason,
    implementation: `
## 实施步骤

1. 根据建议调整相关参数
2. 在配置文件或代码中更新
3. 测试调整后的效果

## 调整建议

${suggestion.description}

预期效果: ${suggestion.expectedImpact}
`,
  });

  result.applied.push({
    suggestionId: suggestion.id,
    type: 'adjust_parameter',
    status: 'skipped',
    message: `已生成实施任务（需手动配置）`,
  });
}

/**
 * 保存执行结果到文件
 */
export async function saveExecutionResult(
  result: ExecutionResult,
  evolutionDir: string
): Promise<string> {
  const timestamp = new Date().toISOString().split('T')[0];
  const resultPath = path.join(evolutionDir, `execution-${timestamp}.json`);

  await fs.writeFile(
    resultPath,
    JSON.stringify(result, null, 2),
    'utf-8'
  );

  return resultPath;
}
