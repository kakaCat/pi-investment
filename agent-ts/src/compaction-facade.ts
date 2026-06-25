/**
 * Compaction Facade — 封装 estimateTokens / generateSummary
 *
 * SDK 变更这些函数签名时，只需修改此文件。
 */

import {
  estimateTokens as sdkEstimateTokens,
  generateSummary as sdkGenerateSummary,
} from "@mariozechner/pi-coding-agent";

/**
 * 估算消息的 token 数量
 */
export function estimateTokens(message: unknown): number {
  return sdkEstimateTokens(message as any);
}

/**
 * 生成对话摘要（用于上下文压缩）
 * 参数透传给 SDK，签名变更仅影响此文件
 */
export async function generateSummary(...args: any[]): Promise<void> {
  await (sdkGenerateSummary as any)(...args);
}
