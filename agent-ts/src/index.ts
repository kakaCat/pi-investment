/**
 * PI Investment - AI 股票投资顾问
 * Entry point
 */
import "./infrastructure/tui/pi-tui-compat.js";
import "./api/index.js";
import { initAgentDecisionTasks } from "./services/scheduler/init-agent-tasks.js";
import { startSchedulerRuntime } from "./services/scheduler/scheduler-runtime.js";
import { createSession } from "./session-facade.js";
import {
  runStartupHealthCheck,
  formatHealthForConsole,
} from "./services/health/startup-health-check.js";
import { startService } from "./infrastructure/tools/agent/backend-control-tool.js";

// 注意：调度器已迁移到 quantsys-v2
// Agent 只保留 AI 决策任务，通过 agent_turn 类型执行
// 数据处理任务由 quantsys-v2 的调度器自主完成

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

    // 1. 初始化 Agent AI 决策任务
    await initAgentDecisionTasks();
    console.log("✅ Agent AI 决策任务初始化完成");

    // 2. 启动调度器（关键！）
    console.log("\n🚀 正在启动调度器...");
    await startSchedulerRuntime({
      promptAgent: async (message: string) => {
        console.log("\n⏰ 定时任务触发，唤醒 Agent...");
        console.log(`📋 任务消息: ${message.substring(0, 100)}...`);

        try {
          // 创建新的 Agent 会话
          const { session } = await createSession({
            cwd: process.cwd()
          });

          // 执行 Agent prompt（自主决策）
          await session.prompt(message);

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
