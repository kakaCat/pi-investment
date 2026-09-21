/**
 * SlippageReportTool - 滑点报告工具
 */

import { defineTool } from '@deepseek-ai/dsh-tools';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import type { OsMemoryStore } from '../../index';
import { SlippageReportTool } from './SlippageReportTool';

export { slippageReportPrompt } from './prompt';
export type { SlippageReportParams, SlippageReportResult } from './prompt';
export { SlippageReportTool } from './SlippageReportTool';

/**
 * 创建 DSH 工具
 */
export function createSlippageReportTool(qv2: QuantsysV2Client, osMemory: OsMemoryStore) {
  const tool = new SlippageReportTool(qv2, osMemory);
  return defineTool(tool.toDSHToolDefinition() as any);
}
