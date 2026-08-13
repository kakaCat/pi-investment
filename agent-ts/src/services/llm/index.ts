/**
 * llm 模块组合根。
 * 启动引导调用 initLLM(piDir)；旧调用方可直接用 getLLM()（惰性单例，
 * 未初始化时 selection 回退 env/default，保证向后兼容）。
 */
import { dirname, join } from 'path';
import { fileURLToPath } from 'url';
import { buildModelConfig, envModelId, isProviderConfigured, PROVIDER_NAMES, resolveModelTarget } from './catalog.js';
import { complete as clientComplete } from './client.js';
import { toSDKModel } from './adapters/pi-ai.js';
import type { LLMPort } from './port.js';
import {
  effectiveSelection,
  initSelection,
  onSelectionChange,
  resetSelectionForTests,
  selectionSource,
} from './selection.js';
import { switchLLM } from './switch-service.js';
import type { ChatRequest, ChatResponse, LLMModelConfig, LLMStatus, SwitchResult } from './types.js';

const __filename = fileURLToPath(import.meta.url);
const AGENT_ROOT = join(dirname(__filename), '../../..');
const DEFAULT_PI_DIR = join(AGENT_ROOT, '.pi-invest');

let port: LLMPort | null = null;

export function initLLM(piDir: string = DEFAULT_PI_DIR): LLMPort {
  if (port) return port; // 幂等：多入口点（index.ts/api.index.ts）重复调用不重置选择
  initSelection(piDir);
  port = createPort(piDir);
  return port;
}

export function getLLM(): LLMPort {
  if (!port) port = createPort(DEFAULT_PI_DIR);
  return port;
}

/** 仅测试使用 */
export function resetLLMForTests(): void {
  port = null;
  resetSelectionForTests();
}

/**
 * 会话级模型档位解析（三 Agent 拆分 A0-T3）。
 *
 * 不经 llm-state.json（全局选择）——按「档位」临时合成一份会话模型配置：
 * - 'inherit' → 当前全局选择（fin，model_switch 现状保留）
 * - 'pro'     → deepseek-v4-pro（evolution，改代码要强度）
 * - 'flash'   → deepseek-v4-flash（memory，初标是体力活）
 *
 * 档位 → 具体模型 ID 走 catalog.resolveModelTarget（与 model_switch 别名同源）。
 */
export function getSessionModelFor(
  preference: 'flash' | 'pro' | 'inherit' = 'inherit',
): unknown {
  const llm = getLLM();
  if (preference === 'inherit') return llm.getSessionModel();
  const target = resolveModelTarget(preference);
  if (!target) return llm.getSessionModel();
  return toSDKModel(buildModelConfig(target.provider, target.modelId));
}

function createPort(piDir: string): LLMPort {
  const config = (): LLMModelConfig => {
    const sel = effectiveSelection();
    return buildModelConfig(sel.provider, sel.modelId);
  };
  return {
    current: () => effectiveSelection(),
    source: () => selectionSource(),
    getModelConfig: config,
    getSessionModel: () => toSDKModel(config()),
    complete: (req: ChatRequest): Promise<ChatResponse> => clientComplete(config(), req),
    switch: (target, by): SwitchResult => switchLLM(target, by, { piDir }),
    status: (): LLMStatus => {
      const sel = effectiveSelection();
      return {
        current: sel,
        source: selectionSource(),
        providers: PROVIDER_NAMES.map((name) => ({
          name,
          configured: isProviderConfigured(name),
          active: name === sel.provider,
          modelId: name === sel.provider ? sel.modelId : envModelId(name),
        })),
      };
    },
    onChange: (cb) => onSelectionChange(cb),
  };
}
