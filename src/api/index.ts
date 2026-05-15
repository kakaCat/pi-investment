/**
 * PI Investment - AI 股票投资顾问
 *
 * 基于 pi-coding-agent SDK 构建的命令行交互式投资分析 Agent
 */
import { config } from "dotenv";
import { InteractiveMode } from "@mariozechner/pi-coding-agent";
import { getSession as getSessionNormal } from "../core/agent/agent-loop.js";
import { getSession as getSessionBackground } from "../core/agent/background-agent-loop.js";
import * as logger from "../infrastructure/logging/observable-logger.js";
import { wrapSessionWithLogger } from "../infrastructure/session/session-factory.js";
import { PerformanceMonitor } from "../infrastructure/monitoring/performance-monitor.js";
import { CronService } from "../services/operations/cron-service.js";
import { DailyReviewService } from "../services/operations/daily-review-service.js";
import { StopLossAlertService } from "../services/operations/stop-loss-alert-service.js";
import { runWeeklyEvolution } from "../services/intelligence/evolution-service.js";
import { saveSessionMemoryAsync } from "../services/intelligence/session-memory-saver.js";
import { join } from "path";

// 加载环境变量
config();

// 选择 agent loop 模式
const USE_BACKGROUND_MODE = process.env.BACKGROUND_MODE === "true";

const piDir = join(process.cwd(), ".pi-invest");

async function main() {
  try {
    console.log("🚀 启动 PI Investment - AI 股票投资顾问...\n");

    // 先初始化 logger（在创建 session 之前）
    logger.initSession();
    console.log(`📋 Session: ${logger.getSessionKey()}\n`);

    // 初始化服务
    const reviewService = new DailyReviewService(piDir);
    const alertService = new StopLossAlertService(piDir);

    // 启动时自动复盘检查（工作日收盘后，且今日未复盘）
    if (reviewService.shouldAutoRun()) {
      console.log("📋 检测到今日复盘尚未完成，自动执行复盘...\n");
      try {
        const report = await reviewService.run();
        console.log(report);
        console.log();
      } catch (e) {
        console.warn(`[复盘] 自动复盘失败: ${e instanceof Error ? e.message : String(e)}\n`);
      }
    } else if (reviewService.isReviewDone()) {
      console.log("✅ 今日持仓复盘已完成\n");
    }

    // 根据环境变量选择 agent loop
    const session = USE_BACKGROUND_MODE
      ? await getSessionBackground()
      : await getSessionNormal();

    console.log(`📌 模式: ${USE_BACKGROUND_MODE ? "Background (并行任务)" : "Normal (串行)"}\n`);

    console.log("✅ 投资顾问初始化完成\n");

    // 初始化性能监控
    const perfMonitor = new PerformanceMonitor();

    // 用工厂函数包装 session，注入 logger + 性能监控
    wrapSessionWithLogger(session, perfMonitor);

    // 启动 CronService（后台定时任务）
    const cronService = new CronService(
      join(piDir, "CRON.json"),
      piDir,
      async (payload) => {
        if (payload.kind === "daily_review") {
          const report = await reviewService.run();
          process.stdout.write("\n\n" + "─".repeat(60) + "\n");
          process.stdout.write("[定时复盘] " + report + "\n");
          process.stdout.write("─".repeat(60) + "\n\n");
        } else if (payload.kind === "stop_loss_alert") {
          const result = await alertService.run();
          process.stdout.write(result.summary + "\n");
        } else if (payload.kind === "weekly_evolution") {
          process.stdout.write("\n\n" + "═".repeat(60) + "\n");
          process.stdout.write("[进化分析] 开始运行每周进化分析...\n");
          process.stdout.write("═".repeat(60) + "\n\n");
          try {
            // 初始化 session 并设置上下文
            const { getSession } = await import("../core/agent/agent-loop.js");
            await getSession({
              type: 'cron_evolution',
              sessionId: `evolution-${Date.now()}`,
              metadata: { trigger: 'cron', jobId: 'weekly-evolution' }
            });

            const result = await runWeeklyEvolution();
            process.stdout.write(`✅ 进化分析完成\n`);
            process.stdout.write(`📊 报告路径: ${result.reportPath}\n`);
            process.stdout.write(`📈 目标收益: ${result.summary.targetReturn}% | 实际收益: ${result.summary.realizedReturn}%\n`);
            process.stdout.write(`🎯 胜率: ${(result.summary.winRate * 100).toFixed(1)}% | 交易次数: ${result.summary.totalTrades}\n`);
            process.stdout.write(`🔍 归因: ${result.summary.attribution}\n`);
            process.stdout.write(`💡 优化建议: ${result.summary.suggestionCount} 条\n`);
            if (result.summary.appliedCount > 0) {
              process.stdout.write(`✨ 已自动应用: ${result.summary.appliedCount} 条\n`);
            }
            if (result.summary.manualTaskCount > 0) {
              process.stdout.write(`⚠️  需人工处理: ${result.summary.manualTaskCount} 条\n`);
            }
            process.stdout.write("\n" + "═".repeat(60) + "\n\n");
          } catch (e) {
            process.stdout.write(`❌ 进化分析失败: ${e instanceof Error ? e.message : String(e)}\n`);
            process.stdout.write("═".repeat(60) + "\n\n");
          }
        } else if (payload.kind === "agent_turn" && payload.message) {
          // 直接通过 session 注入消息
          await session.prompt(payload.message);
        } else if (payload.kind === "system_event" && payload.text) {
          process.stdout.write(`\n[系统] ${payload.text}\n`);
        }
      }
    );
    cronService.start();

    // 列出已加载的 cron 任务
    const jobs = cronService.listJobs();
    if (jobs.length > 0) {
      console.log(`⏰ Cron 任务（${jobs.length} 个）:`);
      for (const j of jobs) {
        const status = j.enabled ? "✅" : "❌";
        const next = j.nextIn !== null ? ` 下次：${j.nextRun}（${Math.round(j.nextIn / 60)} 分钟后）` : "";
        console.log(`  ${status} ${j.name}（${j.kind}: ${j.id}）${next}`);
      }
      console.log();
    }

    // 监听进程退出
    process.on('SIGINT', async () => {
      cronService.stop();
      console.log(perfMonitor.getReport());
      logger.logSessionEnd();

      // 异步保存会话记忆（不阻塞退出）
      console.log("\n🧠 保存会话记忆...");
      saveSessionMemoryAsync(session, {
        timeout: 30000,
        verbose: false
      }).catch(err => {
        console.error(`记忆保存失败: ${err instanceof Error ? err.message : String(err)}`);
      });

      // 等待500ms让记忆保存agent启动
      await new Promise(resolve => setTimeout(resolve, 500));
      process.exit(0);
    });

    process.on('exit', () => {
      logger.logSessionEnd();
    });

    // 启动交互式模式
    const mode = new InteractiveMode(session);
    await mode.run();

    // 正常退出时保存会话记忆
    console.log("\n🧠 保存会话记忆...");
    await saveSessionMemoryAsync(session, {
      timeout: 30000,
      verbose: false
    }).catch(err => {
      console.error(`记忆保存失败: ${err instanceof Error ? err.message : String(err)}`);
    });

    cronService.stop();
    logger.logSessionEnd();
  } catch (error) {
    console.error("❌ 启动失败:", error instanceof Error ? error.message : String(error));
    process.exit(1);
  }
}

main();
