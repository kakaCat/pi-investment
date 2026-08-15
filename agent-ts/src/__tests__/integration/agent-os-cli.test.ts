/**
 * Agent OS CLI Integration Test
 *
 * 验证 Agent OS CLI 基本功能
 */

import { describe, it, expect, beforeAll } from '@jest/globals';
import {
  agentOSMemoryWrite,
  agentOSMemorySearch,
  agentOSDecisionRecord,
  agentOSNotificationSend,
} from '../../../src/infrastructure/agent-os/cli.js';

describe('Agent OS CLI Integration', () => {
  const testNamespace = 'test-agent';

  beforeAll(() => {
    // 确保环境变量设置正确
    if (!process.env.AGENT_OS_CLI_PATH) {
      console.warn('AGENT_OS_CLI_PATH not set, using default');
    }
  });

  it('should write memory successfully', async () => {
    const result = await agentOSMemoryWrite({
      namespace: testNamespace,
      content: 'Test memory entry from integration test',
      tags: ['test', 'integration'],
      metadata: {
        test: true,
        timestamp: new Date().toISOString(),
      },
    });

    expect(result.success).toBe(true);
    expect(result.data).toBeDefined();
    if (result.data) {
      expect(result.data.id).toBeDefined();
    }
  }, 10000);

  it('should search memory successfully', async () => {
    const result = await agentOSMemorySearch({
      namespace: testNamespace,
      query: 'test memory',
      limit: 5,
    });

    expect(result.success).toBe(true);
    expect(Array.isArray(result.data)).toBe(true);
  }, 10000);

  it('should record decision successfully', async () => {
    const result = await agentOSDecisionRecord({
      namespace: testNamespace,
      type: 'test-decision',
      reasoning: 'This is a test decision for integration testing',
      result: 'approved',
      metadata: {
        test: true,
        confidence: 0.85,
      },
    });

    expect(result.success).toBe(true);
    expect(result.data).toBeDefined();
    if (result.data) {
      expect(result.data.id).toBeDefined();
    }
  }, 10000);

  it('should send notification successfully', async () => {
    const result = await agentOSNotificationSend({
      channel: 'default',
      title: 'Test Notification',
      content: 'This is a test notification from integration test',
      priority: 'low',
      metadata: {
        test: true,
      },
    });

    expect(result.success).toBe(true);
    expect(result.data).toBeDefined();
    if (result.data) {
      expect(result.data.id).toBeDefined();
    }
  }, 10000);
});
