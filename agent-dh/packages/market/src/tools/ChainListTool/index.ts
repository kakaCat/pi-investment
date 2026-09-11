import { defineTool } from '@deepseek-ai/dsh-tools';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { ChainListTool } from './ChainListTool';
export { chainListPrompt } from './prompt';
export type { ChainListParams } from './prompt';
export { ChainListTool } from './ChainListTool';
export function createChainListTool(qv2: QuantsysV2Client) {
  return defineTool(new ChainListTool(qv2).toDSHToolDefinition() as any);
}
