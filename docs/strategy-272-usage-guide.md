# 272策略实战使用指南

## 策略概况

**策略ID**: 272  
**策略名称**: 新能源动量策略 v1.0  
**策略类型**: 动量策略（momentum）  
**适用标的**: 高波动成长股（新能源、科技、医药）

## 买入信号触发条件（满足任一即可）

### 条件1：RSI超卖反弹
- RSI < 50（未过热）
- 连续2日上涨（价格突破下降趋势）

### 条件2：放量突破
- 突破5日均线1%以上
- 成交量放大30%以上（资金介入）

### 条件3：MACD金叉
- MACD在零轴上方（多头趋势）
- MACD上升（动能增强）

## 卖出信号触发条件

1. **硬止损**：亏损达到 -3%
2. **追踪止盈**：盈利>5%后，从最高点回撤1.5%
3. **硬止盈**：盈利达到 +8%
4. **时间止损**：持仓超过12天

## 冷却期机制

- 止损卖出后：等待3天
- 止盈卖出后：等待2天
- 避免追涨杀跌，控制情绪化交易

## 实战使用方法

### 1. 回测验证（首次使用必做）

```bash
# 通过 API 回测
curl -X POST http://127.0.0.1:5001/api/backtest \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "300750.SZ",
    "strategy_id": 272,
    "start_date": "2025-01-01",
    "end_date": "2026-06-04"
  }'
```

或使用 TypeScript 工具：

```typescript
indicator_backtest({
  indicator_id: 272,
  symbol: "300750.SZ",
  start_date: "2025-01-01",
  end_date: "2026-06-04"
})
```

**关键指标解读**：
- 胜率 > 60% → 策略有效
- 夏普比率 > 1.0 → 风险收益比合理
- 最大回撤 < 20% → 风险可控

### 2. 批量扫描买点（每日收盘后）

```typescript
// 扫描新能源+科技板块
opportunity_scan({
  symbols: [
    "300750.SZ",  // 宁德时代
    "002594.SZ",  // 比亚迪
    "688981.SH",  // 中芯国际
    "600036.SH",  // 招商银行
    "300059.SZ",  // 东方财富
    "300124.SZ",  // 汇川技术
    "603259.SH",  // 药明康德
    "688599.SH"   // 天合光能
  ],
  limit: 10,
  technical: ["rsi_oversold", "macd_golden_cross"],
  enable_dynamic_weights: true
})
```

**结果排序逻辑**：
- 综合评分（technical 50% + fundamental 30% + capital 20%）
- 风险等级筛选
- 自动推荐 Top 5

### 3. 单股实时查询（盘中）

```typescript
// 查看特定股票当前是否符合买入条件
strategy_execute({
  action: "single",
  symbol: "300750.SZ",
  strategy: "272"
})
```

**返回内容**：
- 当前是否有买入信号
- 风险评估（风险等级、止损价、目标价）
- 持仓建议（仓位比例）

### 4. 构建动态股票池（自动化）

```typescript
// 创建272策略专用股票池
pool_manage({
  action: "create",
  name: "272策略-新能源成长股池",
  filter_template: {
    rsi_oversold: true,
    min_volume_ratio: 1.3,
    sectors: ["新能源", "半导体", "医药"],
    min_quality_score: 70
  }
})

// 每日自动刷新，捕捉新机会
pool_manage({
  action: "refresh",
  pool_id: 1
})
```

## 风险控制要点

### 1. 仓位管理
- 单只股票：不超过总资金的 10%
- 同板块股票：不超过总资金的 30%
- 留足止损空间：3% × 仓位 = 单笔最大损失

### 2. 市场环境判断
```typescript
// 先判断市场风格
market_style_detect({
  lookback_days: 60
})
```

**适用市场**：
- ✅ 牛市/震荡市上沿 → 效果最佳
- ⚠️ 震荡市 → 降低仓位
- ❌ 熊市/单边下跌 → 暂停使用

### 3. 冷却期严格执行
- 不要在冷却期内重复买入同一只股票
- 用 `strategy_status` 工具查看冷却期状态

## 常见问题

### Q1: 为什么回测效果好，实盘不行？
**可能原因**：
- 市场环境变化（牛市策略在熊市失效）
- 滑点和手续费影响（回测未考虑）
- 情绪化操作（未严格执行冷却期）

**解决方案**：
- 先用小仓位测试1-2周
- 记录每笔交易，分析偏差
- 使用 `signal.test_record` 工具追踪实盘表现

### Q2: 如何判断当前是否在冷却期？
```typescript
// 查询策略状态
strategy_status()
```

### Q3: 可以同时用多个策略吗？
可以，但要注意：
- 不同策略的信号可能冲突
- 建议用 `strategy_combo_backtest` 测试组合效果
- Portfolio 模式：按权重分配资金（如 272策略 30% + 其他策略 70%）

### Q4: 买点信号有效期多久？
- **技术面信号**（RSI、MACD）：1-2天
- **放量突破信号**：当天最佳，次日可能高开
- **建议**：收盘后发现信号 → 次日集合竞价挂单

## 进阶技巧

### 1. 因子有效性分析
```typescript
// 分析272策略使用的因子是否仍然有效
factor_analyze({
  factors: ["rsi14", "macd", "volume_ratio"],
  symbols: ["300750.SZ", "002594.SZ"],
  start_date: "2025-01-01",
  end_date: "2026-06-04"
})
```

**关键指标**：
- IC（信息系数）> 0.05 → 因子有效
- 覆盖率 > 90% → 数据质量好
- 单调性 > 80% → 因子分层收益递增

### 2. 策略优化
如果272策略表现不佳，可以调整参数：

```python
# 修改止损阈值（-3% → -2%）
if pnl <= -0.02:  # 原来是 -0.03
    df.iloc[i, df.columns.get_loc("sell")] = True
```

使用 `strategy_write` 工具更新代码：

```typescript
strategy_write({
  indicator_id: 272,
  name: "新能源动量策略 v1.1",
  code: "...",  // 修改后的代码
  description: "优化止损阈值为-2%"
})
```

### 3. 组合回测
测试272策略与其他策略的组合效果：

```typescript
strategy_combo_backtest({
  mode: "portfolio",
  strategies: [
    { strategy_id: 272, weight: 0.4 },   // 272策略 40%
    { strategy_id: 53, weight: 0.6 }     // 多因子波段策略 60%
  ],
  symbols: ["300750.SZ", "002594.SZ"],
  start_date: "2025-01-01",
  end_date: "2026-06-04"
})
```

## 参考文档

- 策略循环闭合：`docs/superpowers/specs/2026-05-29-strategy-loop-p2-completion.md`
- 因子库参考：`docs/FACTOR_LIBRARY_REFERENCE.md`
- 工具使用指南：`docs/tools/tool-development-guide.md`
