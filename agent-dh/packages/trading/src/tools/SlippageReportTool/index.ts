/**
 * SlippageReportTool - 滑点报告工具
 */

import { defineTool } from '@deepseek-ai/dsh-tools';
import { SlippageReportTool } from './SlippageReportTool';

export { slippageReportPrompt } from './prompt';
export type { SlippageReportParams, SlippageReportResult } from './prompt';
export { SlippageReportTool } from './SlippageReportTool';

// OsMemoryStore 类型（简化）
interface OsMemoryStore {
  search(params: { query: string; namespace: string; top_k?: number }): Promise<any>;
}

/**
 * 创建 DSH 工具
 */
export function createSlippageReportTool(osMemory: OsMemoryStore) {
  const tool = new SlippageReportTool(osMemory);
  return defineTool(tool.toDSHToolDefinition() as any);
}
