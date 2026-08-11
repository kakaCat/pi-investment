/**
 * LLM 自有类型体系 —— 禁止 import 任何 SDK 类型。
 * agent 世界（agent loop / 工具 / 命令）只依赖本文件与 port.ts。
 */

export type LLMProviderName = 'deepseek' | 'kimi';

export interface LLMCompat {
  supportsDeveloperRole?: boolean;
  supportsStore?: boolean;
  maxTokensField?: 'max_tokens' | 'max_completion_tokens';
}

/** 已解析完成的模型配置（凭证/端点已合成终值） */
export interface LLMModelConfig {
  provider: LLMProviderName;
  modelId: string;
  displayName: string;
  baseUrl: string;
  apiKey: string;
  contextWindow: number;
  maxTokens: number;
  reasoning: boolean;
  compat?: LLMCompat;
  timeoutMs: number;
  maxRetries: number;
}

export interface ChatMessage {
  role: 'system' | 'user' | 'assistant';
  content: string;
}

export interface ChatRequest {
  messages: ChatMessage[];
  maxTokens?: number;
  temperature?: number;
}

export interface Usage {
  input: number;
  output: number;
  totalTokens: number;
}

export interface ChatResponse {
  text: string;
  usage: Usage;
  model: string;
}

export type LLMErrorKind =
  | 'auth'
  | 'rate_limit'
  | 'overloaded'
  | 'timeout'
  | 'invalid_request'
  | 'unknown';

export class LLMError extends Error {
  readonly kind: LLMErrorKind;
  readonly retryable: boolean;
  constructor(message: string, kind: LLMErrorKind = 'unknown', retryable = false) {
    super(message);
    this.name = 'LLMError';
    this.kind = kind;
    this.retryable = retryable;
  }
}

/** 当前选择来源：state 文件 > env > 默认 */
export type SelectionSource = 'state' | 'env' | 'default';

export interface LLMSelection {
  provider: LLMProviderName;
  modelId: string;
  updatedBy: 'human' | 'agent' | 'env' | 'default';
  updatedAt: string; // ISO
  version: number;   // 单调递增，惰性生效比对用
}

export interface SwitchResult {
  ok: boolean;
  changed: boolean;
  from: string; // 'provider:modelId'
  to: string;
  error?: string;
}

export interface LLMProviderStatus {
  name: LLMProviderName;
  configured: boolean;
  active: boolean;
  modelId: string;
}

export interface LLMStatus {
  current: LLMSelection;
  source: SelectionSource;
  providers: LLMProviderStatus[];
}
