/**
 * AgentOsRestartTool - 重启工具导出
 */

import { defineTool } from '@deepseek-ai/dsh-tools';
import { AgentOsRestartTool } from './AgentOsRestartTool';
import type { AgentOsConfig } from '../AgentOsStatusTool';

/**
 * 创建 agent-os 重启工具实例
 */
export function createAgentOsRestartTool(config: AgentOsConfig) {
  const tool = new AgentOsRestartTool(config);
  return defineTool(tool.toDSHToolDefinition());
}

export { AgentOsRestartTool } from './AgentOsRestartTool';
export { agentOsRestartPrompt } from './prompt';
export type { AgentOsRestartParams, AgentOsRestartResult } from './prompt';
