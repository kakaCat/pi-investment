# 工具选择决策树

快速找到适合任务的工具。

---

## 🎯 决策流程

```
开始
  ↓
需要什么类型的任务？
  ├─ 数据获取 → 跳转到 [数据获取决策树](#数据获取)
  ├─ 策略相关 → 跳转到 [策略决策树](#策略管理)
  ├─ 分析选股 → 跳转到 [分析决策树](#分析和选股)
  ├─ 回测验证 → 跳转到 [回测决策树](#回测和验证)
  ├─ 模型训练 → 跳转到 [模型决策树](#模型训练)
  ├─ 快速查询 → 跳转到 [CLI工具决策树](#cli-快速查询)
  └─ 系统操作 → 跳转到 [元工具决策树](#agent-元工具)
```

---

## 📊 数据获取

```
需要什么数据？
  ├─ 股票基本信息/实时价格/新闻/公告
  │   → data_fetch_stock
  │   参数：symbol, fields=["info", "price", "news", "announcements"]
  │   支持实时行情（延迟<3秒）
  │
  ├─ K线数据（日线/周线/月线）
  │   → data_fetch_kline
  │   参数：symbol, period="daily", start_date, end_date
  │
  ├─ 财务数据（利润表/资产负债表/现金流）
  │   → data_fetch_financial
  │   参数：symbol, report_type, years
  │
  └─ 分红数据
      ├─ 单股历史分红 → data_fetch_dividend (mode="single")
      ├─ 高股息筛选 → data_fetch_dividend (mode="screen")
      └─ 分红日历 → data_fetch_dividend (mode="calendar")
```

**选择建议**:
- ✅ **优先使用独立工具** (data_fetch_*) - 类型安全，文档完整
- ⚠️ 仅支持A股，港股暂不支持

---

## 🎲 策略管理

```
策略相关任务？
  ├─ 查看现有策略
  │   ├─ 列出所有策略 → strategy_list
  │   └─ 查看策略详情 → strategy_detail (strategy_id)
  │
  ├─ 创建/编辑策略
  │   ├─ 创建新策略 → strategy_create (name, description)
  │   └─ 编写策略代码 → strategy_write (strategy_id, code)
  │
  ├─ 执行策略
  │   ├─ 单股执行（详细信号） → strategy_execute (action="single", symbol, strategy)
  │   ├─ 批量执行（汇总统计） → strategy_execute (action="batch", symbols, strategy)
  │   └─ 完整流水线 → strategy_execute (action="pipeline", symbols, strategy)
  │
  ├─ 优化和验证
  │   ├─ 参数优化 → strategy_optimize (strategy_id, param_ranges)
  │   └─ 批量验证 → strategy_batch_validate (strategy_ids, symbols, start_date, end_date)
  │
  └─ 运行状态
      └─ 查询运行状态 → strategy_status
```

**关键区别**:
- `strategy_execute` = **实时执行**，支持三种模式
- `strategy_batch_validate` = **历史回测**，批量验证多个策略
- `strategy_optimize` = **参数优化**，网格搜索最优参数

---

## 🔍 分析和选股

```
分析类型？
  ├─ 投资机会扫描
  │   → opportunity_scan
  │   多维评分（技术+基本面+资金），返回综合评分排名
  │
  ├─ 因子分析
  │   ├─ 计算因子 → factor_calculate (symbols, factors)
  │   └─ 分析因子有效性 → factor_analyze (factor_name, ic_analysis=true)
  │
  ├─ 波段分析
  │   → analysis_swing_points (symbol, zigzag_threshold)
  │   ZigZag算法识别买卖点
  │
  └─ 股票池管理
      ├─ 筛选建池 → pool_manage (action="scan_create", filter_template)
      ├─ 查看池子 → pool_manage (action="list" | "get")
      ├─ 更新池子 → pool_manage (action="update" | "refresh")
      └─ 多策略验证 → pool_validate (pool_id, strategy_ids)
```

**使用场景**:
- **快速扫描** → `opportunity_scan` (400只股票，<0.2秒)
- **深度分析** → `factor_calculate` + `factor_analyze`
- **构建股票池** → `pool_manage` (scan_create) + `pool_validate`

---

## 📈 回测和验证

```
回测类型？
  ├─ 单策略回测
  │   → backtest_cli (command="backtest.run", strategy_id, start_date, end_date)
  │
  ├─ 组合策略回测（新功能 2026-06-02）
  │   → strategy_combo_backtest
  │   三种模式：
  │   ├─ Portfolio（仓位分配）: weights=[0.3, 0.7]
  │   ├─ Ensemble（信号融合）: fusion_method="weighted"
  │   └─ Pipeline（流程编排）: stages=["selection", "timing", "risk_control"]
  │
  ├─ 股票池验证
  │   → pool_validate (pool_id, strategy_ids)
  │   对池内所有股票 × 多个策略批量回测，按评分排名
  │
  └─ 绩效分析
      → quant_cli (command="performance.analyze", strategy_id, days)
```

**性能参考**:
- 单策略回测：1股票 × 1年数据 ≈ 1-2秒
- 组合回测：3策略 × 50股票 ≈ 30秒
- 股票池验证：1池子(30股) × 5策略 ≈ 3-5分钟

---

## 🤖 模型训练

```
模型相关任务？
  ├─ 训练模型
  │   → model_train (model_type, training_data, hyperparams)
  │
  ├─ 模型预测
  │   → model_predict (model_id, input_data)
  │
  ├─ 评估模型
  │   → model_evaluate (model_id, test_data)
  │
  ├─ 监控漂移
  │   → model_monitor (model_id, window_days)
  │
  └─ 列出模型
      → model_list
```

**注意**:
- 模型工具需要 quantsys-v2 服务运行（端口 5001）
- 训练数据需要事先准备好

---

## ⚡ CLI 快速查询

```
查询类型？
  ├─ 市场数据 → market_cli
  │   12个命令：market.overview, market.sectors, market.hot_stocks 等
  │
  ├─ 个股数据 → stock_cli
  │   5个命令：stock.quote, stock.list, stock.score 等
  │
  ├─ 财务数据 → financial_cli
  │   7个命令：financial.indicators, financial.valuation 等
  │
  ├─ 市场情绪 → sentiment_cli
  │   8个命令：sentiment.lhb, sentiment.fund_holdings 等
  │
  ├─ 股票分析 → analysis_cli
  │   7个命令：analysis.technical, analysis.quality 等
  │
  ├─ 信号测试 → signal_cli
  │   4个命令：signal.list, signal.generate 等
  │
  ├─ 回测 → backtest_cli
  │   3个命令：backtest.run, backtest.results 等
  │
  └─ 自选股 → watchlist_cli
      5个命令：watchlist.list, watchlist.add 等
```

**使用建议**:
- CLI工具适合**快速查询**和**批量操作**
- 独立工具适合**复杂逻辑**和**类型安全**要求高的场景

---

## 🛠️ Agent 元工具

```
系统操作类型？
  ├─ 任务管理
  │   ├─ 创建任务 → task_create
  │   ├─ 更新任务 → task_update
  │   ├─ 列出任务 → task_list
  │   └─ 异步执行 → task_execute_async
  │
  ├─ 记忆和经验
  │   ├─ 写入记忆 → memory_write
  │   ├─ 搜索记忆 → memory_search
  │   ├─ 查询经验 → experience_query
  │   └─ 写入经验 → experience_write
  │
  ├─ 规划和反思
  │   ├─ 制定计划 → plan
  │   ├─ 澄清需求 → clarify
  │   └─ 反思总结 → reflect
  │
  └─ 系统运维
      ├─ 重启Agent → restart_agent
      ├─ 后端控制 → backend_control (start/stop/restart/status)
      ├─ 委托Claude Code → claude_code
      └─ 进化优化 → evolution_run
```

---

## 🚫 已移除功能

以下功能已移除，请使用替代方案：

### 港股相关（2026-06-02移除）
- ❌ `hk.market_overview`
- ❌ `hk.south_flow`
- ❌ `hk.technical`
- ❌ `hk.hot_rank`
- **原因**: v1 quantsys废弃，v2无港股数据
- **替代**: 暂无，港股功能不在当前支持范围

### 组合和交易（2026-05-27移除）
- ❌ `portfolio_rebalance`
- ❌ `trade_manage_orders`
- **原因**: 依赖已废弃的本地服务
- **替代**: 使用 quantsys-v2 的 API 端点

---

## 💡 最佳实践

### 1. 工具选择原则

**独立工具 vs CLI工具**:
```
使用独立工具 (data_fetch_*, strategy_*, model_*)，如果：
  ✓ 需要类型安全和参数验证
  ✓ 需要详细的错误提示
  ✓ 任务逻辑复杂

使用CLI工具 (*_cli)，如果：
  ✓ 快速查询
  ✓ 批量操作
  ✓ 命令行风格交互
```

### 2. 性能优化

**数据获取**:
- 批量查询优于循环单次查询
- 使用 `data_fetch_stock` 的 `fields` 参数只获取需要的字段
- 重复查询考虑缓存（TTL=60s）

**回测和验证**:
- 小范围测试（10股 × 1策略）验证逻辑
- 大范围验证（100股 × 5策略）使用 `pool_validate`
- 组合策略优先用 Portfolio 模式（最快）

### 3. 错误处理

所有工具都集成了统一的错误处理：
- 参数验证错误 → 自动提示正确格式
- 后端服务错误 → 自动重试或降级
- 缺少必填参数 → 自动附加可用选项（如策略列表）

---

## 📞 需要帮助？

- 📖 [工具开发指南](./tool-development-guide.md)
- 📊 [工具参考文档](./tool-reference/)
- 🔧 [优化历史](../reviews/)
- 🐛 [已知问题](../reviews/2026-06-02-agent-tools-optimization-analysis.md#三发现的问题)

---

**更新日期**: 2026-06-02
