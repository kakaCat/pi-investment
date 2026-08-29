/**
 * QuantsysV2LogsTool - 日志查询工具导出
 */

import { defineTool } from '@deepseek-ai/dsh-tools';
import { QuantsysV2LogsTool } from './QuantsysV2LogsTool';

export interface QuantsysV2LogsConfig {
  projectRoot: string;
  logFile: string;
}

/**
 * 创建 quantsys-v2 日志查询工具实例
 */
export function createQuantsysV2LogsTool(config: QuantsysV2LogsConfig) {
  const tool = new QuantsysV2LogsTool(config);
  return defineTool(tool.toDSHToolDefinition());
}

export { QuantsysV2LogsTool } from './QuantsysV2LogsTool';
export { quantsysV2LogsPrompt } from './prompt';
export type { QuantsysV2LogsParams, QuantsysV2LogsResult } from './prompt';
