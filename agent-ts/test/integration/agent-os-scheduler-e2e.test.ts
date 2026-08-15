/**
 * Agent OS Scheduler E2E Test
 * 测试从 Agent OS 到 agent-ts webhook 的完整调度流程
 */
import { describe, it, expect, beforeAll, afterAll } from '@jest/globals';
import axios from 'axios';
import { getAgentOSClient } from '../../src/infrastructure/agent-os/client.js';

describe('Agent OS Scheduler E2E', () => {
  const TEST_TASK_NAME = 'test_scheduler_e2e';
  const AGENT_WEBHOOK_URL = process.env.AGENT_WEBHOOK_BASE_URL || 'http://localhost:3002';
  const AGENT_OS_API_URL = process.env.AGENT_OS_API_URL || 'http://localhost:8080';

  let client: ReturnType<typeof getAgentOSClient>;
  let testTaskId: string;

  beforeAll(async () => {
    client = getAgentOSClient();
  });

  afterAll(async () => {
    // 清理测试任务
    if (testTaskId) {
      try {
        await client.scheduler.deleteTask(testTaskId);
      } catch (error) {
        console.warn('Failed to cleanup test task:', error);
      }
    }
  });

  it('should register a test task to Agent OS', async () => {
    const taskRequest = {
      name: TEST_TASK_NAME,
      owner: 'test',
      enabled: true,
      cron: '0 0 * * *', // 每天 00:00（不会真正触发）
      webhook_url: `${AGENT_WEBHOOK_URL}/api/webhook/agent-os/trigger`,
      payload: {
        kind: 'agent_turn' as const,
        message: 'E2E 测试任务',
        agentKind: 'fin' as const,
      },
      timeout: 60,
      retry_count: 1,
    };

    const task = await client.scheduler.registerTask(taskRequest);

    expect(task).toBeDefined();
    expect(task.id).toBeDefined();
    expect(task.name).toBe(TEST_TASK_NAME);
    expect(task.webhook_url).toBe(taskRequest.webhook_url);

    testTaskId = task.id;
  });

  it('should list tasks and find the test task', async () => {
    const tasks = await client.scheduler.listTasks();

    expect(Array.isArray(tasks)).toBe(true);

    const testTask = tasks.find(t => t.name === TEST_TASK_NAME);
    expect(testTask).toBeDefined();
    expect(testTask?.id).toBe(testTaskId);
  });

  it('should manually trigger the test task', async () => {
    // 手动触发任务
    const execution = await client.scheduler.triggerTask(testTaskId);

    expect(execution).toBeDefined();
    expect(execution.id).toBeDefined();
    expect(execution.task_id).toBe(testTaskId);
    expect(execution.status).toBe('running');

    // 等待执行完成（最多 30 秒）
    let finalExecution;
    for (let i = 0; i < 30; i++) {
      await new Promise(resolve => setTimeout(resolve, 1000));

      finalExecution = await client.scheduler.getExecution(execution.id);

      if (finalExecution.status === 'completed' || finalExecution.status === 'failed') {
        break;
      }
    }

    expect(finalExecution).toBeDefined();
    expect(['completed', 'failed']).toContain(finalExecution!.status);

    // 如果失败，打印错误信息
    if (finalExecution!.status === 'failed') {
      console.error('Execution failed:', finalExecution!.error);
    }
  });

  it('should verify agent-ts webhook endpoint is accessible', async () => {
    // 直接调用 webhook 端点测试（模拟 Agent OS 行为）
    const webhookPayload = {
      task_id: testTaskId,
      task_name: TEST_TASK_NAME,
      execution_id: 'test-execution-id',
      payload: {
        kind: 'agent_turn',
        message: '直接 webhook 测试',
        agentKind: 'fin',
      },
    };

    try {
      const response = await axios.post(
        `${AGENT_WEBHOOK_URL}/api/webhook/agent-os/trigger`,
        webhookPayload,
        {
          headers: {
            'Content-Type': 'application/json',
          },
          timeout: 10000,
        }
      );

      expect(response.status).toBe(200);
      expect(response.data).toHaveProperty('success');
    } catch (error) {
      if (axios.isAxiosError(error)) {
        console.error('Webhook call failed:', {
          status: error.response?.status,
          data: error.response?.data,
          message: error.message,
        });
      }
      throw error;
    }
  });

  it('should get task statistics', async () => {
    const stats = await client.scheduler.getTaskStats(testTaskId);

    expect(stats).toBeDefined();
    expect(stats.task_id).toBe(testTaskId);
    expect(stats.total_runs).toBeGreaterThanOrEqual(0);
    expect(stats.success_count).toBeGreaterThanOrEqual(0);
    expect(stats.failure_count).toBeGreaterThanOrEqual(0);
  });

  it('should pause and resume task', async () => {
    // 暂停任务
    await client.scheduler.pauseTask(testTaskId);

    let task = await client.scheduler.getTask(testTaskId);
    expect(task.enabled).toBe(false);

    // 恢复任务
    await client.scheduler.resumeTask(testTaskId);

    task = await client.scheduler.getTask(testTaskId);
    expect(task.enabled).toBe(true);
  });
});
