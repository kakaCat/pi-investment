# Strategy Combiner Design

**Date:** 2026-05-19  
**Status:** Approved  
**Author:** Claude (Opus 4.6)

## Problem Statement

The TypeScript quant tools currently run each strategy independently, missing the opportunity to combine multiple signals for higher accuracy. The Python quant system (`quant/quantsys/strategies/combiner.py`) already supports multi-strategy fusion with OR/AND/VOTE modes, but this capability is not exposed to the TypeScript layer.

**Current State:**
- Python: Full combiner implementation with OR/AND/VOTE modes, weighted voting, confidence scoring
- TypeScript: `SignalGenerator.generateSignal()` accepts only a single strategy
- Gap: No way to combine RSI + MA + Bollinger signals for voting

**Goal:**
Enable TypeScript tools to combine multiple strategy signals using Python's proven combiner logic.

## Requirements

### Functional Requirements

1. **New Tool: `combine_strategy_signals`**
   - Accept multiple strategy IDs and a stock symbol
   - Support OR/AND/VOTE combination modes
   - Allow custom strategy weights
   - Return combined signals with decision metadata

2. **Enhanced Tool: `generate_signals`**
   - Accept `strategy_ids` array (in addition to single `strategy_id`)
   - Automatically combine signals when multiple strategies provided
   - Default to VOTE mode with equal weights

3. **SignalGenerator API**
   - Add `combineSignals()` method to call Python combiner
   - Add `scanMarketMultiStrategy()` for batch processing

### Non-Functional Requirements

1. **Performance:** Combiner calls should complete within 35 seconds (TIMEOUT_MEDIUM)
2. **Reliability:** Retry up to 2 times on failure, with graceful degradation
3. **Compatibility:** Maintain backward compatibility with single-strategy workflows
4. **Testability:** Unit and integration tests for all new components

## Architecture

### Data Flow

```
Agent calls tool
  ↓
TypeScript Tool Layer (quant-tools.ts)
  ↓
SignalGenerator.combineSignals() (signal-generator.ts)
  ↓
callPythonResilient('combine_strategy_signals', ...)
  ↓
Python akshare_bridge.py
  ↓
quant/quantsys/strategies/combiner.py (StrategyCombiner)
  ↓
Return combined signals + metadata
```

### Component Breakdown

#### 1. Python Layer (`python/akshare_bridge.py`)

**New Function:**
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
            'combined_signals': [...],  # List of signals that passed combination
            'metadata': {
                'mode': 'vote',
                'winner': 'buy',
                'buy_score': 2.3,
                'sell_score': 0.5,
                'kept_signals': 2,
                'reason': 'vote_winner'
            }
        }
    """
```

**Implementation Steps:**
1. Import `StrategyCombiner`, `Signal`, `CombinerConfig` from `quant/quantsys/strategies/combiner.py`
2. Convert TypeScript signal objects to Python `Signal` dataclass instances
3. Create `CombinerConfig` from params
4. Instantiate `StrategyCombiner` and call `combine_signals()`
5. Serialize results back to JSON

#### 2. TypeScript SignalGenerator (`src/services/quant/signal-generator.ts`)

**New Method:**
```typescript
async combineSignals(
  signals: Signal[],
  mode: 'or' | 'and' | 'vote' = 'vote',
  weights?: Record<string, number>,
  confidenceThreshold: number = 0.5
): Promise<{ signals: Signal[], metadata: any }>
```

**Implementation:**
- Map TypeScript `Signal` objects to Python-compatible format
- Call `callPythonResilient('combine_strategy_signals', ...)`
- Parse JSON response and return typed result

**New Method:**
```typescript
async scanMarketMultiStrategy(
  strategies: QuantStrategy[],
  stockData: StockData[],
  mode: 'or' | 'and' | 'vote' = 'vote',
  weights?: Record<string, number>
): Promise<Signal[]>
```

**Implementation:**
1. For each stock, generate signals for all strategies
2. Group signals by symbol
3. For each symbol, call `combineSignals()` with that symbol's signals
4. Flatten and return combined signals

#### 3. Tool Layer (`src/infrastructure/tools/quant-tools.ts`)

**New Tool: `combine_strategy_signals`**

```typescript
{
  name: 'combine_strategy_signals',
  label: '组合多策略信号',
  description: `组合多个策略的交易信号，支持 OR/AND/VOTE 模式。
  
使用场景：
- RSI + 均线 + 布林带三个信号投票
- 要求所有策略一致才执行（AND 模式）
- 任一策略触发即执行（OR 模式）

返回：组合后的信号和决策元数据`,

  parameters: {
    symbol: string,
    strategy_ids: string[],  // min 2
    mode?: 'vote' | 'and' | 'or',  // default 'vote'
    weights?: Record<string, number>,  // default all 1.0
    confidence_threshold?: number  // default 0.5
  }
}
```

**Enhanced Tool: `generate_signals`**

Add optional parameters:
- `strategy_ids?: string[]` - alternative to single `strategy_id`
- `mode?: 'vote' | 'and' | 'or'` - used when `strategy_ids` provided
- `weights?: Record<string, number>` - strategy weights for VOTE mode

**Behavior:**
- If `strategy_id` provided: existing single-strategy logic
- If `strategy_ids` provided: generate signals for each strategy, then combine

#### 4. Configuration (`src/infrastructure/tools/shared/python-caller-resilient-adapter.ts`)

Add timeout and retry config:
```typescript
TIMEOUT_CONFIG: {
  combine_strategy_signals: TIMEOUT_MEDIUM  // 35000ms
}

RETRY_CONFIG: {
  // Use default: 2 retries
}
```

## Combination Modes

### VOTE Mode (Default)

**Logic:** Weighted voting based on strategy weights and signal confidence.

**Score Calculation:**
```
buy_score = Σ(weight[strategy] × confidence) for all buy signals
sell_score = Σ(weight[strategy] × confidence) for all sell signals
```

**Winner:** Direction with highest score (if tie, skip by default)

**Example:**
```
Signals:
- RSI: buy, confidence=0.8, weight=1.5 → buy_score += 1.2
- MA: buy, confidence=0.6, weight=1.0 → buy_score += 0.6
- BB: sell, confidence=0.5, weight=1.2 → sell_score += 0.6

Result: buy_score=1.8 > sell_score=0.6 → BUY
```

### AND Mode

**Logic:** All strategies must agree on direction.

**Behavior:**
- If any strategy disagrees: return empty (no signal)
- If all agree: return all signals
- Optional: `min_agree_count` to require minimum number of strategies

**Use Case:** Conservative trading, reduce false positives

### OR Mode

**Logic:** Any strategy triggers a signal.

**Behavior:**
- Return all signals without filtering
- Useful for capturing more opportunities

**Use Case:** Aggressive trading, maximize coverage

## Error Handling

### Error Scenarios

1. **Python Call Failure**
   - Cause: Network timeout, process crash, import error
   - Handling: Retry up to 2 times with exponential backoff
   - Fallback: Return all signals (OR mode) with warning in metadata

2. **Insufficient Signals**
   - Cause: Only 1 strategy generated a signal
   - Handling: Return that single signal, metadata marks `insufficient_signals`

3. **Strategy Conflict (AND mode)**
   - Cause: Strategies disagree on direction
   - Handling: Return empty signal list, metadata explains conflict

4. **VOTE Tie**
   - Cause: buy_score == sell_score
   - Handling: Skip (return empty) by default, configurable via `tie_policy`

5. **Invalid Parameters**
   - Cause: Empty strategy_ids, invalid mode, negative weights
   - Handling: Return error message, do not call Python

### Degradation Strategy

If Python combiner fails after retries:
1. Log error with full context
2. Return all signals (OR mode behavior)
3. Add metadata: `{ fallback: true, reason: 'python_error', error: '...' }`
4. Agent can decide whether to use fallback signals

## Testing Strategy

### Unit Tests

**Python Layer** (`quant/tests/test_combiner.py` - already exists)
- Verify OR/AND/VOTE modes
- Verify weight calculations
- Verify edge cases (empty, single, conflict)

**TypeScript Layer** (new: `src/services/quant/signal-generator.test.ts`)
- Test `combineSignals()` calls Python and parses response
- Test `scanMarketMultiStrategy()` groups signals by symbol
- Mock Python calls, test error degradation

### Integration Tests

**Tool Layer** (extend: `src/infrastructure/tools/quant-tools.test.ts`)
- Test `combine_strategy_signals` tool end-to-end
- Test `generate_signals` with multiple strategies
- Use real strategies (RSI + MA) to verify combination

### Manual Test Scenarios

1. Create 3 strategies (RSI, MA, BB)
2. Generate signals for same stock
3. Verify VOTE mode calculates scores correctly
4. Verify AND mode returns empty on conflict
5. Verify OR mode returns all signals

## Documentation

### Tool Descriptions

Add `promptSnippet` examples:

```typescript
promptSnippet: `
Example 1: Combine three strategies (VOTE mode)
combine_strategy_signals({
  symbol: "600519",
  strategy_ids: ["rsi_reversal", "ma_cross", "bollinger_breakout"],
  mode: "vote",
  weights: {"rsi_reversal": 1.5, "ma_cross": 1.0, "bollinger_breakout": 1.2}
})

Example 2: Require all strategies to agree (AND mode)
combine_strategy_signals({
  symbol: "600519",
  strategy_ids: ["rsi_reversal", "ma_cross"],
  mode: "and"
})

Example 3: Batch generate with multi-strategy
generate_signals({
  action: "batch",
  strategy_ids: ["rsi_reversal", "ma_cross"],
  symbols: ["600519", "000001"],
  mode: "vote"
})
`
```

### README Updates

Update `quant/README.md`:
- Add "Strategy Combination" section
- Explain OR/AND/VOTE modes with use cases
- Provide weight tuning guidelines
- Link to combiner.py documentation

## Implementation Checklist

1. **Python Layer**
   - [ ] Add `combine_strategy_signals()` to `akshare_bridge.py`
   - [ ] Import and integrate with `quant/quantsys/strategies/combiner.py`
   - [ ] Handle signal serialization/deserialization
   - [ ] Add error handling and logging

2. **TypeScript SignalGenerator**
   - [ ] Add `combineSignals()` method
   - [ ] Add `scanMarketMultiStrategy()` method
   - [ ] Add unit tests with mocked Python calls

3. **Tool Layer**
   - [ ] Create `combine_strategy_signals` tool
   - [ ] Extend `generate_signals` to support `strategy_ids`
   - [ ] Add timeout/retry config
   - [ ] Add integration tests

4. **Documentation**
   - [ ] Add promptSnippet examples to tools
   - [ ] Update `quant/README.md`
   - [ ] Add inline code comments

5. **Testing**
   - [ ] Run existing Python combiner tests
   - [ ] Add TypeScript unit tests
   - [ ] Add integration tests
   - [ ] Manual testing with real strategies

## Success Criteria

1. Agent can call `combine_strategy_signals` with 2+ strategies and get combined result
2. `generate_signals` with `strategy_ids` array automatically combines signals
3. VOTE mode correctly calculates weighted scores
4. AND mode returns empty on conflict
5. OR mode returns all signals
6. Python call failures degrade gracefully
7. All tests pass
8. Documentation is clear and includes examples

## Future Enhancements (Out of Scope)

1. Dynamic weight adjustment based on historical performance
2. Strategy grouping (combine within groups, then combine groups)
3. TypeScript-native combiner for offline/browser use
4. Real-time strategy performance tracking
5. A/B testing framework for combination strategies
