import type { Context } from '@deepseek-ai/cordis';
import type { AgentDHClient } from '@pi-investment/agent-dh-client';
import { createEvolutionStatusTool } from './tools/evolution-status-tool.js';
import { createWatchListTool } from './tools/watch-list-tool.js';

export interface IntelligencePluginConfig {
  client: AgentDHClient;
}

/**
 * Intelligence plugin for Agent-DH
 * Provides intelligence tools: evolution status (BLOCKED), watch list
 * 
 * NOTE: evolution_status tool is blocked due to missing backend endpoint.
 */
export default function intelligencePlugin(ctx: Context, config: IntelligencePluginConfig) {
  ctx.effect(() => {
    const tools = [
      createEvolutionStatusTool(config.client),
      createWatchListTool(config.client),
    ];

    const disposers = tools.map((tool) => ctx.tools.register(tool));

    return () => {
      disposers.forEach((disposer) => disposer());
    };
  });
}

export { createEvolutionStatusTool, createWatchListTool };
