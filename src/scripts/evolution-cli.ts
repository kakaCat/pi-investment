#!/usr/bin/env tsx
/**
 * PI Investment — 进化分析 CLI
 *
 * 用法:
 *   npm run evolution          运行进化分析并输出报告
 *   npm run evolution -- --view  查看最近一次进化报告
 *
 * 自动调度已在 CRON.json 中配置：每周日 20:00 自动触发
 */

import { runWeeklyEvolution } from "../services/intelligence/evolution-service.js";
import { formatReportAsMarkdown } from "../services/intelligence/evolution-reporter.js";
import { readFileSync, existsSync, readdirSync } from "fs";
import { join } from "path";

const piDir = join(process.cwd(), ".pi-invest");
const evolutionDir = join(piDir, "evolution");
const arg = process.argv[2];

function line(char = "─", len = 60): void {
  console.log(char.repeat(len));
}

async function runEvolution(): Promise<void> {
  console.log("\n🧬 正在运行进化分析...\n");

  try {
    const result = await runWeeklyEvolution();
    const markdown = formatReportAsMarkdown(result.report);

    console.log(markdown);
    line();
    console.log(`\n✅ 进化报告已保存: ${result.reportPath}\n`);
  } catch (e) {
    console.error("❌ 进化分析失败:", e instanceof Error ? e.message : String(e));
    process.exit(1);
  }
}

function viewLatestReport(): void {
  if (!existsSync(evolutionDir)) {
    console.log("\n  暂无进化报告。运行 npm run evolution 生成第一份报告。\n");
    return;
  }

  const reports = readdirSync(evolutionDir)
    .filter(f => f.startsWith("evolution-") && f.endsWith(".md"))
    .sort()
    .reverse();

  if (reports.length === 0) {
    console.log("\n  暂无进化报告。运行 npm run evolution 生成第一份报告。\n");
    return;
  }

  const latest = join(evolutionDir, reports[0]);
  const content = readFileSync(latest, "utf-8");

  console.log(`\n📋 最近报告: ${reports[0]}\n`);
  console.log(content);
  line();
}

async function main(): Promise<void> {
  if (arg === "--view" || arg === "-v") {
    viewLatestReport();
  } else {
    await runEvolution();
  }
}

main().catch(e => {
  console.error(e);
  process.exit(1);
});
