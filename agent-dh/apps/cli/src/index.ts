#!/usr/bin/env node

import { Context } from '@deepseek-ai/cordis';
import { InvestmentAgentLoop } from '@pi-investment/investment-agent-loop';
import { AgentOSClient } from '@pi-investment/agent-os-client';

/**
 * Main entry point
 * Runs in local mode by default (no Agent OS backend required)
 */
async function main() {
  console.log('=== Agent-DH CLI Starting (Local Mode) ===\n');

  // Create Cordis Context
  const ctx = new Context();

  console.log('[CLI] Loading DSH core plugins...');

  // Create Agent OS client (local mode - no backend required)
  const useLocalMode = !process.env.AGENT_OS_BASE_URL;
  const osClient = useLocalMode
    ? new AgentOSClient()  // Local in-memory registry
    : new AgentOSClient({
        baseURL: process.env.AGENT_OS_BASE_URL,
      });

  console.log('[CLI] Mode:', useLocalMode ? 'LOCAL (in-memory)' : 'REMOTE (' + process.env.AGENT_OS_BASE_URL + ')');

  // Create Investment Agent Loop
  const agentLoop = new InvestmentAgentLoop(ctx, {
    osClient,
    agentType: 'worker',
    capabilities: ['data-analysis', 'backtest', 'strategy'],
  });

  console.log('[CLI] Creating agent...\n');

  // Create an agent
  const agent = await agentLoop.create('demo-session-001', {
    agentId: 'worker-001',
    type: 'worker',
    capabilities: ['data-analysis', 'backtest'],
  });

  console.log('\n[CLI] Agent created successfully!');
  console.log('[CLI] Agent Info:', agent.getInfo());

  // Simulate some work
  console.log('\n[CLI] Executing demo task...');
  const result = await agent.executeTask('task-001', { action: 'analyze' });
  console.log('[CLI] Task result:', result);

  // Keep running for a while to see heartbeats
  console.log('\n[CLI] Agent is running. Press Ctrl+C to stop.\n');

  // Handle graceful shutdown
  const shutdown = async () => {
    console.log('\n\n[CLI] Shutting down...');
    await agentLoop.stopAll();
    console.log('[CLI] Shutdown complete.');
    process.exit(0);
  };

  process.on('SIGINT', shutdown);
  process.on('SIGTERM', shutdown);

  // Keep the process alive
  await new Promise(() => {});
}

// Run
main().catch((error) => {
  console.error('[CLI] Fatal error:', error);
  process.exit(1);
});
