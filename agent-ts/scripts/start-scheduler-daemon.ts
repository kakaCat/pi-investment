#!/usr/bin/env tsx
/**
 * 启动调度器守护进程
 * 持续运行，执行定时任务
 */
import { initAgentDecisionTasks } from "../src/services/scheduler/init-agent-tasks.js";
import { startSchedulerRuntime } from "../src/services/scheduler/scheduler-runtime.js";
import { createSession } from "../src/session-facade.js";

console.log("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
console.log("🤖 启动 Agent AI 调度器守护进程");
console.log("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n");

async function main() {
  try {
    // 1. 初始化 Agent AI 决策任务
    console.log("📋 初始化 Agent AI 决策任务...");
    await initAgentDecisionTasks();
    console.log("✅ 任务初始化完成\n");

    // 2. 启动调度器
    console.log("🚀 启动调度器...");
    const runtime = await startSchedulerRuntime({
      promptAgent: async (message: string) => {
        const timestamp = new Date().toLocaleString("zh-CN");
        console.log("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
        console.log(`⏰ ${timestamp} - 定时任务触发`);
        console.log("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
        console.log(`📋 任务消息:\n${message.substring(0, 200)}...\n`);

        try {
          // 创建新的 Agent 会话
          const { session } = await createSession({
            cwd: process.cwd(),
          });

          // 执行 Agent prompt（自主决策）
          await session.prompt(message);

          console.log("✅ Agent 任务执行完成\n");
        } catch (error) {
          console.error("❌ Agent 任务执行失败:", error);
          throw error;
        }
      },
    });

    console.log("✅ 调度器启动成功\n");

    // 3. 显示任务摘要
    const summaries = await runtime.service.listTaskSummaries();
    console.log("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
    console.log("📊 定时任务列表");
    console.log("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n");

    for (const summary of summaries) {
      if ((summary as any).deletedAt) continue;

      console.log(`  • ${summary.name}`);
      console.log(`    状态: ${summary.enabled ? "✅ 启用" : "⏸️  禁用"}`);
      console.log(`    调度: ${summary.scheduleExpr || "无"}`);
      console.log(
        `    下次运行: ${summary.nextRunAt ? new Date(summary.nextRunAt).toLocaleString("zh-CN") : "无"}`
      );
      console.log("");
    }

    console.log("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
    console.log("🎉 Agent AI 自主决策系统已启动");
    console.log("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
    console.log("\n💡 调度器将持续运行，按 Ctrl+C 停止\n");

    // 4. 保持进程运行
    process.on("SIGINT", () => {
      console.log("\n\n🛑 收到停止信号，正在关闭...");
      process.exit(0);
    });

    // 定期输出心跳，确认调度器仍在运行
    setInterval(() => {
      const now = new Date().toLocaleString("zh-CN");
      console.log(`💓 ${now} - 调度器运行中...`);
    }, 60000); // 每分钟输出一次

  } catch (error) {
    console.error("❌ 启动失败:", error);
    process.exit(1);
  }
}

main();
