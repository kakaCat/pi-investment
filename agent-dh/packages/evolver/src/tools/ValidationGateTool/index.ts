/**
 * ValidationGateTool - 验证门工具
 */

import type { Context } from '@deepseek-ai/cordis';
import { defineTool } from '@deepseek-ai/dsh-tools';
import type { OsMemoryStore } from '../../index';
import { ValidationGateTool } from './ValidationGateTool';

export { validationGatePrompt } from './prompt';
export type { ValidationGateParams, ValidationGateResult } from './prompt';
export { ValidationGateTool } from './ValidationGateTool';

/**
 * 创建 DSH 工具
 */
export function createValidationGateTool(
  ctx: Context,
  osMemory: OsMemoryStore,
  observeDays: number
) {
  const tool = new ValidationGateTool(ctx, osMemory, observeDays);
  return defineTool(tool.toDSHToolDefinition() as any);
}
