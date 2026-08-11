/**
 * 模型 Provider 运行时切换状态
 *
 * @deprecated 生产切换已迁移到 services/llm/switch-service.ts（持久化到
 * llm-state.json）。本模块仅保留为 config.ts 薄代理的遗留运行时
 * override 层与单测兼容。
 *
 * LLM_PROVIDER 环境变量决定启动时的 provider；本模块提供进程内
 * 热切换能力（仅内存，重启后回到环境变量）。
 *
 * config.ts 的 getActiveProvider() 优先读这里的 override。
 * 切换入口：/provider 斜杠命令（人）、model_switch 工具（agent）。
 */
import { appendFileSync, mkdirSync } from "fs";
import { join, dirname } from "path";
import { fileURLToPath } from "url";

export type RuntimeProviderName = "deepseek" | "kimi";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const AGENT_ROOT = join(__dirname, "../..");
const SWITCH_LOG_DIR = join(AGENT_ROOT, ".pi-invest");
const SWITCH_LOG_FILE = join(SWITCH_LOG_DIR, "model-switch.log");

/**
 * 各 provider 的专用 key 环境变量（用于"是否已配置"判断）。
 * 故意不包含 OPENAI_API_KEY：createModel() 会把当前 provider 的 key
 * 同步到 OPENAI_API_KEY，包含它会让另一 provider 出现"假已配置"。
 */
const PROVIDER_KEY_ENV: Record<RuntimeProviderName, string[]> = {
  deepseek: ["DEEPSEEK_API_KEY"],
  kimi: ["KIMI_API_KEY", "MOONSHOT_API_KEY"],
};

let runtimeProvider: RuntimeProviderName | null = null;

/**
 * 模型粒度 override（如 deepseek-v4-flash ↔ deepseek-v4-pro）。
 * 记录所属 provider：provider 切走后旧模型 override 不得泄漏
 * （getActiveModelId 只在 provider 匹配时采用）。
 */
let runtimeModel: { provider: RuntimeProviderName; modelId: string } | null = null;

/** 当前运行时 override；null 表示未切换过（用 LLM_PROVIDER 环境变量） */
export function getRuntimeOverride(): RuntimeProviderName | null {
  return runtimeProvider;
}

export function setRuntimeProvider(p: RuntimeProviderName): void {
  runtimeProvider = p;
}

/** 当前运行时模型 override；null 表示未设置 */
export function getRuntimeModelOverride(): { provider: RuntimeProviderName; modelId: string } | null {
  return runtimeModel;
}

export function setRuntimeModelOverride(p: RuntimeProviderName, modelId: string): void {
  runtimeProvider = p;
  runtimeModel = { provider: p, modelId };
}

/** 仅测试使用：清除运行时 override */
export function resetRuntimeProviderForTests(): void {
  runtimeProvider = null;
  runtimeModel = null;
}

/** 目标 provider 的 API key 是否已配置（LLM_API_KEY 通用覆盖也算） */
export function isProviderConfigured(p: RuntimeProviderName): boolean {
  if (process.env.LLM_API_KEY) return true;
  return PROVIDER_KEY_ENV[p].some((k) => !!process.env[k]);
}

export interface ProviderInfo {
  name: RuntimeProviderName;
  configured: boolean;
}

export function listProviders(): ProviderInfo[] {
  return (Object.keys(PROVIDER_KEY_ENV) as RuntimeProviderName[]).map((name) => ({
    name,
    configured: isProviderConfigured(name),
  }));
}

/** 切换审计日志：JSON 行追加到 .pi-invest/model-switch.log，同时打 console */
export function logSwitch(
  from: string,
  to: string,
  trigger: "human" | "agent"
): void {
  const entry = { ts: new Date().toISOString(), from, to, trigger };
  console.log(`[model-switch] ${entry.ts} ${from} → ${to} (${trigger})`);
  try {
    mkdirSync(SWITCH_LOG_DIR, { recursive: true });
    appendFileSync(SWITCH_LOG_FILE, JSON.stringify(entry) + "\n");
  } catch {
    // 日志写失败不影响切换
  }
}
