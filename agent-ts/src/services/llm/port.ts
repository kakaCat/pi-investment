/**
 * LLMPort —— agent 世界依赖的唯一抽象。
 * 依赖规则：agent loop / session-factory / 工具 / 命令 只允许 import
 * 本文件与 types.ts；禁止 import adapters/pi-ai.ts。
 */
import type {
  ChatRequest,
  ChatResponse,
  LLMModelConfig,
  LLMSelection,
  LLMStatus,
  SelectionSource,
  SwitchResult,
} from './types.js';

export interface LLMPort {
  /** 当前选择（含版本号） */
  current(): LLMSelection;
  /** 当前选择来源：state / env / default */
  source(): SelectionSource;
  /** 自有模型配置（可不透明传递） */
  getModelConfig(): LLMModelConfig;
  /** 给 SDK 会话的模型句柄（内部经 adapter，调用方不理解其结构） */
  getSessionModel(): unknown;
  /** 一次性 LLM 调用（plan agents 等直接调用方使用） */
  complete(req: ChatRequest): Promise<ChatResponse>;
  /** 统一切换入口（/provider 与 model_switch 共用） */
  switch(target: string, by: 'human' | 'agent'): SwitchResult;
  /** 各 provider 配置状态 + 当前选择 */
  status(): LLMStatus;
  /** 选择变化监听（惰性生效钩子） */
  onChange(cb: (s: LLMSelection) => void): void;
}
