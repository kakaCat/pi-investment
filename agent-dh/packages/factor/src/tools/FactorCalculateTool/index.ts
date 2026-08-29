/**
 * FactorCalculateTool - 因子计算工具导出
 */

import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { defineTool } from '@deepseek-ai/dsh-tools';
import { FactorCalculateTool } from './FactorCalculateTool';

/**
 * 创建因子计算工具实例
 */
export function createFactorCalculateTool(qv2: QuantsysV2Client) {
  const tool = new FactorCalculateTool(qv2);
  return defineTool(tool.toDSHToolDefinition());
}

export { FactorCalculateTool } from './FactorCalculateTool';
export { factorCalculatePrompt } from './prompt';
export type { FactorCalculateParams, FactorCalculateResult } from './prompt';
