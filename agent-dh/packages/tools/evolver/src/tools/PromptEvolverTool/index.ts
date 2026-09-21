/**
 * PromptEvolverTool - 提示词进化工具
 */

import type { Context } from '@deepseek-ai/cordis';
import { defineTool } from '@deepseek-ai/dsh-tools';
import type { OsMemoryStore } from '../../index';
import { PromptEvolverTool } from './PromptEvolverTool';

export { promptEvolverPrompt } from './prompt';
export type { PromptEvolverParams, PromptEvolverResult } from './prompt';
export { PromptEvolverTool } from './PromptEvolverTool';

/**
 * 创建 DSH 工具
 */
export function createPromptEvolverTool(
  ctx: Context,
  osMemory: OsMemoryStore,
  llmProvider: string,
  llmModel: string,
  observeDays: number
) {
  const tool = new PromptEvolverTool(ctx, osMemory, llmProvider, llmModel, observeDays);
  return defineTool(tool.toDSHToolDefinition() as any);
}
