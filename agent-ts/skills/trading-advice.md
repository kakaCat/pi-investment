---
name: trading-advice
description: >
  Generate daily trading recommendations with market sentiment analysis,
  sector screening, stock selection, and actionable trade plans (entry/stop/target/position).
  Use when user asks to: (1) Generate trading advice/recommendations,
  (2) Create daily trading report, (3) Analyze market opportunities,
  (4) Get stock picks with entry/exit plans, or any trading strategy requests.
---

# Trading Advice

Generate professional daily trading recommendations through systematic analysis.

## Workflow

### 1. Collect Market Data (Parallel)

Fetch in parallel to minimize latency:
- `data_fetch_market_sentiment` - 5 major indices
- `data_fetch_north_flow` - Foreign capital flow
- `sector_analysis` - Sector performance and capital ranking

### 2. Analyze Market Sentiment

**Judge** sentiment, don't just list numbers:

- Average index change:
  - `>+1%` = Strong bullish
  - `0~+1%` = Moderately bullish
  - `-1~0%` = Moderately bearish
  - `<-1%` = Strong bearish

- North flow (sum last 5 days):
  - `>5B CNY` = Sustained inflow
  - `0~5B` = Mild inflow
  - `-5~0B` = Mild outflow
  - `<-5B` = Sustained outflow

**Output**: "Market shows **strong bullish** sentiment with sustained foreign inflow."

### 3. Screen Top Sectors

Identify top 3 by combining fund flow + momentum:

1. Sort `sector_analysis` results by net inflow (desc)
2. Cross-check `sector_analysis` for positive change %
3. Select sectors with **both** high inflow AND momentum

Format:
```
Top 3 Sectors:
1. New Energy - +3.2%, inflow 2.5B
2. Semiconductors - +2.8%, inflow 1.8B
3. AI - +2.5%, inflow 1.5B
```

### 4. Select Stocks from Top Sectors

For each of top 3 sectors:

```
screening({
  action: "quality",
  sector: sector_name,
  min_score: 60,
  limit: 3
})
```

Then for each candidate (max 2 per sector):

**Parallel fetch**:
- `factor_calculate` - MACD, RSI, MA20/60
- `risk_controller`（command: 'position_size'） - Entry zone, stop loss, target

**Signal rules**:
- MACD > 0 + RSI < 40 + MA20 > MA60 = **BUY**
- MACD > 0 + RSI < 60 + MA20 > MA60 = **WATCH**
- Otherwise = Skip (don't output)

**Stop at 5 total candidates**.

### 5. Generate Trade Plans

For each candidate, output:

```markdown
### Stock Name (Symbol)
- **Price**: 185.50 (+2.34%)
- **Signal**: BUY
- **Technicals**: MACD golden cross, RSI 38 (oversold), MA20 > MA60
- **Entry**: 180.00 ~ 183.00 (scale in)
- **Stop**: 171.00 (-5%)
- **Target**: 198.00 (R:R 1:2)
- **Position**: 20% (normal)
- **Logic**: New Energy sector leading with strong inflow, technical breakout
```

**Position sizing**:
- RSI < 30 → 30% (oversold, scale in)
- RSI 30-50 → 20% (normal)
- RSI 50-70 → 10% (light probe)

### 6. Add Risk Warnings

Include:
1. Macro risks (Fed meetings, economic data)
2. Market risks (margin balance high, outflow trend)
3. Stock-specific risks (earnings warnings, insider selling)

## Report Template

```markdown
# Daily Trading Recommendations YYYY-MM-DD HH:MM

## 📊 Market Sentiment

### Indices
- SSE: 3245.67 (+1.23%)
- SZSE: 10234.56 (+1.45%)
- ChiNext: 2156.78 (+2.10%)

### Sentiment: Strong Bullish
5-index average +1.5%, strong breadth.
North flow: Sustained inflow (5-day total +12.5B CNY).

## 🔥 Top Sectors

1. **New Energy** - +3.2%, inflow 2.5B
2. **Semiconductors** - +2.8%, inflow 1.8B
3. **AI** - +2.5%, inflow 1.5B

## 🎯 Stock Picks

[Each stock per Stage 5 format]

## 💡 Action Summary

Market strong bullish with foreign inflow. Top sectors: New Energy, Semiconductors, AI.
Found 2 BUY signals, 3 WATCH candidates. Suggest light participation with strict stops.

## ⚠️ Risk Warnings

1. Fed meeting tonight - watch rate decision
2. Margin balance near 1.8T - leverage risk elevated
3. Some stocks extended - pullback risk

---
> For reference only. Not investment advice.
```

## Save Report

After generation, save with `memory_write`:

```
memory_write({
  content: [full report],
  tags: ["trading_advice", "daily_report", date],
  category: "trading_strategy"
})
```

File path: `.pi-invest/trading-advice/YYYY-MM-DD.md`

## Key Principles

1. **No LLM math** - All calculations via tools
2. **Parallel optimization** - Fetch independent data in parallel
3. **Reasoning over listing** - Analyze WHY, not just WHAT
4. **Risk-first** - Every recommendation has stop/target/position
5. **Max 5 candidates** - Avoid information overload
