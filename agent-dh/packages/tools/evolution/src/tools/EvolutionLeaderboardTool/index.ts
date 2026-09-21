/**
 * EvolutionLeaderboardTool - 策略进化排行榜工具导出
 */

import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { defineTool } from '@deepseek-ai/dsh-tools';
import { EvolutionLeaderboardTool } from './EvolutionLeaderboardTool';

/**
 * 创建策略进化排行榜工具实例
 */
export function createEvolutionLeaderboardTool(qv2: QuantsysV2Client) {
  const tool = new EvolutionLeaderboardTool(qv2);
  return defineTool(tool.toDSHToolDefinition());
}

export { EvolutionLeaderboardTool } from './EvolutionLeaderboardTool';
export type { EvolutionLeaderboardParams, EvolutionLeaderboardResult } from './prompt';
