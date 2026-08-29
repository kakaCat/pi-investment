import { Context, Service } from '@deepseek-ai/cordis';
import z from '@deepseek-ai/schemastery';
import { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { OsMemoryStore } from '@pi-investment/os-memory';
import { createMarketStyleDetectTool } from './tools/MarketStyleDetectTool';
import { createSectorAnalysisTool } from './tools/SectorAnalysisTool';
import { createChipAnalysisTool } from './tools/ChipAnalysisTool';
import { createRegimeDailyTool } from './tools/RegimeDailyTool';
import { createMainlineScanTool } from './tools/MainlineScanTool';
import { createMainlineStocksTool } from './tools/MainlineStocksTool';

export interface Config {
  quantsysV2?: {
    baseURL?: string;
    timeout?: number;
  };
}

/**
 * Market Analysis Plugin for Agent-DH
 *
 * Market style detection, sector analysis, chip distribution analysis.
 */
export default class MarketPlugin extends Service {
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
    super(ctx, 'market');
    this.qv2 = new QuantsysV2Client({
      baseURL: config.quantsysV2?.baseURL || 'http://localhost:5001',
      timeout: config.quantsysV2?.timeout || 30000,
    });
    this.osMemory = new OsMemoryStore({ baseURL: (config as any).agentOS?.baseURL || 'http://localhost:8080', agentId: (config as any).agentOS?.agentId || 'agent-dh' });
    this.registerTools();
  }

  private registerTools() {
    const { ctx, qv2, osMemory } = this;

    // 市场风格检测
    ctx.tools.register(createMarketStyleDetectTool(qv2));

    // 行业分析
    ctx.tools.register(createSectorAnalysisTool(qv2));

    // 筹码分析
    ctx.tools.register(createChipAnalysisTool(qv2));

    // ===== M1 市场感知：每日落库三件套（RFC 004/005，2026-08-20）=====
    // 落库介质：memory（kind=episode, scope=market:*），不依赖后端改表；
    // 幂等：同日已有记录则跳过（盘后例程重复触发不会产生重复记录）

    // M1-1 + M1-3: regime 与情绪每日落库
    ctx.tools.register(createRegimeDailyTool(qv2, osMemory));

    // M1-2: 每日主线识别（Top3 强势主线 + 依据）
    ctx.tools.register(createMainlineScanTool(qv2, osMemory));

    // M2-1: 主线→标的映射器（RFC 004/005，2026-08-22）
    ctx.tools.register(createMainlineStocksTool(qv2));
  }
}
