/**
 * FactorAnalyzeTool - 因子分析工具导出
 */

import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { defineTool } from '@deepseek-ai/dsh-tools';
import { FactorAnalyzeTool } from './FactorAnalyzeTool';

/**
 * 创建因子分析工具实例
 */
export function createFactorAnalyzeTool(qv2: QuantsysV2Client) {
  const tool = new FactorAnalyzeTool(qv2);
  return defineTool(tool.toDSHToolDefinition());
}

export { FactorAnalyzeTool } from './FactorAnalyzeTool';
export { factorAnalyzePrompt } from './prompt';
export type { FactorAnalyzeParams, FactorAnalyzeResult } from './prompt';
