# Financial Indicators Injection Design

**Date**: 2026-05-27  
**Status**: Approved  
**Implementation**: Phase 1 (Minimal Implementation)

## Overview

Add `_inject_financial()` method to `StrategyCodeService` to inject quarterly and annual financial indicators into K-line DataFrames, enabling strategy code to use fundamental analysis factors alongside technical indicators.

## Problem Statement

Current strategy engine only supports technical indicators. Key fundamental metrics (ROE, gross margin, debt ratio, etc.) are available via akshare but not accessible in strategy code. This limits the ability to build strategies that combine technical and fundamental analysis.

**Example use case**:
```python
# Currently impossible in strategy code
df['quality_stock'] = (
    (df['roe_y'] >= 15) &           # Annual ROE >= 15%
    (df['debt_ratio_y'] < 60) &     # Debt ratio < 60%
    (df['gross_margin_q'] > 30) &   # Quarterly gross margin > 30%
    (df['ocf_to_profit_q'] > 0.8)   # Cash flow quality
)

# Technical + Fundamental confluence
df['buy'] = (df['rsi'] < 30) & df['quality_stock']
```

## Design Decisions

### 1. Implementation Approach

**Chosen**: Minimal implementation (Plan A)
- Add `_inject_financial()` method in `StrategyCodeService`
- Direct akshare API calls with in-memory calculation
- No database persistence
- Pattern matches existing `_inject_fund_flow()` method

**Rationale**:
- Fastest time to value (1-2 hours implementation)
- Validates functionality before investing in optimization
- Easy to upgrade to Plan B (service layer) or Plan C (persistence) later

### 2. Data Sources

**Primary**: akshare `stock_financial_report_sina()` (Sina Finance)
**Fallback**: akshare `stock_financial_analysis_indicator()` (East Money)

**Degradation chain**:
```
Sina Finance (akshare)
  ↓ on failure
East Money (akshare)
  ↓ on failure
Fill all columns with NaN
```

**Rationale**:
- Two-tier fallback covers 95% of scenarios
- Both sources are free and require no tokens
- tushare (tier 3) deferred to future optimization due to token requirement

### 3. Temporal Alignment Strategy

**Rule**: Use announcement date (`公告日期`) for forward-fill

**Algorithm**:
- For each K-line date, find the most recent financial report where `announcement_date <= kline_date`
- If no report exists before that date, fill with NaN
- Start using report data from announcement date (same day), not report period end date

**Rationale**:
- Avoids future information leakage
- Announcement date is when data becomes publicly available
- NaN for missing data lets strategy code decide how to handle

### 4. Indicators and Column Naming

**9 indicators × 2 periods = 18 columns**

**Quarterly indicators** (suffix `_q`):
- `roe_q` - Return on Equity (%)
- `gross_margin_q` - Gross Profit Margin (%)
- `net_profit_margin_q` - Net Profit Margin (%)
- `debt_ratio_q` - Debt to Asset Ratio (%)
- `revenue_growth_q` - Revenue Growth YoY (%)
- `ocf_to_profit_q` - Operating Cash Flow / Net Profit
- `current_ratio_q` - Current Ratio
- `roa_q` - Return on Assets (%)
- `operating_margin_q` - Operating Profit Margin (%)

**Annual indicators** (suffix `_y`):
Same 9 indicators with `_y` suffix

**Calculation formulas**:

| Indicator | Formula | Data Sources |
|-----------|---------|--------------|
| ROE | 净利润 / 股东权益合计 × 100 | Income + Balance |
| Gross Margin | (营业收入 - 营业成本) / 营业收入 × 100 | Income |
| Net Profit Margin | 净利润 / 营业收入 × 100 | Income |
| Debt Ratio | 负债合计 / 资产总计 × 100 | Balance |
| Revenue Growth | (本期营收 - 去年同期) / 去年同期 × 100 | Income (historical) |
| OCF to Profit | 经营活动现金流量净额 / 净利润 | Cash Flow + Income |
| Current Ratio | 流动资产合计 / 流动负债合计 | Balance |
| ROA | 净利润 / 资产总计 × 100 | Income + Balance |
| Operating Margin | 营业利润 / 营业收入 × 100 | Income |

## Architecture

### Component Diagram

```
StrategyCodeService
  ├── execute_indicator_strategy()
  │     ├── get_klines_for_strategy()
  │     ├── _inject_fund_flow()          ← existing
  │     ├── _inject_financial()          ← NEW
  │     └── indicator_executor.execute()
  │
  ├── execute_script_strategy()
  │     ├── get_klines_for_strategy()
  │     ├── _inject_fund_flow()          ← existing
  │     ├── _inject_financial()          ← NEW
  │     └── script_executor.execute()
  │
  └── _inject_financial()                ← NEW METHOD
        ├── _fetch_financial_data()
        │     ├── _fetch_from_sina()
        │     └── _fetch_from_eastmoney()  (fallback)
        ├── _calculate_indicators()
        └── _forward_fill_to_klines()
```

### Data Flow

```
1. Get K-lines (daily)
   ↓
2. Fetch financial reports (quarterly + annual)
   - Income statements
   - Balance sheets
   - Cash flow statements
   ↓
3. Calculate 9 indicators for each report
   ↓
4. Build timeline: [(announce_date, indicators), ...]
   ↓
5. Forward-fill to K-lines
   - For each K-line date
   - Find most recent report where announce_date <= kline_date
   - Copy indicator values to K-line
   ↓
6. Return enhanced K-lines with 18 new columns
```

## Implementation Details

### Method Signature

```python
def _inject_financial(
    self,
    klines: List[Dict],
    symbol: str
) -> List[Dict]:
    """
    Inject financial indicators into K-line list.
    
    Adds 18 columns (9 indicators × 2 periods):
    - Quarterly: roe_q, gross_margin_q, net_profit_margin_q, debt_ratio_q,
                 revenue_growth_q, ocf_to_profit_q, current_ratio_q, roa_q, operating_margin_q
    - Annual: same indicators with _y suffix
    
    Uses forward-fill based on announcement date to avoid future information leakage.
    If data unavailable, columns are filled with NaN.
    
    Args:
        klines: List of K-line dicts with 'trade_date' field
        symbol: Stock code (6-digit A-share code)
    
    Returns:
        Enhanced K-line list with financial indicator columns
    """
```

### Temporal Alignment Algorithm

```python
# Pseudocode
def _forward_fill_to_klines(klines, financial_timeline_q, financial_timeline_y):
    # Sort timelines by announcement date
    timeline_q = sorted(financial_timeline_q, key=lambda x: x['announce_date'])
    timeline_y = sorted(financial_timeline_y, key=lambda x: x['announce_date'])
    
    for kline in klines:
        kline_date = kline['trade_date']
        
        # Find most recent quarterly report
        latest_q = None
        for report in timeline_q:
            if report['announce_date'] <= kline_date:
                latest_q = report
            else:
                break
        
        # Fill quarterly indicators
        if latest_q:
            kline['roe_q'] = latest_q['roe']
            kline['gross_margin_q'] = latest_q['gross_margin']
            # ... other indicators
        else:
            kline['roe_q'] = float('nan')
            # ... other indicators as NaN
        
        # Same logic for annual indicators
        # ...
    
    return klines
```

**Optimization**: Use binary search or pointer-based traversal to avoid O(n²) complexity.

### Error Handling

| Error Scenario | Handling Strategy | User Impact |
|----------------|-------------------|-------------|
| akshare API failure | Try fallback source, then fill NaN | Strategy runs with missing data |
| Missing report fields | Set that indicator to NaN | Other indicators still available |
| Invalid announcement date | Skip that report, log warning | Use other valid reports |
| Division by zero in calculation | Catch exception, set NaN | Other indicators unaffected |
| Network timeout | 30s timeout, then fill NaN | Strategy execution not blocked |

**Logging strategy**:
- `logger.debug()` - Normal flow (fetch success, match count)
- `logger.warning()` - Recoverable errors (missing fields, calculation errors)
- `logger.error()` - Unexpected errors (should not happen in normal operation)

**Graceful degradation guarantee**:
- Even if all financial data fetch fails, strategy code still runs
- Strategy code can check `pd.isna(df['roe_q'])` to detect missing data
- Consistent with `_inject_fund_flow()` error handling pattern

## Performance Characteristics

**First call per stock**:
- API calls: 6 (3 statements × 2 periods)
- Expected time: 2-5 seconds (network dependent)
- Memory: ~50KB per stock (raw financial data)

**Computational complexity**:
- Naive: O(n × m) where n=K-lines, m=reports (typically m < 20)
- Optimized: O(n log m) with binary search

**Optimization techniques**:
- Binary search for temporal alignment
- Disable proxy for domestic API access
- Fast-fail on exceptions to avoid blocking

## Known Limitations

1. **No batch optimization**: Each stock fetches data independently
2. **No caching**: Re-fetches data on every execution (Plan B will add caching)
3. **Historical data dependency**: Limited by akshare's historical coverage
4. **Revenue growth calculation**: First year may be NaN (requires prior year data)

**Suitable for**:
- ✅ Single-stock strategy backtesting
- ✅ Small-scale multi-stock backtesting (< 10 stocks)
- ❌ Large-scale batch backtesting (> 50 stocks, upgrade to Plan B/C recommended)

## Future Optimization Path

**Phase 2 (Plan B)**: Service layer encapsulation
- Move calculation logic to `DataService`
- Add quarterly-level caching
- Enable code reuse across services

**Phase 3 (Plan C)**: Full persistence
- Use `FinancialRepository` for database storage
- Add data backfill task (similar to K-line backfill)
- Support batch query optimization
- Production-ready for large-scale usage

## Testing Strategy

**Unit tests**:
- `test_calculate_indicators()` - Verify calculation formulas
- `test_forward_fill_alignment()` - Verify temporal alignment logic
- `test_error_handling()` - Verify graceful degradation

**Integration tests**:
- Test with real akshare data for known stock (e.g., 600519)
- Verify all 18 columns are injected
- Verify NaN handling when data unavailable

**Manual verification**:
- Run strategy with financial indicators
- Check that `df['roe_q']` values match manual calculation
- Verify no future information leakage (announcement date alignment)

## Success Criteria

1. ✅ Strategy code can access 18 financial indicator columns
2. ✅ No future information leakage (forward-fill based on announcement date)
3. ✅ Graceful degradation when data unavailable (NaN filling)
4. ✅ Performance acceptable for single-stock backtesting (< 10s total)
5. ✅ Error handling prevents strategy execution from failing

## References

- Existing pattern: `_inject_fund_flow()` at line 823 in `strategy_code_service.py`
- Data source: akshare `stock_financial_report_sina()` documentation
- Related: `DataService.get_financial_statements()` at line 680 in `data_service.py`
