/**
 * AgentOSAdapter — Agent OS Scheduler webhook 接收通道
 * POST /api/webhook/agent-os/trigger → 执行 Agent OS 调度任务
 */
import type { Express } from "express";
import { agentOSWebhookRouter } from "../../webhook/agent-os-trigger.js";
import type { ChannelAdapter, GatewayHandlers } from "../types.js";

export class AgentOSAdapter implements ChannelAdapter {
  readonly name = "agent-os";

  start(handlers: GatewayHandlers): void {
    // 独立启动模式不支持（需要共享 Express app）
    console.warn('[AgentOS Adapter] 需要共享 Express app，请使用 startShared() 方法');
  }

  /**
   * 使用共享的 Express app 启动
   * @param handlers - Gateway handlers
   * @param app - 共享的 Express app
   */
  startShared(handlers: GatewayHandlers, app: Express): void {
    // 注册 Agent OS webhook 路由
    app.use('/api/webhook', agentOSWebhookRouter);

    console.log('[AgentOS] Webhook 路由已注册:');
    console.log('  - POST /api/webhook/agent-os/trigger');
  }

  shutdown(): void {
    // Webhook 路由随 Express app 关闭，无需额外清理
  }
}
