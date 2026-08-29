import { Context, Service } from '@deepseek-ai/cordis';
import z from '@deepseek-ai/schemastery';
import { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';

import { createStrategyExecuteTool } from './tools/StrategyExecuteTool';
import { createStrategyOptimizeTool } from './tools/StrategyOptimizeTool';
import { createOpportunityScanTool } from './tools/OpportunityScanTool';
import { createScreeningTool } from './tools/ScreeningTool';
import { createRotationProposalTool } from './tools/RotationProposalTool';
import { createRotationSimulateTool } from './tools/RotationSimulateTool';
import { createRotationExecuteTool } from './tools/RotationExecuteTool';

export interface Config {
  quantsysV2?: {
    baseURL?: string;
    timeout?: number;
  };
}

/**
 * Strategy Plugin for Agent-DH
 *
 * Strategy execution, backtest, screening, sector rotation.
 *
 * Refactored to BaseTool architecture (2026-08-28)
 */
export default class StrategyPlugin extends Service {
  static inject = ['tools'];
  static Config = z.object({
    quantsysV2: z.object({
      baseURL: z.string().default('http://localhost:5001'),
      timeout: z.number().default(30000),
    }).default({} as any),
  }).default({} as any)

  private qv2: QuantsysV2Client;

  constructor(ctx: Context, config: Config) {
    super(ctx, 'strategy');
    this.qv2 = new QuantsysV2Client({
      baseURL: config.quantsysV2?.baseURL || 'http://localhost:5001',
      timeout: config.quantsysV2?.timeout || 30000,
    });
    this.registerTools();
  }

  private registerTools() {
    const { ctx, qv2 } = this;

    // Register all 7 strategy tools
    ctx.tools.register(createStrategyExecuteTool(qv2));
    ctx.tools.register(createStrategyOptimizeTool(qv2));
    ctx.tools.register(createOpportunityScanTool(qv2));
    ctx.tools.register(createScreeningTool(qv2));
    ctx.tools.register(createRotationProposalTool(qv2));
    ctx.tools.register(createRotationSimulateTool(qv2));
    ctx.tools.register(createRotationExecuteTool(qv2));
  }
}
