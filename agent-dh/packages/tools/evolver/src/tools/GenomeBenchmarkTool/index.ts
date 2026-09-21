/**
 * GenomeBenchmarkTool - 候选健康检查工具（L4-B benchmark 静态腿）
 */

import type { Context } from '@deepseek-ai/cordis';
import { defineTool } from '@deepseek-ai/dsh-tools';
import { GenomeBenchmarkTool } from './GenomeBenchmarkTool';

export { genomeBenchmarkPrompt } from './prompt';
export type { GenomeBenchmarkParams, GenomeBenchmarkResult } from './prompt';
export { GenomeBenchmarkTool } from './GenomeBenchmarkTool';

/**
 * 创建 DSH 工具
 */
export function createGenomeBenchmarkTool(ctx: Context) {
  const tool = new GenomeBenchmarkTool(ctx);
  return defineTool(tool.toDSHToolDefinition() as any);
}
