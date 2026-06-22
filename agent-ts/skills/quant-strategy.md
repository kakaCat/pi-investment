---
name: quant-strategy
description: 设计或执行A股量化框架（市场过滤+行业轮动+质量评分+趋势确认）
---

# 量化策略技能 (Quant Strategy)

## 允许的工具

- get_market_overview()
- get_north_flow()
- get_macro_data()
- get_sector_fund_flow()
- screen_stocks_quality()
- get_quality_score()
- get_financial_data()
- get_pe_percentile()
- get_valuation()
- analyze_price_action()
- get_stock_price()
- manage_portfolio()

## 触发条件

用户想让系统:

- 设计量化方案
- 跑一套量化筛选
- 给出量化选股和仓位建议
- 做行业轮动或趋势打分

关键词:

- 量化
- 策略
- 因子
- 轮动
- 打分
- 组合优化

## 核心原则

这不是高频策略，也不是纯黑盒多因子。默认采用:

- 市场过滤
- 行业轮动
- 个股质量过滤
- 技术趋势确认
- 波动率风控

## 执行流程

### 1. 市场状态判断

先并行获取:

- `get_market_overview()`
- `get_north_flow()`
- `get_macro_data()`

给出市场结论:

- 进攻
- 中性
- 防守

如果市场明显弱势，直接降低建议仓位，不强行选股。

### 2. 行业层筛选

调用 `get_sector_fund_flow()` 找出资金净流入和相对强势行业。

只保留 Top 3 到 Top 5 板块。

### 3. 板块内选股

对每个候选板块调用:

`screen_stocks_quality(sector, min_score=60, limit=10)`

然后对 Top 候选补充调用:

- `get_quality_score(symbol)`
- `get_financial_data(symbol)`
- `get_pe_percentile(symbol)` 或 `get_valuation(symbol)`
- `analyze_price_action(symbol)`

### 4. 评分逻辑

默认综合分:

`Q = 0.35 * quality + 0.25 * trend + 0.20 * sector + 0.10 * valuation + 0.10 * risk`

硬过滤:

- 质量分 < 60 不入池
- 明显空头趋势不入池
- 估值极贵且高拥挤不入池

### 5. 仓位建议

默认规则:

- 总仓位随市场状态调整
- 单股上限 12%
- 单行业上限 25%
- 留 15% 以上现金

### 6. 输出要求

输出必须包含:

- 市场状态
- 候选行业
- 候选股票列表
- 每只股票的核心评分依据
- 建议仓位
- 止损和调仓条件

## 输出模板

```markdown
## 量化结果

### 市场状态
- 结论: 进攻/中性/防守
- 建议总仓位: XX%

### 候选行业
| 行业 | 资金流 | 结论 |
|------|--------|------|
| XX | +XX亿 | 保留 |

### 候选股票
| 股票 | 代码 | 综合分Q | 质量分 | 趋势分 | 估值 | 建议仓位 |
|------|------|---------|--------|--------|------|----------|
| XX | 600XXX | 82 | 78 | 85 | 合理 | 10% |

### 风控规则
- 止损: 8% 或 2ATR
- 市场转弱时先降高波动仓位
- 跌破 MA20 且放量时减仓
```
