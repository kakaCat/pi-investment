import { defineTool } from '@deepseek-ai/dsh-tools';
import { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { LimitUpPoolTool } from './LimitUpPoolTool';

export * from './LimitUpPoolTool';
export * from './prompt';

export function createLimitUpPoolTool(qv2: QuantsysV2Client) {
  const tool = new LimitUpPoolTool(qv2);
  return defineTool(tool.toDSHToolDefinition());
}
