/**
 * Agent OS Webhook Handler
 * 接收 Agent OS 的任务触发请求
 */
import { Router } from 'express';
import { logger } from '../../infrastructure/logging/index.js';
import type { AgentKind } from '../../domain/agent-roles/types.js';
import { createSchedulerSession } from '../../services/scheduler/scheduler-session.js';

export const agentOSWebhookRouter = Router();

/**
 * WP-15 接收契约（2026-09-08 修复对齐，w-752decf5）：
 * Agent OS scheduler 实际发送体（见 agent-os buildWebhookPayload）为
 *   { job_id, job_name, trigger_time, metadata: { ...task.Payload, run_id, owner, triggered_by } }
 * 任务定义 payload（fin-agent 注册的 { kind:'agent_turn', message, agentKind? }、
 * DH 注册的 { prompt, executor }）被 Agent OS 平铺进 metadata。
 * 旧实现按 agent_turn 顶层形状解析（payload.payload.agentKind），实际 body 顶层无 payload 键
 * → metadata 里的指令永远取不到 → 每次 500（undefined.agentKind）→ fin-agent 例行任务 100% failed。
 * 现按 WP-15 主路径解析，兼容旧形状（payload.payload）以防误配。
 */
interface AgentOSWebhookPayload {
  // WP-15（Agent OS 实发）
  job_id?: string;
  job_name?: string;
  trigger_time?: string;
  metadata?: {
    kind?: string;
    message?: string;
    prompt?: string;
    agentKind?: AgentKind;
    run_id?: string;
    owner?: string;
    triggered_by?: string;
  };
  // 旧 agent_turn 形状兼容
  task_id?: string;
  task_name?: string;
  execution_id?: string;
  payload?: {
    kind?: string;
    message?: string;
    agentKind?: AgentKind;
  };
}

/**
 * Agent OS 任务触发端点
 * POST /api/webhook/agent-os/trigger
 */
agentOSWebhookRouter.post('/agent-os/trigger', async (req, res) => {
  const body = (req.body || {}) as AgentOSWebhookPayload;
  const md = body.metadata ?? body.payload ?? {};

  const jobId = body.job_id ?? body.task_id ?? '';
  const taskName = body.job_name ?? body.task_name ?? '';
  const message = md.message ?? body.payload?.message ?? md.prompt ?? '';
  const agentKind = (md.agentKind ?? body.payload?.agentKind ?? 'fin') as AgentKind;
  const executionId = body.execution_id ?? md.run_id ?? '';

  logger.info('[AgentOS Webhook] Task triggered', {
    job_id: jobId,
    task_name: taskName,
    execution_id: executionId,
  });

  // 任务指令缺失直接 400 明确报错（替代原 TypeError 500），Agent OS 记 failed
  if (!message) {
    const errMsg = 'webhook body 缺任务指令 message（WP-15 在 metadata.message/prompt；旧契约在 payload.message）。job_name=' + (taskName || '(空)') + ' job_id=' + (jobId || '(空)');
    logger.error('[AgentOS Webhook] Task rejected: missing message', { task_name: taskName, job_id: jobId });
    res.status(400).json({ success: false, error: errMsg });
    return;
  }

  try {
    // 1. 创建 agent session（agentKind 取自任务 payload：fin / memory / evolution）
    const { session } = await createSchedulerSession(agentKind);

    // 2. 执行任务
    logger.info('[AgentOS Webhook] Executing task', {
      task_name: taskName,
      agentKind,
    });

    // 通过 message 执行任务，使用 source: 'rpc' 跳过召回注入（调度任务专属 flow）
    await session.prompt(message, { source: 'rpc' });

    logger.info('[AgentOS Webhook] Task completed', {
      task_name: taskName,
      execution_id: executionId,
    });

    // 3. 返回 2xx —— Agent OS WP-15 以 HTTP 2xx 记 run success
    //    （旧 execution_id 回执模型不适用本链路，已移除 updateExecution 调用）
    res.json({
      success: true,
      job_id: jobId,
      task_name: taskName,
    });

  } catch (error) {
    logger.error('[AgentOS Webhook] Task failed', {
      task_name: taskName,
      execution_id: executionId,
      error: error instanceof Error ? error.message : String(error),
    });

    // 返回错误响应（非 2xx → Agent OS 记 run failed）
    res.status(500).json({
      success: false,
      task_name: taskName,
      error: error instanceof Error ? error.message : 'Unknown error',
    });
  }
});
