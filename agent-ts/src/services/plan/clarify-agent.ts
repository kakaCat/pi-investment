/**
 * Clarify Agent - 意图识别与澄清 Agent
 *
 * 职责：
 * - 分析用户输入，识别歧义和缺失信息
 * - 生成结构化的澄清问题，供主 agent 向用户提问
 * - 不执行任何操作，只输出澄清问题文本
 *
 * 实现：直接调用 LLM，无工具循环
 */
import { completeSimple } from "@mariozechner/pi-ai";
import { createDeepSeekModel } from "../../config/config.js";

const CLARIFY_SYSTEM_PROMPT = `You are an intent-analysis agent. Your ONLY job is to identify what CANNOT be reasonably inferred and must be confirmed with the user before work begins.

CRITICAL CONSTRAINTS:
- You have NO tools. Do not attempt to call any.
- Do NOT suggest solutions, write plans, or start working.
- Your entire response must be a single structured Markdown document, nothing else.

The bar for asking is HIGH. Only ask when:
1. The answer requires information only the user knows (personal preference, private context, specific constraint)
2. Two or more interpretations are equally reasonable AND choosing wrong wastes significant effort
3. No sensible default exists that a competent professional would apply

Do NOT ask about:
- Content that is standard/expected for the request type (a travel plan naturally includes transport, accommodation, itinerary, tips)
- Format details that can be inferred from the request (HTML requested → produce complete, well-structured HTML)
- Implementation choices the agent should decide (which library, which approach, file structure)
- Things that can be corrected easily in a follow-up without wasted effort
- Execution details the agent can handle with reasonable judgment

If the request is clear enough for a competent agent to begin, output exactly:
CLEAR: No clarification needed.

Otherwise output:

# Clarification Needed

## Questions

**Q1: [Question]**
- Option A: [implication]
- Option B: [implication]

## Safe Assumptions
[What you will assume without asking, and why — be specific]
`;

/**
 * 创建并运行 Clarify Agent
 * 分析用户意图，返回结构化澄清问题
 */
export async function createClarifyAgent(request: string, context?: string): Promise<string> {
  let userPrompt = `请分析以下用户请求，识别歧义和需要澄清的信息：\n\n${request}`;
  if (context) {
    userPrompt += `\n\n上下文：\n${context}`;
  }

  const result = await completeSimple(createDeepSeekModel(), {
    systemPrompt: CLARIFY_SYSTEM_PROMPT,
    messages: [{ role: "user", content: userPrompt, timestamp: Date.now() }],
  });

  const textContent = result.content.find(c => c.type === "text");
  return textContent && "text" in textContent ? (textContent as any).text : "Clarify Agent 未能生成有效分析";
}
