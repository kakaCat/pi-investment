/**
 * RecallAuditTool - 记忆召回审计
 */

import { defineTool } from '@deepseek-ai/dsh-tools';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { RecallAuditTool } from './RecallAuditTool';

export { recallAuditPrompt } from './prompt';
export type { RecallAuditParams } from './prompt';
export { RecallAuditTool } from './RecallAuditTool';

export function createRecallAuditTool(qv2: QuantsysV2Client) {
  const tool = new RecallAuditTool(qv2);
  return defineTool(tool.toDSHToolDefinition() as any);
}
