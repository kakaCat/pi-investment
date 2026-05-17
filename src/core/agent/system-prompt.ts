/**
 * Agent 系统提示词管理 - 投资版
 *
 * 职责:
 * - skills block 的组装与缓存（SDK skills + 插件 skills）
 * - 每轮记忆召回（auto-recall）
 * - 今日每日记忆读取
 * - 将以上内容装配成最终的系统提示词
 */
import { type Skill } from "@mariozechner/pi-coding-agent";
import { join } from "path";
import { readFileSync, existsSync } from "fs";
import { getMemoryStore } from "../../services/intelligence/memory-store.js";
import { buildSystemPrompt } from "../../services/intelligence/system-prompt-builder.js";
import { getBootstrapData } from "../../config/config.js";
import type { PluginSkill } from "../../infrastructure/plugins/index.js";
import { chinaDate } from "../../utils/china-time.js";


// skills block 缓存（会话初始化时设置，之后每轮复用）
let skillsBlock = "";

/**
 * 生成 <available_skills> XML 块（纯数据，不含任何指令前缀）。
 * 指令前缀由 system-prompt-builder.ts 第 4 层统一管理，避免重复。
 */
function buildAvailableSkillsXml(sdkSkills: Skill[]): string {
  if (sdkSkills.length === 0) return "";

  const lines: string[] = ["<available_skills>"];
  for (const skill of sdkSkills) {
    const filePath = (skill as any).filePath ?? (skill as any).location ?? "";
    lines.push("  <skill>");
    lines.push(`    <name>${skill.name}</name>`);
    lines.push(`    <description>${skill.description}</description>`);
    lines.push(`    <location>${filePath}</location>`);
    lines.push("  </skill>");
  }
  lines.push("</available_skills>");
  return lines.join("\n");
}

/**
 * 初始化 skills block。在会话创建后调用一次。
 * skillsBlock 只含 <available_skills> XML + plugin skills 内联内容，
 * 不含 mandatory 指令前缀（前缀由 system-prompt-builder.ts 统一注入）。
 */
export function initSkillsBlock(sdkSkills: Skill[], pluginSkills: PluginSkill[]): void {
  if (sdkSkills.length === 0 && pluginSkills.length === 0) {
    skillsBlock = "";
    return;
  }

  const sdkBlock = buildAvailableSkillsXml(sdkSkills);

  // Plugin skills 没有文件路径，直接内联
  const pluginLines: string[] = [];
  if (pluginSkills.length > 0) {
    pluginLines.push("## Plugin Skills", "");
    for (const s of pluginSkills) {
      pluginLines.push(`### Skill: ${s.name}`);
      pluginLines.push(`Description: ${s.description}`);
      if (s.invocation) pluginLines.push(`Invocation: ${s.invocation}`);
      if (s.content) pluginLines.push(s.content);
      pluginLines.push("");
    }
  }

  skillsBlock = [sdkBlock, pluginLines.join("\n")].filter(Boolean).join("\n\n");
}

/**
 * 根据用户消息自动搜索相关记忆，返回注入提示词的上下文字符串。
 */
export function autoRecall(userMessage: string): string {
  try {
    const store = getMemoryStore();
    const results = store.hybridSearch(userMessage, 3);
    if (!results.length) return "";
    return results.map(r => `- [${r.path}] ${r.snippet}`).join("\n");
  } catch {
    return "";
  }
}

/**
 * 读取今日的每日记忆文件，返回纯文本内容。
 */
export function readDailyMemory(piDir: string): string {
  try {
    const today = chinaDate();
    const dailyFile = join(piDir, "memory", "daily", `${today}.jsonl`);
    if (!existsSync(dailyFile)) return "";
    const lines = readFileSync(dailyFile, "utf-8").split("\n").filter(l => l.trim());
    return lines.map(l => {
      try { return JSON.parse(l).content; } catch { return ""; }
    }).filter(Boolean).join("\n");
  } catch {
    return "";
  }
}

/**
 * 构建投资 Agent 的完整系统提示词。
 */
export function buildAgentSystemPrompt(params: {
  memoryContext?: string;
  dailyMemory?: string;
  tools?: Array<{ name: string; description: string; label?: string; promptGuidelines?: string[] }>;
  workspaceDir: string;
}): string {
  const {
    memoryContext = "",
    dailyMemory = "",
    tools = [],
    workspaceDir,
  } = params;

  const now = new Date();

  const customToolsBlock = tools.map(t => `- ${t.name}: ${t.description}`).join("\n");

  return buildSystemPrompt({
    bootstrap: getBootstrapData(),
    skillsBlock,
    memoryContext,
    dailyMemory,
    date: chinaDate(now),
    cwd: workspaceDir,
    model: "deepseek-chat",
    channel: "terminal",
    mode: "full",
    customToolsBlock,
    customTools: tools,
  });
}

