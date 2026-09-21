import { defineTool } from '@deepseek-ai/dsh-tools';
import { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { LhbTool } from './LhbTool';

export * from './LhbTool';
export * from './prompt';

export function createLhbTool(qv2: QuantsysV2Client) {
  const tool = new LhbTool(qv2);
  return defineTool(tool.toDSHToolDefinition());
}
