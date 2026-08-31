import { defineTool } from '@deepseek-ai/dsh-tools';
import { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { RetailPanicIndexTool } from './RetailPanicIndexTool';

export * from './RetailPanicIndexTool';
export * from './prompt';

/**
 * Create Retail Panic Index Tool (M7-2)
 */
export function createRetailPanicIndexTool(qv2: QuantsysV2Client) {
  const tool = new RetailPanicIndexTool(qv2);
  return defineTool(tool.toDSHToolDefinition());
}
