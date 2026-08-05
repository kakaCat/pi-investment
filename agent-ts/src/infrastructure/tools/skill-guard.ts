import { readFileSync } from "fs";
import { AsyncLocalStorage } from "async_hooks";
import type { Skill, ToolDefinition } from "../../sdk-facade.js";

const TOOL_CALL_RE = /`([A-Za-z_][A-Za-z0-9_]*)\(/g;
// skill 的 T 步骤格式：— tool_name {params}（可选反引号）。
// 84daffc 幽灵工具清理后 skill 全面改用此格式，只匹配旧反引号+括号格式会
// 把 skill 自己声明的 data_fetch_* 流程全部挡掉（白名单只剩 plan_task）。
const TOOL_BRACE_RE = /[—\-]\s*`?([A-Za-z_][A-Za-z0-9_]*)\s*\{/g;

const skillContext = new AsyncLocalStorage<{ skillName: string | null }>();
const allowedToolsBySkill = new Map<string, Set<string>>();

function getSkillPath(skill: Skill): string {
  return ((skill as any).filePath ?? (skill as any).location ?? "") as string;
}

function extractAllowedTools(skillContent: string): Set<string> {
  const allowed = new Set<string>();
  for (const match of skillContent.matchAll(TOOL_CALL_RE)) {
    allowed.add(match[1]);
  }
  for (const match of skillContent.matchAll(TOOL_BRACE_RE)) {
    allowed.add(match[1]);
  }
  return allowed;
}

let skillGuardInitialized = false;

export function initSkillGuard(skills: Skill[]): void {
  if (skillGuardInitialized) return;
  skillGuardInitialized = true;
  allowedToolsBySkill.clear();

  for (const skill of skills) {
    const filePath = getSkillPath(skill);
    if (!filePath) continue;

    try {
      const content = readFileSync(filePath, "utf-8");
      allowedToolsBySkill.set(skill.name, extractAllowedTools(content));
    } catch {
      allowedToolsBySkill.set(skill.name, new Set<string>());
    }
  }
}

export function withForcedSkillScope<T>(skillName: string | null, fn: () => Promise<T>): Promise<T> {
  return skillContext.run({ skillName }, fn);
}

export function getExplicitSkillFromPrompt(userMessage: string): string | null {
  const match = userMessage.trimStart().match(/^\/skill:([a-z0-9-]+)/i);
  return match?.[1] ?? null;
}

export function assertToolAllowedForActiveSkill(toolName: string): void {
  const activeSkill = skillContext.getStore()?.skillName;
  if (!activeSkill) return;

  const allowed = allowedToolsBySkill.get(activeSkill);
  if (!allowed) return;
  if (allowed.has(toolName)) return;

  throw new Error(`技能 ${activeSkill} 未授权调用工具 ${toolName}。请严格按该 skill 的工具流程执行。`);
}

export function wrapInvestToolWithSkillGuard(tool: ToolDefinition): ToolDefinition {
  return {
    ...tool,
    execute: async (toolCallId, params, signal, onUpdate, ctx) => {
      assertToolAllowedForActiveSkill(tool.name);
      return await tool.execute(toolCallId, params, signal, onUpdate, ctx);
    },
  };
}
