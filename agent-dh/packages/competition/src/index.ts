import { Context, Service } from '@deepseek-ai/cordis';
import z from '@deepseek-ai/schemastery';
import { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { createCompetitionAnalysisTool } from './tools/CompetitionAnalysisTool';
import { createOpponentBehaviorTool } from './tools/OpponentBehaviorTool';
import { createManipulationDetectTool } from './tools/ManipulationDetectTool';
import { createRetailPanicIndexTool } from './tools/RetailPanicIndexTool';
import { createPoolBattlefieldTool } from './tools/PoolBattlefieldTool';
import { createFundFlowTool } from './tools/FundFlowTool';
import { createLhbTool } from './tools/LhbTool';
import { createLimitUpPoolTool } from './tools/LimitUpPoolTool';

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

    // 竞争分析（个股行业格局）
    ctx.tools.register(createCompetitionAnalysisTool(qv2));
    // 对手行为分析（M7-1：散户/机构/游资博弈）
    ctx.tools.register(createOpponentBehaviorTool(qv2));
    // 操纵检测（M7-3：拉高出货/对倒识别）
    ctx.tools.register(createManipulationDetectTool(qv2));
    // 散户恐慌代理指标（M7-2：连续恐慌指数）
    ctx.tools.register(createRetailPanicIndexTool(qv2));
    // 池子战场评估（M2-3：竞争格局/三方对手强度/攻防建议）
    ctx.tools.register(createPoolBattlefieldTool(qv2));
    // 资金动向（P0：个股主力资金流+两融 / 板块资金流全景）
    ctx.tools.register(createFundFlowTool(qv2));
    // 龙虎榜（P0：游资/机构席位动向）
    ctx.tools.register(createLhbTool(qv2));
    // 涨停池（P0：短线情绪温度计+连板分布）
    ctx.tools.register(createLimitUpPoolTool(qv2));
  }
}

// Re-export tools for testing
export {
  CompetitionAnalysisTool,
  competitionAnalysisPrompt,
} from './tools/CompetitionAnalysisTool';
export {
  OpponentBehaviorTool,
  opponentBehaviorPrompt,
} from './tools/OpponentBehaviorTool';
export {
  ManipulationDetectTool,
  manipulationDetectPrompt,
} from './tools/ManipulationDetectTool';
export {
  RetailPanicIndexTool,
  retailPanicIndexPrompt,
} from './tools/RetailPanicIndexTool';
export {
  PoolBattlefieldTool,
  poolBattlefieldPrompt,
} from './tools/PoolBattlefieldTool';
export {
  FundFlowTool,
  fundFlowPrompt,
} from './tools/FundFlowTool';
export {
  LhbTool,
  lhbPrompt,
} from './tools/LhbTool';
export {
  LimitUpPoolTool,
  limitUpPoolPrompt,
} from './tools/LimitUpPoolTool';
export type {
  CompetitionAnalysisParams,
  CompetitionAnalysisResult,
} from './tools/CompetitionAnalysisTool';
export type {
  OpponentBehaviorParams,
  OpponentBehaviorResult,
} from './tools/OpponentBehaviorTool';
export type {
  ManipulationDetectParams,
  ManipulationDetectResult,
} from './tools/ManipulationDetectTool';
export type {
  RetailPanicIndexParams,
  RetailPanicIndexResult,
} from './tools/RetailPanicIndexTool';
export type {
  PoolBattlefieldParams,
  PoolBattlefieldResult,
} from './tools/PoolBattlefieldTool';
export type {
  FundFlowParams,
  FundFlowResult,
} from './tools/FundFlowTool';
export type {
  LhbParams,
  LhbResult,
} from './tools/LhbTool';
export type {
  LimitUpPoolParams,
  LimitUpPoolResult,
} from './tools/LimitUpPoolTool';
