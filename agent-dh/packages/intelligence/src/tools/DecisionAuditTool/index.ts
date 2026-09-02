/**
 * DecisionAuditTool - 决策审计工具（记录 + 评估）
 */

import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { defineTool } from '@deepseek-ai/dsh-tools';
import { DecisionAuditTool } from './DecisionAuditTool';

export { decisionAuditPrompt } from './prompt';
export type { DecisionAuditParams } from './prompt';
export { DecisionAuditTool } from './DecisionAuditTool';

export function createDecisionAuditTool(qv2: QuantsysV2Client) {
  const tool = new DecisionAuditTool(qv2);
  return defineTool(tool.toDSHToolDefinition() as any);
}
