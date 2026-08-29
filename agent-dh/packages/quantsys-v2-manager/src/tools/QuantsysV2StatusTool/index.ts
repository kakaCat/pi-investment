/**
 * QuantsysV2StatusTool - 状态检查工具导出
 */

import { defineTool } from '@deepseek-ai/dsh-tools';
import { QuantsysV2StatusTool } from './QuantsysV2StatusTool';

export interface QuantsysV2Config {
  projectRoot: string;
  port: number;
  healthCheckUrl: string;
  startupScript: string;
  activateScript: string;
  logFile: string;
}

/**
 * 创建 quantsys-v2 状态检查工具实例
 */
export function createQuantsysV2StatusTool(config: QuantsysV2Config) {
  const tool = new QuantsysV2StatusTool(config);
  return defineTool(tool.toDSHToolDefinition());
}

export { QuantsysV2StatusTool } from './QuantsysV2StatusTool';
export { quantsysV2StatusPrompt } from './prompt';
export type { QuantsysV2StatusParams, QuantsysV2StatusResult } from './prompt';
