/**
 * T8 实测闸：3 个典型任务在 Tool Search 模式下的真实运行
 * 用法（agent-ts 根目录）: ./node_modules/.bin/tsx src/scripts/t8-live-test.ts
 */
import "dotenv/config";
import { mkdtempSync, readFileSync, readdirSync } from "fs";
import { tmpdir } from "os";
import { join } from "path";

// 工具面 = 生产 gateway 同款（core + 三件套）
import { getCoreTools, isToolSearchMode } from "../../infrastructure/tools/catalog.js";
import { toolSearchMetaTools } from "../../infrastructure/tools/meta/tool-search-tools.js";
import { allCustomTools, initMemoryTools } from "../../infrastructure/tools/index.js";
import { setPlanToolContext } from "../../infrastructure/tools/agent/plan-tool.js";
import { loadSkills, type Skill } from "../../sdk-facade.js";
import { initSkillsBlock } from "../../core/agent/system-prompt.js";
import { initSkillRouter } from "../../services/intelligence/skill-router.js";
import { initSkillGuard } from "../../infrastructure/tools/skill-guard.js";
import { createGatewaySessionFactory } from "../../api/gateway/session-factory.js";
import { initLLM } from "../../services/llm/index.js";
import { paths } from "../../config/config.js";
import type { ToolDefinition } from "../../infrastructure/tools/index.js";

const TASKS = [
  { key: "t8-pool", name: "股票池查询（非常驻 pool_manage）", prompt: "列出当前所有股票池，告诉我有哪些动态池。用工具查，不要凭记忆回答。" },
  { key: "t8-chan", name: "缠论分析（非常驻 chan_analyze）", prompt: "对 600519 做一次缠论分析，给出结论摘要。" },
  { key: "t8-portfolio", name: "持仓查询（常驻 portfolio_status，回归对照）", prompt: "看一下 agent_virtual 账户当前持仓状态，简要汇报。" },
];

async function main() {
  console.log("tool_search mode:", isToolSearchMode());

  initLLM(paths.piDir);
  initMemoryTools(paths.piDir);
  const { skills } = loadSkills({ cwd: paths.root, skillPaths: [join(paths.root, "skills")] } as any);
  initSkillsBlock(skills as Skill[], []);
  initSkillRouter(skills as Skill[]);
  initSkillGuard(skills as Skill[]);

  const tools = [...getCoreTools(), ...toolSearchMetaTools] as ToolDefinition[];
  console.log(`工具面: ${tools.length}（core ${getCoreTools().length} + meta ${toolSearchMetaTools.length}）`);
  setPlanToolContext(allCustomTools as unknown as ToolDefinition[]);

  const factory = createGatewaySessionFactory(tools, skills as Skill[]);

  for (const task of TASKS) {
    const sessionDir = mkdtempSync(join(tmpdir(), task.key + "-"));
    console.log(`\n===== ${task.name} =====`);
    const session = await factory.createSession(task.key, sessionDir);
    await factory.beforePrompt(session as any, task.key, task.prompt, sessionDir);
    const t0 = Date.now();
    try {
      await (session as any).prompt(task.prompt);
      console.log(`完成，耗时 ${((Date.now() - t0) / 1000).toFixed(0)}s`);
    } catch (e) {
      console.log(`失败: ${e instanceof Error ? e.message : e}`);
    }
    // 从 session jsonl 统计工具调用
    const files = readdirSync(sessionDir).filter((f) => f.endsWith(".jsonl"));
    const calls: string[] = [];
    let input = 0, cacheRead = 0;
    for (const f of files) {
      for (const line of readFileSync(join(sessionDir, f), "utf-8").split("\n")) {
        if (!line.trim()) continue;
        try {
          const d = JSON.parse(line);
          const msg = d.message ?? d;
          if (msg?.role === "assistant" && Array.isArray(msg?.content)) {
            for (const c of msg.content) if (c.type === "toolCall") calls.push(c.name);
          }
          const u = msg?.usage;
          if (u) { input += u.input ?? 0; cacheRead += u.cacheRead ?? 0; }
        } catch { /* skip */ }
      }
    }
    console.log(`工具调用序列: ${calls.join(" → ") || "(无)"}`);
    console.log(`tokens: input=${input} cacheRead=${cacheRead}`);
  }
  process.exit(0);
}

main().catch((e) => { console.error(e); process.exit(1); });
