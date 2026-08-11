/**
 * 统一配置管理
 */
import { Model } from "@mariozechner/pi-ai";
import { join, dirname } from "path";
import { fileURLToPath } from "url";
import { BootstrapLoader } from "../services/intelligence/bootstrap-loader.js";
import { getRuntimeOverride, getRuntimeModelOverride } from "./model-switcher.js";

// 获取 agent-ts 根目录（无论从哪里运行都指向固定位置）
const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const AGENT_ROOT = join(__dirname, "../..");

// Bootstrap loader 实例 - 使用 agent-ts/.pi-invest
const _bootstrapLoader = new BootstrapLoader(join(AGENT_ROOT, ".pi-invest"));

/**
 * 获取 bootstrap 数据（每次重新加载，确保修改后立即生效）
 */
export function getBootstrapData(): Record<string, string> {
  return _bootstrapLoader.loadAll("full");
}

// 向后兼容：保留 bootstrapData 导出（但建议使用 getBootstrapData()）
// 注意：这个会在模块加载时缓存，修改文件后需要重启进程
export const bootstrapData = _bootstrapLoader.loadAll("full");

/**
 * LLM Provider 配置 —— 薄代理，转发到 services/llm 模块。
 * @deprecated 新代码直接用 services/llm 的 getLLM()；此处仅为向后兼容保留。
 *
 * 生效链（生产）：model-switcher 运行时 override（遗留/单测）
 *   > llm-state.json（state） > LLM_PROVIDER env > catalog 默认。
 */
import { getLLM } from "../services/llm/index.js";
import {
  buildModelConfig,
  envModelId,
  resolveModelTarget as catalogResolveModelTarget,
} from "../services/llm/catalog.js";
import { toSDKModel } from "../services/llm/adapters/pi-ai.js";
import type { LLMProviderName } from "../services/llm/types.js";

export type { LLMProviderName };

/**
 * 当前激活的 LLM provider
 * 优先级：遗留运行时 override（model-switcher，单测/旧路径） > llm 模块当前选择
 */
export function getActiveProvider(): LLMProviderName {
  return getRuntimeOverride() ?? getLLM().current().provider;
}

/** 当前激活 provider 的 API key（LLM_API_KEY > provider 专用 key > OPENAI_API_KEY） */
export function getActiveApiKey(): string {
  return getLLM().getModelConfig().apiKey;
}

/**
 * 当前激活的模型 ID
 * 遗留运行时模型 override（provider 匹配时）> 当前选择（provider 匹配时）> env 链
 */
export function getActiveModelId(): string {
  const provider = getActiveProvider();
  const runtimeModel = getRuntimeModelOverride();
  if (runtimeModel && runtimeModel.provider === provider) return runtimeModel.modelId;
  const sel = getLLM().current();
  if (sel.provider === provider) return sel.modelId;
  return envModelId(provider);
}

/** 可热切换的模型目标解析（flash/pro/完整模型 ID）；未知串返回 null */
export function resolveModelTarget(input: string): { provider: LLMProviderName; modelId: string } | null {
  return catalogResolveModelTarget(input);
}

/**
 * 模型配置 — 根据当前选择创建 SDK 模型
 * 遗留运行时 override 存在时按旧语义构造（单测/旧路径兼容）。
 */
export function createModel(): Model<'openai-completions'> {
  const override = getRuntimeOverride();
  if (override) {
    const runtimeModel = getRuntimeModelOverride();
    const modelId = runtimeModel && runtimeModel.provider === override
      ? runtimeModel.modelId
      : envModelId(override);
    return toSDKModel(buildModelConfig(override, modelId));
  }
  return getLLM().getSessionModel() as Model<'openai-completions'>;
}

/**
 * 路径配置
 * 所有路径现在相对于 agent-ts 根目录，而非当前工作目录
 */
export const paths = {
  root: AGENT_ROOT,
  piDir: join(AGENT_ROOT, ".pi-invest"),
  sessionsDir: join(AGENT_ROOT, ".pi-invest", "sessions"),
  sessionMapFile: join(AGENT_ROOT, ".pi-invest", "session-id-map.json"),
  skillsDir: join(AGENT_ROOT, "skills"),
  /** 插件目录列表：项目级 plugins/ 和用户本地 .pi-invest/plugins/ */
  pluginDirs: [
    join(AGENT_ROOT, "plugins"),
    join(AGENT_ROOT, ".pi-invest", "plugins"),
  ],
  /** 工具输出目录：存储工具生成的文件供 LLM 读取 */
  toolOutputsDir: join(AGENT_ROOT, ".pi-invest", "tool-outputs"),
};

/**
 * 压缩配置
 */
export const compactionConfig = {
  // 保留最近 N 个工具调用结果
  keepRecentToolResults: 3,
  // 工具结果超过此长度才压缩
  minLengthToCompact: 100,
};

/**
 * Agent 配置
 *
 * systemPrompt 现在是动态构建的，每轮由 agent-loop 调用 buildSystemPrompt()。
 * 工具指令从 .pi-invest/bootstrap/TOOLS.md 加载。
 */
export const agentConfig = {};

/**
 * Evolution 配置
 */
export const evolutionConfig = {
  // 是否启用自动代码生成（需要 Codex 账户余额充足）
  enableCodeGeneration: true,
  // Codex 超时时间（毫秒）
  codexTimeout: 120000,
};
