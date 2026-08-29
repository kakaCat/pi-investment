/**
 * QuantsysV2RestartTool - 重启工具导出
 */

import { defineTool } from '@deepseek-ai/dsh-tools';
import { QuantsysV2RestartTool } from './QuantsysV2RestartTool';
import type { QuantsysV2Config } from '../QuantsysV2StatusTool';

/**
 * 创建 quantsys-v2 重启工具实例
 */
export function createQuantsysV2RestartTool(config: QuantsysV2Config) {
  const tool = new QuantsysV2RestartTool(config);
  return defineTool(tool.toDSHToolDefinition());
}

export { QuantsysV2RestartTool } from './QuantsysV2RestartTool';
export { quantsysV2RestartPrompt } from './prompt';
export type { QuantsysV2RestartParams, QuantsysV2RestartResult } from './prompt';
