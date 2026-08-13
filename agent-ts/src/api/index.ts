/**
 * PI Investment - AI 股票投资顾问
 *
 * 基于 pi-coding-agent SDK 构建的命令行交互式投资分析 Agent
 */
import { config } from "dotenv";
import { InteractiveMode, createAgentSessionRuntime, getAgentDir } from "../sdk-facade.js";
import { getSession as getSessionNormal, createRuntimeForSession } from "../core/agent/agent-loop.js";
import { getSession as getSessionBackground } from "../core/agent/background-agent-loop.js";
import * as logger from "../infrastructure/logging/observable-logger.js";
import { wrapSessionWithLogger, type PromptOptionsWithRouting } from "../infrastructure/session/session-factory.js";
import { PerformanceMonitor } from "../infrastructure/monitoring/performance-monitor.js";
import { startSchedulerRuntime } from "../services/scheduler/scheduler-runtime.js";
import { FxRateServiceAdapter } from "../services/fx-rate-service-adapter.js";
import { runWeeklyEvolution } from "../services/intelligence/evolution-service.js";
import { saveSessionMemoryAsync } from "../services/intelligence/session-memory-saver.js";
import { startFeishuBot } from "./feishu.js";
import type { FeishuBotHandle } from "./feishu.js";
import { join } from "path";
import { existsSync, readFileSync, unlinkSync } from "fs";
import { spawn } from "child_process";
import type { AgentSession } from "../sdk-facade.js";
import { addMessage, createUserMessage, createAssistantMessage } from "../core/agent/session-adapter.js";
import { getTaskManager, getBackgroundManager } from "../infrastructure/tools/index.js";
import type { TaskManager } from "../core/task/task-manager.js";
import type { BackgroundTaskManager } from "../core/task/background-task-manager.js";
import type { Task } from "../core/task/task-manager.js";

// 加载环境变量
config();

// 初始化 LLM 供给模块（state 文件 > env > 默认；幂等，多入口安全）
import { initLLM } from "../services/llm/index.js";
import { paths as llmPaths } from "../config/config.js";
initLLM(llmPaths.piDir);

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
  sdkSessionFile?: string;
  sdkSessionId?: string;
  conversationMessageCount?: number;
  messages?: ConversationMessage[];
  env: {
    NODE_ENV: string;
    BACKGROUND_MODE: string;
  };
  // 新增字段
  tasks?: {
    pending: Task[];
    inProgress: Task[];
    completed: Task[];
  };
  backgroundTasks?: {
    interrupted: Array<{
      id: string;
      taskId: number;
      toolName: string;
      params: any;
      startTime: number;
      reason: string;
    }>;
  };
}

const RESTART_DIR = join(process.cwd(), ".restart");
const RESTART_CONTEXT = join(RESTART_DIR, "context.json");

let restartData: RestartContext | null = null;

/**
 * 恢复任务状态到管理器中
 */
function restoreTasksIntoManagers(
  restartData: RestartContext,
  taskManager: TaskManager,
  backgroundTaskManager: BackgroundTaskManager
): { taskCount: number; backgroundCount: number } {
  let taskCount = 0;
  let backgroundCount = 0;

  // 恢复 TaskManager 任务
  if (restartData.tasks) {
    const allTasks = [
      ...restartData.tasks.pending,
      ...restartData.tasks.inProgress,
      ...(restartData.tasks.completed || [])
    ];

    if (allTasks.length > 0) {
      taskManager.restoreTasks(allTasks);
      taskCount = restartData.tasks.pending.length + restartData.tasks.inProgress.length;
      console.log(`📋 已恢复 ${taskCount} 个未完成任务 (pending: ${restartData.tasks.pending.length}, in_progress: ${restartData.tasks.inProgress.length})`);
    }
  }

  // 恢复 BackgroundTaskManager 中断任务
  if (restartData.backgroundTasks?.interrupted && restartData.backgroundTasks.interrupted.length > 0) {
    backgroundTaskManager.restoreInterruptedTasks(restartData.backgroundTasks.interrupted);
    backgroundCount = restartData.backgroundTasks.interrupted.length;
    console.log(`⚠️  已标记 ${backgroundCount} 个后台任务为失败（被重启中断）`);
  }

  return { taskCount, backgroundCount };
}

/**
 * 自动触发 agent 循环
 */
function triggerAgentLoop(session: AgentSession, contextPrompt?: string): void {
  setImmediate(() => {
    try {
      // 触发 agent 响应（发送实际消息，而非空消息）
      if (typeof session.prompt === 'function') {
        const message = contextPrompt || "继续之前的工作";
        session.prompt(message);
      } else {
        console.warn("⚠️  session.prompt 不可用，无法自动触发 agent 循环");
      }
    } catch (error) {
      console.warn("⚠️  自动触发 agent 循环失败:", error);
    }
  });
}

/**
 * 从重启上下文恢复任务（包装函数）
 */
function restoreTasksFromContext(): { taskCount: number; backgroundCount: number } {
  if (!restartData) {
    return { taskCount: 0, backgroundCount: 0 };
  }

  try {
    const taskManager = getTaskManager();
    const backgroundTaskManager = getBackgroundManager();
    return restoreTasksIntoManagers(restartData, taskManager, backgroundTaskManager);
  } catch (error) {
    console.warn("⚠️  任务恢复失败:", error instanceof Error ? error.message : String(error));
    return { taskCount: 0, backgroundCount: 0 };
  }
}

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
function restoreConversationIntoSession(
  session: AgentSession,
  taskCounts: { taskCount: number; backgroundCount: number }
): void {
  if (!restartData?.messages || restartData.messages.length === 0) {
    // 即使没有对话历史，如果有任务也要触发
    if (taskCounts.taskCount > 0 || taskCounts.backgroundCount > 0) {
      const prompt = "Agent 已重启完成。请使用 task_list 查看恢复的任务，然后继续执行未完成的工作。";
      triggerAgentLoop(session, prompt);
    }
    return;
  }
  if (restartData.sdkSessionFile) {
    console.log(`📋 已恢复 SDK 会话: ${restartData.sdkSessionId || restartData.sdkSessionFile}\n`);

    // SDK 会话恢复不代表任务会自己继续——有未完成任务时必须显式触发 agent，
    // 否则任务只被恢复到 TaskManager 却永远得不到执行（agent 空转等待输入）
    if (taskCounts.taskCount > 0 || taskCounts.backgroundCount > 0) {
      let contextPrompt = `Agent 已重启完成，SDK 会话已恢复。`;
      if (restartData.tasks) {
        if (restartData.tasks.pending.length > 0) {
          contextPrompt += `\n- 待执行任务：${restartData.tasks.pending.length} 个`;
        }
        if (restartData.tasks.inProgress.length > 0) {
          contextPrompt += `\n- 进行中任务：${restartData.tasks.inProgress.length} 个`;
        }
      }
      if (taskCounts.backgroundCount > 0) {
        contextPrompt += `\n- 中断的后台任务：${taskCounts.backgroundCount} 个（已标记为失败）`;
      }
      contextPrompt += `\n\n请使用 task_list 查看所有任务，然后继续执行未完成的工作。优先处理 in_progress 状态的任务。`;

      console.log(`💡 准备自动触发 Agent 继续之前的工作\n`);
      triggerAgentLoop(session, contextPrompt);
    }

    try { unlinkSync(RESTART_CONTEXT); } catch { /* ignore */ }
    restartData = null;
    return;
  }

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

    // 构建上下文提示消息
    let contextPrompt = `Agent 已重启完成，新工具已加载。

上下文已恢复：
- 最后的用户请求：${lastUserMessage.slice(0, 200)}${lastUserMessage.length > 200 ? '...' : ''}
- 你之前的回复：${lastAssistantMessage.slice(0, 200)}${lastAssistantMessage.length > 200 ? '...' : ''}`;

    // 如果有任务，添加任务信息
    if (taskCounts.taskCount > 0 || taskCounts.backgroundCount > 0) {
      contextPrompt += `

任务状态已恢复：`;

      if (restartData.tasks) {
        if (restartData.tasks.pending.length > 0) {
          contextPrompt += `\n- 待执行任务：${restartData.tasks.pending.length} 个`;
        }
        if (restartData.tasks.inProgress.length > 0) {
          contextPrompt += `\n- 进行中任务：${restartData.tasks.inProgress.length} 个`;
        }
      }

      if (taskCounts.backgroundCount > 0) {
        contextPrompt += `\n- 中断的后台任务：${taskCounts.backgroundCount} 个（已标记为失败）`;
      }

      contextPrompt += `

请使用 task_list 查看所有任务，然后继续执行未完成的工作。优先处理 in_progress 状态的任务。`;
    } else {
      contextPrompt += `

请继续完成之前的任务。如果任务已完成，请总结结果。`;
    }

    // 不要使用 addMessage，而是直接通过 prompt 触发
    console.log(`💡 准备自动触发 Agent 继续之前的工作\n`);

    // 清理上下文文件
    try { unlinkSync(RESTART_CONTEXT); } catch { /* ignore */ }
    restartData = null;

    // 直接发送上下文提示消息，触发 agent 循环
    triggerAgentLoop(session, contextPrompt);
  } else {
    // 清理上下文文件
    try { unlinkSync(RESTART_CONTEXT); } catch { /* ignore */ }
    restartData = null;
  }
}

checkRestartContext();

// 选择 agent loop 模式
const USE_BACKGROUND_MODE = process.env.BACKGROUND_MODE === "true";

const piDir = join(process.cwd(), ".pi-invest");

async function main() {
  let feishuBot: FeishuBotHandle | null = null;
  let gatewayHandle: import("./gateway/start-gateway.js").GatewayHandle | null = null;

  try {
    console.log("🚀 启动 PI Investment - AI 股票投资顾问...\n");

    // 自动化锁（2026-08-13）：headless 进程持有调度器/gateway/feishu 三件套时，
    // TUI 降级为纯交互模式——不重复起三件套（防任务双跑 + 3002 端口抢占 + 飞书双连）
    const { readLiveAutomationLock, acquireAutomationLock, releaseAutomationLock } =
      await import("../services/runtime-lock.js");
    const heldLock = readLiveAutomationLock(piDir);
    const automationDegraded = heldLock !== null && heldLock.pid !== process.pid;
    if (automationDegraded) {
      console.log(
        `ℹ️ 检测到 headless 自动化进程（pid=${heldLock!.pid}），本 TUI 以纯交互模式运行\n` +
          `   （调度器/wake/feishu 由 headless 托管）\n`,
      );
    } else {
      acquireAutomationLock(piDir, "tui");
    }

    // 启动飞书 Bot（后台 WebSocket 监听）
    if (!automationDegraded) {
      feishuBot = await startFeishuBot();
      if (feishuBot) {
        console.log("");
      }
    }

    // Wake channel（gateway WakeAdapter）：与 TUI/feishu 同进程提供 /wake 接收
    // 失败仅降级警告，不影响 TUI 与 feishu
    if (!automationDegraded) {
      try {
        const { startGateway } = await import("./gateway/start-gateway.js");
        const { WakeAdapter } = await import("./gateway/adapters/wake-adapter.js");
        gatewayHandle = await startGateway([new WakeAdapter()]);
        console.log("🔔 Wake channel 已集成启动（127.0.0.1:3002）");
      } catch (err) {
        console.warn("⚠️ Wake channel 启动失败（降级，不影响 TUI/feishu）:", err instanceof Error ? err.message : err);
      }
    }

    // 先初始化 logger（在创建 session 之前）
    logger.initSession(restartData?.prevSessionKey);
    console.log(`📋 Session: ${logger.getSessionKey()}\n`);

    // 注意：DailyReviewService 和 StopLossAlertService 已被移除
    // 如需复盘和止损告警功能，请使用 Agent 工具

    // 根据环境变量选择 agent loop
    const session = USE_BACKGROUND_MODE
      ? await getSessionBackground()
      : await getSessionNormal(restartData?.sdkSessionFile
          ? {
              type: "interactive",
              sessionId: restartData.sdkSessionId || restartData.prevSessionKey || "restarted",
              metadata: { sdkSessionFile: restartData.sdkSessionFile },
            }
          : undefined);

    console.log(`📌 模式: ${USE_BACKGROUND_MODE ? "Background (并行任务)" : "Normal (串行)"}\n`);

    console.log("✅ 投资顾问初始化完成\n");

    // 初始化性能监控
    const perfMonitor = new PerformanceMonitor();

    // 用工厂函数包装 session，注入 logger + 性能监控
    wrapSessionWithLogger(session, perfMonitor);

    // 如果是从 restart_agent 重启，先恢复任务，再恢复对话历史
    const taskCounts = restoreTasksFromContext();
    restoreConversationIntoSession(session, taskCounts);

    // 启动数据库调度器。CRON.json 已废弃，数据库是唯一任务来源。
    // headless 持锁时跳过（自动化三件套归 headless）
    const schedulerRuntime = automationDegraded ? null : await startSchedulerRuntime({
      promptAgent: async (message) => {
        // 调度任务消息自带完整工作流，跳过技能路由（避免被强制注入 portfolio-entry 等 skill）
        const options: PromptOptionsWithRouting = { skipSkillRouting: true };
        await session.prompt(message, options);
      },
      writeOutput: (message) => process.stdout.write(message),
    }).catch((error) => {
      console.error(`❌ 数据库调度器启动失败: ${error instanceof Error ? error.message : String(error)}`);
      return null;
    });

    // 列出已加载的数据库调度任务
    const jobs = schedulerRuntime ? await schedulerRuntime.service.listTaskSummaries() : [];
    if (jobs.length > 0) {
      console.log(`⏰ 数据库调度任务（${jobs.length} 个）:`);
      for (const j of jobs) {
        const status = j.enabled ? "✅" : "❌";
        const next = j.nextRunAt ? ` 下次：${new Date(j.nextRunAt).toLocaleString("zh-CN")}` : "";
        console.log(`  ${status} ${j.name}（${j.scheduleKind}: ${j.id}）${next}`);
      }
      console.log();
    }

    // 监听进程退出
    process.on('SIGINT', async () => {
      schedulerRuntime?.service.stop();
      if (feishuBot) feishuBot.shutdown();
      if (gatewayHandle) await gatewayHandle.shutdown();
      releaseAutomationLock(piDir);
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
    // 使用 createAgentSessionRuntime 正确构造 runtime，支持 /resume 命令
    // SDK 0.73+：services 由 runtime factory（createRuntimeForSession）内部通过
    // createAgentSessionServices 创建，此处只需提供 cwd / agentDir / sessionManager
    const runtime = await createAgentSessionRuntime(
      createRuntimeForSession as any,
      {
        cwd: process.cwd(),
        agentDir: getAgentDir(),
        sessionManager: (session as any).sessionManager,
      },
    );
    const mode = new InteractiveMode(runtime as any);
    await mode.run();

    // 正常退出时保存会话记忆
    console.log("\n🧠 保存会话记忆...");
    await saveSessionMemoryAsync(session, {
      timeout: 30000,
      verbose: false
    }).catch(err => {
      console.error(`记忆保存失败: ${err instanceof Error ? err.message : String(err)}`);
    });

    schedulerRuntime?.service.stop();
    logger.logSessionEnd();
  } catch (error) {
    console.error("❌ 启动失败:", error instanceof Error ? error.message : String(error));
    process.exit(1);
  }
}

main();
