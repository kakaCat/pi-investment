import { InvestmentAgentLoop } from '@pi-investment/investment-agent-loop';
import { AgentOSClient } from '@pi-investment/agent-os-client';
import { Context } from '@deepseek-ai/cordis';

/**
 * 示例 1: 创建一个简单的 Worker Agent
 * 
 * 这个示例展示如何：
 * 1. 创建 Agent Loop
 * 2. 注册 Agent 到 Agent OS
 * 3. 发送心跳
 * 4. 执行任务
 * 5. 优雅关闭
 */

async function main() {
  console.log('=== 简单 Agent 示例 ===\n');

  // 1. 创建 Cordis 上下文
  const ctx = new Context();

  // 2. 创建 Agent OS 客户端
  const osClient = new AgentOSClient({
    baseURL: process.env.AGENT_OS_BASE_URL || 'http://localhost:8080',
  });

  console.log('[1] Cordis 上下文和 Agent OS 客户端已创建\n');

  // 3. 创建 Investment Agent Loop
  const agentLoop = new InvestmentAgentLoop(ctx, {
    osClient,
    agentType: 'worker',
    capabilities: ['data-analysis', 'basic-tasks'],
  });

  console.log('[2] Investment Agent Loop 已创建\n');

  // 4. 创建并启动 Agent
  const agent = await agentLoop.create('simple-agent-session', {
    agentId: 'simple-worker-001',
    type: 'worker',
    capabilities: ['data-analysis', 'basic-tasks'],
  });

  console.log('[3] Agent 已注册并启动');
  console.log('    Agent ID:', agent.agentId);
  console.log('    Session ID:', agent.sessionId);
  console.log('    Capabilities:', agent.getInfo().capabilities);
  console.log();

  // 5. 执行一些任务
  console.log('[4] 开始执行任务...\n');

  for (let i = 1; i <= 3; i++) {
    const taskId = `task-${i}`;
    console.log(`    执行任务 ${taskId}...`);
    
    const result = await agent.executeTask(taskId, {
      action: 'analyze',
      data: { value: i * 10 },
    });

    console.log(`    ✓ 任务 ${taskId} 完成:`, result);
    console.log();

    // 等待 2 秒
    await new Promise(resolve => setTimeout(resolve, 2000));
  }

  // 6. 优雅关闭
  console.log('[5] 开始优雅关闭...\n');
  await agentLoop.stopAll();
  console.log('    ✓ Agent 已停止并注销\n');

  console.log('=== 示例完成 ===');
}

// 运行示例
main().catch((error) => {
  console.error('❌ 错误:', error);
  process.exit(1);
});
