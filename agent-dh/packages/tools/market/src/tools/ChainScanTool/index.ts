import { defineTool } from '@deepseek-ai/dsh-tools';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { ChainScanTool } from './ChainScanTool';
export { chainScanPrompt } from './prompt';
export type { ChainScanParams } from './prompt';
export { ChainScanTool } from './ChainScanTool';
export function createChainScanTool(qv2: QuantsysV2Client) {
  return defineTool(new ChainScanTool(qv2).toDSHToolDefinition() as any);
}
