/**
 * DataFetchDividendTool - 股息/分红数据工具
 */

import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { DataFetchDividendTool } from './DataFetchDividendTool';

export { dataFetchDividendPrompt } from './prompt';
export type { DataFetchDividendParams } from './prompt';
export { DataFetchDividendTool } from './DataFetchDividendTool';

export function createDataFetchDividendTool(qv2: QuantsysV2Client) {
  const tool = new DataFetchDividendTool(qv2);
  return tool.toDSHToolDefinition() as any;
}
