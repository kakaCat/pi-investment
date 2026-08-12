import { readFileSync } from "fs";
import { AsyncLocalStorage } from "async_hooks";
import type { Skill, ToolDefinition } from "../../sdk-facade.js";

const TOOL_CALL_RE = /`([A-Za-z_][A-Za-z0-9_]*)\(/g;
// skill 的 T 步骤格式：— tool_name {params}（可选反引号）。
// 84daffc 幽灵工具清理后 skill 全面改用此格式，只匹配旧反引号+括号格式会
// 把 skill 自己声明的 data_fetch_* 流程全部挡掉（白名单只剩 plan_task）。
const TOOL_BRACE_RE = /[—\-]\s*`?([A-Za-z_][A-Za-z0-9_]*)\s*\{/g;
// 「## 允许的工具」声明区是白名单的权威来源：`- tool_name()` 列表项（反引号可选）。
// 2026-08-12 审计发现：仅匹配正文两种格式时，声明区无反引号的写法全部漏提
// （portfolio-review 7 个声明工具漏 6 个），强制路由后 skill 自己的流程被拦。
const DECLARED_SECTION_RE = /##\s*允许的工具([\s\S]*?)(?=\n##\s|$)/;
const DECLARED_TOOL_RE = /^\s*[-*]\s*`?([A-Za-z_][A-Za-z0-9_]*)\s*\(/gm;

const skillContext = new AsyncLocalStorage<{ skillName: string | null }>();
const allowedToolsBySkill = new Map<string, Set<string>>();

function getSkillPath(skill: Skill): string {
  return ((skill as any).filePath ?? (skill as any).location ?? "") as string;
}

function extractAllowedTools(skillContent: string): Set<string> {
  const allowed = new Set<string>();
  const declaredSection = skillContent.match(DECLARED_SECTION_RE);
  if (declaredSection) {
    for (const match of declaredSection[1].matchAll(DECLARED_TOOL_RE)) {
      allowed.add(match[1]);
    }
  }
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
