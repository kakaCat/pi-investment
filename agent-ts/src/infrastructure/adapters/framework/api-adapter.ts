/**
 * API Adapter
 *
 * 封装对后端 API 的调用，处理参数类型转换
 * 主要适配 runQuantV2 的新签名
 */

import type { QuantAPIParams, QuantAPIResponse } from './types.js';

/**
 * 调用 QuantV2 API（适配层）
 *
 * 旧签名: runQuantV2(module: string, action: string, params: any)
 * 新签名: runQuantV2(command: string, params: Record<string, unknown>)
 *
 * @param module API 模块名（如 "benchmark", "sector"）
 * @param action API 操作名（如 "compare", "aggregate"）
 * @param params 请求参数
 * @returns API 响应
 */
export async function callQuantAPI<T = unknown>(
  module: string,
  action: string,
  params: QuantAPIParams = {}
): Promise<QuantAPIResponse<T>> {
  // 动态导入 runQuantV2，避免循环依赖
  const { runQuantV2 } = await import('../quant/quant-v2-client.js');

  // 将 module.action 格式转换为 command
  const command = `${module}.${action}`;

  // 确保 params 是 Record<string, unknown> 类型
  const normalizedParams: Record<string, unknown> = { ...params };

  // 调用新的 runQuantV2 API
  const result = await runQuantV2<T>(command, normalizedParams);

  // 确保返回值包含 success 字段
  return result as unknown as QuantAPIResponse<T>;
}

/**
 * 直接调用 runQuantV2（使用 command 格式）
 *
 * @param command 命令格式（如 "stock.list", "market.overview"）
 * @param params 请求参数
 * @returns API 响应
 */
export async function callQuantCommand<T = unknown>(
  command: string,
  params: QuantAPIParams = {}
): Promise<QuantAPIResponse<T>> {
  const { runQuantV2 } = await import('../quant/quant-v2-client.js');
  const normalizedParams: Record<string, unknown> = { ...params };
  const result = await runQuantV2<T>(command, normalizedParams);
  return result as unknown as QuantAPIResponse<T>;
}
