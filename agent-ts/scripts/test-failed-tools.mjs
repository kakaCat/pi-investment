#!/usr/bin/env node
/**
 * 测试9个报错工具的后端端点可用性
 */

const BASE_URL = 'http://127.0.0.1:5001';
const TIMEOUT = 10000;

const tests = [
  {
    name: 'risk_barra_decomposition',
    method: 'POST',
    url: '/api/factor-models/barra/calculate',
    body: { symbols: ['600519.SH'], weights: [1.0] }
  },
  {
    name: 'data_fetch_financial',
    method: 'GET',
    url: '/api/financial/stock/600519.SH'
  },
  {
    name: 'data_fetch_macro',
    method: 'GET',
    url: '/api/market/macro'
  },
  {
    name: 'factor_calculate',
    method: 'POST',
    url: '/api/compute/factors',
    body: { symbols: ['600519.SH'], factors: ['momentum_6m'] }
  },
  {
    name: 'sector_analysis',
    method: 'GET',
    url: '/api/analysis/sector'
  },
  {
    name: 'kline_daily_sync',
    method: 'POST',
    url: '/api/data/sync-daily-klines',
    body: { symbol: '600519.SH', start_date: '2026-08-01', end_date: '2026-08-30' }
  },
  {
    name: 'watch_manage',
    method: 'GET',
    url: '/api/watch/rules'
  },
  {
    name: 'trade_verify',
    method: 'GET',
    url: '/api/trades/verify?account_name=agent_virtual'
  },
  {
    name: 'agent_os_logs',
    type: 'file',
    path: '/Users/yunpeng/pi-investment/agent-os/logs/main.log'
  }
];

async function testEndpoint(test) {
  if (test.type === 'file') {
    // 文件检查
    const fs = await import('fs');
    const exists = fs.existsSync(test.path);
    return {
      ok: exists,
      status: exists ? 200 : 404,
      error: exists ? null : 'File not found'
    };
  }

  const url = `${BASE_URL}${test.url}`;
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), TIMEOUT);

  try {
    const options = {
      method: test.method,
      headers: { 'Content-Type': 'application/json' },
      signal: controller.signal
    };

    if (test.body) {
      options.body = JSON.stringify(test.body);
    }

    const response = await fetch(url, options);
    clearTimeout(timeoutId);

    const text = await response.text();
    let data;
    try {
      data = JSON.parse(text);
    } catch {
      data = text;
    }

    return {
      ok: response.ok,
      status: response.status,
      data,
      error: null
    };
  } catch (error) {
    clearTimeout(timeoutId);
    return {
      ok: false,
      status: error.name === 'AbortError' ? 'TIMEOUT' : 'ERROR',
      error: error.message
    };
  }
}

async function main() {
  console.log('🔍 Testing 9 failed tools...\n');

  const results = [];

  for (const test of tests) {
    const result = await testEndpoint(test);
    results.push({ ...test, ...result });

    const statusIcon = result.ok ? '✅' : '❌';
    const statusText = typeof result.status === 'number' ? result.status : result.status;

    console.log(`${statusIcon} ${test.name}`);
    console.log(`   Status: ${statusText}`);

    if (!result.ok) {
      if (result.error) {
        console.log(`   Error: ${result.error}`);
      }
      if (result.data) {
        const dataStr = typeof result.data === 'string'
          ? result.data.substring(0, 100)
          : JSON.stringify(result.data).substring(0, 100);
        console.log(`   Response: ${dataStr}...`);
      }
    }
    console.log('');
  }

  // 汇总
  const failed = results.filter(r => !r.ok);
  console.log('\n' + '='.repeat(60));
  console.log(`Summary: ${results.length - failed.length}/${results.length} passed`);

  if (failed.length > 0) {
    console.log('\n❌ Failed tools:');
    failed.forEach(f => {
      console.log(`   - ${f.name}: ${f.status} ${f.error || ''}`);
    });
  }
}

main().catch(console.error);
