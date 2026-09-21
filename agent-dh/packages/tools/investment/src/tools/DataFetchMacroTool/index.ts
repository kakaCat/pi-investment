import { DataFetchMacroTool } from './DataFetchMacroTool';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';

export type { DataFetchMacroParams, DataFetchMacroResult } from './prompt';

export function createDataFetchMacroTool(qv2: QuantsysV2Client) {
  const tool = new DataFetchMacroTool(qv2);
  return tool.toDSHToolDefinition();
}
