/**
 * Agent OS Task Executor
 *
 * 实现 TaskExecutor 接口，用于 Webhook 服务器调用
 * 接收 Agent OS 的任务触发，创建新的 agent session 执行
 */

import { createSchedulerSession } from '../../services/scheduler/scheduler-session.js';
import type { AgentKind } from '../../domain/agent-roles/types.js';
import type { TaskExecutor } from '../gateway/webhook-server.js';

/**
 * Create Agent OS Task Executor
 */
export function createAgentOSTaskExecutor(): TaskExecutor {
  return {
    async executeTask(params: {
      taskName: string;
      prompt: string;
      executionId?: string;
    }): Promise<any> {
      console.log(`[TaskExecutor] Executing task: ${params.taskName}`);
      console.log(`[TaskExecutor] Prompt: ${params.prompt.substring(0, 100)}...`);

      if (params.executionId) {
        console.log(`[TaskExecutor] Execution ID: ${params.executionId}`);
      }

      try {
        // 根据任务名称确定 agent 类型
        const agentKind = determineAgentKind(params.taskName);

        // 创建新的 Agent 会话
        const { session } = await createSchedulerSession(agentKind);

        // 执行 Agent prompt（自主决策）
        const result = await session.prompt(params.prompt, {
          source: "rpc",
          metadata: {
            task: params.taskName,
            executionId: params.executionId,
            triggeredBy: 'agent-os',
          }
        });

        console.log(`[TaskExecutor] Task completed: ${params.taskName}`);

        return {
          success: true,
          task: params.taskName,
          executionId: params.executionId,
          result: result,
        };
      } catch (error: any) {
        console.error(`[TaskExecutor] Task failed: ${params.taskName}`, error);

        return {
          success: false,
          task: params.taskName,
          executionId: params.executionId,
          error: error.message,
          stack: error.stack,
        };
      }
    }
  };
}

/**
 * 根据任务名称确定 Agent 类型
 */
function determineAgentKind(taskName: string): AgentKind {
  // 根据任务名称映射到不同的 agent 类型
  if (taskName.includes('memory') || taskName.includes('recall')) {
    return 'memory'; // 记忆相关任务
  }

  if (taskName.includes('market') || taskName.includes('pool') || taskName.includes('signal')) {
    return 'fin'; // 金融投资任务
  }

  if (taskName.includes('research') || taskName.includes('analysis')) {
    return 'research'; // 研究分析任务
  }

  // 默认使用 fin agent
  return 'fin';
}
