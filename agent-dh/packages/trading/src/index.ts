import type { Context } from '@deepseek-ai/cordis';
import type { AgentDHClient } from '@pi-investment/agent-dh-client';
import { createAccountInfoTool } from './tools/account-info-tool.js';
import { createPositionListTool } from './tools/position-list-tool.js';

export interface TradingPluginConfig {
  client: AgentDHClient;
}

/**
 * Trading plugin for Agent-DH
 * Provides trading tools: account info, position list
 */
export default function tradingPlugin(ctx: Context, config: TradingPluginConfig) {
  ctx.effect(() => {
    const tools = [
      createAccountInfoTool(config.client),
      createPositionListTool(config.client),
    ];

    const disposers = tools.map((tool) => ctx.tools.register(tool));

    return () => {
      disposers.forEach((disposer) => disposer());
    };
  });
}

export { createAccountInfoTool, createPositionListTool };
