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
import { FxRateServiceAdapter } from "../services/fx-rate-service-adapter.js";
import { runWeeklyEvolution } from "../services/intelligence/evolution-service.js";
import { saveSessionMemoryAsync } from "../services/intelligence/session-memory-saver.js";
import { startFeishuBot } from "./feishu.js";
import type { FeishuBotHandle } from "./feishu.js";
import { join } from "path";
import { existsSync, readFileSync, unlinkSync } from "fs";
import { spawn } from "child_process";
import type { AgentSession } from "@mariozechner/pi-coding-agent";
import { addMessage, createUserMessage, createAssistantMessage } from "../core/agent/session-adapter.js";

// 加载环境变量
config();

// ── 重启上下文处理 ─────────────────────────────────────────────────────────
// 检测是否有 .restart/context.json（由 restart_agent 工具写入）
// 如果有，说明这是重启后的新进程，打印提示信息并恢复对话历史

interface ConversationMessage {
  role: string;
  content: string;
  timestamp?: string;
}

interface RestartContext {
  timestamp: string;
  cwd: string;
  reason: string;
  prevSessionKey?: string;
  conversationMessageCount?: number;
  messages?: ConversationMessage[];
  env: {
    NODE_ENV: string;
    BACKGROUND_MODE: string;
  };
}

const RESTART_DIR = join(process.cwd(), ".restart");
const RESTART_CONTEXT = join(RESTART_DIR, "context.json");

let restartData: RestartContext | null = null;

function checkRestartContext(): void {
  if (process.env.PI_RESTARTED === "true" && existsSync(RESTART_CONTEXT)) {
    try {
      // 确保终端使用 UTF-8 编码
      if (process.stdout.isTTY) {
        process.stdout.write('\x1b[?1049h'); // 保存屏幕
        process.stdout.write('\x1b[?1049l'); // 恢复屏幕（触发终端重置）
      }

      const data: RestartContext = JSON.parse(readFileSync(RESTART_CONTEXT, "utf-8"));
      restartData = data;
      const ts = new Date(data.timestamp).getTime();
      const elapsed = !isNaN(ts) ? Math.round((Date.now() - ts) / 1000) : 0;
      const msgCount = data.conversationMessageCount ?? data.messages?.length ?? 0;

      // 使用 Buffer 确保 UTF-8 编码输出
      const output = Buffer.from(
        `🔄 检测到 Agent 重启（${elapsed > 0 ? `${elapsed} 秒前` : '时间未知'}）\n` +
        `   - 原因: ${data.reason || '未指定'}\n` +
        `   - 对话消息: ${msgCount} 条待恢复\n` +
        `   - 新工具已加载\n\n`,
        'utf-8'
      );
      process.stdout.write(output);
    } catch {
      const output = Buffer.from("🔄 检测到 Agent 重启（新工具已加载）\n\n", 'utf-8');
      process.stdout.write(output);
    }
  } else if (existsSync(RESTART_CONTEXT)) {
    // 非重启启动，清理旧文件
    try { unlinkSync(RESTART_CONTEXT); } catch { /* ignore */ }
  }
}

/** 将上一个 session 的对话历史恢复到新 session 中 */
function restoreConversationIntoSession(session: AgentSession): void {
  if (!restartData?.messages || restartData.messages.length === 0) return;

  const messages = restartData.messages;
  let injected = 0;
  let lastUserMessage = "";
  let lastAssistantMessage = "";

  for (const msg of messages) {
    if (!msg.role || !msg.content) continue;
    if (msg.role === "user") {
      addMessage(session, createUserMessage(msg.content));
      lastUserMessage = msg.content;
      injected++;
    } else if (msg.role === "assistant") {
      addMessage(session, createAssistantMessage(msg.content));
      lastAssistantMessage = msg.content;
      injected++;
    }
  }

  if (injected > 0) {
    console.log(`📋 已恢复 ${injected} 条对话消息（共 ${messages.length} 条）\n`);

    // 添加一条系统提示消息，告诉 agent 继续之前的工作
    const contextPrompt = `Agent 已重启完成，新工具已加载。

上下文已恢复：
- 最后的用户请求：${lastUserMessage.slice(0, 200)}${lastUserMessage.length > 200 ? '...' : ''}
- 你之前的回复：${lastAssistantMessage.slice(0, 200)}${lastAssistantMessage.length > 200 ? '...' : ''}

请继续完成之前的任务。如果任务已完成，请总结结果。如果任务未完成，请继续执行。`;

    addMessage(session, createUserMessage(contextPrompt));
    console.log(`💡 已添加上下文提示，Agent 将自动继续之前的工作\n`);
  }

  // 清理上下文文件
  try { unlinkSync(RESTART_CONTEXT); } catch { /* ignore */ }
  restartData = null;
}

checkRestartContext();

// 选择 agent loop 模式
const USE_BACKGROUND_MODE = process.env.BACKGROUND_MODE === "true";

const piDir = join(process.cwd(), ".pi-invest");

async function main() {
  let feishuBot: FeishuBotHandle | null = null;

  try {
    console.log("🚀 启动 PI Investment - AI 股票投资顾问...\n");

    // 启动飞书 Bot（后台 WebSocket 监听）
    feishuBot = await startFeishuBot();
    if (feishuBot) {
      console.log("");
    }

    // 先初始化 logger（在创建 session 之前）
    logger.initSession();
    console.log(`📋 Session: ${logger.getSessionKey()}\n`);

    // 初始化服务
    const reviewService = new DailyReviewService(piDir);
    const alertService = new StopLossAlertService(piDir);
    const fxRateService = new FxRateServiceAdapter(piDir);

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

    // 如果是从 restart_agent 重启，恢复对话历史
    restoreConversationIntoSession(session);

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
        } else if (payload.kind === "system_event" && payload.message === "update_fx_rates") {
          try {
            await fxRateService.updateCache();
            console.log("✅ 汇率缓存已更新");
          } catch (error) {
            console.error("❌ 汇率更新失败:", error);
          }
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
      if (feishuBot) feishuBot.shutdown();
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
