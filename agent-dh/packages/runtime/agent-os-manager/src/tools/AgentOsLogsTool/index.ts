/**
 * AgentOsLogsTool - 日志查询工具导出
 */

import { defineTool } from '@deepseek-ai/dsh-tools';
import { AgentOsLogsTool } from './AgentOsLogsTool';

export interface AgentOsLogsConfig {
  projectRoot: string;
  logDir: string;
}

/**
 * 创建 agent-os 日志查询工具实例
 */
export function createAgentOsLogsTool(config: AgentOsLogsConfig) {
  const tool = new AgentOsLogsTool(config);
  return defineTool(tool.toDSHToolDefinition());
}

export { AgentOsLogsTool } from './AgentOsLogsTool';
export { agentOsLogsPrompt } from './prompt';
export type { AgentOsLogsParams, AgentOsLogsResult } from './prompt';
