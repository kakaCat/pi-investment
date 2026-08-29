/**
 * EvolutionLeaderboardTool - 策略进化排行榜工具导出
 */

import type { AgentOSClient } from '@pi-investment/agent-os-client';
import { defineTool } from '@deepseek-ai/dsh-tools';
import { EvolutionLeaderboardTool } from './EvolutionLeaderboardTool';

/**
 * 创建策略进化排行榜工具实例
 */
export function createEvolutionLeaderboardTool(aos: AgentOSClient) {
  const tool = new EvolutionLeaderboardTool(aos);
  return defineTool(tool.toDSHToolDefinition());
}

export { EvolutionLeaderboardTool } from './EvolutionLeaderboardTool';
export type { EvolutionLeaderboardParams, EvolutionLeaderboardResult } from './prompt';
