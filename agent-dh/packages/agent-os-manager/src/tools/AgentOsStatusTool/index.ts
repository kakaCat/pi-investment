/**
 * AgentOsStatusTool - 状态检查工具导出
 */

import { defineTool } from '@deepseek-ai/dsh-tools';
import { AgentOsStatusTool } from './AgentOsStatusTool';

export interface AgentOsConfig {
  projectRoot: string;
  port: number;
  healthCheckUrl: string;
  startCommand: string;
  logDir: string;
  launchdLabel: string;
}

/**
 * 创建 agent-os 状态检查工具实例
 */
export function createAgentOsStatusTool(config: AgentOsConfig) {
  const tool = new AgentOsStatusTool(config);
  return defineTool(tool.toDSHToolDefinition());
}

export { AgentOsStatusTool } from './AgentOsStatusTool';
export { agentOsStatusPrompt } from './prompt';
export type { AgentOsStatusParams, AgentOsStatusResult } from './prompt';
