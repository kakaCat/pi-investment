import { DataFetchFinancialTool } from './DataFetchFinancialTool';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';

export type { DataFetchFinancialParams, DataFetchFinancialResult } from './prompt';

export function createDataFetchFinancialTool(qv2: QuantsysV2Client) {
  const tool = new DataFetchFinancialTool(qv2);
  return tool.toDSHToolDefinition();
}
