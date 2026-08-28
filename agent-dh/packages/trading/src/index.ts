import { Context, Service } from '@deepseek-ai/cordis';
import z from '@deepseek-ai/schemastery';
import { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { OsMemoryStore } from '@pi-investment/os-memory';
import { createAccountInfoTool } from './tools/AccountInfoTool';
import { createPositionListTool } from './tools/PositionListTool';
import { createPortfolioTradeTool } from './tools/PortfolioTradeTool';
import { createM4CircuitBreakerTool } from './tools/M4CircuitBreakerTool';
import { createTradeMonitorTool } from './tools/TradeMonitorTool';
import { createAlgoExecuteTool } from './tools/AlgoExecuteTool';
import { createTradeVerifyTool } from './tools/TradeVerifyTool';
import { createSlippageReportTool } from './tools/SlippageReportTool';

export { assertTradingHours } from './utils/trading-hours';

export interface Config {
  quantsysV2?: {
    baseURL?: string;
    timeout?: number;
  };
  agentOS?: {
    baseURL?: string;
    agentId?: string;
  };
}

/**
 * Trading Plugin for Agent-DH
 *
 * Portfolio management, trade execution, and monitoring tools.
 */
export default class TradingPlugin extends Service {
  static inject = ['tools'];
  static Config = z.object({
    quantsysV2: z.object({
      baseURL: z.string().default('http://localhost:5001'),
      timeout: z.number().default(30000),
    }).default({} as any),
    agentOS: z.object({
      baseURL: z.string().default('http://localhost:8080'),
      agentId: z.string().default('agent-dh'),
    }).default({} as any),
  }).default({} as any)

  private qv2: QuantsysV2Client;
  private osMemory: OsMemoryStore;

  constructor(ctx: Context, config: Config) {
    super(ctx, 'trading');

    this.qv2 = new QuantsysV2Client({
      baseURL: config.quantsysV2?.baseURL || 'http://localhost:5001',
      timeout: config.quantsysV2?.timeout || 30000,
    });

    this.osMemory = new OsMemoryStore({
      baseURL: config.agentOS?.baseURL || 'http://localhost:8080',
      agentId: config.agentOS?.agentId || 'agent-dh',
    });

    this.registerTools();
  }

  private registerTools() {
    const { ctx, qv2, osMemory } = this;

    // 1. 账户信息（重构为 BaseTool）
    ctx.tools.register(createAccountInfoTool(qv2));

    // 2. 持仓列表（重构为 BaseTool）
    ctx.tools.register(createPositionListTool(qv2));

    // 3. 交易执行（虚拟仓）- 已重构为 BaseTool（包含完整业务编排：R-008/M4-1/M4-2/M2-2/M5/M3-3）
    ctx.tools.register(createPortfolioTradeTool(qv2, osMemory, ctx));

    // 4. 交易监控（重构为 BaseTool）
    ctx.tools.register(createTradeMonitorTool(qv2));

    // 5. 算法执行（重构为 BaseTool）
    ctx.tools.register(createAlgoExecuteTool(qv2));

    // 6. 交易对账（重构为 BaseTool）
    ctx.tools.register(createTradeVerifyTool(qv2));

    // 7. 滑点报告（M5，2026-08-25）- 重构为 BaseTool
    ctx.tools.register(createSlippageReportTool(osMemory));

    // M4-2: 组合回撤熔断检查（2026-08-26）- 重构为 BaseTool
    ctx.tools.register(createM4CircuitBreakerTool(qv2, osMemory));
  }
}
