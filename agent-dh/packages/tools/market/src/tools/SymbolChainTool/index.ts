import { defineTool } from '@deepseek-ai/dsh-tools';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { SymbolChainTool } from './SymbolChainTool';
export { symbolChainPrompt } from './prompt';
export type { SymbolChainParams } from './prompt';
export { SymbolChainTool } from './SymbolChainTool';
export function createSymbolChainTool(qv2: QuantsysV2Client) {
  return defineTool(new SymbolChainTool(qv2).toDSHToolDefinition() as any);
}
