import { Context, Service } from '@deepseek-ai/cordis';
import z from '@deepseek-ai/schemastery';
import { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { OsMemoryStore } from '@pi-investment/os-memory';
import { createRiskControllerTool } from './tools/RiskControllerTool';
import { createRiskMetricsTool } from './tools/RiskMetricsTool';
import { createBarraDecompositionTool } from './tools/BarraDecompositionTool';
import { createRegimePositionLimitTool } from './tools/RegimePositionLimitTool';

export interface Config {
  quantsysV2?: {
    baseURL?: string;
    timeout?: number;
  };
}

/**
 * Risk Management Plugin for Agent-DH
 *
 * Risk control, position sizing, portfolio risk assessment.
 */
export default class RiskPlugin extends Service {
  static inject = ['tools'];
  static Config = z.object({
    quantsysV2: z.object({
      baseURL: z.string().default('http://localhost:5001'),
      timeout: z.number().default(30000),
    }).default({} as any),
  }).default({} as any)

  private qv2: QuantsysV2Client;
  private osMemory: OsMemoryStore;

  constructor(ctx: Context, config: Config) {
    super(ctx, 'risk');
    this.qv2 = new QuantsysV2Client({
      baseURL: config.quantsysV2?.baseURL || 'http://localhost:5001',
      timeout: config.quantsysV2?.timeout || 30000,
    });
    this.osMemory = new OsMemoryStore({ baseURL: (config as any).agentOS?.baseURL || 'http://localhost:8080', agentId: (config as any).agentOS?.agentId || 'agent-dh' });
    this.registerTools();
  }

  private registerTools() {
    const { ctx, qv2, osMemory } = this;

    // 风险控制
    ctx.tools.register(createRiskControllerTool(qv2));

    // 风险指标
    ctx.tools.register(createRiskMetricsTool(qv2));

    // Barra风险分解
    ctx.tools.register(createBarraDecompositionTool(qv2));

    // M4 仓位映射表（RFC 004，2026-08-21）
    ctx.tools.register(createRegimePositionLimitTool(qv2, osMemory));
  }
}

