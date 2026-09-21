/**
 * WatchManageTool - 盯盘规则管理工具导出
 */

import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { defineTool } from '@deepseek-ai/dsh-tools';
import { WatchManageTool } from './WatchManageTool';

/**
 * 创建盯盘规则管理工具实例
 */
export function createWatchManageTool(qv2: QuantsysV2Client) {
  const tool = new WatchManageTool(qv2);
  return defineTool(tool.toDSHToolDefinition());
}

export { WatchManageTool } from './WatchManageTool';
export type { WatchManageParams, WatchManageResult } from './prompt';
