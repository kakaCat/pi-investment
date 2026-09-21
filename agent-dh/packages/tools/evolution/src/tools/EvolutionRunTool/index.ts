/**
 * EvolutionRunTool - 策略进化执行工具导出
 */

import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { defineTool } from '@deepseek-ai/dsh-tools';
import { EvolutionRunTool } from './EvolutionRunTool';

/**
 * 创建策略进化执行工具实例
 */
export function createEvolutionRunTool(qv2: QuantsysV2Client) {
  const tool = new EvolutionRunTool(qv2);
  return defineTool(tool.toDSHToolDefinition());
}

export { EvolutionRunTool } from './EvolutionRunTool';
export type { EvolutionRunParams, EvolutionRunResult } from './prompt';
