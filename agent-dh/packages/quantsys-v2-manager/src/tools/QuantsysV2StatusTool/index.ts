/**
 * QuantsysV2StatusTool - 状态检查工具导出
 */

import { defineTool } from '@deepseek-ai/dsh-tools';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { QuantsysV2StatusTool } from './QuantsysV2StatusTool';

/**
 * 创建 quantsys-v2 状态检查工具实例
 */
export function createQuantsysV2StatusTool(qv2: QuantsysV2Client) {
  const tool = new QuantsysV2StatusTool(qv2);
  return defineTool(tool.toDSHToolDefinition());
}

export { QuantsysV2StatusTool } from './QuantsysV2StatusTool';
export { quantsysV2StatusPrompt } from './prompt';
export type { QuantsysV2StatusParams, QuantsysV2StatusResult } from './prompt';
