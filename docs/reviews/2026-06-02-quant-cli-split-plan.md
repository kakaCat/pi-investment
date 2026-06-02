# quant-cli-tool 完全拆分执行计划

**执行时间**: 2026-06-02  
**任务**: 从 quant-cli-tool.ts 中移除已拆分的51个命令  
**风险等级**: 🔴 高（破坏性操作）

---

## 执行步骤

### 阶段1: 备份和分析（5分钟）

1. ✅ 创建备份文件
2. ✅ 统计要移除的命令数量：51个
3. ✅ 分析依赖关系

### 阶段2: 移除命令定义（15分钟）

需要移除的命令（51个）：

**market-cli-tool (12个)**:
- market.overview, market.index_history, market.sectors
- market.concept_stocks, market.concepts, market.macro
- market.north_flow, market.sector_flow, market.margin
- market.news, market.hot_stocks, market.sentiment

**stock-cli-tool (5个)**:
- stock.batch_quotes, stock.list, stock.score
- stock.screen, stock.technical

**financial-cli-tool (7个)**:
- financial.indicators, financial.valuation, financial.pe_percentile
- financial.income_statement, financial.cash_flow
- financial.hk_financials, financial.hk_analysis

**sentiment-cli-tool (8个)**:
- sentiment.stock_fund_flow, sentiment.lhb, sentiment.insider_trades
- sentiment.fund_holdings, sentiment.top_fund_stocks
- sentiment.top_holders, sentiment.holder_changes, sentiment.margin_data

**analysis-cli-tool (7个)**:
- analysis.technical, analysis.price_action, analysis.candlestick
- analysis.buy_range, analysis.quality, analysis.exit_plan, analysis.peers

**signal-cli-tool (4个)**:
- signal.list, signal.generate, signal.arbitrate, signal.statistics

**backtest-cli-tool (3个)**:
- backtest.run, backtest.results, backtest.strategy

**watchlist-cli-tool (5个)**:
- watchlist.list, watchlist.add, watchlist.remove
- watchlist.update, watchlist.groups

### 阶段3: 更新工具描述（5分钟）

更新 quant-cli-tool 的 description，说明部分命令已迁移到独立工具。

### 阶段4: 更新帮助文档（5分钟）

更新命令列表，移除已拆分的命令引用。

### 阶段5: 测试验证（10分钟）

1. 编译检查
2. 验证剩余命令仍可用
3. 验证新工具可用

---

## 预期结果

**移除前**:
- 文件大小: 1,472行 (58KB)
- 命令总数: ~100个

**移除后**:
- 文件大小: 预计~800行 (30KB)
- 命令总数: ~49个
- 减少: **-45%**

---

## 风险控制

### 备份策略
✅ 创建 `quant-cli-tool.ts.backup`

### 回滚方案
如果出现问题：
```bash
mv quant-cli-tool.ts.backup quant-cli-tool.ts
```

### 测试清单
- [ ] 编译通过
- [ ] 剩余命令可执行
- [ ] 新CLI工具可用
- [ ] 工具注册正确

---

## 开始执行？

**准备就绪，等待确认执行。**
