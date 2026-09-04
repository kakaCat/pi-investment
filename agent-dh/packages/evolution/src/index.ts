import { Context, Service } from '@deepseek-ai/cordis';
import z from '@deepseek-ai/schemastery';
import { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { createEvolutionRunTool } from './tools/EvolutionRunTool';
import { createEvolutionLeaderboardTool } from './tools/EvolutionLeaderboardTool';

export interface Config {
  quantsysV2?: {
    baseURL?: string;
    timeout?: number;
  };
}

/**
 * Evolution Plugin for Agent-DH
 *
 * RFC 012 P2（2026-09-05）：数据源从 Agent OS（:8080，占位 0.05×i 冒充）切换到
 * quantsys-v2 策略进化引擎（:5001，真实回测进化，RFC 012 P1 落位）。
 * 工具直接消费 qv2_real 进化结果；A 链（Agent OS evolution）已退役，不再 fallback。
 */
export default class EvolutionPlugin extends Service {
  static inject = ['tools'];
  static Config = z.object({
    quantsysV2: z.object({
      baseURL: z.string().default('http://localhost:5001'),
      timeout: z.number().default(120000),
    }).default({} as any),
  }).default({} as any);

  private qv2: QuantsysV2Client;

  constructor(ctx: Context, config: Config) {
    super(ctx, 'evolution');
    this.qv2 = new QuantsysV2Client({
      baseURL: config.quantsysV2?.baseURL || 'http://localhost:5001',
      timeout: config.quantsysV2?.timeout || 120000,
    });
    this.registerTools();
  }

  private registerTools() {
    const { ctx, qv2 } = this;

    // 注册进化运行工具（qv2 真实回测进化）
    ctx.tools.register(createEvolutionRunTool(qv2));

    // 注册进化排行榜工具（策略最近进化结果行）
    ctx.tools.register(createEvolutionLeaderboardTool(qv2));
  }
}
