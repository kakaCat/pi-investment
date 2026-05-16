/**
 * 统一配置管理
 */
import { Model } from "@mariozechner/pi-ai";
import { join } from "path";
import { BootstrapLoader } from "../services/intelligence/bootstrap-loader.js";

// Bootstrap loader 实例
const _bootstrapLoader = new BootstrapLoader(join(process.cwd(), ".pi-invest"));

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
  return {
    id: 'deepseek-chat',
    name: 'DeepSeek Chat',
    api: 'openai-completions',
    provider: 'openai',
    baseUrl: process.env.DEEPSEEK_BASE_URL || 'https://api.deepseek.com/v1',
    reasoning: false,
    input: ['text'],
    cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },
    contextWindow: 64000,
    maxTokens: 8000
  } as any;
}

/**
 * 路径配置
 */
export const paths = {
  root: process.cwd(),
  piDir: join(process.cwd(), ".pi-invest"),
  sessionsDir: join(process.cwd(), ".pi-invest", "sessions"),
  sessionMapFile: join(process.cwd(), ".pi-invest", "session-id-map.json"),
  skillsDir: join(process.cwd(), "skills"),
  /** 插件目录列表：项目级 plugins/ 和用户本地 .pi-invest/plugins/ */
  pluginDirs: [
    join(process.cwd(), "plugins"),
    join(process.cwd(), ".pi-invest", "plugins"),
  ],
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
