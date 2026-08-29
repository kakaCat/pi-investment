import { Context, Service } from '@deepseek-ai/cordis';
import z from '@deepseek-ai/schemastery';
import { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { createFactorCalculateTool } from './tools/FactorCalculateTool';
import { createFactorAnalyzeTool } from './tools/FactorAnalyzeTool';

export interface Config {
  quantsysV2?: {
    baseURL?: string;
    timeout?: number;
  };
}

/**
 * Factor Plugin for Agent-DH
 *
 * Factor calculation and effectiveness analysis.
 */
export default class FactorPlugin extends Service {
  static inject = ['tools'];
  static Config = z.object({
    quantsysV2: z.object({
      baseURL: z.string().default('http://localhost:5001'),
      timeout: z.number().default(30000),
    }).default({} as any),
  }).default({} as any)

  private qv2: QuantsysV2Client;

  constructor(ctx: Context, config: Config) {
    super(ctx, 'factor');
    this.qv2 = new QuantsysV2Client({
      baseURL: config.quantsysV2?.baseURL || 'http://localhost:5001',
      timeout: config.quantsysV2?.timeout || 30000,
    });
    this.registerTools();
  }

  private registerTools() {
    const { ctx, qv2 } = this;

    // 注册因子计算工具
    ctx.tools.register(createFactorCalculateTool(qv2));

    // 注册因子分析工具
    ctx.tools.register(createFactorAnalyzeTool(qv2));
  }
}

// Re-export tools for testing
export { FactorCalculateTool, createFactorCalculateTool } from './tools/FactorCalculateTool';
export { FactorAnalyzeTool, createFactorAnalyzeTool } from './tools/FactorAnalyzeTool';
export type { FactorCalculateParams, FactorCalculateResult } from './tools/FactorCalculateTool';
export type { FactorAnalyzeParams, FactorAnalyzeResult } from './tools/FactorAnalyzeTool';
