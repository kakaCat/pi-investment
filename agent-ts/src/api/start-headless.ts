#!/usr/bin/env node
/**
 * Headless Agent 入口（无 TUI）——自动化宿主
 *
 * 用途：以纯后台形态运行 agent 的自动化三件套：
 *   - 调度器（agent_turn 定时任务：盘前/盘中/复盘/周日蒸馏等）
 *   - Wake gateway（127.0.0.1:3002，接收 v2 WatchEngine/调度器唤醒）
 *   - 飞书 bot
 *
 * 与 TUI（npm run dev）互斥：经 automation.lock（services/runtime-lock.ts）
 * 先到者持有自动化三件套；TUI 后启动时检测到锁会降级为纯交互模式
 * （不重复起调度器/gateway/feishu，避免任务双跑与端口抢占）。
 *
 * 运维脚本：scripts/ops/pi-services.sh restart agent
 */
import "dotenv/config";
import { initLLM } from "../services/llm/index.js";
import { paths } from "../config/config.js";
import {
  acquireAutomationLock,
  releaseAutomationLock,
  readLiveAutomationLock,
} from "../services/runtime-lock.js";
import { initAgentDecisionTasks } from "../services/scheduler/init-agent-tasks.js";
import { startSchedulerRuntime } from "../services/scheduler/scheduler-runtime.js";
import { createSchedulerSession } from "../services/scheduler/scheduler-session.js";
import type { AgentKind } from "../domain/agent-roles/types.js";
import { startGateway } from "./gateway/start-gateway.js";
import { WakeAdapter } from "./gateway/adapters/wake-adapter.js";
import { startFeishuBot } from "./feishu.js";
import {
  runStartupHealthCheck,
  formatHealthForConsole,
} from "../services/health/startup-health-check.js";
import { runToolReferenceCheckOnStartup } from "../infrastructure/tools/tool-reference-check.js";

async function main() {
  console.log("🤖 PI Investment Agent（headless 自动化模式）\n");

  // 0. 自动化锁：已有活体持有者（TUI 或另一个 headless）则拒起，防任务双跑
  const existing = readLiveAutomationLock(paths.piDir);
  if (existing) {
    console.error(
      `❌ 自动化锁已被持有：pid=${existing.pid} role=${existing.role}（${existing.startedAt}）\n` +
        `   如需接管，请先停止该进程。`,
    );
    process.exit(1);
  }
  if (!acquireAutomationLock(paths.piDir, "headless")) {
    console.error("❌ 获取自动化锁失败");
    process.exit(1);
  }

  // 1. 启动健康自检（只诊断，不在 headless 里重启后端——那是 launchd 的职责）
  const healthReport = await runStartupHealthCheck({
    apiUrl: process.env.QUANTSYS_V2_API_URL ?? "http://127.0.0.1:5001",
  });
  console.log(formatHealthForConsole(healthReport));

  // 2. 工具引用 sanity check（warn 不阻断）
  await runToolReferenceCheckOnStartup(process.cwd());

  // 3. 启动调度器 + 注册 agent_turn 定时任务
  // 顺序关键（2026-08-13 事故）：getSchedulerRuntime 是单例，先到者的 executor 生效。
  // initAgentDecisionTasks 内部用无参 getSchedulerRuntime()——若它先跑，
  // 单例 executor 没有 promptAgent，agent_turn 任务到点全抛
  // "No prompt agent configured"（run 记录只在内存，无任何日志，静默丢失）。
  // 必须先带 promptAgent 建运行时，再注册任务。
  const schedulerRuntime = await startSchedulerRuntime({
    promptAgent: async (message: string, agentKind?: AgentKind) => {
      console.log(`\n⏰ 定时任务触发: ${message.substring(0, 80)}...`);
      // 每个任务独立会话（与 index.ts 同款模式）；
      // createSchedulerSession 出来的会话不经 TUI 的 wrapSessionWithLogger，
      // 调度消息本身自带完整工作流。A2-T2：按任务 agentKind 装配（fin 走裸会话零变化）。
      // P2-T3 接线：resourceLoader 让 recallExtension 加载；source=rpc → scheduled-task flow。
      const { session } = await createSchedulerSession(agentKind ?? "fin");
      await session.prompt(message, { source: "rpc" });
      console.log("✅ 定时任务执行完成");
    },
    writeOutput: (message) => process.stdout.write(message),
  });
  await initAgentDecisionTasks();

  const jobs = await schedulerRuntime.service.listTaskSummaries();
  console.log(`⏰ 调度任务（${jobs.length} 个）:`);
  for (const j of jobs) {
    const next = j.nextRunAt ? ` 下次：${new Date(j.nextRunAt).toLocaleString("zh-CN")}` : "";
    console.log(`  ${j.enabled ? "✅" : "❌"} ${j.name}（${j.id}）${next}`);
  }

  // 4. Wake gateway（3002）
  const gatewayHandle = await startGateway([new WakeAdapter()]);
  console.log("🔔 Wake channel 已启动（127.0.0.1:3002）");

  // 5. 飞书 bot（未配置时返回 null，自动跳过）
  const feishuBot = await startFeishuBot();
  if (feishuBot) console.log("💬 飞书 bot 已启动");

  console.log("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
  console.log("🎉 Headless agent 启动完成（调度器 + wake + feishu）");
  console.log("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");

  const shutdown = async (signal: string) => {
    console.log(`\n🛑 收到 ${signal}，正在优雅退出...`);
    try {
      schedulerRuntime.service.stop();
      await gatewayHandle.shutdown();
      if (feishuBot) await feishuBot.shutdown();
    } finally {
      releaseAutomationLock(paths.piDir);
      process.exit(0);
    }
  };
  process.on("SIGINT", () => void shutdown("SIGINT"));
  process.on("SIGTERM", () => void shutdown("SIGTERM"));
}

initLLM(paths.piDir);
main().catch((err) => {
  console.error("❌ headless 启动失败:", err);
  releaseAutomationLock(paths.piDir);
  process.exit(1);
});
