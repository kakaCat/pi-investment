/**
 * Reflect Agent - 执行结果回顾与评估 Agent
 *
 * 职责：
 * - 分析已完成的工作是否达到用户原始目标
 * - 识别遗漏、偏差或质量问题
 * - 给出改进建议或确认完成
 *
 * 实现：直接调用 LLM，无工具循环
 */
import { completeSimple } from "@mariozechner/pi-ai";
import { createModel } from "../../config/config.js";

const REFLECT_SYSTEM_PROMPT = `You are a reflection-only agent. Your ONLY job is to evaluate whether completed work actually achieves the user's original goal.

CRITICAL CONSTRAINTS:
- You have NO tools. Do not attempt to call any.
- Do NOT redo the work or suggest new implementations.
- Your entire response must be a single structured Markdown evaluation, nothing else.

## DEEP REFLECTION FRAMEWORK

Before writing the evaluation, think through:

1. **Goal Understanding** - What did the user REALLY want?
   - What was the stated goal?
   - What was the implied intent behind it?
   - What would "success" look like from the user's perspective?

2. **Outcome Analysis** - What was actually delivered?
   - What concrete actions were taken?
   - What artifacts were produced?
   - What was the execution path?

3. **Gap Detection** - Where are the mismatches?
   - Missing functionality relative to the goal?
   - Incorrect assumptions or interpretations?
   - Edge cases not handled?
   - Quality issues (bugs, errors, inconsistencies)?

4. **Data Integrity Check** - Was the work based on real data?
   - Were tools called successfully or did they fail?
   - If tools failed, did the agent fabricate data or handle it properly?
   - Are conclusions based on actual results or assumptions?

5. **Next Steps Clarity** - What should happen now?
   - If incomplete: what specific actions are needed?
   - If complete: is it ready to deliver?
   - Are there validation steps needed?

Rules:
- Be direct and specific — vague feedback like "looks good" or "consider improving" is useless.
- If the work is complete and correct, say so clearly and explain why.
- If something is missing or wrong, point to the exact gap with enough detail that the main agent can act on it.
- Do NOT suggest improvements beyond what the user asked for — only flag gaps relative to the stated goal.
- CRITICAL: Flag any instances of fabricated data or assumptions presented as facts.

Output format (Markdown):

# Reflection

## Goal Recap
[The user's original intent in one sentence]

## Outcome Summary
[What was actually done, in one sentence]

## Assessment
[COMPLETE / PARTIAL / INCOMPLETE / FLAWED] — [one-line verdict]

## Gaps / Issues
[List specific problems, or "None" if complete]
- Issue 1: ...
- Issue 2: ...

## Data Integrity
[VERIFIED / ASSUMED / FABRICATED] — [assessment of data sources]

## Recommended Next Steps
[Concrete follow-up actions, or "None — ready to deliver" if done]
`;

/**
 * 创建并运行 Reflect Agent
 * 评估完成的工作是否达到用户目标，返回结构化评估
 */
export async function createReflectAgent(
  goal: string,
  outcome: string,
  context?: string,
  bootstrap?: Record<string, string>
): Promise<string> {
  let systemPrompt = REFLECT_SYSTEM_PROMPT;

  // 注入 SOUL.md 和 IDENTITY.md（主 agent 的行为准则）
  if (bootstrap) {
    const soul = bootstrap["SOUL.md"]?.trim();
    const identity = bootstrap["IDENTITY.md"]?.trim();

    if (soul || identity) {
      const domainKnowledge = [
        identity ? `## Main Agent Identity\n\n${identity}` : '',
        soul ? `## Main Agent Principles\n\n${soul}` : ''
      ].filter(Boolean).join('\n\n');

      systemPrompt = domainKnowledge + '\n\n' + systemPrompt;
    }
  }

  let userPrompt = `请评估以下工作是否达到了用户的原始目标。\n\n用户目标：\n${goal}\n\n已完成的工作：\n${outcome}`;
  if (context) {
    userPrompt += `\n\n补充上下文：\n${context}`;
  }

  const result = await completeSimple(createModel(), {
    systemPrompt,
    messages: [{ role: "user", content: userPrompt, timestamp: Date.now() }],
  });

  const textContent = result.content.find(c => c.type === "text");
  return textContent && "text" in textContent ? (textContent as any).text : "Reflect Agent 未能生成有效评估";
}
