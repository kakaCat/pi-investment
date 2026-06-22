---
name: evolution
description: 运行进化分析——评估投资表现，归因差距，生成优化建议，支持参数配置
---

# 进化分析技能 (Evolution)

运行完整的进化分析流程，评估投资表现，生成优化建议，并自动应用改进。

## 触发条件

用户想要运行进化分析、查看进化报告、评估 Agent 表现时使用此技能。

**关键词**: 进化、进化分析、自我优化、优化、调整能力、查看报告

## 命令格式

```
/evolution [选项]
```

## 支持的选项

- `--view` 或 `-v`: 查看最近一次进化报告
- `--days <N>` 或 `-d <N>`: 只分析最近 N 天的交易（默认 90 天）
- `--all` 或 `-a`: 分析全部交易记录
- `--target <N>` 或 `-t <N>`: 设置目标收益率百分比（默认 10%）
- `--reviews <N>` 或 `-r <N>`: 分析最近 N 份复盘报告（默认 10）
- `--help` 或 `-h`: 显示帮助信息

## 实现代码

```typescript
import { runWeeklyEvolution, type EvolutionConfig } from "../services/intelligence/evolution-service.js";
import { formatReportAsMarkdown } from "../services/intelligence/evolution-reporter.js";
import { readFileSync, existsSync, readdirSync } from "fs";
import { join } from "path";

const piDir = join(process.cwd(), ".pi-invest");
const evolutionDir = join(piDir, "evolution");

// 解析参数
const args = context.args.split(/\s+/).filter(Boolean);

// --help: 显示帮助
if (args.includes("--help") || args.includes("-h")) {
  return `🧬 进化分析命令

用法:
  /evolution                    运行进化分析（默认配置）
  /evolution --view             查看最近一次进化报告
  /evolution --days 30          只分析最近 30 天交易
  /evolution --all              分析全部交易记录
  /evolution --target 15        设置目标收益率 15%
  /evolution --reviews 20       分析最近 20 份复盘报告

参数:
  -d, --days <天数>       交易记录时间窗口（默认 90 天）
  -a, --all               分析全部交易记录
  -t, --target <百分比>   目标收益率（默认 10%）
  -r, --reviews <数量>    复盘报告数量（默认 10）
  -v, --view              查看最近一次报告
  -h, --help              显示帮助信息

示例:
  /evolution --days 60 --target 12
  /evolution --all --reviews 20`;
}

// --view: 查看最近报告
if (args.includes("--view") || args.includes("-v")) {
  if (!existsSync(evolutionDir)) {
    return "❌ 尚未运行过进化分析。使用 /evolution 运行第一次分析。";
  }

  const files = readdirSync(evolutionDir)
    .filter(f => f.startsWith("evolution-") && f.endsWith(".md"))
    .sort()
    .reverse();

  if (files.length === 0) {
    return "❌ 未找到进化报告。使用 /evolution 运行第一次分析。";
  }

  const latestReport = readFileSync(join(evolutionDir, files[0]), "utf-8");
  return `📊 最近一次进化报告 (${files[0]}):\n\n${latestReport}`;
}

// 解析配置参数
const config: EvolutionConfig = {};

for (let i = 0; i < args.length; i++) {
  const arg = args[i];

  if (arg === "--days" || arg === "-d") {
    const days = parseInt(args[++i], 10);
    if (isNaN(days) || days <= 0) {
      return "❌ --days 参数必须是正整数";
    }
    config.tradeWindowDays = days;
  } else if (arg === "--all" || arg === "-a") {
    config.tradeWindowDays = undefined; // 全部
  } else if (arg === "--target" || arg === "-t") {
    const target = parseFloat(args[++i]);
    if (isNaN(target) || target <= 0) {
      return "❌ --target 参数必须是正数";
    }
    config.targetReturn = target;
  } else if (arg === "--reviews" || arg === "-r") {
    const count = parseInt(args[++i], 10);
    if (isNaN(count) || count <= 0) {
      return "❌ --reviews 参数必须是正整数";
    }
    config.reviewWindowCount = count;
  }
}

// 运行进化分析
console.log("\n" + "═".repeat(60));
console.log("🧬 正在运行进化分析...");
console.log("═".repeat(60) + "\n");

try {
  const result = await runWeeklyEvolution(config);
  const markdown = formatReportAsMarkdown(result.report);

  // 输出完整报告
  console.log(markdown);
  console.log("─".repeat(60));

  // 返回摘要
  const summary = [
    "\n✅ 进化分析完成",
    `📊 报告路径: ${result.reportPath}`,
    `📈 目标收益: ${result.summary.targetReturn}% | 实际收益: ${result.summary.realizedReturn}%`,
    `🎯 胜率: ${result.summary.winRate}% | 交易次数: ${result.summary.totalTrades}`,
    `🔍 归因: ${result.summary.attribution}`,
    `💡 优化建议: ${result.summary.suggestionCount} 条`,
  ];

  if (result.summary.appliedCount > 0) {
    summary.push(`✨ 已自动应用: ${result.summary.appliedCount} 条`);
  }

  if (result.summary.manualTaskCount > 0) {
    summary.push(`⚠️  需人工处理: ${result.summary.manualTaskCount} 条`);
  }

  return summary.join("\n");
} catch (error) {
  return `❌ 进化分析失败: ${error instanceof Error ? error.message : String(error)}`;
}
```

## 使用示例

### 示例 1: 默认配置运行

**用户**: `/evolution`

**输出**:
```
═══════════════════════════════════════════════════════════
🧬 正在运行进化分析...
═══════════════════════════════════════════════════════════

[进化] 配置参数:
  - 目标收益率: 10%
  - 交易窗口: 90 天
  ...

✅ 进化分析完成
📊 报告路径: .pi-invest/evolution/evolution-2026-05-15.md
📈 目标收益: 10% | 实际收益: 8.5%
🎯 胜率: 65% | 交易次数: 12
🔍 归因: capability_insufficient
💡 优化建议: 3 条
✨ 已自动应用: 2 条
```

### 示例 2: 查看最近报告

**用户**: `/evolution --view`

**输出**: 显示最近一次进化报告的完整内容

### 示例 3: 自定义参数

**用户**: `/evolution --days 30 --target 15`

**输出**: 分析最近 30 天交易，目标收益率 15%

### 示例 4: 分析全部交易

**用户**: `/evolution --all --reviews 20`

**输出**: 分析全部交易记录，参考最近 20 份复盘报告

## 注意事项

- 进化分析需要至少 3 笔交易数据才能产生有意义的结果
- 代码生成使用 Codex (GPT-5.4)，需要确保 Codex 可用
- 自动应用的优化建议会创建 Git 分支并自动合并
- 建议在非交易时段运行（避免影响实时决策）
- 每周日 20:00 会自动触发进化分析（CRON 配置）
