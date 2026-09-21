import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { defineTool } from '@deepseek-ai/dsh-tools';
import { DataManagerTool } from './DataManagerTool';

/**
 * 创建数据管理工具实例
 */
export function createDataManagerTool(qv2: QuantsysV2Client) {
  const tool = new DataManagerTool(qv2);
  return defineTool(tool.toDSHToolDefinition());
}

export { DataManagerTool } from './DataManagerTool';
export { dataManagerPrompt } from './prompt';
export type { DataManagerParams, DataManagerResult } from './prompt';
