import { BaseTool } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext, ToolResponse, ValidationResult } from '@pi-investment/core-tool';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { dataFetchMarketSentimentPrompt, DataFetchMarketSentimentParams, DataFetchMarketSentimentResult } from './prompt';

export class DataFetchMarketSentimentTool extends BaseTool<DataFetchMarketSentimentParams, DataFetchMarketSentimentResult> {
  protected readonly metadata: ToolMetadata = {
    name: 'data_fetch_market_sentiment',
    category: 'data',
    version: '2.0.0',
    timeoutMs: 30000,
  };

  protected readonly prompt = dataFetchMarketSentimentPrompt;

  constructor(private qv2: QuantsysV2Client) {
    super();
  }

  protected validate(args: DataFetchMarketSentimentParams): ValidationResult {
    return { success: true };
  }

  protected async execute(
    args: DataFetchMarketSentimentParams,
    context: ToolContext
  ): Promise<DataFetchMarketSentimentResult> {
    const s = await this.qv2.getMarketSentiment();
    return {
      sentiment_score: (s as any).sentimentScore,
      sentiment_level: (s as any).sentimentLevel,
      fear_greed_index: (s as any).fearGreedIndex,
      advance_decline_ratio: (s as any).indicators?.advanceDecline?.ratio,
      market_phase: (s as any).marketPhase,
      recommendation: (s as any).recommendation,
      indicators: (s as any).indicators,
    };
  }

  protected wrap(data: DataFetchMarketSentimentResult): ToolResponse<DataFetchMarketSentimentResult> {
    return { success: true, data };
  }
}
