/**
 * 统一配置管理
 */
import { Model } from "@mariozechner/pi-ai";
import { join, dirname } from "path";
import { fileURLToPath } from "url";
import { BootstrapLoader } from "../services/intelligence/bootstrap-loader.js";

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
 * 模型配置
 */
export function createDeepSeekModel(): Model<'openai-completions'> {
  const baseUrl = process.env.DEEPSEEK_BASE_URL || 'https://api.deepseek.com/v1';
  const apiKey = process.env.DEEPSEEK_API_KEY || process.env.OPENAI_API_KEY;

  return {
    id: process.env.MODEL_ID || 'deepseek-chat',
    name: 'DeepSeek Chat',
    api: 'openai-completions',
    provider: 'openai',              // SDK 要求 openai provider 才能正确路由 key
    apiKey,
    baseUrl,                         // ← 始终显式设置，不依赖 SDK 默认值
    reasoning: true,                 // DeepSeek支持reasoning，设为true避免解析错误
    input: ['text'],
    cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },
    contextWindow: 64000,
    maxTokens: 8000,                 // 恢复到8000，真正问题是reasoning配置
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
