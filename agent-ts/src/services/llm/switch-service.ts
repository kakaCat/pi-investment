/**
 * 统一切换服务 —— /provider 命令与 model_switch 工具的唯一入口。
 * resolve → validate(key 已配置) → 持久化 → 审计日志。
 * （agent 侧 1 小时 3 次限流保留在 model_switch 工具层，不属于本服务。）
 */
import { appendFileSync, mkdirSync } from 'fs';
import { join } from 'path';
import type { LLMProviderName, SwitchResult } from './types.js';
import {
  envModelId,
  isProviderConfigured,
  PROVIDER_NAMES,
  resolveModelTarget,
  resolveProvider,
} from './catalog.js';
import { effectiveSelection, setSelection } from './selection.js';

export interface SwitchDeps {
  piDir: string;
  env?: NodeJS.ProcessEnv;
}

const MODEL_HINTS = ['flash', 'pro', 'deepseek-v4-flash', 'deepseek-v4-pro', 'kimi-k3'];

/** 解析切换目标：模型别名/完整模型 ID 优先，其次 provider 名（模型走 env 链） */
export function resolveSwitchTarget(
  input: string,
  env = process.env,
): { provider: LLMProviderName; modelId: string } | null {
  const modelTarget = resolveModelTarget(input);
  if (modelTarget) return modelTarget;
  const provider = resolveProvider(input);
  if (provider) return { provider, modelId: envModelId(provider, env) };
  return null;
}

export function switchLLM(
  input: string,
  by: 'human' | 'agent',
  deps: SwitchDeps,
): SwitchResult {
  const current = effectiveSelection(deps.env);
  const from = `${current.provider}:${current.modelId}`;

  const target = resolveSwitchTarget(input, deps.env);
  if (!target) {
    return {
      ok: false, changed: false, from, to: from,
      error: `未知目标 "${input}"，可选：${[...PROVIDER_NAMES, ...MODEL_HINTS].join(', ')}`,
    };
  }
  const to = `${target.provider}:${target.modelId}`;

  if (target.provider === current.provider && target.modelId === current.modelId) {
    return { ok: true, changed: false, from, to };
  }
  if (!isProviderConfigured(target.provider, deps.env)) {
    return {
      ok: false, changed: false, from, to,
      error: `${target.provider} 的 API key 未配置（检查 .env 的 ${target.provider.toUpperCase()}_API_KEY）`,
    };
  }

  const sel = setSelection(target.provider, target.modelId, by);
  appendSwitchLog(deps.piDir, { ts: sel.updatedAt, from, to, trigger: by });
  console.log(`[model-switch] ${sel.updatedAt} ${from} → ${to} (${by})`);
  return { ok: true, changed: true, from, to };
}

/** 审计日志：JSON 行追加到 .pi-invest/model-switch.log（格式与历史一致） */
function appendSwitchLog(
  piDir: string,
  entry: { ts: string; from: string; to: string; trigger: 'human' | 'agent' },
): void {
  try {
    mkdirSync(piDir, { recursive: true });
    appendFileSync(join(piDir, 'model-switch.log'), JSON.stringify(entry) + '\n');
  } catch {
    // 日志写失败不影响切换
  }
}
