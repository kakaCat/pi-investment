/**
 * WeeklyReportTool - M6 学习飞轮周报工具
 */

import { defineTool } from '@deepseek-ai/dsh-tools';
import { WeeklyReportTool } from './WeeklyReportTool';

export { weeklyReportPrompt } from './prompt';
export type { WeeklyReportParams, WeeklyReportResult } from './prompt';
export { WeeklyReportTool } from './WeeklyReportTool';

/**
 * 创建 DSH 工具
 */
export function createWeeklyReportTool(baseURL: string) {
  const tool = new WeeklyReportTool(baseURL);
  return defineTool(tool.toDSHToolDefinition() as any);
}
