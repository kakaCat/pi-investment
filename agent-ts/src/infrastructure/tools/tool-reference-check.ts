/**
 * 工具引用 Sanity Check
 *
 * 背景：skill 文件 / 调度任务 prompt / 事件唤醒 prompt 里曾长期引用
 * 不存在的工具名（pool_list、alert_check、knowledge_record 等），
 * LLM 每次执行都要现场"纠错"，浪费 token 且增加出错概率。
 *
 * 本模块扫描这些文本源中的工具名候选，与注册表比对，
 * 未注册且不在白名单的名字作为 warn 报告（不阻断启动）。
 *
 * 用法：
 *   - 启动时：runToolReferenceCheckOnStartup()（src/index.ts 调用）
 *   - 手动：npm run check:tool-refs
 */
import { readdir, readFile } from "node:fs/promises";
import path from "node:path";

export interface ToolRefIssue {
  path: string;
  name: string;
  line: number;
}

export interface TextSource {
  path: string;
  text: string;
}

const SNAKE = "[a-z][a-z0-9]*(?:_[a-z0-9]+)+";

/** 提取文本中的工具名候选（snake_case，至少两段） */
export function extractToolRefs(text: string): string[] {
  const found = new Set<string>();
  const patterns = [
    new RegExp(`\\b(${SNAKE})\\s*\\(\\s*\\{`, "g"),      // X({ ... }) 调用写法
    new RegExp("`(" + SNAKE + ")`", "g"),                // `X` 反引号
  ];
  for (const re of patterns) {
    for (const m of text.matchAll(re)) {
      found.add(m[1]);
    }
  }
  // 含"使用/调用"的行：该行的所有 snake_case 标识符都算候选
  // （覆盖"使用 A 和 B"、"调用 A、B、C"等并列写法）
  if (/使用|调用/.test(text)) {
    for (const m of text.matchAll(new RegExp(`\\b(${SNAKE})\\b`, "g"))) {
      found.add(m[1]);
    }
  }
  return [...found];
}

/** 比对注册表，报告未注册且未加白的引用（同源同名只报一次） */
export function checkToolRefs(
  sources: TextSource[],
  registry: ReadonlySet<string>,
  allowlist: ReadonlySet<string>,
): ToolRefIssue[] {
  const issues: ToolRefIssue[] = [];
  for (const { path: p, text } of sources) {
    const seen = new Set<string>();
    const lines = text.split("\n");
    lines.forEach((lineText, idx) => {
      for (const name of extractToolRefs(lineText)) {
        if (registry.has(name) || allowlist.has(name) || seen.has(name)) continue;
        seen.add(name);
        issues.push({ path: p, name, line: idx + 1 });
      }
    });
  }
  return issues;
}

/**
 * 已知非工具的 snake_case 标识符白名单。
 * 新增前请确认：它确实不是"应该注册的工具"，而是字段名/模式名/枚举值。
 */
export const TOOL_REF_ALLOWLIST = new Set([
  // payload / schema 字段名
  "total_pnl_pct", "total_assets", "holdings_count", "buy_count", "sell_count",
  "trades_today", "key_findings", "message_type", "tool_name", "task_id",
  "agent_virtual", "signal_count", "trade_date", "signal_type", "strategy_name",
  "rule_id", "alert_type", "cost_price", "current_price", "change_pct",
  // 任务/事件类型枚举
  "agent_turn", "weekly_evolution", "signals_ready", "signal_generated",
  "watch_triggered", "position_alert", "premarket_report", "weekly_report",
  "agent_reminder", "morning_scan", "t1_generate", "daily_report",
  // cron / 通用词
  "delete_after_run", "schedule_expr", "schedule_kind",
  // K线形态/筛选参数/枚举值（非工具）
  "retracing_down", "retracing_up", "gap_up", "gap_down",
  "min_score", "max_pe", "stop_loss", "avg_cost",
]);

/** 收集默认扫描源：skills/*.md + 调度任务 prompt + 事件唤醒 prompt */
export async function collectDefaultSources(agentRoot: string): Promise<TextSource[]> {
  const sources: TextSource[] = [];

  const skillsDir = path.join(agentRoot, "skills");
  try {
    for (const f of await readdir(skillsDir)) {
      if (!f.endsWith(".md")) continue;
      sources.push({
        path: `skills/${f}`,
        text: await readFile(path.join(skillsDir, f), "utf8"),
      });
    }
  } catch { /* skills 目录不存在时跳过 */ }

  const promptFiles = [
    "src/services/scheduler/tasks/agent-decision-tasks.ts",
    "src/api/gateway/adapters/wake-adapter.ts",
  ];
  for (const rel of promptFiles) {
    try {
      sources.push({ path: rel, text: await readFile(path.join(agentRoot, rel), "utf8") });
    } catch { /* 文件缺失时跳过 */ }
  }

  return sources;
}

/** 启动时执行：发现问题打 warn，不阻断 */
export async function runToolReferenceCheckOnStartup(agentRoot: string): Promise<ToolRefIssue[]> {
  try {
    const { allCustomTools } = await import("./index.js");
    const registry = new Set(allCustomTools.map(t => t.name));
    const sources = await collectDefaultSources(agentRoot);
    const issues = checkToolRefs(sources, registry, TOOL_REF_ALLOWLIST);
    if (issues.length > 0) {
      console.warn(`[tool-ref-check] ⚠️ 发现 ${issues.length} 处疑似不存在的工具引用：`);
      for (const i of issues.slice(0, 20)) {
        console.warn(`  ${i.path}:${i.line} → ${i.name}`);
      }
      if (issues.length > 20) console.warn(`  …还有 ${issues.length - 20} 处，运行 npm run check:tool-refs 查看全部`);
    }
    return issues;
  } catch (e) {
    console.warn(`[tool-ref-check] 检查失败（忽略，不影响启动）: ${e instanceof Error ? e.message : e}`);
    return [];
  }
}
