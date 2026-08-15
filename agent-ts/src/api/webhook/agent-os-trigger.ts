/**
 * Agent OS Webhook Handler
 * 接收 Agent OS 的任务触发请求
 */
import { Router } from 'express';
import { getAgentOSClient } from '../../infrastructure/agent-os/client.js';
import { logger } from '../../infrastructure/logging/index.js';
import type { AgentKind } from '../../domain/agent-roles/types.js';
import { createSchedulerSession } from '../../services/scheduler/scheduler-session.js';

export const agentOSWebhookRouter = Router();

interface AgentOSWebhookPayload {
  task_id: string;
  task_name: string;
  execution_id: string;
  payload: {
    kind: 'agent_turn';
    message: string;
    agentKind?: AgentKind;
  };
}

/**
 * Agent OS 任务触发端点
 * POST /api/webhook/agent-os/trigger
 */
agentOSWebhookRouter.post('/agent-os/trigger', async (req, res) => {
  const payload: AgentOSWebhookPayload = req.body;

  logger.info('[AgentOS Webhook] Task triggered', {
    task_id: payload.task_id,
    task_name: payload.task_name,
    execution_id: payload.execution_id,
  });

  try {
    // 1. 创建 agent session
    const agentKind = payload.payload.agentKind || 'fin';
    const { session } = await createSchedulerSession(agentKind);

    // 2. 执行任务
    logger.info('[AgentOS Webhook] Executing task', {
      task_name: payload.task_name,
      agentKind,
    });

    // 通过 prompt 执行任务，使用 source: 'rpc' 跳过召回注入（调度任务专属 flow）
    await session.prompt(payload.payload.message, { source: 'rpc' });

    logger.info('[AgentOS Webhook] Task completed', {
      execution_id: payload.execution_id,
    });

    // 3. 更新 Agent OS execution 状态
    const client = getAgentOSClient();
    await client.scheduler.updateExecution(payload.execution_id, {
      status: 'completed',
      result: { success: true },
    });

    // 4. 返回成功响应
    res.json({
      success: true,
      execution_id: payload.execution_id,
    });

  } catch (error) {
    logger.error('[AgentOS Webhook] Task failed', {
      execution_id: payload.execution_id,
      error: error instanceof Error ? error.message : String(error),
    });

    // 更新失败状态
    try {
      const client = getAgentOSClient();
      await client.scheduler.updateExecution(payload.execution_id, {
        status: 'failed',
        error: error instanceof Error ? error.message : String(error),
      });
    } catch (updateError) {
      logger.error('[AgentOS Webhook] Failed to update execution status', {
        error: updateError,
      });
    }

    // 返回错误响应
    res.status(500).json({
      success: false,
      error: error instanceof Error ? error.message : 'Unknown error',
    });
  }
});
