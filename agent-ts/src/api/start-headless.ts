#!/usr/bin/env node
/**
 * Headless Agent 入口（无 TUI）——自动化宿主
 *
 * 用途：以纯后台形态运行 agent 的自动化三件套：
 *   - Agent OS Scheduler（定时任务统一调度）
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
import { registerTasksToAgentOS } from "../core/bootstrap/agent-os-task-registration.js";
import { initializeAgentOS } from "../infrastructure/agent-os/client.js";
import { startGateway } from "./gateway/start-gateway.js";
import { WakeAdapter } from "./gateway/adapters/wake-adapter.js";
import { AgentOSAdapter } from "./gateway/adapters/agent-os-adapter.js";
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

  // 1. 初始化 LLM
  initLLM(paths.piDir);

  // 2. 初始化 Agent OS Client
  console.log("🔌 正在连接 Agent OS...");
  await initializeAgentOS();
  console.log("✅ Agent OS Client 已初始化");

  // 3. 启动健康自检（只诊断，不在 headless 里重启后端——那是 launchd 的职责）
  const healthReport = await runStartupHealthCheck({
    apiUrl: process.env.QUANTSYS_V2_API_URL ?? "http://127.0.0.1:5001",
  });
  console.log(formatHealthForConsole(healthReport));

  // 4. 工具引用 sanity check（warn 不阻断）
  await runToolReferenceCheckOnStartup(process.cwd());

  // 5. 注册任务到 Agent OS Scheduler
  console.log("\n🚀 正在注册任务到 Agent OS...");
  const webhookBaseUrl = process.env.AGENT_WEBHOOK_BASE_URL || 'http://localhost:3002';

  try {
    const { summary, results } = await registerTasksToAgentOS({
      webhookBaseUrl,
      force: false,
    });

    console.log(`✅ 任务注册完成: ${summary.created} 创建, ${summary.updated} 更新, ${summary.skipped} 跳过, ${summary.failed} 失败`);
    results.forEach((result) => {
      const statusIcon = result.status === 'failed' ? '✗' : '✓';
      console.log(`  ${statusIcon} ${result.task}: ${result.status}`);
    });
  } catch (error) {
    console.error("❌ 任务注册失败:", error);
    throw error;
  }

  // 6. Gateway (Wake + Agent OS webhook, 端口 3002)
  const gatewayHandle = await startGateway(
    [new WakeAdapter(), new AgentOSAdapter()],
    { sharedPort: 3002 }
  );
  console.log("🌐 Gateway 已启动（127.0.0.1:3002）");
  console.log("  - Wake channel: POST /wake");
  console.log("  - Agent OS webhook: POST /api/webhook/agent-os/trigger");

  // 7. 飞书 bot（未配置时返回 null，自动跳过）
  const feishuBot = await startFeishuBot();
  if (feishuBot) console.log("💬 飞书 bot 已启动");

  console.log("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
  console.log("🎉 Headless agent 启动完成（Agent OS 调度 + wake + feishu）");
  console.log("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");

  const shutdown = async (signal: string) => {
    console.log(`\n🛑 收到 ${signal}，正在优雅退出...`);
    try {
      // Note: Scheduler now runs in Agent OS, no local runtime to stop
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
