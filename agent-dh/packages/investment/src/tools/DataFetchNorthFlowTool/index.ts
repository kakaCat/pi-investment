import { DataFetchNorthFlowTool } from './DataFetchNorthFlowTool';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';

export type { DataFetchNorthFlowParams, DataFetchNorthFlowResult } from './prompt';

export function createDataFetchNorthFlowTool(qv2: QuantsysV2Client) {
  const tool = new DataFetchNorthFlowTool(qv2);
  return tool.toDSHToolDefinition();
}
