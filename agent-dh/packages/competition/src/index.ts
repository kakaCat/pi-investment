import { Context, Service } from '@deepseek-ai/cordis';
import z from '@deepseek-ai/schemastery';
import { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { createCompetitionAnalysisTool } from './tools/CompetitionAnalysisTool';

export interface Config {
  quantsysV2?: {
    baseURL?: string;
    timeout?: number;
  };
}

/**
 * Competition Analysis Plugin for Agent-DH
 *
 * Provides industry competition analysis and peer comparison capabilities.
 */
export default class CompetitionPlugin extends Service {
  static inject = ['tools'];
  static Config = z.object({
    quantsysV2: z.object({
      baseURL: z.string().default('http://localhost:5001'),
      timeout: z.number().default(30000),
    }).default({} as any),
  }).default({} as any)

  private qv2: QuantsysV2Client;

  constructor(ctx: Context, config: Config) {
    super(ctx, 'competition');
    this.qv2 = new QuantsysV2Client({
      baseURL: config.quantsysV2?.baseURL || 'http://localhost:5001',
      timeout: config.quantsysV2?.timeout || 30000,
    });
    this.registerTools();
  }

  private registerTools() {
    const { ctx, qv2 } = this;

    // 竞争分析
    ctx.tools.register(createCompetitionAnalysisTool(qv2));
  }
}

// Re-export tools for testing
export {
  CompetitionAnalysisTool,
  competitionAnalysisPrompt,
} from './tools/CompetitionAnalysisTool';
export type {
  CompetitionAnalysisParams,
  CompetitionAnalysisResult,
} from './tools/CompetitionAnalysisTool';
