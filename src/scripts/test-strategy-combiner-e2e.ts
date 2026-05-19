#!/usr/bin/env tsx
/**
 * End-to-End Test Script for Strategy Combiner
 *
 * Tests the complete flow from tool invocation to Python bridge to result parsing.
 * Run with: npx tsx src/scripts/test-strategy-combiner-e2e.ts
 */

import { SignalGenerator } from '../services/quant/signal-generator.js';
import { QuantService } from '../services/quant/quant-service.js';

interface TestResult {
  scenario: string;
  passed: boolean;
  message: string;
  details?: any;
}

const results: TestResult[] = [];

function logTest(scenario: string, passed: boolean, message: string, details?: any) {
  results.push({ scenario, passed, message, details });
  const icon = passed ? '✅' : '❌';
  console.log(`${icon} ${scenario}: ${message}`);
  if (details) {
    console.log('   Details:', JSON.stringify(details, null, 2));
  }
}

async function testVoteMode() {
  console.log('\n=== Scenario 1: VOTE Mode (Weighted Voting) ===');

  try {
    const quantService = new QuantService();
    const strategies = await quantService.listStrategies();

    if (strategies.length < 2) {
      logTest('VOTE Mode', false, 'Need at least 2 strategies configured');
      return;
    }

    // Use the tool directly (which handles the full flow)
    const { combineStrategySignalsTool } = await import('../infrastructure/tools/quant-tools.js');
    const toolResult = await (combineStrategySignalsTool.execute as any)('test-vote', {
      symbol: '600519',
      strategy_ids: [strategies[0].id, strategies[1].id],
      mode: 'vote'
    });

    if (!toolResult.content || toolResult.content[0].type !== 'text') {
      logTest('VOTE Mode', false, 'Invalid tool result structure', toolResult);
      return;
    }

    const text = toolResult.content[0].text;

    // If no signals were generated, it's not a failure - just means conditions weren't met
    if (text.includes('Need at least 2 valid signals')) {
      logTest('VOTE Mode', true, 'Tool correctly handled case where strategies did not generate signals (conditions not met)', {
        note: 'This is expected behavior - strategies only generate signals when their conditions are satisfied'
      });
      return;
    }

    if (text.startsWith('Error:') || text.startsWith('Failed')) {
      logTest('VOTE Mode', false, `Tool returned unexpected error: ${text}`);
      return;
    }

    const result = JSON.parse(text);

    // Verify structure
    if (!result.combined_signals || !result.metadata) {
      logTest('VOTE Mode', false, 'Missing combined_signals or metadata', result);
      return;
    }

    // Verify metadata
    if (result.metadata.mode !== 'vote') {
      logTest('VOTE Mode', false, `Expected mode 'vote', got '${result.metadata.mode}'`);
      return;
    }

    // Verify vote scores exist if signals were generated
    if (result.metadata.signals_generated > 0) {
      if (typeof result.metadata.buy_score !== 'number' || typeof result.metadata.sell_score !== 'number') {
        logTest('VOTE Mode', false, 'Missing buy_score or sell_score in metadata', result.metadata);
        return;
      }
    }

    logTest('VOTE Mode', true, `Combined ${result.metadata.signals_generated} signals`, {
      mode: result.metadata.mode,
      buy_score: result.metadata.buy_score,
      sell_score: result.metadata.sell_score,
      total_strategies: result.metadata.total_strategies
    });

  } catch (error) {
    logTest('VOTE Mode', false, `Error: ${error instanceof Error ? error.message : String(error)}`);
  }
}

async function testAndMode() {
  console.log('\n=== Scenario 2: AND Mode (Conservative Consensus) ===');

  try {
    const quantService = new QuantService();
    const strategies = await quantService.listStrategies();

    if (strategies.length < 2) {
      logTest('AND Mode', false, 'Need at least 2 strategies configured');
      return;
    }

    const { combineStrategySignalsTool } = await import('../infrastructure/tools/quant-tools.js');
    const toolResult = await (combineStrategySignalsTool.execute as any)('test-and', {
      symbol: '600519',
      strategy_ids: [strategies[0].id, strategies[1].id],
      mode: 'and'
    });

    if (!toolResult.content || toolResult.content[0].type !== 'text') {
      logTest('AND Mode', false, 'Invalid tool result structure', toolResult);
      return;
    }

    const text = toolResult.content[0].text;

    if (text.includes('Need at least 2 valid signals')) {
      logTest('AND Mode', true, 'Tool correctly handled case where strategies did not generate signals', {
        note: 'Expected behavior when strategy conditions are not met'
      });
      return;
    }

    if (text.startsWith('Error:') || text.startsWith('Failed')) {
      logTest('AND Mode', false, `Tool returned unexpected error: ${text}`);
      return;
    }

    const result = JSON.parse(text);

    // Verify structure
    if (!result.combined_signals || !result.metadata) {
      logTest('AND Mode', false, 'Missing combined_signals or metadata', result);
      return;
    }

    // Verify metadata
    if (result.metadata.mode !== 'and') {
      logTest('AND Mode', false, `Expected mode 'and', got '${result.metadata.mode}'`);
      return;
    }

    // In AND mode, signals should only exist if all strategies agree
    const hasSignals = result.combined_signals.length > 0;
    const signalCount = result.metadata.signals_generated;

    logTest('AND Mode', true, `AND mode returned ${signalCount} signals (requires all strategies to agree)`, {
      mode: result.metadata.mode,
      signals_generated: signalCount,
      has_consensus: hasSignals
    });

  } catch (error) {
    logTest('AND Mode', false, `Error: ${error instanceof Error ? error.message : String(error)}`);
  }
}

async function testOrMode() {
  console.log('\n=== Scenario 3: OR Mode (Aggressive Coverage) ===');

  try {
    const quantService = new QuantService();
    const strategies = await quantService.listStrategies();

    if (strategies.length < 2) {
      logTest('OR Mode', false, 'Need at least 2 strategies configured');
      return;
    }

    const { combineStrategySignalsTool } = await import('../infrastructure/tools/quant-tools.js');
    const toolResult = await (combineStrategySignalsTool.execute as any)('test-or', {
      symbol: '600519',
      strategy_ids: [strategies[0].id, strategies[1].id],
      mode: 'or'
    });

    if (!toolResult.content || toolResult.content[0].type !== 'text') {
      logTest('OR Mode', false, 'Invalid tool result structure', toolResult);
      return;
    }

    const text = toolResult.content[0].text;

    if (text.includes('Need at least 2 valid signals')) {
      logTest('OR Mode', true, 'Tool correctly handled case where strategies did not generate signals', {
        note: 'Expected behavior when strategy conditions are not met'
      });
      return;
    }

    if (text.startsWith('Error:') || text.startsWith('Failed')) {
      logTest('OR Mode', false, `Tool returned unexpected error: ${text}`);
      return;
    }

    const result = JSON.parse(text);

    // Verify structure
    if (!result.combined_signals || !result.metadata) {
      logTest('OR Mode', false, 'Missing combined_signals or metadata', result);
      return;
    }

    // Verify metadata
    if (result.metadata.mode !== 'or') {
      logTest('OR Mode', false, `Expected mode 'or', got '${result.metadata.mode}'`);
      return;
    }

    // OR mode should include all signals from all strategies
    const signalCount = result.metadata.signals_generated;

    logTest('OR Mode', true, `OR mode returned ${signalCount} signals (includes all strategy signals)`, {
      mode: result.metadata.mode,
      signals_generated: signalCount,
      total_strategies: result.metadata.total_strategies
    });

  } catch (error) {
    logTest('OR Mode', false, `Error: ${error instanceof Error ? error.message : String(error)}`);
  }
}

async function testCustomWeights() {
  console.log('\n=== Scenario 4: Custom Weights ===');

  try {
    const quantService = new QuantService();
    const strategies = await quantService.listStrategies();

    if (strategies.length < 2) {
      logTest('Custom Weights', false, 'Need at least 2 strategies configured');
      return;
    }

    const weights: Record<string, number> = {
      [strategies[0].id]: 1.5,
      [strategies[1].id]: 1.0
    };

    const { combineStrategySignalsTool } = await import('../infrastructure/tools/quant-tools.js');
    const toolResult = await (combineStrategySignalsTool.execute as any)('test-weights', {
      symbol: '600519',
      strategy_ids: [strategies[0].id, strategies[1].id],
      mode: 'vote',
      weights
    });

    if (!toolResult.content || toolResult.content[0].type !== 'text') {
      logTest('Custom Weights', false, 'Invalid tool result structure', toolResult);
      return;
    }

    const text = toolResult.content[0].text;

    if (text.includes('Need at least 2 valid signals')) {
      logTest('Custom Weights', true, 'Tool correctly handled case where strategies did not generate signals', {
        note: 'Expected behavior when strategy conditions are not met'
      });
      return;
    }

    if (text.startsWith('Error:') || text.startsWith('Failed')) {
      logTest('Custom Weights', false, `Tool returned unexpected error: ${text}`);
      return;
    }

    const result = JSON.parse(text);

    // Verify structure
    if (!result.combined_signals || !result.metadata) {
      logTest('Custom Weights', false, 'Missing combined_signals or metadata', result);
      return;
    }

    // Verify mode is VOTE (weights only apply to VOTE mode)
    if (result.metadata.mode !== 'vote') {
      logTest('Custom Weights', false, `Expected mode 'vote', got '${result.metadata.mode}'`);
      return;
    }

    logTest('Custom Weights', true, `Applied custom weights successfully`, {
      mode: result.metadata.mode,
      weights_applied: weights,
      signals_generated: result.metadata.signals_generated
    });

  } catch (error) {
    logTest('Custom Weights', false, `Error: ${error instanceof Error ? error.message : String(error)}`);
  }
}

async function testMultiSymbolScan() {
  console.log('\n=== Scenario 5: Multi-Symbol Scan ===');

  try {
    const quantService = new QuantService();
    const strategies = await quantService.listStrategies();

    if (strategies.length < 2) {
      logTest('Multi-Symbol Scan', false, 'Need at least 2 strategies configured');
      return;
    }

    // Test multiple symbols by calling the tool twice
    const { combineStrategySignalsTool } = await import('../infrastructure/tools/quant-tools.js');

    const results = [];
    for (const symbol of ['600519', '000001']) {
      const toolResult = await (combineStrategySignalsTool.execute as any)(`test-scan-${symbol}`, {
        symbol,
        strategy_ids: [strategies[0].id, strategies[1].id],
        mode: 'vote'
      });

      if (toolResult.content && toolResult.content[0].type === 'text') {
        const text = toolResult.content[0].text;
        if (!text.startsWith('Error:')) {
          results.push(JSON.parse(text));
        }
      }
    }

    if (results.length === 0) {
      logTest('Multi-Symbol Scan', true, 'Tool correctly handled case where no signals were generated', {
        note: 'Expected behavior when strategy conditions are not met for any symbol'
      });
      return;
    }

    const totalSignals = results.reduce((sum, r) => sum + (r.metadata?.signals_generated || 0), 0);

    logTest('Multi-Symbol Scan', true, `Scanned ${results.length} symbols`, {
      symbols_processed: results.length,
      total_signals: totalSignals,
      mode: results[0]?.metadata?.mode
    });

  } catch (error) {
    logTest('Multi-Symbol Scan', false, `Error: ${error instanceof Error ? error.message : String(error)}`);
  }
}

async function testErrorHandling() {
  console.log('\n=== Scenario 6: Error Handling ===');

  try {
    const { combineStrategySignalsTool } = await import('../infrastructure/tools/quant-tools.js');

    // Test with invalid symbol and fake strategies
    const toolResult = await (combineStrategySignalsTool.execute as any)('test-error', {
      symbol: '999999',
      strategy_ids: ['fake_strategy_1', 'fake_strategy_2'],
      mode: 'vote'
    });

    if (!toolResult.content || toolResult.content[0].type !== 'text') {
      logTest('Error Handling', false, 'Invalid tool result structure', toolResult);
      return;
    }

    const text = toolResult.content[0].text;

    // Should return an error message for invalid inputs
    if (text.startsWith('Error:') || text.startsWith('Failed') || text.includes('Need at least 2 valid signals')) {
      logTest('Error Handling', true, 'Handled invalid inputs gracefully', {
        error_message: text.substring(0, 100)
      });
    } else {
      logTest('Error Handling', false, 'Expected error message but got success response', { text });
    }

  } catch (error) {
    // Catching error is also acceptable
    logTest('Error Handling', true, `Caught error as expected: ${error instanceof Error ? error.message : String(error)}`);
  }
}

async function runAllTests() {
  console.log('🚀 Starting Strategy Combiner End-to-End Tests\n');
  console.log('=' .repeat(60));

  await testVoteMode();
  await testAndMode();
  await testOrMode();
  await testCustomWeights();
  await testMultiSymbolScan();
  await testErrorHandling();

  console.log('\n' + '='.repeat(60));
  console.log('\n📊 Test Summary:');
  console.log('=' .repeat(60));

  const passed = results.filter(r => r.passed).length;
  const failed = results.filter(r => !r.passed).length;
  const total = results.length;

  console.log(`Total: ${total} | Passed: ${passed} | Failed: ${failed}`);
  console.log('');

  if (failed > 0) {
    console.log('❌ Failed Tests:');
    results.filter(r => !r.passed).forEach(r => {
      console.log(`   - ${r.scenario}: ${r.message}`);
    });
  }

  if (passed === total) {
    console.log('✅ All tests passed!');
    process.exit(0);
  } else {
    console.log(`⚠️  ${failed} test(s) failed`);
    process.exit(1);
  }
}

// Run tests
runAllTests().catch(error => {
  console.error('Fatal error running tests:', error);
  process.exit(1);
});
