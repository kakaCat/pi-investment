import type { Context } from '@deepseek-ai/cordis';
import type { AgentDHClient } from '@pi-investment/agent-dh-client';
import { createQuoteTool } from './tools/quote-tool.js';
import { createKlineTool } from './tools/kline-tool.js';
import { createFinancialTool } from './tools/financial-tool.js';
import { createPoolListTool } from './tools/pool-list-tool.js';
import { createStrategyListTool } from './tools/strategy-list-tool.js';

export interface InvestmentPluginConfig {
  client: AgentDHClient;
}

/**
 * Investment plugin for Agent-DH
 * Provides core investment tools: quote, kline, financial data, pool list, strategy list
 */
export default function investmentPlugin(ctx: Context, config: InvestmentPluginConfig) {
  ctx.effect(() => {
    const tools = [
      createQuoteTool(config.client),
      createKlineTool(config.client),
      createFinancialTool(config.client),
      createPoolListTool(config.client),
      createStrategyListTool(config.client),
    ];

    const disposers = tools.map((tool) => ctx.tools.register(tool));

    return () => {
      disposers.forEach((disposer) => disposer());
    };
  });
}

export { createQuoteTool, createKlineTool, createFinancialTool, createPoolListTool, createStrategyListTool };
