/**
 * llm 模块组合根。
 * 启动引导调用 initLLM(piDir)；旧调用方可直接用 getLLM()（惰性单例，
 * 未初始化时 selection 回退 env/default，保证向后兼容）。
 */
import { dirname, join } from 'path';
import { fileURLToPath } from 'url';
import { buildModelConfig, envModelId, isProviderConfigured, PROVIDER_NAMES } from './catalog.js';
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
