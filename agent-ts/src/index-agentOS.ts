/**
 * PI Investment - AI 股票投资顾问
 * Entry point with Agent OS Integration (WP-4)
 *
 * 集成 Agent OS:
 * 1. 启动时注册任务到 Agent OS Scheduler
 * 2. 启动 Webhook 服务器接收 Agent OS 任务触发
 * 3. Memory 工具通过 Agent OS 实现（可选切换）
 */
import "./infrastructure/tui/pi-tui-compat.js";
import "./api/index.js";
import { initAgentDecisionTasks } from "./services/scheduler/init-agent-tasks.js";
import { startSchedulerRuntime } from "./services/scheduler/scheduler-runtime.js";
import { createSchedulerSession } from "./services/scheduler/scheduler-session.js";
import type { AgentKind } from "./domain/agent-roles/types.js";
import {
  runStartupHealthCheck,
  formatHealthForConsole,
} from "./services/health/startup-health-check.js";
import { startService } from "./infrastructure/tools/agent/backend-control-tool.js";
import { runToolReferenceCheckOnStartup } from "./infrastructure/tools/tool-reference-check.js";

// WP-4: Agent OS 集成
import { registerTasksToOS, unregisterTasksFromOS } from "./core/bootstrap/task-registration.js";
import { createWebhookServer, startWebhookServer } from "./infrastructure/gateway/webhook-server.js";
import { createAgentOSTaskExecutor } from "./core/bootstrap/agent-os-executor.js";

// 配置：是否启用 Agent OS 集成
const ENABLE_AGENT_OS = process.env.ENABLE_AGENT_OS === 'true';
const WEBHOOK_PORT = parseInt(process.env.WEBHOOK_PORT || '3000', 10);
const WEBHOOK_HOST = process.env.WEBHOOK_HOST || '0.0.0.0';

console.log("🤖 正在初始化 Agent AI 决策任务...");

async function main() {
  try {
    // 0. 启动健康自检（后端宕机时自动重启一次，结果注入系统提示词）
    const healthReport = await runStartupHealthCheck({
      apiUrl: process.env.QUANTSYS_V2_API_URL ?? "http://127.0.0.1:5001",
      restartBackend: async () => {
        console.log("🔄 检测到后端宕机，尝试自动重启...");
        const result = await startService("all");
        return result.success;
      },
    });
    console.log(formatHealthForConsole(healthReport));

    // 0.5 工具引用 sanity check：skill/任务模板引用了不存在的工具名时 warn（不阻断）
    await runToolReferenceCheckOnStartup(process.cwd());

    // === WP-4: Agent OS 集成 ===
    if (ENABLE_AGENT_OS) {
      console.log("\n🔧 Agent OS 集成模式已启用");

      // 1. 启动 Webhook 服务器
      console.log("🌐 正在启动 Webhook 服务器...");
      const taskExecutor = createAgentOSTaskExecutor();
      const webhookApp = createWebhookServer(taskExecutor, {
        port: WEBHOOK_PORT,
        host: WEBHOOK_HOST,
      });

      await startWebhookServer(webhookApp, WEBHOOK_PORT, WEBHOOK_HOST);
      console.log("✅ Webhook 服务器启动成功");

      // 2. 注册任务到 Agent OS Scheduler
      console.log("\n📋 正在注册任务到 Agent OS...");
      const webhookUrl = `http://localhost:${WEBHOOK_PORT}/api/agent/trigger`;
      try {
        await registerTasksToOS(webhookUrl, 'fin-agent');
        console.log("✅ 任务注册成功");
      } catch (error: any) {
        console.warn("⚠️  任务注册失败（Agent OS 可能未启动）:", error.message);
        console.log("   继续启动，任务可以稍后手动注册");
      }

      // 3. 注册退出时清理
      process.on('SIGINT', async () => {
        console.log("\n\n🛑 收到退出信号，正在清理...");
        try {
          await unregisterTasksFromOS();
          console.log("✅ 任务已注销");
        } catch (error: any) {
          console.warn("⚠️  任务注销失败:", error.message);
        }
        process.exit(0);
      });

      console.log("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
      console.log("🎉 Agent OS 集成启动成功");
      console.log("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
      console.log("\n💡 Agent OS 任务将自动触发:");
      console.log("  - daily_recall_audit:    每天 02:00");
      console.log("  - market_open_scan:      工作日 09:00");
      console.log("  - market_close_review:   工作日 15:30");
      console.log("  - weekly_pool_refresh:   每周六 20:00\n");

    } else {
      // === 传统模式：本地调度器 ===
      console.log("\n🔧 本地调度器模式（传统）");

      // 1. 初始化 Agent AI 决策任务 + 启动调度器
      // 自动化锁守卫（2026-08-13）：headless 进程持有时 TUI 不起调度器（防任务双跑）
      const { readLiveAutomationLock } = await import("./services/runtime-lock.js");
      const { paths: lockPaths } = await import("./config/config.js");
      if (readLiveAutomationLock(lockPaths.piDir)) {
        console.log("ℹ️ 调度器由 headless 进程托管，本进程跳过");
      } else {
        await initAgentDecisionTasks();
        console.log("✅ Agent AI 决策任务初始化完成");

        // 2. 启动调度器（关键！）
        console.log("\n🚀 正在启动调度器...");
        await startSchedulerRuntime({
          promptAgent: async (message: string, agentKind?: AgentKind) => {
            console.log("\n⏰ 定时任务触发，唤醒 Agent...");
            console.log(`📋 任务消息: ${message.substring(0, 100)}...`);

            try {
              // 创建新的 Agent 会话（A2-T2：按任务 agentKind 装配，fin 走裸会话零变化）
              // P2-T3 接线：resourceLoader 让 recallExtension 加载；source=rpc → scheduled-task flow。
              const { session } = await createSchedulerSession(agentKind ?? "fin");

              // 执行 Agent prompt（自主决策）
              await session.prompt(message, { source: "rpc" });

              console.log("✅ Agent 任务执行完成");
            } catch (error) {
              console.error("❌ Agent 任务执行失败:", error);
              throw error;
            }
          }
        });

        console.log("✅ 调度器启动成功");
        console.log("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
        console.log("🎉 Agent AI 自主决策系统已启动");
        console.log("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
        console.log("\n💡 定时任务将自动执行:");
        console.log("  - morning_ai_analysis:   工作日 09:00");
        console.log("  - realtime_quick_check:  工作日 09:00-14:55 (每30分钟)");
        console.log("  - daily_ai_review:       每天 18:00\n");
      }
    }

  } catch (error) {
    console.error("❌ 初始化失败:", error);
    throw error;
  }
}

// 启动
main().catch((err) => {
  console.error("❌ 启动失败:", err);
  process.exit(1);
});
