import { Context, Service } from '@deepseek-ai/cordis';
import { defineTool } from '@deepseek-ai/dsh-tools';
import z from '@deepseek-ai/schemastery';
import { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { createDataFetchQuoteTool } from './tools/DataFetchQuoteTool';
import { createDataFetchKlineTool } from './tools/DataFetchKlineTool';
import { createDataFetchFinancialTool } from './tools/DataFetchFinancialTool';
import { createDataFetchMacroTool } from './tools/DataFetchMacroTool';
import { createDataFetchNorthFlowTool } from './tools/DataFetchNorthFlowTool';
import { createDataFetchMarketSentimentTool } from './tools/DataFetchMarketSentimentTool';
import { createPoolListTool } from './tools/PoolListTool';
import { createStrategyListTool } from './tools/StrategyListTool';
import { createEventCalendarTool } from './tools/EventCalendarTool';
import { createStockIntelTool } from './tools/StockIntelTool';
import { createTradingCalendarTool } from './tools/TradingCalendarTool';

// ========== Plugin Config Schema ==========

export interface Config {
  quantsysV2?: {
    baseURL?: string;
    timeout?: number;
  };
}

// ========== Investment Plugin (Cordis Service) ==========

/**
 * Investment Plugin for Agent-DH
 *
 * Provides market data tools: real-time quotes, kline, financial reports,
 * macro data, north-bound flow, market sentiment, stock pool and strategy lists.
 */
export default class InvestmentPlugin extends Service {
  static inject = ['tools'];
  static Config = z.object({
    quantsysV2: z.object({
      baseURL: z.string().default('http://localhost:5001'),
      timeout: z.number().default(30000),
    }).default({} as any),
  }).default({} as any)

  private qv2: QuantsysV2Client;

  constructor(ctx: Context, config: Config) {
    super(ctx, 'investment');

    this.qv2 = new QuantsysV2Client({
      baseURL: config.quantsysV2?.baseURL || 'http://localhost:5001',
      timeout: config.quantsysV2?.timeout || 30000,
    });

    this.registerTools();
  }

  private registerTools() {
    const { ctx, qv2 } = this;

    // BaseTool 输出扁平 spec，defineTool 负责转换为标准 JSON Schema
    // （顶层 type:'object' + required 数组），供 deepseek API 校验使用
    const reg = (def: any) => ctx.tools.register(defineTool(def));

    // 1. 实时行情 - 已重构为 BaseTool
    reg(createDataFetchQuoteTool(qv2));

    // 2. K线数据 - 已重构为 BaseTool
    reg(createDataFetchKlineTool(qv2));

    // 3. 财务数据 - 已重构为 BaseTool
    reg(createDataFetchFinancialTool(qv2));

    // 4. 宏观经济数据 - 已重构为 BaseTool
    reg(createDataFetchMacroTool(qv2));

    // 5. 北向资金流向 - 已重构为 BaseTool
    reg(createDataFetchNorthFlowTool(qv2));

    // 6. 市场情绪 - 已重构为 BaseTool
    reg(createDataFetchMarketSentimentTool(qv2));

    // 7. 股票池列表 - 已重构为 BaseTool
    reg(createPoolListTool(qv2));

    // 8. 策略列表 - 已重构为 BaseTool
    reg(createStrategyListTool(qv2));

    // 9. 事件日历 - E1 特殊日子（宏观发布/央行议息/财报/交割）
    reg(createEventCalendarTool(qv2));

    // 10. 个股情报 - P0 排雷（公告+新闻+内部人交易聚合）
    reg(createStockIntelTool(qv2));

    // 11. 交易日历 - P0（是否交易日判断，含周末兜底）
    reg(createTradingCalendarTool(qv2));
  }
}
