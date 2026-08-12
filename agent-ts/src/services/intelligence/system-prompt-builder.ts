/**
 * System Prompt Builder - 8 层系统提示词动态组装
 *
 * 层级：
 * 1. Identity   - IDENTITY.md 或默认身份
 * 2. Soul       - SOUL.md 人格注入
 * 3. Tools      - TOOLS.md 工具使用指南
 * 4. Skills     - 已发现的技能列表
 * 5. Memory     - MEMORY.md 长期记忆 + 本轮自动召回
 * 6. Bootstrap  - BOOTSTRAP.md / AGENTS.md 启动上下文
 * 7. Runtime    - 当前时间、cwd、model
 * 8. Channel    - 渠道提示（terminal / api）
 */

import {
  getLastHealthReport,
  formatHealthForPrompt,
} from "../health/startup-health-check.js";

export interface BuildSystemPromptOptions {
  bootstrap: Record<string, string>;
  skillsBlock?: string;
  memoryContext?: string;
  dailyMemory?: string;
  recalledMemory?: string; // W1.4: 召回注入的记忆
  date: string;
  cwd: string;
  model: string;
  channel?: "terminal" | "api";
  mode?: "full" | "minimal" | "none";
  customToolsBlock?: string;
  customTools?: Array<{
    name: string;
    label?: string;
    promptGuidelines?: string[];
  }>;
}

const CHANNEL_HINTS: Record<string, string> = {
  terminal: "You are responding via a terminal REPL. Markdown is supported.",
  api: "You are responding via API. Be concise and structured.",
};

/** 读取启动健康自检结果（未执行自检时返回 null） */
function loadHealthSummary(): string | null {
  const report = getLastHealthReport();
  return report ? formatHealthForPrompt(report) : null;
}

export function buildSystemPrompt(opts: BuildSystemPromptOptions): string {
  const {
    bootstrap,
    skillsBlock = "",
    memoryContext = "",
    dailyMemory = "",
    recalledMemory = "",
    date,
    cwd,
    model,
    channel = "terminal",
    mode = "full",
    customToolsBlock = "",
    customTools = [],
  } = opts;

  const sections: string[] = [];

  // 第 1 层: 身份
  const identity = bootstrap["IDENTITY.md"]?.trim();
  sections.push(identity || DEFAULT_IDENTITY);

  // 第 2 层: 灵魂（仅 full 模式）
  if (mode === "full") {
    const soul = bootstrap["SOUL.md"]?.trim();
    if (soul) sections.push(`## Personality\n\n${soul}`);
  }

  // 第 3 层: 工具（Tools）
  // 分为三个子层：
  // 3.1 执行策略（来自 TOOLS.md）
  // 3.2 工具列表（来自 customToolsBlock，框架自动生成）
  // 3.3 工具使用细则（来自 promptGuidelines）

  const toolsSections: string[] = [];

  // 3.1 执行策略
  const toolsMd = bootstrap["TOOLS.md"]?.trim();
  if (toolsMd) {
    toolsSections.push('### 执行策略（何时用什么工具）\n\n' + toolsMd);
  }

  // 3.2 工具列表
  if (customToolsBlock) {
    const toolListHeader = `### 工具列表（按使用频率排序，优先考虑靠前的工具）

以下是所有可用工具，按使用频率从高到低排列。选择工具时，优先考虑列表前面的工具。

`;
    toolsSections.push(toolListHeader + customToolsBlock);
  }

  // 3.3 工具使用细则
  if (customTools && customTools.length > 0) {
    const guidelines = buildToolGuidelines(customTools);
    if (guidelines.trim()) {
      const guidelinesHeader = `### 工具使用细则（复杂工具的特殊注意事项）

以下工具有特殊的使用规则或注意事项，使用前请仔细阅读：

`;
      toolsSections.push(guidelinesHeader + guidelines);
    }
  }

  if (toolsSections.length > 0) {
    sections.push(`## Tools\n\n${toolsSections.join('\n\n')}`);
  }

  // 第 4 层: 技能（仅 full 模式）
  if (mode === "full" && skillsBlock) {
    const mandatoryPrefix =
      "## Skills（必须执行）\n\n" +
      "你必须先执行 skill 选择，再决定是否调用其他工具或直接回答。\n\n" +
      "强制顺序：\n" +
      "1. 扫描 `<available_skills>` 中的 `<description>`\n" +
      "2. 如果有明确匹配，先选最具体的一个 skill\n" +
      "3. 选定后，第一个外部动作必须是：用 `read` 读取该 skill 的 `<location>`\n" +
      "4. 只有在 `read` 返回后，才能按 skill 内容调用工具或组织回复\n" +
      "5. 如果没有明确匹配，才允许跳过 skill，正常回复\n\n" +
      "硬性约束：\n" +
      "- 命中 skill 后，`read` 之前禁止直接回答\n" +
      "- 命中 skill 后，`read` 之前禁止调用普通投资工具\n" +
      "- 命中 skill 后，`read` 之前禁止套用 Path A~H 的默认流程\n" +
      "- 每次回复最多预读一个 skill；必须先选定再读取\n\n" +
      "Few-shot 示例：\n" +
      "- 用户说：`帮我全面分析一下贵州茅台` → 命中 `deep-analysis` → 先 `read(<location>)` → 再按 skill 工作流分析\n" +
      "- 用户说：`看下我的持仓` → 命中 `portfolio` → 先 `read(<location>)` → 再调用 `manage_portfolio(action=\"get_with_pnl\")`\n" +
      "- 用户说：`什么是市盈率` → 不命中 skill → 不读 skill，直接回答\n\n" +
      "判错规则：如果已经命中 skill，却没有先执行 `read(<location>)` 就开始回答或调工具，这就是错误执行。";
    sections.push(mandatoryPrefix + "\n\n" + skillsBlock);
  }

  // 第 5 层: 记忆（仅 full 模式）
  if (mode === "full") {
    const memMd = bootstrap["MEMORY.md"]?.trim();
    const userMd = bootstrap["USER.md"]?.trim();
    const parts: string[] = [];
    if (memMd) parts.push(`### Evergreen Memory\n\n${memMd}`);
    if (userMd) parts.push(`### User Profile\n\n${userMd}`);
    if (dailyMemory) parts.push(`### Recent Memory (today)\n\n${dailyMemory}`);
    if (memoryContext) parts.push(`### Recalled Memories (auto-searched)\n\n${memoryContext}`);
    // W1.4: 召回注入的记忆（prefetch top-3）
    if (recalledMemory) parts.push(`### Recalled Memory\n\n${recalledMemory}`);
    if (parts.length) {
      sections.push("## Memory\n\n" + parts.join("\n\n"));
    }
    sections.push(
      "## Memory Instructions\n\n" +
      "- Use memory_write to save important user facts, preferences, and context.\n" +
      "- Reference remembered facts naturally in conversation.\n" +
      "- Use memory_search to recall specific past information.\n" +
      "- Recalled memories above were auto-retrieved based on your current context."
    );
  }

  // 第 6 层: Bootstrap 上下文
  if (mode === "full" || mode === "minimal") {
    for (const name of ["BOOTSTRAP.md", "PORTFOLIO.md", "AGENTS.md", "HEARTBEAT.md"]) {
      const content = bootstrap[name]?.trim();
      if (content) {
        sections.push(`## ${name.replace(".md", "")}\n\n${content}`);
      }
    }
  }

  // 第 7 层: 运行时上下文
  const runtimeLines = [
    `- Model: ${model}`,
    `- Current date: ${date}`,
    `- Current working directory: ${cwd}`,
    `- Prompt mode: ${mode}`,
  ];
  const healthSummary = loadHealthSummary();
  if (healthSummary) {
    runtimeLines.push(``, `### System Health（启动自检）`, healthSummary);
  }
  sections.push(`## Runtime Context\n\n` + runtimeLines.join("\n"));

  // 第 8 层: 渠道提示
  sections.push(`## Channel\n\n${CHANNEL_HINTS[channel] ?? `You are responding via ${channel}.`}`);

  return sections.join("\n\n");
}

/**
 * 从工具的 promptGuidelines 构建使用细则文本
 * 只包含有 promptGuidelines 的工具
 */
function buildToolGuidelines(tools: Array<{
  name: string;
  label?: string;
  promptGuidelines?: string[];
}>): string {
  const lines: string[] = [];

  for (const tool of tools) {
    if (!tool.promptGuidelines || tool.promptGuidelines.length === 0) {
      continue;
    }

    const label = tool.label || tool.name;
    lines.push(`**${tool.name}**（${label}）`);

    for (const guideline of tool.promptGuidelines) {
      lines.push(`- ${guideline}`);
    }

    lines.push(''); // 空行分隔
  }

  return lines.join('\n');
}

const DEFAULT_IDENTITY = `你是「PI 投资顾问」，拥有华尔街顶级分析师的专业素养，深谙 A 股市场规律。

你是一个专业的 AI 投资顾问，帮助用户进行投资分析和决策支持。你通过调用各种数据工具获取实时市场数据，提供基于数据的分析和建议。`;
