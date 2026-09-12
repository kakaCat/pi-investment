#!/usr/bin/env node
/**
 * RFC 010 测试：手动触发窗口注册
 */

import { AgentOSClient } from '@pi-investment/agent-os-client';

const client = new AgentOSClient({
  baseURL: 'http://localhost:8080',
  agentId: 'test-window',
});

async function testWindowRegistration() {
  console.log('🧪 RFC 010 窗口注册测试');
  console.log('================================\n');

  const windowId = `w-test-${Date.now()}`;
  
  try {
    // 1. 注册窗口
    console.log('1️⃣ 注册窗口:', windowId);
    const registerResp = await client.post('/api/v1/registry/agents/register', {
      agent_id: windowId,
      type: 'investor',
      name: '测试投资窗口',
      instance: 'test-instance',
      session_id: `session-${Date.now()}`,
      capabilities: ['trading', 'analysis'],
      status: 'idle',
      host: '127.0.0.1',
      port: 13080,
      pid: process.pid,
      metadata: {
        test: true,
        started_at: new Date().toISOString(),
      },
    });
    console.log('✅ 注册成功:', JSON.stringify(registerResp, null, 2));
    console.log('');

    // 2. 查询窗口
    console.log('2️⃣ 查询窗口:', windowId);
    const getResp = await client.get(`/api/v1/registry/agents/${windowId}`);
    console.log('✅ 查询成功:', JSON.stringify(getResp, null, 2));
    console.log('');

    // 3. 发送心跳
    console.log('3️⃣ 发送心跳');
    const heartbeatResp = await client.post('/api/v1/registry/agents/heartbeat', {
      agent_id: windowId,
      status: 'active',
    });
    console.log('✅ 心跳成功:', JSON.stringify(heartbeatResp, null, 2));
    console.log('');

    // 4. 按 role 查询
    console.log('4️⃣ 按 role 查询 investor 窗口');
    const listResp = await client.get('/api/v1/registry/agents/available?role=investor');
    console.log('✅ 查询成功，找到', Array.isArray(listResp) ? listResp.length : 0, '个窗口');
    if (Array.isArray(listResp)) {
      const found = listResp.find(w => w.agent_id === windowId);
      if (found) {
        console.log('   找到刚注册的窗口:', found.agent_id);
      }
    }
    console.log('');

    // 5. 注销
    console.log('5️⃣ 注销窗口');
    const unregisterResp = await client.post('/api/v1/registry/agents/unregister', {
      agent_id: windowId,
    });
    console.log('✅ 注销成功:', JSON.stringify(unregisterResp, null, 2));
    console.log('');

    console.log('================================');
    console.log('✅ 所有测试通过');
  } catch (error) {
    console.error('❌ 测试失败:', error.message);
    if (error.response) {
      console.error('响应:', error.response.data);
    }
    process.exit(1);
  }
}

testWindowRegistration();
