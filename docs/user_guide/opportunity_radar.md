# Opportunity Radar User Guide

## Overview

The Opportunity Radar feature helps you discover investment opportunities by scanning stocks and scoring them across three dimensions: technical analysis, fundamental analysis, and capital flow.

## How to Use

### 1. Basic Scan

Scan your watchlist and hot stocks without filters:

```bash
curl -X POST http://localhost:5001/api/signals/scan \
  -H "Content-Type: application/json" \
  -d '{}'
```

This scans ~400 stocks (your watchlist + 沪深300 + 创业板50 + 科创50).

### 2. Scan Specific Stocks

```bash
curl -X POST http://localhost:5001/api/signals/scan \
  -H "Content-Type: application/json" \
  -d '{"stocks": ["600519.SH", "000001.SZ"]}'
```

### 3. Filter by Score

Only show opportunities with score ≥ 70:

```bash
curl -X POST http://localhost:5001/api/signals/scan \
  -H "Content-Type: application/json" \
  -d '{"minScore": 70}'
```

### 4. Filter by Risk Level

Only show low-risk opportunities:

```bash
curl -X POST http://localhost:5001/api/signals/scan \
  -H "Content-Type: application/json" \
  -d '{"maxRiskLevel": "low"}'
```

Risk levels:
- **low**: confidence ≥ 0.7 (score ≥ 70)
- **medium**: confidence ≥ 0.5 (score ≥ 50)
- **high**: confidence < 0.5 (score < 50)

### 5. Technical Filters

Find stocks with specific technical patterns:

```bash
curl -X POST http://localhost:5001/api/signals/scan \
  -H "Content-Type: application/json" \
  -d '{
    "technical": ["rsi_oversold", "macd_golden_cross"]
  }'
```

Available technical filters:
- `rsi_oversold`: RSI < 30 (oversold)
- `macd_golden_cross`: MACD golden cross
- `bollinger_breakout`: Price breaks above upper Bollinger Band
- `volume_surge`: Volume > 2x average

### 6. Fundamental Filters

Find stocks with strong fundamentals:

```bash
curl -X POST http://localhost:5001/api/signals/scan \
  -H "Content-Type: application/json" \
  -d '{
    "fundamental": ["low_pe", "high_roe"]
  }'
```

Available fundamental filters:
- `low_pe`: PE ratio < 30
- `high_roe`: ROE > 15%
- `high_margin`: Gross margin > 30%
- `low_debt`: Debt ratio < 50%

### 7. Combined Filters

Combine multiple filters for precise screening:

```bash
curl -X POST http://localhost:5001/api/signals/scan \
  -H "Content-Type: application/json" \
  -d '{
    "minScore": 70,
    "maxRiskLevel": "medium",
    "technical": ["rsi_oversold"],
    "fundamental": ["low_pe", "high_roe"]
  }'
```

## Understanding the Scores

### Comprehensive Score (0-100)

The overall opportunity score, calculated as:
- Technical Score × 50%
- Fundamental Score × 30%
- Capital Score × 20%

**Formula**: `comprehensive_score = technical × 0.5 + fundamental × 0.3 + capital × 0.2`

### Technical Score (0-100)

Based on technical indicators:
- RSI oversold (RSI < 30): +25 points
- MACD golden cross: +25 points
- Bollinger Band breakout: +25 points
- Volume surge (volume > 2x avg): +25 points

### Fundamental Score (0-100)

Based on fundamental metrics:
- PE < 30: +25 points
- ROE > 15%: +25 points
- Gross Margin > 30%: +25 points
- Debt Ratio < 50%: +25 points

**Note**: If fundamental data is not available, a neutral score of 50 is assigned.

### Capital Score (0-100)

Based on capital flow indicators:
- Volume growth > 50% (vs 5-day avg): +25 points
- 3+ consecutive volume increases: +25 points
- Volume > MA20: +25 points
- Volume MA5 > MA20: +25 points

## Interpreting Results

### Example Response

```json
{
  "success": true,
  "opportunities": [
    {
      "symbol": "600519.SH",
      "name": "贵州茅台",
      "score": 85,
      "technical_score": 90,
      "fundamental_score": 80,
      "capital_score": 75,
      "confidence": 0.85,
      "risk_level": "low",
      "signal_type": "buy",
      "timestamp": "2026-05-24T12:00:00"
    }
  ],
  "total": 1,
  "scanned": 400
}
```

### What Each Field Means

- **symbol**: Stock code (e.g., "600519.SH")
- **name**: Stock name (e.g., "贵州茅台")
- **score**: Comprehensive score (0-100) - higher is better
- **technical_score**: Technical analysis score (0-100)
- **fundamental_score**: Fundamental analysis score (0-100)
- **capital_score**: Capital flow score (0-100)
- **confidence**: Confidence level (0-1) - same as score/100
- **risk_level**: Risk assessment (low/medium/high)
- **signal_type**: Signal type (currently always "buy")
- **timestamp**: When the opportunity was identified
- **total**: Number of opportunities found
- **scanned**: Total number of stocks scanned

## Tips for Effective Use

### 1. Start Broad, Then Narrow

Begin with no filters to see all opportunities, then add filters to focus on specific criteria:

```bash
# Step 1: See all opportunities
curl -X POST http://localhost:5001/api/signals/scan \
  -H "Content-Type: application/json" \
  -d '{}'

# Step 2: Focus on high-quality opportunities
curl -X POST http://localhost:5001/api/signals/scan \
  -H "Content-Type: application/json" \
  -d '{"minScore": 70, "maxRiskLevel": "low"}'
```

### 2. Balance the Three Dimensions

A well-balanced opportunity should have good scores across all three dimensions:

- **High technical + Low fundamental**: May indicate short-term opportunity but long-term risk
- **High fundamental + Low technical**: May indicate good long-term value but poor entry timing
- **High capital + Low technical/fundamental**: May indicate speculation or manipulation

Look for opportunities with balanced scores across all dimensions.

### 3. Check Risk Level

Low-risk opportunities (confidence ≥ 0.7) are more reliable:

```bash
curl -X POST http://localhost:5001/api/signals/scan \
  -H "Content-Type: application/json" \
  -d '{"maxRiskLevel": "low", "minScore": 70}'
```

### 4. Use Technical Filters for Entry Timing

Technical filters help identify good entry points:

```bash
# Find oversold stocks (potential bounce)
curl -X POST http://localhost:5001/api/signals/scan \
  -H "Content-Type: application/json" \
  -d '{"technical": ["rsi_oversold"]}'

# Find momentum breakouts
curl -X POST http://localhost:5001/api/signals/scan \
  -H "Content-Type: application/json" \
  -d '{"technical": ["macd_golden_cross", "volume_surge"]}'
```

### 5. Use Fundamental Filters for Quality

Fundamental filters help identify quality companies:

```bash
# Find value stocks
curl -X POST http://localhost:5001/api/signals/scan \
  -H "Content-Type: application/json" \
  -d '{"fundamental": ["low_pe", "low_debt"]}'

# Find growth stocks
curl -X POST http://localhost:5001/api/signals/scan \
  -H "Content-Type: application/json" \
  -d '{"fundamental": ["high_roe", "high_margin"]}'
```

### 6. Monitor Performance

The scan is fast (~0.2s for 400 stocks), so you can run it frequently:

- **Morning**: Scan before market open to identify opportunities
- **Midday**: Re-scan to catch intraday movements
- **Evening**: Final scan to prepare for next day

### 7. Combine with Your Own Research

The Opportunity Radar is a screening tool, not a trading signal:

1. Use the radar to discover opportunities
2. Review the stock's chart and fundamentals
3. Check news and market sentiment
4. Make your own investment decision

**Important**: Always do your own research before investing. The radar provides data-driven insights, but investment decisions should consider your own risk tolerance, investment goals, and market knowledge.

## Common Use Cases

### Use Case 1: Daily Morning Scan

Find high-quality opportunities to watch during the day:

```bash
curl -X POST http://localhost:5001/api/signals/scan \
  -H "Content-Type: application/json" \
  -d '{
    "minScore": 70,
    "maxRiskLevel": "medium",
    "technical": ["rsi_oversold", "macd_golden_cross"]
  }'
```

### Use Case 2: Value Investing

Find undervalued stocks with strong fundamentals:

```bash
curl -X POST http://localhost:5001/api/signals/scan \
  -H "Content-Type: application/json" \
  -d '{
    "fundamental": ["low_pe", "high_roe", "low_debt"],
    "minScore": 65
  }'
```

### Use Case 3: Momentum Trading

Find stocks with strong momentum:

```bash
curl -X POST http://localhost:5001/api/signals/scan \
  -H "Content-Type: application/json" \
  -d '{
    "technical": ["macd_golden_cross", "volume_surge", "bollinger_breakout"],
    "minScore": 60
  }'
```

### Use Case 4: Conservative Screening

Find low-risk, high-quality opportunities:

```bash
curl -X POST http://localhost:5001/api/signals/scan \
  -H "Content-Type: application/json" \
  -d '{
    "minScore": 75,
    "maxRiskLevel": "low",
    "fundamental": ["low_debt", "high_roe"]
  }'
```

## Troubleshooting

### No Opportunities Found

If the scan returns no opportunities:

1. **Relax filters**: Try removing some filters or lowering minScore
2. **Check market conditions**: In bear markets, fewer opportunities may exist
3. **Verify data**: Ensure K-line and fundamental data is up to date

### Scan Takes Too Long

If the scan takes more than 10 seconds:

1. **Check database**: Ensure PostgreSQL is running and responsive
2. **Reduce scope**: Scan specific stocks instead of the full pool
3. **Check logs**: Look for errors in the API server logs

### Unexpected Results

If results don't match expectations:

1. **Review scoring logic**: Check the scoring algorithm in the documentation
2. **Verify data quality**: Ensure K-line and fundamental data is accurate
3. **Check filters**: Verify filter parameters are correct

## Performance Characteristics

- **Scan time**: ~0.2 seconds for 400 stocks
- **Database queries**: 3-5 total queries (batch optimized)
- **Parallel processing**: 10 workers
- **Memory usage**: 50-100 MB
- **Data window**: 120 days of K-line data

## Next Steps

After identifying opportunities with the Opportunity Radar:

1. **Review details**: Check the stock's detailed information
2. **Analyze charts**: Look at price charts and technical indicators
3. **Read news**: Check recent news and announcements
4. **Set alerts**: Monitor the stock for entry opportunities
5. **Plan trade**: Define entry price, stop loss, and target price
6. **Execute**: Place orders through your trading platform

Remember: The Opportunity Radar is a tool to help you discover opportunities, but successful investing requires careful analysis, risk management, and disciplined execution.
