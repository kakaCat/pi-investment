#!/usr/bin/env node

/**
 * Integration Smoke Test for agent-dh Phase 4 Tools
 * 
 * Tests all 8 tools against real quantsys-v2 service (port 5001).
 * Reports ✅/❌ with HTTP status and first 200 chars of response.
 * 
 * Usage: node scripts/integration-smoke.mjs
 */

import { QuantsysV2Client } from '../../quantsys-v2-client/dist/index.mjs';

const API_BASE_URL = 'http://127.0.0.1:5001';
const TEST_SYMBOL = '600519'; // 贵州茅台
const TEST_ACCOUNT = 'agent_virtual';

// ANSI color codes
const GREEN = '\x1b[32m';
const RED = '\x1b[31m';
const YELLOW = '\x1b[33m';
const RESET = '\x1b[0m';

function truncate(str, maxLen = 200) {
  if (str.length <= maxLen) return str;
  return str.substring(0, maxLen) + '...';
}

async function testTool(name, testFn) {
  process.stdout.write(`Testing ${name}... `);
  try {
    const result = await testFn();
    const resultStr = JSON.stringify(result);
    console.log(`${GREEN}✅${RESET} [200 OK] ${truncate(resultStr)}`);
    return { name, success: true, result: truncate(resultStr) };
  } catch (error) {
    const status = error.response?.status || 'ERROR';
    const message = error.response?.data ? JSON.stringify(error.response.data) : error.message;
    console.log(`${RED}❌${RESET} [${status}] ${truncate(message)}`);
    return { name, success: false, error: truncate(message), status };
  }
}

async function main() {
  console.log(`${YELLOW}=== Agent-DH Phase 4 Integration Smoke Test ===${RESET}\n`);
  console.log(`Target: ${API_BASE_URL}`);
  console.log(`Test Symbol: ${TEST_SYMBOL}`);
  console.log(`Test Account: ${TEST_ACCOUNT}\n`);

  // Check if service is reachable
  try {
    const response = await fetch(`${API_BASE_URL}/api/health`);
    if (!response.ok) {
      console.error(`${RED}❌ Service at ${API_BASE_URL} is not healthy${RESET}`);
      process.exit(1);
    }
    const health = await response.json();
    console.log(`${GREEN}✅ Service health check passed${RESET}: ${JSON.stringify(health)}\n`);
  } catch (error) {
    console.error(`${RED}❌ Cannot reach service at ${API_BASE_URL}${RESET}`);
    console.error(`Error: ${error.message}`);
    console.error(`\nPlease ensure quantsys-v2 service is running on port 5001.`);
    process.exit(1);
  }

  const client = new QuantsysV2Client({ baseURL: API_BASE_URL });

  const results = [];

  // Test 1: data_fetch_quote
  results.push(await testTool('data_fetch_quote', async () => {
    return await client.getQuote(TEST_SYMBOL);
  }));

  // Test 2: data_fetch_kline
  results.push(await testTool('data_fetch_kline', async () => {
    const klines = await client.getKlines(TEST_SYMBOL, '2024-01-01', '2024-01-10', 'daily');
    return { count: klines.length, sample: klines[0] };
  }));

  // Test 3: data_fetch_financial
  results.push(await testTool('data_fetch_financial', async () => {
    return await client.getFinancialData(TEST_SYMBOL);
  }));

  // Test 4: pool_list
  results.push(await testTool('pool_list', async () => {
    const pools = await client.listPools();
    return { count: pools.length, sample: pools[0] };
  }));

  // Test 5: strategy_list
  results.push(await testTool('strategy_list', async () => {
    const strategies = await client.listStrategies();
    return { total: strategies.total, page: strategies.page, itemCount: strategies.items.length };
  }));

  // Test 6: watch_list
  results.push(await testTool('watch_list', async () => {
    const rules = await client.listWatchRules();
    return { count: rules.length, sample: rules[0] };
  }));

  // Test 7: account_info
  results.push(await testTool('account_info', async () => {
    return await client.getPortfolioSummary(TEST_ACCOUNT);
  }));

  // Test 8: position_list
  results.push(await testTool('position_list', async () => {
    const positions = await client.getPositions(TEST_ACCOUNT);
    return { count: positions.length, sample: positions[0] };
  }));

  // Test 9: evolution_status (new!)
  results.push(await testTool('evolution_status', async () => {
    const [leaderboard, scores] = await Promise.all([
      client.getEvolutionLeaderboard(),
      client.getEvolutionDecisionScores(),
    ]);
    return {
      leaderboard: { count: leaderboard.ranking.length, top: leaderboard.ranking[0]?.accountName },
      scores: { total: scores.total }
    };
  }));

  // Summary
  console.log(`\n${YELLOW}=== Summary ===${RESET}`);
  const successCount = results.filter(r => r.success).length;
  const totalCount = results.length;
  console.log(`${successCount}/${totalCount} tools passed\n`);

  results.forEach(r => {
    const icon = r.success ? `${GREEN}✅${RESET}` : `${RED}❌${RESET}`;
    console.log(`${icon} ${r.name}`);
  });

  if (successCount < totalCount) {
    console.log(`\n${RED}Some tools failed. See errors above.${RESET}`);
    process.exit(1);
  } else {
    console.log(`\n${GREEN}All tools passed!${RESET}`);
    process.exit(0);
  }
}

main().catch(error => {
  console.error(`${RED}Unhandled error:${RESET}`, error);
  process.exit(1);
});
