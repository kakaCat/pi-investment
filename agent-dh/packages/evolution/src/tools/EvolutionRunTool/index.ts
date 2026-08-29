/**
 * EvolutionRunTool - 策略进化执行工具导出
 */

import type { AgentOSClient } from '@pi-investment/agent-os-client';
import { defineTool } from '@deepseek-ai/dsh-tools';
import { EvolutionRunTool } from './EvolutionRunTool';

/**
 * 创建策略进化执行工具实例
 */
export function createEvolutionRunTool(aos: AgentOSClient) {
  const tool = new EvolutionRunTool(aos);
  return defineTool(tool.toDSHToolDefinition());
}

export { EvolutionRunTool } from './EvolutionRunTool';
export type { EvolutionRunParams, EvolutionRunResult } from './prompt';
