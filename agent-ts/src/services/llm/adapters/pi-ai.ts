/**
 * pi-ai SDK 适配器 —— llm 模块内唯一允许 import pi-ai 的文件。
 * 全部 SDK 怪癖封装在此：
 * 1) SDK 不读 model.apiKey，openai provider 的 key 只从 OPENAI_API_KEY
 *    环境变量解析 → 这里把当前 provider 的 key 同步过去（否则切 provider
 *    后带着旧 key 请求新端点，401 Invalid Authentication）。
 * 2) kimi compat（supportsDeveloperRole=false 等）透传——两次事故教训。
 */
import type { Model } from '@mariozechner/pi-ai';
import type { LLMModelConfig } from '../types.js';

export function toSDKModel(config: LLMModelConfig): Model<'openai-completions'> {
  if (config.apiKey) {
    process.env.OPENAI_API_KEY = config.apiKey;
  }
  return {
    id: config.modelId,
    name: config.displayName,
    api: 'openai-completions',
    provider: 'openai',
    apiKey: config.apiKey,
    baseUrl: config.baseUrl,
    reasoning: config.reasoning,
    input: ['text'],
    cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },
    ...(config.compat ? { compat: config.compat } : {}),
    contextWindow: config.contextWindow,
    maxTokens: config.maxTokens,
    timeout: config.timeoutMs,
    maxRetries: config.maxRetries,
  } as any;
}
