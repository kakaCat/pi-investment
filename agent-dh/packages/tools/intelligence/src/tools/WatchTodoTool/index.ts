/**
 * WatchTodoTool - 盯盘待办（闭环工单）工具导出（2026-10-16）
 */

import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { defineTool } from '@deepseek-ai/dsh-tools';
import { WatchTodoTool } from './WatchTodoTool';

/**
 * 创建盯盘待办工具实例（list / claim / close）
 */
export function createWatchTodoTool(qv2: QuantsysV2Client) {
  const tool = new WatchTodoTool(qv2);
  return defineTool(tool.toDSHToolDefinition());
}

export { WatchTodoTool, AGENT_REF } from './WatchTodoTool';
export type { WatchTodoParams } from './prompt';
