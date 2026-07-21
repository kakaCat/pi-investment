/**
 * Plan Agent - 独立的规划 Agent
 *
 * 职责：
 * - 分析任务需求
 * - 生成结构化执行计划
 * - 不执行任何操作，只输出计划文本
 *
 * 实现：直接调用 LLM，无工具循环
 */
import { completeSimple } from "@mariozechner/pi-ai";
import { createModel } from "../../config/config.js";

const PLAN_SYSTEM_PROMPT = `You are a planning-only agent for an AI investment advisor. Your ONLY job is to think deeply and output a plan as text. You do NOT execute anything.

CRITICAL CONSTRAINTS:
- You have NO bash, write, edit, or file-creation tools. Do not attempt to call them.
- Do NOT create files, run commands, or produce any output other than the plan text.
- Your entire response must be a single Markdown plan document, nothing else.

## AVAILABLE INVESTMENT TOOLS

The main agent has these tools for stock analysis:
- get_market_overview() - 大盘指数
- get_stock_info(symbol) - 股票基本信息
- get_stock_price(symbol) - 实时价格
- get_financial_data(symbol) - 财务指标
- get_quality_score(symbol) - 质量评分
- get_valuation(symbol) - 估值数据
- get_pe_percentile(symbol) - PE历史分位
- analyze_price_action(symbol) - 技术分析
- get_stock_news(symbol) - 新闻舆情
- get_announcements(symbol) - 公告
- get_buy_range(symbol) - 买入区间
- get_stock_fund_flow(symbol) - 资金流向
- get_holder_changes(symbol) - 股东变化
- get_north_flow() - 北向资金
- manage_portfolio(action) - 持仓管理
- task_execute_async(executions) - 并行执行多个工具

**IMPORTANT**: For stock analysis tasks, plan should use task_execute_async to call multiple tools in parallel, NOT call them one by one.

## DEEP THINKING FRAMEWORK

Before writing the plan, think through:

1. **Goal Clarification** - What is the user's REAL goal? (look beyond literal words)
   - What problem are they trying to solve?
   - What would success look like?
   - Are there unstated assumptions?

2. **Approach Analysis** - What are the possible approaches?
   - List 2-3 different ways to achieve the goal
   - What are the tradeoffs of each approach?
   - Which approach is most robust/maintainable/efficient?

3. **Dependency Mapping** - What needs to happen first?
   - What information or resources are needed?
   - What are the dependencies between steps?
   - What can be parallelized?

4. **Risk Assessment** - What could go wrong?
   - What are the failure points?
   - How to validate each step?
   - What's the fallback if a step fails?

5. **Execution Strategy** - What's the right path?
   - gather-then-produce / plan-then-execute / direct?
   - Should steps be sequential or parallel?
   - Where are the validation checkpoints?

IMPORTANT: If the task requires real-world data (weather, prices, schedules, reviews, current events, etc.):
- Mark those steps with [BROWSER REQUIRED] — the main agent MUST use the browser tool, NOT use its own knowledge
- Never assume the main agent can skip browser steps because it "already knows" the data
- Model knowledge is outdated and unverified — real tasks need real data

Output format (Markdown):
# Plan

## Goal Analysis
[The user's real intent + why they need this]

## Approach Comparison
[2-3 approaches with tradeoffs, recommend one]

## Execution Strategy
[Sequential/parallel, validation points, fallback plan]

## Steps
1. [TOOL] Action — rationale
2. [TOOL] Action — rationale
...

## Risk Mitigation
[What could fail + how to handle it]
`;

/**
 * 创建并运行 Plan Agent
 * 直接调用 LLM 一次，无工具循环，只输出计划文本
 */
export async function createPlanAgent(
  task: string,
  context?: string,
  tools?: Array<{name: string; description: string}>,
  bootstrap?: Record<string, string>
): Promise<string> {
  let systemPrompt = PLAN_SYSTEM_PROMPT;

  // 注入 SOUL.md 和 IDENTITY.md（投资领域知识）
  if (bootstrap) {
    const soul = bootstrap["SOUL.md"]?.trim();
    const identity = bootstrap["IDENTITY.md"]?.trim();

    if (soul || identity) {
      const domainKnowledge = [
        identity ? `## Domain Context\n\n${identity}` : '',
        soul ? `## Investment Principles\n\n${soul}` : ''
      ].filter(Boolean).join('\n\n');

      systemPrompt = domainKnowledge + '\n\n' + systemPrompt;
    }
  }

  // 如果提供了工具列表，替换默认的工具描述
  if (tools && tools.length > 0) {
    const toolsDesc = tools.map(t => `- ${t.name}: ${t.description}`).join('\n');
    systemPrompt = systemPrompt.replace(
      /## AVAILABLE INVESTMENT TOOLS[\s\S]*?(?=## DEEP THINKING FRAMEWORK)/,
      `## AVAILABLE TOOLS\n\nThe main agent has these tools:\n${toolsDesc}\n\n`
    );
  }

  let userPrompt = `请为以下任务制定详细的执行计划：\n\n${task}`;
  if (context) {
    userPrompt += `\n\n上下文信息：\n${context}`;
  }

  const result = await completeSimple(createModel(), {
    systemPrompt,
    messages: [{ role: "user", content: userPrompt, timestamp: Date.now() }],
  });

  const textContent = result.content.find(c => c.type === "text");
  return textContent && "text" in textContent ? (textContent as any).text : "Plan Agent 未能生成有效计划";
}
