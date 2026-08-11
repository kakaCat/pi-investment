/**
 * Provider 目录：代码内置 presets + env 合成（自 config.ts 迁入，数值逐字保留）。
 *
 * 所有 provider 均走 OpenAI 兼容接口；.env 是所有 provider 的"配置目录"
 * （凭证/端点/模型覆盖），启动时由本模块合成为内存配置。
 */
import type { LLMCompat, LLMModelConfig, LLMProviderName } from './types.js';

export interface ProviderPreset {
  name: string;
  baseUrl: string;
  modelId: string;
  apiKeyEnv: string[];
  contextWindow: number;
  maxTokens: number;
  reasoning: boolean;
  compat?: LLMCompat;
}

export const PROVIDER_PRESETS: Record<LLMProviderName, ProviderPreset> = {
  deepseek: {
    name: 'DeepSeek Chat',
    baseUrl: 'https://api.deepseek.com/v1',
    // 官方模型列表现仅 deepseek-v4-flash / deepseek-v4-pro（deepseek-chat 为遗留别名）。
    modelId: 'deepseek-v4-flash',
    apiKeyEnv: ['DEEPSEEK_API_KEY', 'OPENAI_API_KEY'],
    // v4 全系实际上下文 1M / 最大输出 384K。这里按 128K 工作窗口配置：
    // agent 每轮全量重发上下文，窗口越大单轮成本越高；需要长上下文时
    // 用 LLM_CONTEXT_WINDOW 覆盖（上限 1048576）。
    contextWindow: 128000,
    maxTokens: 8000,
    reasoning: true,
  },
  kimi: {
    name: 'Kimi (Moonshot)',
    baseUrl: 'https://api.moonshot.cn/v1',
    modelId: 'kimi-k3',
    apiKeyEnv: ['KIMI_API_KEY', 'MOONSHOT_API_KEY', 'OPENAI_API_KEY'],
    contextWindow: 256000,
    maxTokens: 8000,
    reasoning: true,
    // api.kimi.com / 本地代理 不匹配 SDK 的 isMoonshot 检测（只认 api.moonshot.*），
    // 会被当作标准 OpenAI：reasoning=true 时 system prompt 以 role:"developer" 发送，
    // Kimi 端点不认识该 role，报 400 Invalid request: tokenization failed。
    // ⚠️ 勿删——已两次因丢失此配置出事故。
    compat: {
      supportsDeveloperRole: false,
      supportsStore: false,
      maxTokensField: 'max_tokens',
    },
  },
};

export const PROVIDER_NAMES = Object.keys(PROVIDER_PRESETS) as LLMProviderName[];

/** LLM_PROVIDER 常见误写兜底（模型 ID 误填进 provider 时映射回正确 provider） */
const PROVIDER_ALIASES: Record<string, LLMProviderName> = {
  kimi: 'kimi',
  moonshot: 'kimi',
  k3: 'kimi',
  'kimi-k3': 'kimi',
  deepseek: 'deepseek',
  'deepseek-chat': 'deepseek',
  'deepseek-v4-flash': 'deepseek',
  'deepseek-v4-pro': 'deepseek',
  'deepseek-reasoner': 'deepseek',
};

export function resolveProvider(input: string): LLMProviderName | null {
  return PROVIDER_ALIASES[input.trim().toLowerCase()] ?? null;
}

/** 可热切换的模型目标（短别名 + 完整模型 ID）；provider 名/未知串返回 null */
const MODEL_TARGETS: Record<string, { provider: LLMProviderName; modelId: string }> = {
  flash: { provider: 'deepseek', modelId: 'deepseek-v4-flash' },
  pro: { provider: 'deepseek', modelId: 'deepseek-v4-pro' },
  'deepseek-v4-flash': { provider: 'deepseek', modelId: 'deepseek-v4-flash' },
  'deepseek-v4-pro': { provider: 'deepseek', modelId: 'deepseek-v4-pro' },
  'kimi-k3': { provider: 'kimi', modelId: 'kimi-k3' },
  k3: { provider: 'kimi', modelId: 'kimi-k3' },
};

export function resolveModelTarget(
  input: string,
): { provider: LLMProviderName; modelId: string } | null {
  return MODEL_TARGETS[input.trim().toLowerCase()] ?? null;
}

/**
 * 各 provider 的专用 key 环境变量（用于"是否已配置"判断）。
 * 故意不包含 OPENAI_API_KEY：adapter 会把当前 provider 的 key 同步到
 * OPENAI_API_KEY，包含它会让另一 provider 出现"假已配置"。
 */
const PROVIDER_KEY_ENV: Record<LLMProviderName, string[]> = {
  deepseek: ['DEEPSEEK_API_KEY'],
  kimi: ['KIMI_API_KEY', 'MOONSHOT_API_KEY'],
};

export function isProviderConfigured(p: LLMProviderName, env = process.env): boolean {
  if (env.LLM_API_KEY) return true;
  return PROVIDER_KEY_ENV[p].some((k) => !!env[k]);
}

export function resolveApiKey(provider: LLMProviderName, env = process.env): string {
  const preset = PROVIDER_PRESETS[provider];
  return env.LLM_API_KEY || preset.apiKeyEnv.map((k) => env[k]).find(Boolean) || '';
}

/** env 链模型解析：{PROVIDER}_MODEL_ID > MODEL_ID > preset 默认 */
export function envModelId(provider: LLMProviderName, env = process.env): string {
  return (
    env[`${provider.toUpperCase()}_MODEL_ID`] ||
    env.MODEL_ID ||
    PROVIDER_PRESETS[provider].modelId
  );
}

/** 合成最终模型配置：preset 为底，LLM_* / {PROVIDER}_* env 覆盖 */
export function buildModelConfig(
  provider: LLMProviderName,
  modelId: string,
  env = process.env,
): LLMModelConfig {
  const preset = PROVIDER_PRESETS[provider];
  return {
    provider,
    modelId,
    displayName: preset.name,
    baseUrl:
      env.LLM_BASE_URL || env[`${provider.toUpperCase()}_BASE_URL`] || preset.baseUrl,
    apiKey: resolveApiKey(provider, env),
    contextWindow: Number(env.LLM_CONTEXT_WINDOW) || preset.contextWindow,
    maxTokens: Number(env.LLM_MAX_TOKENS) || preset.maxTokens,
    reasoning: env.LLM_REASONING ? env.LLM_REASONING !== 'false' : preset.reasoning,
    ...(preset.compat ? { compat: preset.compat } : {}),
    timeoutMs: 120000,
    maxRetries: 2,
  };
}
