---
name: candlestick-analysis
description: 识别K线形态信号（锤子线/吞没/十字星+趋势线突破+斐波那契回调+缺口分析）
---

# K线形态分析技能

## 允许的工具
- get_stock_history()
- analyze_candlestick()
- analyze_price_action()
- get_stock_price()

## 触发条件

用户询问K线形态、蜡烛图信号、趋势线、斐波那契位、跳空缺口时使用。

关键词：K线形态、蜡烛图、锤子线、吞没形态、趋势线、斐波那契、缺口、跳空

## 工具调用

1. 请用户提供股票代码（如果未提供）
2. 调用 `analyze_candlestick(symbol)` 获取结构化分析数据

## 结果解读规则

### patterns（K线形态）

| 形态 | 方向 | 强度 | 含义 |
|------|------|------|------|
| 锤子线 | 看涨 | 强 | 下跌趋势中出现，可能反转向上 |
| 上吊线 | 看跌 | 中 | 上涨趋势中出现，警惕见顶 |
| 流星线 | 看跌 | 强 | 上涨后出现，空方力量增强 |
| 看涨吞没 | 看涨 | 强 | 当日阳线吞没前日阴线，强烈反转信号 |
| 看跌吞没 | 看跌 | 强 | 当日阴线吞没前日阳线，强烈见顶信号 |
| 十字星 | 中性 | 中 | 多空均衡，趋势可能转变 |
| 孕线 | 趋势减弱 | 中 | 小实体在前日实体内，动能衰减 |
| 启明星 | 看涨 | 强 | 三根K线底部反转，可靠度高 |
| 黄昏星 | 看跌 | 强 | 三根K线顶部反转，可靠度高 |

### trend_lines（趋势线）

- `type`: "support"（支撑线）/ "resistance"（阻力线）
- `slope`: 正值=上升趋势，负值=下降趋势，0=水平
- `currentValue`: 当前趋势线价格
- `touchCount`: 触碰次数，≥3次可信度高
- `r2`: 拟合度，越接近1越准确
- `isBreaking`: **true = 价格正在突破趋势线** — 重要操作信号

### fibonacci（斐波那契）

- 方向 `retracing_down`: 价格从高点回调中，各回调位是支撑
- 方向 `retracing_up`: 价格从低点反弹中，各回调位是阻力
- 关键支撑/阻力位: **38.2%、50%、61.8%**（黄金分割）
- `nearestLevel.isNearCurrent=true`: 当前价格在此位附近2%，重要参考

### gaps（跳空缺口）

- `gap_up`: 跳空向上（当日最低 > 前日最高），看涨信号
- `gap_down`: 跳空向下（当日最高 < 前日最低），看跌信号
- `filled=false`: **未回补缺口** — 往往会形成支撑/阻力，关注是否回补
- `gapPct`: 缺口大小，越大意义越重要

## 输出格式

```
## {股票名称}({代码}) K线形态分析

### K线形态信号
- 最近形态：{pattern} — {bullish/bearish/neutral}信号
  解读：{含义}

### 趋势线
- 支撑线：当前值 {currentValue}，斜率 {slope}（{上升/下降}趋势）
  可信度：{touchCount}次触碰，拟合度{r2}
  {isBreaking ? "⚠️ 价格正在跌破支撑线，注意风险" : "支撑线完好"}

- 阻力线：当前值 {currentValue}
  {isBreaking ? "✅ 价格突破阻力线，强烈看涨信号" : "尚未突破"}

### 斐波那契回调位
- 区间：{swingLow} ~ {swingHigh}（近60日）
- 方向：{direction}
- 关键位：
  - 38.2%: {price}
  - 50.0%: {price}
  - 61.8%: {price}（黄金分割）
- 当前价格最近的位：{nearestLevel.label} ({nearestLevel.price})

### 缺口分析
- 未回补缺口：{count}个
  - {date}: {gap_up/gap_down}，{gapPct}%，{已/未}回补

### 综合研判
{summary}

⚠️ 以上分析基于纯价格形态，需结合基本面和市场环境综合判断。
```
