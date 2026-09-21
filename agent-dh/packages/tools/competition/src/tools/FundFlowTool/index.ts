import { defineTool } from '@deepseek-ai/dsh-tools';
import { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { FundFlowTool } from './FundFlowTool';

export * from './FundFlowTool';
export * from './prompt';

export function createFundFlowTool(qv2: QuantsysV2Client) {
  const tool = new FundFlowTool(qv2);
  return defineTool(tool.toDSHToolDefinition());
}
