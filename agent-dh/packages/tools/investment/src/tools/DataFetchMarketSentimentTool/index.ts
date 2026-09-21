import { DataFetchMarketSentimentTool } from './DataFetchMarketSentimentTool';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';

export type { DataFetchMarketSentimentParams, DataFetchMarketSentimentResult } from './prompt';

export function createDataFetchMarketSentimentTool(qv2: QuantsysV2Client) {
  const tool = new DataFetchMarketSentimentTool(qv2);
  return tool.toDSHToolDefinition();
}
