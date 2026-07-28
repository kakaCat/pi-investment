/**
 * 统一配置管理
 */
import { Model } from "@mariozechner/pi-ai";
import { join, dirname } from "path";
import { fileURLToPath } from "url";
import { BootstrapLoader } from "../services/intelligence/bootstrap-loader.js";
import { getRuntimeOverride } from "./model-switcher.js";

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
 * LLM Provider 配置
 *
 * 通过 LLM_PROVIDER 环境变量切换模型提供方（默认 deepseek）。
 * 所有 provider 均走 OpenAI 兼容接口（api: 'openai-completions'），
 * 区别仅在于 baseUrl / apiKey / modelId / 上下文参数。
 */
export type LLMProviderName = 'deepseek' | 'kimi';

interface ProviderPreset {
  /** 展示名称 */
  name: string;
  baseUrl: string;
  /** 默认模型 ID（可被 MODEL_ID 覆盖） */
  modelId: string;
  /** API key 环境变量，按优先级依次尝试 */
  apiKeyEnv: string[];
  contextWindow: number;
  maxTokens: number;
  /** 是否按 reasoning 模型解析（思考内容单独返回） */
  reasoning: boolean;
  /** pi-ai SDK 兼容模式覆盖（见 providers/openai-completions.js getCompat） */
  compat?: {
    supportsDeveloperRole?: boolean;
    supportsStore?: boolean;
    maxTokensField?: 'max_tokens' | 'max_completion_tokens';
  };
}

const PROVIDER_PRESETS: Record<LLMProviderName, ProviderPreset> = {
  deepseek: {
    name: 'DeepSeek Chat',
    baseUrl: 'https://api.deepseek.com/v1',
    modelId: 'deepseek-chat',
    apiKeyEnv: ['DEEPSEEK_API_KEY', 'OPENAI_API_KEY'],
    contextWindow: 64000,
    maxTokens: 8000,
    reasoning: true, // DeepSeek支持reasoning，设为true避免解析错误
  },
  kimi: {
    name: 'Kimi (Moonshot)',
    baseUrl: 'https://api.moonshot.cn/v1',
    modelId: 'kimi-k3', // 可用 MODEL_ID 覆盖为具体版本（如 kimi-k3-xxxx-preview）
    apiKeyEnv: ['KIMI_API_KEY', 'MOONSHOT_API_KEY', 'OPENAI_API_KEY'],
    contextWindow: 256000,
    maxTokens: 8000,
    reasoning: true, // K3 为思考模型；若改用非思考模型可设 LLM_REASONING=false
    // api.kimi.com / 本地代理 不匹配 SDK 的 isMoonshot 检测（只认 api.moonshot.*），
    // 会被当作标准 OpenAI：reasoning=true 时 system prompt 以 role:"developer" 发送，
    // Kimi 端点不认识该 role，报 400 Invalid request: tokenization failed。
    // 这里显式按 Moonshot 兼容模式声明。⚠️ 勿删——已两次因丢失此配置出事故。
    compat: {
      supportsDeveloperRole: false,
      supportsStore: false,
      maxTokensField: 'max_tokens',
    },
  },
};

/**
 * LLM_PROVIDER 别名映射（小写）。常见误写兜底：
 * 把模型 ID（k3、kimi-k3、deepseek-chat 等）误填进 LLM_PROVIDER 时
 * 映射回正确 provider，避免静默回退 deepseek 导致"配置与实跑模型不一致"。
 */
const PROVIDER_ALIASES: Record<string, LLMProviderName> = {
  kimi: 'kimi',
  moonshot: 'kimi',
  k3: 'kimi',
  'kimi-k3': 'kimi',
  deepseek: 'deepseek',
  'deepseek-chat': 'deepseek',
  'deepseek-v4-pro': 'deepseek',
  'deepseek-reasoner': 'deepseek',
};

/**
 * 当前激活的 LLM provider
 * 优先级：运行时 override（/provider 命令或 model_switch 工具设置）
 *        > LLM_PROVIDER 环境变量（含别名） > 默认 deepseek
 */
export function getActiveProvider(): LLMProviderName {
  const override = getRuntimeOverride();
  if (override) return override;
  const p = (process.env.LLM_PROVIDER || 'deepseek').toLowerCase();
  const alias = PROVIDER_ALIASES[p];
  if (alias) {
    if (alias !== p) console.warn(`[config] LLM_PROVIDER="${p}" 按别名解析为 ${alias}`);
    return alias;
  }
  console.warn(`[config] 未知 LLM_PROVIDER="${p}"，回退到 deepseek（有效值：deepseek/kimi）`);
  return 'deepseek';
}

/**
 * 当前激活 provider 的 API key
 * 优先级：LLM_API_KEY > provider 专用 key 环境变量 > OPENAI_API_KEY
 */
export function getActiveApiKey(): string {
  const preset = PROVIDER_PRESETS[getActiveProvider()];
  return process.env.LLM_API_KEY
    || preset.apiKeyEnv.map((k) => process.env[k]).find(Boolean)
    || "";
}

/**
 * 当前激活的模型 ID
 * 优先级：{PROVIDER}_MODEL_ID（如 KIMI_MODEL_ID）> MODEL_ID > provider 默认值
 */
export function getActiveModelId(): string {
  const provider = getActiveProvider();
  return process.env[`${provider.toUpperCase()}_MODEL_ID`]
    || process.env.MODEL_ID
    || PROVIDER_PRESETS[provider].modelId;
}

/**
 * 模型配置 — 根据 LLM_PROVIDER 创建对应 provider 的模型
 *
 * 通用覆盖环境变量：
 * - LLM_API_KEY       覆盖任意 provider 的 key
 * - LLM_BASE_URL      覆盖任意 provider 的 baseUrl
 * - LLM_REASONING     "false" 关闭 reasoning 解析
 * - LLM_CONTEXT_WINDOW / LLM_MAX_TOKENS  覆盖上下文/输出上限
 */
export function createModel(): Model<'openai-completions'> {
  const provider = getActiveProvider();
  const preset = PROVIDER_PRESETS[provider];

  const apiKey = getActiveApiKey();

  // 关键：pi-ai SDK 不读取 model.apiKey，openai provider 的 key 只从
  // OPENAI_API_KEY 环境变量解析。这里把当前 provider 的 key 同步过去，
  // 否则切换 provider 后会带着旧 key 请求新端点（401 Invalid Authentication）。
  if (apiKey) {
    process.env.OPENAI_API_KEY = apiKey;
  }

  // 保留各 provider 自己的 BASE_URL 环境变量（如 DEEPSEEK_BASE_URL / KIMI_BASE_URL）
  const baseUrl = process.env.LLM_BASE_URL
    || process.env[`${provider.toUpperCase()}_BASE_URL`]
    || preset.baseUrl;
  const reasoning = process.env.LLM_REASONING
    ? process.env.LLM_REASONING !== 'false'
    : preset.reasoning;

  return {
    id: getActiveModelId(),
    name: preset.name,
    api: 'openai-completions',
    provider: 'openai',              // SDK 要求 openai provider 才能正确路由 key
    apiKey,
    baseUrl,                         // ← 始终显式设置，不依赖 SDK 默认值
    reasoning,
    input: ['text'],
    cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },
    ...(preset.compat ? { compat: preset.compat } : {}),
    contextWindow: Number(process.env.LLM_CONTEXT_WINDOW) || preset.contextWindow,
    maxTokens: Number(process.env.LLM_MAX_TOKENS) || preset.maxTokens,
    // HTTP超时配置 - 防止API调用卡死
    timeout: 120000,                 // 120秒超时
    maxRetries: 2                    // 失败后重试2次
  } as any;
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
