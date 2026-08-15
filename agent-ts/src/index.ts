/**
 * PI Investment - AI 股票投资顾问
 * Entry point
 */
import "./infrastructure/tui/pi-tui-compat.js";
import "./api/index.js";
import {
  runStartupHealthCheck,
  formatHealthForConsole,
} from "./services/health/startup-health-check.js";
import { startService } from "./infrastructure/tools/agent/backend-control-tool.js";
import { runToolReferenceCheckOnStartup } from "./infrastructure/tools/tool-reference-check.js";
import { notificationService } from "./services/notification/notification-service.js";
import { NotificationFactory } from "./infrastructure/notification/notification-factory.js";
import { initAsyncLogQueue, getAsyncLogQueue } from "./infrastructure/agent-os/async-log-queue.js";
import { initializeAgentOS } from "./infrastructure/agent-os/client.js";
import { registerTasksToAgentOS } from "./core/bootstrap/agent-os-task-registration.js";

// 注意：调度器已完全迁移到 Agent OS
// Agent 只保留 AI 决策任务，通过 Agent OS Scheduler 统一调度
// 数据处理任务由 quantsys-v2 的调度器自主完成

console.log("🤖 正在初始化 Agent AI 决策任务...");

async function main() {
  try {
    // 0. 初始化 Agent OS Client（优先级最高）
    console.log('🔌 正在连接 Agent OS...');
    await initializeAgentOS();
    console.log('✅ Agent OS Client 已初始化');

    // 0. 初始化 Agent OS 异步日志队列
    if (process.env.AGENT_OS_ENABLED === 'true') {
      try {
        initAsyncLogQueue({
          maxQueueSize: 1000,
          batchSize: 20,
          flushIntervalMs: 5000,
          maxRetries: 3,
          onSuccess: (count) => {
            console.log(`✅ [Agent OS] 上传 ${count} 条日志`);
          },
          onError: (error, entry) => {
            console.error(`❌ [Agent OS] 日志上传失败:`, error.message);
          },
        });
        console.log('✅ Agent OS 异步日志队列已启动');

        // 记录启动事件
        const queue = getAsyncLogQueue();
        queue.pushDecision(
          'system',
          'agent_startup',
          'Agent 系统启动',
          'success',
          {
            version: process.env.npm_package_version,
            node_version: process.version,
            timestamp: Date.now(),
          },
          'high'
        );
      } catch (error) {
        console.warn('⚠️  Agent OS 异步日志队列启动失败:', error);
      }
    }

    // Note: Agent OS 通知渠道集成待实现
    // TODO: 实现 NotificationFactory.createAgentOSChannel

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

    // 1. 注册任务到 Agent OS Scheduler
    // 自动化锁守卫（2026-08-13）：headless 进程持有时 TUI 不起调度器（防任务双跑）
    const { readLiveAutomationLock } = await import("./services/runtime-lock.js");
    const { paths: lockPaths } = await import("./config/config.js");
    if (readLiveAutomationLock(lockPaths.piDir)) {
      console.log("ℹ️ 调度器由 headless 进程托管，本进程跳过");
    } else {
      // 使用 Agent OS 集中式调度器
      console.log("\n🚀 正在注册任务到 Agent OS...");
      const webhookBaseUrl = process.env.AGENT_WEBHOOK_BASE_URL || 'http://localhost:3002';

      try {
        const { summary, results } = await registerTasksToAgentOS({
          webhookBaseUrl,
          force: false, // 启动时不强制更新已存在的任务
        });

        console.log(`✅ 任务注册完成: ${summary.created} 创建, ${summary.updated} 更新, ${summary.skipped} 跳过, ${summary.failed} 失败`);
        results.forEach((result) => {
          const statusIcon = result.status === 'failed' ? '✗' : '✓';
          console.log(`  ${statusIcon} ${result.task}: ${result.status}`);
        });

        console.log("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
        console.log("🎉 Agent AI 自主决策系统已启动 (Agent OS 调度模式)");
        console.log("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
        console.log(`\n💡 任务由 Agent OS 集中调度，webhook 地址: ${webhookBaseUrl}/api/webhook/agent-os/trigger\n`);
      } catch (error) {
        console.error("❌ 任务注册失败:", error);
        throw error;
      }
    }

  } catch (error) {
    console.error("❌ 初始化失败:", error);
    throw error;
  }
}

// 进程退出时的清理逻辑
process.on('SIGINT', async () => {
  console.log('\n🛑 正在关闭 Agent 系统...');

  try {
    // 记录关闭事件
    if (process.env.AGENT_OS_ENABLED === 'true') {
      const queue = getAsyncLogQueue();
      queue.pushDecision(
        'system',
        'agent_shutdown',
        'Agent 系统正在关闭',
        'shutdown',
        { timestamp: Date.now() },
        'critical' // 关键事件，立即上传
      );

      // 停止日志队列（自动刷新剩余日志）
      await queue.stop();
      console.log('✅ Agent OS 日志队列已关闭');
    }
  } catch (error) {
    console.error('❌ 清理失败:', error);
  }

  console.log('👋 Agent 系统已关闭');
  process.exit(0);
});

process.on('SIGTERM', async () => {
  console.log('\n🛑 收到 SIGTERM 信号，正在关闭...');

  try {
    if (process.env.AGENT_OS_ENABLED === 'true') {
      const queue = getAsyncLogQueue();
      await queue.stop();
    }
  } catch (error) {
    console.error('❌ 清理失败:', error);
  }

  process.exit(0);
});

// 启动
main().catch((err) => {
  console.error("❌ 启动失败:", err);
  process.exit(1);
});
