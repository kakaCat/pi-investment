/**
 * 当前 LLM 选择（provider + modelId）——持久化与优先级链。
 *
 * 优先级：state 文件（.pi-invest/llm-state.json） > LLM_PROVIDER env > catalog 默认。
 *
 * 显式初始化：启动引导必须调用 initSelection(piDir)；未初始化时
 * effectiveSelection() 回退 env/default —— 保证既有单测不读真实 state 文件。
 */
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'fs';
import { join } from 'path';
import type { LLMProviderName, LLMSelection, SelectionSource } from './types.js';
import { envModelId, resolveProvider } from './catalog.js';

export const STATE_FILE_NAME = 'llm-state.json';

interface SelectionState {
  piDir: string;
  selection: LLMSelection;
  source: SelectionSource;
  listeners: Array<(s: LLMSelection) => void>;
}

let state: SelectionState | null = null;

function envSelection(env = process.env): { selection: LLMSelection; source: SelectionSource } {
  const raw = (env.LLM_PROVIDER || '').toLowerCase();
  let provider: LLMProviderName = 'deepseek';
  let source: SelectionSource = 'default';
  if (raw) {
    const alias = resolveProvider(raw);
    if (alias) {
      provider = alias;
      source = 'env';
      if (alias !== raw) console.warn(`[llm] LLM_PROVIDER="${raw}" 按别名解析为 ${alias}`);
    } else {
      console.warn(`[llm] 未知 LLM_PROVIDER="${raw}"，回退 deepseek`);
    }
  }
  return {
    selection: {
      provider,
      modelId: envModelId(provider, env),
      updatedBy: source === 'env' ? 'env' : 'default',
      updatedAt: new Date(0).toISOString(),
      version: 0,
    },
    source,
  };
}

function readStateFile(piDir: string): LLMSelection | null {
  const file = join(piDir, STATE_FILE_NAME);
  try {
    if (!existsSync(file)) return null;
    const parsed = JSON.parse(readFileSync(file, 'utf8'));
    const provider = typeof parsed?.provider === 'string' ? resolveProvider(parsed.provider) : null;
    if (!provider || typeof parsed?.modelId !== 'string') {
      console.warn(`[llm] ${STATE_FILE_NAME} 内容非法，回退 env/default`);
      return null;
    }
    return {
      provider,
      modelId: parsed.modelId,
      updatedBy: parsed.updatedBy === 'agent' ? 'agent' : 'human',
      updatedAt: typeof parsed.updatedAt === 'string' ? parsed.updatedAt : new Date().toISOString(),
      version: Number(parsed.version) || 1,
    };
  } catch (e) {
    console.warn(`[llm] ${STATE_FILE_NAME} 读取失败（回退 env/default）:`, (e as Error).message);
    return null;
  }
}

export function initSelection(piDir: string, env = process.env): LLMSelection {
  const fromFile = readStateFile(piDir);
  const base = envSelection(env);
  state = {
    piDir,
    selection: fromFile ?? base.selection,
    source: fromFile ? 'state' : base.source,
    listeners: [],
  };
  return state.selection;
}

export function isSelectionInitialized(): boolean {
  return state !== null;
}

/** 已初始化时返回当前选择；未初始化返回 null */
export function getSelection(): LLMSelection | null {
  return state?.selection ?? null;
}

/** 当前生效选择（未初始化时回退 env/default） */
export function effectiveSelection(env = process.env): LLMSelection {
  return state?.selection ?? envSelection(env).selection;
}

export function selectionSource(env = process.env): SelectionSource {
  return state?.source ?? envSelection(env).source;
}

export function setSelection(
  provider: LLMProviderName,
  modelId: string,
  updatedBy: 'human' | 'agent',
): LLMSelection {
  if (!state) throw new Error('selection 未初始化：先调用 initSelection(piDir)');
  const next: LLMSelection = {
    provider,
    modelId,
    updatedBy,
    updatedAt: new Date().toISOString(),
    version: state.selection.version + 1,
  };
  state.selection = next;
  state.source = 'state';
  mkdirSync(state.piDir, { recursive: true });
  writeFileSync(join(state.piDir, STATE_FILE_NAME), JSON.stringify(next, null, 2) + '\n');
  for (const cb of state.listeners) cb(next);
  return next;
}

export function onSelectionChange(cb: (s: LLMSelection) => void): void {
  if (!state) throw new Error('selection 未初始化：先调用 initSelection(piDir)');
  state.listeners.push(cb);
}

/** 仅测试使用 */
export function resetSelectionForTests(): void {
  state = null;
}
