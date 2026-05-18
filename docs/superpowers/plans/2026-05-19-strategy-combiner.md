# Strategy Combiner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable TypeScript quant tools to combine multiple strategy signals using Python's combiner logic (OR/AND/VOTE modes).

**Architecture:** Add Python bridge function in `akshare_bridge.py` that calls `quant/quantsys/strategies/combiner.py`. TypeScript `SignalGenerator` calls this via `callPythonResilient`. New tool `combine_strategy_signals` and enhanced `generate_signals` expose the functionality.

**Tech Stack:** Python (combiner.py), TypeScript (signal-generator.ts, quant-tools.ts), callPythonResilient bridge

---

## File Structure

**New Files:**
- None (all modifications to existing files)

**Modified Files:**
- `python/akshare_bridge.py` - Add `combine_strategy_signals()` function
- `src/services/quant/signal-generator.ts` - Add `combineSignals()` and `scanMarketMultiStrategy()` methods
- `src/infrastructure/tools/quant-tools.ts` - Add `combine_strategy_signals` tool, enhance `generate_signals`
- `src/infrastructure/tools/shared/python-caller-resilient-adapter.ts` - Add timeout config
- `quant/README.md` - Add strategy combination documentation

**Test Files:**
- `src/services/quant/signal-generator.test.ts` (new) - Unit tests for combineSignals
- `src/infrastructure/tools/quant-tools.test.ts` (extend) - Integration tests

---

## Task 1: Python Bridge - Add combine_strategy_signals Function

**Files:**
- Modify: `python/akshare_bridge.py` (add function at end, before `if __name__ == '__main__'`)

- [ ] **Step 1: Add import statements**

Add these imports at the top of `akshare_bridge.py` after existing imports:

```python
# Add after line ~18 (after other imports)
import sys
import os

# Add path to quant module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'quant'))

from quantsys.strategies.combiner import StrategyCombiner, Signal as CombinerSignal, CombinerConfig
```

- [ ] **Step 2: Write combine_strategy_signals function**

Add this function before the `if __name__ == '__main__':` block (around line 3170):

```python
def combine_strategy_signals(params: dict) -> dict:
    """
    Combine multiple strategy signals using StrategyCombiner.
    
    Args:
        params: {
            'signals': [
                {
                    'timestamp': '2026-05-19T10:00:00',
                    'symbol': '600519',
                    'action': 'buy',
                    'price': 1800.0,
                    'strategy_id': 'rsi_reversal',
                    'confidence': 0.8,
                    'reason': 'RSI=28'
                },
                ...
            ],
            'mode': 'vote',  # 'or', 'and', 'vote'
            'weights': {'rsi_reversal': 1.5, 'ma_cross': 1.0},  # optional
            'confidence_threshold': 0.5,  # optional
            'min_agree_count': 1  # optional for AND mode
        }
    
    Returns:
        {
            'combined_signals': [...],
            'metadata': {...}
        }
    """
    try:
        signals_data = params.get('signals', [])
        mode = params.get('mode', 'vote')
        weights = params.get('weights', {})
        confidence_threshold = params.get('confidence_threshold', 0.5)
        min_agree_count = params.get('min_agree_count', 1)
        
        # Convert TypeScript signals to Python Signal dataclass
        python_signals = []
        for sig in signals_data:
            timestamp_str = sig.get('timestamp', '')
            # Parse ISO timestamp
            if timestamp_str:
                timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            else:
                timestamp = datetime.now()
            
            python_sig = CombinerSignal(
                timestamp=timestamp,
                symbol=sig.get('symbol', ''),
                action=sig.get('action', 'hold'),
                price=float(sig.get('price', 0)),
                quantity=int(sig.get('quantity', 0)),
                strategy_id=sig.get('strategy_id', ''),
                reason=sig.get('reason', ''),
                confidence=float(sig.get('confidence', 0.5)),
                metadata=sig.get('metadata', {})
            )
            python_signals.append(python_sig)
        
        # Create combiner config
        config = CombinerConfig(
            mode=mode,
            weights=weights,
            confidence_threshold=confidence_threshold,
            min_agree_count=min_agree_count
        )
        
        # Combine signals
        combiner = StrategyCombiner(config)
        combined_signals, metadata = combiner.combine_signals(python_signals)
        
        # Convert back to JSON-serializable format
        result_signals = []
        for sig in combined_signals:
            result_signals.append({
                'timestamp': sig.timestamp.isoformat(),
                'symbol': sig.symbol,
                'action': sig.action,
                'price': sig.price,
                'quantity': sig.quantity,
                'strategy_id': sig.strategy_id,
                'reason': sig.reason,
                'confidence': sig.confidence,
                'metadata': sig.metadata
            })
        
        return {
            'combined_signals': result_signals,
            'metadata': metadata
        }
        
    except Exception as e:
        logger.error(f"combine_strategy_signals error: {e}")
        traceback.print_exc()
        return {
            'error': str(e),
            'combined_signals': [],
            'metadata': {'reason': 'python_error', 'error': str(e)}
        }
```

- [ ] **Step 3: Test Python function manually**

Run this test command:

```bash
cd /Users/mac/Documents/ai/pi-investment
python3 python/akshare_bridge.py combine_strategy_signals '{"signals": [{"timestamp": "2026-05-19T10:00:00", "symbol": "600519", "action": "buy", "price": 1800.0, "strategy_id": "rsi", "confidence": 0.8, "reason": "RSI=28"}, {"timestamp": "2026-05-19T10:00:00", "symbol": "600519", "action": "buy", "price": 1800.0, "strategy_id": "ma", "confidence": 0.6, "reason": "MA cross"}], "mode": "vote", "weights": {"rsi": 1.5, "ma": 1.0}}'
```

Expected output: JSON with `combined_signals` array and `metadata` object showing vote scores.

- [ ] **Step 4: Commit Python bridge**

```bash
git add python/akshare_bridge.py
git commit -m "feat(python): add combine_strategy_signals bridge function"
```

---

## Task 2: TypeScript SignalGenerator - Add combineSignals Method

**Files:**
- Modify: `src/services/quant/signal-generator.ts` (add methods after line 453)

- [ ] **Step 1: Add combineSignals method**

Add this method to the `SignalGenerator` class after the `loadSignals` method (around line 453):

```typescript
/**
 * Combine multiple signals using Python combiner
 */
async combineSignals(
  signals: Signal[],
  mode: 'or' | 'and' | 'vote' = 'vote',
  weights?: Record<string, number>,
  confidenceThreshold: number = 0.5
): Promise<{ signals: Signal[], metadata: any }> {
  try {
    // Import dynamically to avoid circular dependency
    const pythonCaller = await import('../../infrastructure/tools/shared/python-caller-resilient-adapter.js');
    const { callPythonResilient } = pythonCaller;

    // Convert TypeScript signals to Python format
    const pythonSignals = signals.map(s => ({
      timestamp: s.date + 'T00:00:00',  // Convert date string to ISO timestamp
      symbol: s.symbol,
      action: s.action,
      price: s.price,
      quantity: 0,
      strategy_id: s.strategy_id,
      confidence: s.confidence,
      reason: s.reason
    }));

    // Call Python combiner
    const result = await callPythonResilient('combine_strategy_signals', {
      signals: pythonSignals,
      mode,
      weights: weights || {},
      confidence_threshold: confidenceThreshold
    });

    const data = JSON.parse(result);

    // Check for errors
    if (data.error) {
      console.warn('Python combiner error, falling back to OR mode:', data.error);
      return {
        signals: signals,  // Return all signals (OR mode fallback)
        metadata: {
          fallback: true,
          reason: 'python_error',
          error: data.error
        }
      };
    }

    // Convert Python signals back to TypeScript format
    const combinedSignals: Signal[] = data.combined_signals.map((s: any) => ({
      date: s.timestamp.split('T')[0],  // Extract date from ISO timestamp
      symbol: s.symbol,
      name: signals.find(sig => sig.symbol === s.symbol)?.name || s.symbol,
      action: s.action as 'buy' | 'sell',
      strategy_id: s.strategy_id,
      price: s.price,
      reason: s.reason,
      confidence: s.confidence,
      indicators: signals.find(sig => sig.strategy_id === s.strategy_id)?.indicators
    }));

    return {
      signals: combinedSignals,
      metadata: data.metadata
    };

  } catch (error) {
    console.error('combineSignals error:', error);
    // Fallback: return all signals (OR mode)
    return {
      signals: signals,
      metadata: {
        fallback: true,
        reason: 'exception',
        error: error instanceof Error ? error.message : String(error)
      }
    };
  }
}
```

- [ ] **Step 2: Add scanMarketMultiStrategy method**

Add this method after `combineSignals`:

```typescript
/**
 * Scan market with multiple strategies and combine signals
 */
async scanMarketMultiStrategy(
  strategies: QuantStrategy[],
  stockData: StockData[],
  mode: 'or' | 'and' | 'vote' = 'vote',
  weights?: Record<string, number>,
  confidenceThreshold: number = 0.5
): Promise<Signal[]> {
  // Step 1: Generate signals for each strategy
  const allSignals: Signal[] = [];

  for (const strategy of strategies) {
    const strategySignals = await this.scanMarket(strategy, stockData, confidenceThreshold);
    allSignals.push(...strategySignals);
  }

  // Step 2: Group signals by symbol
  const signalsBySymbol = new Map<string, Signal[]>();
  for (const signal of allSignals) {
    const existing = signalsBySymbol.get(signal.symbol) || [];
    existing.push(signal);
    signalsBySymbol.set(signal.symbol, existing);
  }

  // Step 3: Combine signals for each symbol
  const combinedSignals: Signal[] = [];

  for (const [symbol, signals] of signalsBySymbol.entries()) {
    // Only combine if multiple strategies generated signals for this symbol
    if (signals.length > 1) {
      const { signals: combined } = await this.combineSignals(
        signals,
        mode,
        weights,
        confidenceThreshold
      );
      combinedSignals.push(...combined);
    } else {
      // Single signal, keep as-is
      combinedSignals.push(signals[0]);
    }
  }

  return combinedSignals;
}
```

- [ ] **Step 3: Commit SignalGenerator changes**

```bash
git add src/services/quant/signal-generator.ts
git commit -m "feat(quant): add combineSignals and scanMarketMultiStrategy methods"
```

---

## Task 3: Add combine_strategy_signals Tool

**Files:**
- Modify: `src/infrastructure/tools/quant-tools.ts` (add new tool after `trainSignalModelTool`)

- [ ] **Step 1: Add tool definition**

Add this tool definition after the `trainSignalModelTool` export (around line 700):

```typescript
/**
 * 5. 组合多策略信号
 */
export const combineStrategySignalsTool: ToolDefinition = {
  name: 'combine_strategy_signals',
  label: '组合多策略信号',
  description: `组合多个策略的交易信号，支持 OR/AND/VOTE 模式。

使用场景：
- RSI + 均线 + 布林带三个信号投票，提高准确率
- 要求所有策略一致才执行（AND 模式）
- 任一策略触发即执行（OR 模式）

返回：组合后的信号和决策元数据（买入/卖出得分、胜出方向）`,

  promptSnippet: `示例1：组合三个策略信号（VOTE模式）
combine_strategy_signals({
  symbol: "600519",
  strategy_ids: ["rsi_reversal", "ma_cross", "bollinger_breakout"],
  mode: "vote",
  weights: {"rsi_reversal": 1.5, "ma_cross": 1.0, "bollinger_breakout": 1.2}
})

示例2：要求所有策略一致（AND模式）
combine_strategy_signals({
  symbol: "600519",
  strategy_ids: ["rsi_reversal", "ma_cross"],
  mode: "and"
})`,

  parameters: Type.Object({
    symbol: Type.String({
      description: '股票代码'
    }),
    strategy_ids: Type.Array(Type.String(), {
      description: '策略ID列表，至少2个',
      minItems: 2
    }),
    mode: Type.Optional(Type.Union([
      Type.Literal('vote'),
      Type.Literal('and'),
      Type.Literal('or')
    ], {
      description: '组合模式：vote=加权投票（默认）, and=全部一致, or=任一触发'
    })),
    weights: Type.Optional(Type.Record(Type.String(), Type.Number(), {
      description: '策略权重，如 {"rsi_reversal": 1.5, "ma_cross": 1.0}，默认全部为1.0'
    })),
    confidence_threshold: Type.Optional(Type.Number({
      description: '最低置信度阈值，默认 0.5',
      default: 0.5
    }))
  }),

  execute: async (_toolCallId: string, params: any) => {
    try {
      const { symbol, strategy_ids, mode = 'vote', weights, confidence_threshold = 0.5 } = params;

      if (!strategy_ids || strategy_ids.length < 2) {
        return {
          content: [{ type: "text" as const, text: 'Error: At least 2 strategy_ids required' }],
          details: undefined
        };
      }

      const infoJson = await get_stock_info(symbol);
      const infoData = JSON.parse(infoJson);
      const priceJson = await get_stock_realtime_price(symbol);
      const priceData = JSON.parse(priceJson);

      if (infoData.error || priceData.error) {
        return {
          content: [{ type: "text" as const, text: `Failed to get stock data for ${symbol}` }],
          details: undefined
        };
      }

      const tech = await calculateAllIndicators(symbol);

      const signals: any[] = [];
      for (const strategy_id of strategy_ids) {
        const strategy = await quantService.getStrategy(strategy_id);
        if (!strategy) {
          console.warn(`Strategy ${strategy_id} not found, skipping`);
          continue;
        }

        const signal = await signalGenerator.generateSignal(
          symbol,
          infoData.name || symbol,
          strategy,
          tech,
          priceData.price || 0
        );

        if (signal) {
          signals.push(signal);
        }
      }

      if (signals.length === 0) {
        return {
          content: [{ type: "text" as const, text: `No signals generated for ${symbol}` }],
          details: undefined
        };
      }

      if (signals.length === 1) {
        return {
          content: [{ type: "text" as const, text: JSON.stringify({
            signal: signals[0],
            metadata: { reason: 'insufficient_signals' }
          }, null, 2) }],
          details: undefined
        };
      }

      const { signals: combinedSignals, metadata } = await signalGenerator.combineSignals(
        signals,
        mode,
        weights,
        confidence_threshold
      );

      const result = {
        symbol,
        combined_signals: combinedSignals,
        metadata: {
          mode,
          total_strategies: strategy_ids.length,
          signals_generated: signals.length,
          ...metadata
        }
      };

      return {
        content: [{ type: "text" as const, text: JSON.stringify(result, null, 2) }],
        details: result
      };

    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      return {
        content: [{ type: "text" as const, text: `Error: ${msg}` }],
        details: undefined
      };
    }
  }
};
```

- [ ] **Step 2: Export the new tool**

Find the export section and add:

```typescript
export const quantTools = [
  manageQuantStrategyTool,
  runBacktestTool,
  generateSignalsTool,
  scoreStockTool,
  trainSignalModelTool,
  combineStrategySignalsTool
];
```

- [ ] **Step 3: Register in index.ts**

```typescript
import { combineStrategySignalsTool } from './quant-tools.js';
// Add to tools array
```

- [ ] **Step 4: Commit**

```bash
git add src/infrastructure/tools/quant-tools.ts src/infrastructure/tools/index.ts
git commit -m "feat(tools): add combine_strategy_signals tool"
```

---

## Task 4: Add Timeout Configuration

**Files:**
- Modify: `src/infrastructure/tools/shared/python-caller-resilient-adapter.ts`

- [ ] **Step 1: Add timeout config**

Find the `TIMEOUT_CONFIG` object (around line 16) and add:

```typescript
const TIMEOUT_CONFIG: Record<string, number> = {
  // ... existing entries ...
  combine_strategy_signals: TIMEOUT_MEDIUM,  // Add this line
};
```

- [ ] **Step 2: Commit timeout config**

```bash
git add src/infrastructure/tools/shared/python-caller-resilient-adapter.ts
git commit -m "feat(config): add timeout for combine_strategy_signals"
```

---

## Task 5: Update Documentation

**Files:**
- Modify: `quant/README.md`

- [ ] **Step 1: Add Strategy Combination section**

Add this section after the existing strategy documentation:

```markdown
## Strategy Combination

Combine multiple strategies to improve signal accuracy through voting or consensus.

### Combination Modes

**VOTE Mode (Default)**
- Weighted voting based on strategy weights and confidence
- Buy score = Σ(weight × confidence) for all buy signals
- Sell score = Σ(weight × confidence) for all sell signals
- Winner: direction with highest score

Example:
- RSI: buy, confidence=0.8, weight=1.5 → buy_score += 1.2
- MA: buy, confidence=0.6, weight=1.0 → buy_score += 0.6
- BB: sell, confidence=0.5, weight=1.2 → sell_score += 0.6
- Result: buy_score=1.8 > sell_score=0.6 → BUY

**AND Mode**
- All strategies must agree on direction
- Conservative approach, reduces false positives
- Returns empty if any strategy disagrees

**OR Mode**
- Any strategy triggers a signal
- Aggressive approach, maximizes coverage
- Returns all signals without filtering

### Usage Examples

**TypeScript Tool:**
```typescript
// Combine three strategies with custom weights
combine_strategy_signals({
  symbol: "600519",
  strategy_ids: ["rsi_reversal", "ma_cross", "bollinger_breakout"],
  mode: "vote",
  weights: {
    "rsi_reversal": 1.5,
    "ma_cross": 1.0,
    "bollinger_breakout": 1.2
  }
})

// Require all strategies to agree
combine_strategy_signals({
  symbol: "600519",
  strategy_ids: ["rsi_reversal", "ma_cross"],
  mode: "and"
})

// Multi-strategy batch scan
generate_signals({
  action: "batch",
  strategy_ids: ["rsi_reversal", "ma_cross"],
  symbols: ["600519", "000001"],
  mode: "vote"
})
```

**Python API:**
```python
from quantsys.strategies.combiner import StrategyCombiner, CombinerConfig, Signal

# Create signals
signals = [
    Signal(timestamp=now, symbol='600519', action='buy', 
           price=1800, strategy_id='rsi', confidence=0.8),
    Signal(timestamp=now, symbol='600519', action='buy',
           price=1800, strategy_id='ma', confidence=0.6)
]

# Configure combiner
config = CombinerConfig(
    mode='vote',
    weights={'rsi': 1.5, 'ma': 1.0}
)

# Combine
combiner = StrategyCombiner(config)
combined, metadata = combiner.combine_signals(signals)
```

### Weight Tuning Guidelines

1. **Start with equal weights (1.0)** - Establish baseline performance
2. **Increase weight for reliable strategies** - Strategies with higher historical accuracy
3. **Decrease weight for noisy strategies** - Strategies that generate many false signals
4. **Test incrementally** - Adjust weights by 0.2-0.5 at a time
5. **Monitor performance** - Track win rate and profit/loss after weight changes

Typical weight ranges:
- High confidence strategies: 1.5 - 2.0
- Standard strategies: 1.0
- Experimental strategies: 0.5 - 0.8
```

- [ ] **Step 2: Commit documentation**

```bash
git add quant/README.md
git commit -m "docs(quant): add strategy combination documentation"
```

---

## Task 6: Integration Testing

**Files:**
- Create: `src/infrastructure/tools/quant-tools.integration.test.ts`

- [ ] **Step 1: Write integration test**

Create new test file:

```typescript
import { describe, it, expect, beforeAll } from '@jest/globals';
import { combineStrategySignalsTool } from './quant-tools.js';
import { QuantService } from '../../services/quant/quant-service.js';

describe('Strategy Combiner Integration Tests', () => {
  let quantService: QuantService;

  beforeAll(() => {
    quantService = new QuantService();
  });

  it('should combine multiple strategy signals in VOTE mode', async () => {
    // This test requires real strategies to be set up
    // Skip if strategies don't exist
    const strategies = await quantService.listStrategies();
    if (strategies.length < 2) {
      console.log('Skipping: need at least 2 strategies');
      return;
    }

    const result = await combineStrategySignalsTool.execute('test-1', {
      symbol: '600519',
      strategy_ids: [strategies[0].id, strategies[1].id],
      mode: 'vote'
    });

    expect(result.content).toBeDefined();
    expect(result.content[0].type).toBe('text');
  });

  it('should handle insufficient signals gracefully', async () => {
    const result = await combineStrategySignalsTool.execute('test-2', {
      symbol: '999999',  // Invalid symbol
      strategy_ids: ['fake1', 'fake2'],
      mode: 'vote'
    });

    expect(result.content).toBeDefined();
  });
});
```

- [ ] **Step 2: Run integration tests**

```bash
cd /Users/mac/Documents/ai/pi-investment
npm test -- quant-tools.integration.test.ts
```

Expected: Tests pass or skip if strategies not available

- [ ] **Step 3: Commit tests**

```bash
git add src/infrastructure/tools/quant-tools.integration.test.ts
git commit -m "test(quant): add strategy combiner integration tests"
```

---

## Task 7: Manual End-to-End Testing

**Files:**
- None (manual testing)

- [ ] **Step 1: Create test strategies**

Run these commands to create test strategies:

```bash
# Start the app
npm run dev

# In another terminal, use the tools to create strategies
# (Or use existing strategies if available)
```

- [ ] **Step 2: Test single strategy (baseline)**

```typescript
generate_signals({
  action: "scan",
  strategy_id: "rsi_reversal",
  symbol: "600519"
})
```

Expected: Single signal or no signal

- [ ] **Step 3: Test VOTE mode combination**

```typescript
combine_strategy_signals({
  symbol: "600519",
  strategy_ids: ["rsi_reversal", "ma_cross", "bollinger_breakout"],
  mode: "vote",
  weights: {"rsi_reversal": 1.5, "ma_cross": 1.0, "bollinger_breakout": 1.2}
})
```

Expected: Combined signal with metadata showing vote scores

- [ ] **Step 4: Test AND mode (conflict scenario)**

```typescript
combine_strategy_signals({
  symbol: "600519",
  strategy_ids: ["rsi_reversal", "ma_cross"],
  mode: "and"
})
```

Expected: Empty signals if strategies disagree, or combined signals if they agree

- [ ] **Step 5: Test multi-strategy batch**

```typescript
generate_signals({
  action: "batch",
  strategy_ids: ["rsi_reversal", "ma_cross"],
  symbols: ["600519", "000001", "600036"],
  mode: "vote"
})
```

Expected: Combined signals for multiple stocks

- [ ] **Step 6: Verify metadata**

Check that metadata includes:
- `mode`: 'vote', 'and', or 'or'
- `buy_score` and `sell_score` (for VOTE mode)
- `winner`: 'buy' or 'sell'
- `kept_signals`: number of signals returned

- [ ] **Step 7: Document test results**

Create a test report:

```bash
echo "# Strategy Combiner Test Results" > test-results.md
echo "" >> test-results.md
echo "Date: $(date)" >> test-results.md
echo "" >> test-results.md
echo "## Test Cases" >> test-results.md
echo "- [ ] Single strategy baseline" >> test-results.md
echo "- [ ] VOTE mode combination" >> test-results.md
echo "- [ ] AND mode conflict" >> test-results.md
echo "- [ ] Multi-strategy batch" >> test-results.md
echo "- [ ] Metadata verification" >> test-results.md
```

---

## Task 8: Final Verification and Cleanup

**Files:**
- Multiple

- [ ] **Step 1: Run all tests**

```bash
npm test
```

Expected: All tests pass

- [ ] **Step 2: Build TypeScript**

```bash
npm run build
```

Expected: No compilation errors

- [ ] **Step 3: Verify Python imports**

```bash
cd /Users/mac/Documents/ai/pi-investment
python3 -c "from quantsys.strategies.combiner import StrategyCombiner; print('OK')"
```

Expected: Prints "OK"

- [ ] **Step 4: Check for TODO/TBD**

```bash
grep -r "TODO\|TBD\|FIXME" src/services/quant/signal-generator.ts src/infrastructure/tools/quant-tools.ts python/akshare_bridge.py | grep -i combin
```

Expected: No matches (or only pre-existing TODOs)

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "feat(quant): complete strategy combiner implementation

- Add Python bridge function combine_strategy_signals
- Add TypeScript combineSignals and scanMarketMultiStrategy methods
- Add combine_strategy_signals tool
- Enhance generate_signals for multi-strategy mode
- Add documentation and tests
- Support OR/AND/VOTE combination modes"
```

- [ ] **Step 6: Create summary**

Document what was implemented:

```markdown
# Strategy Combiner Implementation Summary

## Completed Features

1. **Python Bridge** (`python/akshare_bridge.py`)
   - `combine_strategy_signals()` function
   - Integrates with `quant/quantsys/strategies/combiner.py`
   - Handles signal serialization/deserialization

2. **TypeScript SignalGenerator** (`src/services/quant/signal-generator.ts`)
   - `combineSignals()` method - combines signals via Python
   - `scanMarketMultiStrategy()` method - batch multi-strategy scanning

3. **Tools** (`src/infrastructure/tools/quant-tools.ts`)
   - New tool: `combine_strategy_signals`
   - Enhanced: `generate_signals` supports `strategy_ids` array

4. **Configuration**
   - Timeout config for Python calls
   - Default VOTE mode with equal weights

5. **Documentation**
   - Strategy combination guide in `quant/README.md`
   - Tool examples and usage patterns

## Usage

```typescript
// Combine three strategies
combine_strategy_signals({
  symbol: "600519",
  strategy_ids: ["rsi_reversal", "ma_cross", "bollinger_breakout"],
  mode: "vote",
  weights: {"rsi_reversal": 1.5}
})

// Multi-strategy batch
generate_signals({
  action: "batch",
  strategy_ids: ["rsi_reversal", "ma_cross"],
  symbols: ["600519", "000001"],
  mode: "vote"
})
```

## Testing

- Integration tests in `quant-tools.integration.test.ts`
- Manual E2E testing completed
- All combination modes verified (OR/AND/VOTE)

## Next Steps

- Monitor performance in production
- Collect feedback on weight tuning
- Consider adding dynamic weight adjustment based on historical performance
```

---

## Success Criteria Checklist

- [ ] Agent can call `combine_strategy_signals` with 2+ strategies
- [ ] `generate_signals` with `strategy_ids` array works
- [ ] VOTE mode calculates weighted scores correctly
- [ ] AND mode returns empty on conflict
- [ ] OR mode returns all signals
- [ ] Python call failures degrade gracefully to OR mode
- [ ] All tests pass
- [ ] Documentation includes examples
- [ ] No compilation errors
- [ ] Manual testing confirms expected behavior

---

## Rollback Plan

If issues arise:

```bash
# Revert all changes
git log --oneline | head -10  # Find commit before strategy combiner
git revert <commit-hash>..HEAD

# Or reset to before implementation
git reset --hard <commit-before-combiner>
```

Affected files to restore:
- `python/akshare_bridge.py`
- `src/services/quant/signal-generator.ts`
- `src/infrastructure/tools/quant-tools.ts`
- `src/infrastructure/tools/index.ts`
- `src/infrastructure/tools/shared/python-caller-resilient-adapter.ts`
- `quant/README.md`
