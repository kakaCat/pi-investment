/**
 * DecisionScoresTool - 决策评分与教训查询工具
 */

import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { defineTool } from '@deepseek-ai/dsh-tools';
import { DecisionScoresTool } from './DecisionScoresTool';

export { decisionScoresPrompt } from './prompt';
export type { DecisionScoresParams } from './prompt';
export { DecisionScoresTool } from './DecisionScoresTool';

export function createDecisionScoresTool(qv2: QuantsysV2Client) {
  const tool = new DecisionScoresTool(qv2);
  return defineTool(tool.toDSHToolDefinition() as any);
}
