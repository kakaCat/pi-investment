/**
 * SignalTrackTool - M3-1 信号质量追踪工具导出
 */

import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { defineTool } from '@deepseek-ai/dsh-tools';
import { SignalTrackTool } from './SignalTrackTool';

/**
 * 创建 M3-1 信号质量追踪工具实例
 */
export function createSignalTrackTool(qv2: QuantsysV2Client) {
  const tool = new SignalTrackTool(qv2);
  return defineTool(tool.toDSHToolDefinition());
}

export { SignalTrackTool } from './SignalTrackTool';
export type { SignalTrackParams, SignalTrackResult } from './prompt';
