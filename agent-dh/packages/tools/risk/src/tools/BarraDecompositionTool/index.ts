/**
 * BarraDecompositionTool - Barra风险分解工具导出
 */

import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { defineTool } from '@deepseek-ai/dsh-tools';
import { BarraDecompositionTool } from './BarraDecompositionTool';

/**
 * 创建Barra风险分解工具实例
 */
export function createBarraDecompositionTool(qv2: QuantsysV2Client) {
  const tool = new BarraDecompositionTool(qv2);
  return defineTool(tool.toDSHToolDefinition());
}

export { BarraDecompositionTool } from './BarraDecompositionTool';
export type { BarraDecompositionParams, BarraDecompositionResult } from './prompt';
