/**
 * WatchListTool - 盯盘规则列表工具导出
 */

import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { defineTool } from '@deepseek-ai/dsh-tools';
import { WatchListTool } from './WatchListTool';

/**
 * 创建盯盘规则列表工具实例
 */
export function createWatchListTool(qv2: QuantsysV2Client) {
  const tool = new WatchListTool(qv2);
  return defineTool(tool.toDSHToolDefinition());
}

export { WatchListTool } from './WatchListTool';
export type { WatchListParams } from './prompt';
