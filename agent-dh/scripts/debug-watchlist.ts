import { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { WatchListTool } from './packages/intelligence/src/tools/WatchListTool/WatchListTool';

const qv2 = new QuantsysV2Client({
  baseURL: 'http://localhost:5001',
  timeout: 30000,
});

const mockContext = {
  sessionId: 'test-session',
  timestamp: Date.now(),
};

async function debug() {
  console.log('1. 直接调用 client.listWatchRules()...');
  try {
    const rules = await qv2.listWatchRules();
    console.log('✅ 成功，返回:', rules.length, '条规则');
  } catch (error: any) {
    console.error('❌ 失败:', error.message);
  }

  console.log('\n2. 调用 WatchListTool...');
  try {
    const tool = new WatchListTool(qv2);
    const result = await tool.call({}, mockContext);
    console.log('✅ 成功，返回:', JSON.stringify(result, null, 2));
  } catch (error: any) {
    console.error('❌ 失败:', error.message, error.stack);
  }
}

debug();
