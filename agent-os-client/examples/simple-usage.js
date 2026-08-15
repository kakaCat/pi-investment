/**
 * Simple usage example for agent-os-client
 */

import { AgentOSClient } from '../dist/index.js';

async function main() {
  // Initialize client
  const client = new AgentOSClient({
    baseURL: process.env.AGENT_OS_API_URL || 'http://localhost:8080',
    agentId: process.env.AGENT_ID || 'fin-agent',
    timeout: 30000,
  });

  console.log('🚀 Agent OS Client initialized');
  console.log(`   Base URL: ${client.getBaseURL()}`);
  console.log(`   Agent ID: ${client.getAgentId()}`);
  console.log();

  try {
    // Test health check
    console.log('📡 Testing health endpoint...');
    const health = await client.health();
    console.log('✅ Health:', health);
    console.log();

    // Test scheduler
    console.log('📅 Testing scheduler...');
    const tasks = await client.scheduler.listTasks({ owner: 'fin-agent' });
    console.log(`✅ Found ${tasks.length} tasks`);
    console.log();

    // Test memory
    console.log('🧠 Testing memory write...');
    const memory = await client.memory.write({
      namespace: 'fin-agent',
      content: 'SDK test memory entry',
      category: 'test',
      importance: 0.5,
      metadata: { test: true, timestamp: new Date().toISOString() },
    });
    console.log('✅ Memory written:', memory.id);
    console.log();

    // Test memory search
    console.log('🔍 Testing memory search...');
    const searchResults = await client.memory.search({
      namespace: 'fin-agent',
      query: 'SDK test',
      top_k: 5,
    });
    console.log(`✅ Found ${searchResults.length} results`);
    console.log();

    // Test decision
    console.log('🎯 Testing decision record...');
    const decision = await client.decision.record({
      namespace: 'fin-agent',
      action: 'test',
      targets: ['SDK'],
      reasoning: 'Testing SDK functionality',
      confidence: 1.0,
      metadata: { test: true },
    });
    console.log('✅ Decision recorded:', decision.id);
    console.log();

    // Test notification channels
    console.log('📢 Testing notification channels...');
    const channels = await client.notification.listChannels();
    console.log(`✅ Found ${channels.length} channels`);
    console.log();

    // Test resource quota
    console.log('💾 Testing resource quota...');
    const quota = await client.resource.getQuota();
    console.log('✅ Quota:', {
      tokens: `${quota.token_used}/${quota.token_quota}`,
      memory: `${quota.memory_used_mb}MB/${quota.memory_quota_mb}MB`,
    });
    console.log();

    console.log('✅ All tests passed!');
  } catch (error: any) {
    console.error('❌ Test failed:', error.message);
    if (error.code) {
      console.error('   Code:', error.code);
    }
    if (error.details) {
      console.error('   Details:', error.details);
    }
    process.exit(1);
  }
}

main();
