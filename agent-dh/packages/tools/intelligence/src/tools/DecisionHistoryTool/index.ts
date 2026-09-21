/**
 * DecisionHistoryTool - 决策历史查询工具
 */

import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { defineTool } from '@deepseek-ai/dsh-tools';
import { DecisionHistoryTool } from './DecisionHistoryTool';

export { decisionHistoryPrompt } from './prompt';
export type { DecisionHistoryParams } from './prompt';
export { DecisionHistoryTool } from './DecisionHistoryTool';

export function createDecisionHistoryTool(qv2: QuantsysV2Client) {
  const tool = new DecisionHistoryTool(qv2);
  return defineTool(tool.toDSHToolDefinition() as any);
}
