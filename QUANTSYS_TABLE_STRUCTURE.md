# quantsys-v2 量化交易表结构汇总

**数据库**: quant_investment
**Schema**: quant
**总表数**: 68张

---

## 📊 核心交易记录表（8张）

### 1. 模拟交易系统（3张）

| 表名 | 说明 | 用途 | 记录数 |
|------|------|------|--------|
| **simulation_account** | 模拟账户表 | 账户基本信息、总资产、收益率 | 1条 |
| **simulation_positions** | 模拟持仓表 | 当前持仓明细 | 4条（应该8条）|
| **simulation_trades** | 模拟交易记录表 | 所有买卖交易历史 | 23条 |

**关系**:
```
simulation_account (1)
    ├── simulation_positions (N) - 持仓
    └── simulation_trades (N) - 交易记录
```

---

### 2. 实盘交易系统（5张）

| 表名 | 说明 | 用途 |
|------|------|------|
| **accounts** | 账户表 | 多账户管理 |
| **positions** | 当前持仓表 | 实时持仓状态 |
| **orders** | 订单表 | 交易订单全生命周期 |
| **trades** | 成交记录表 | 已成交的买卖记录 |
| **position_history** | 持仓变动历史表 | 每次加仓/减仓记录 |

**关系**:
```
accounts (1)
    ├── positions (N) - 当前持仓
    ├── orders (N) - 订单
    │   └── trades (N) - 成交记录
    └── position_history (N) - 持仓历史
```

---

## 📈 策略与信号表（9张）

### 3. 策略配置（4张）

| 表名 | 说明 |
|------|------|
| **strategy_configs** | 策略配置表：参数、代码和元数据 |
| **strategy_metadata** | 策略元数据表：策略类型注册 |
| **strategy_weight_config** | 策略权重配置表 |
| **strategy_circuit_breaker** | 策略熔断表：连续亏损自动停用 |

### 4. 信号生成与执行（5张）

| 表名 | 说明 |
|------|------|
| **signals** | 策略信号表：策略引擎生成的交易信号 |
| **trading_signals** | 交易信号表：经风控裁决后的最终信号 |
| **signal_executions** | 信号执行记录表：信号到订单的追踪 |
| **signal_execution_logs** | 信号执行日志表：批量执行摘要 |
| **signal_factors** | 信号因子明细表：记录触发因子 |

**流程**:
```
策略 → signals → 风控 → trading_signals → signal_executions → orders → trades
```

---

## 💰 账户与资金表（3张）

| 表名 | 说明 |
|------|------|
| **account_balance** | 账户余额快照表：每日资产记录 |
| **daily_quotes** | 日行情快照表：每日收盘Snapshot |
| **portfolio_holdings** | 组合持仓表：TypeScript Agent侧持仓快照 |

---

## 🎯 策略评估表（4张）

| 表名 | 说明 |
|------|------|
| **strategy_performance** | 策略实盘表现表：信号→订单→盈亏闭环 |
| **strategy_stock_matching** | 策略-股票匹配表：回测结果 |
| **strategy_validation_reports** | 策略批量验证报告表 |
| **backtest_results** | 回测结果表：策略回测完整输出 |

---

## 🔍 风控表（4张）

| 表名 | 说明 |
|------|------|
| **risk_config** | 风控配置表：参数化风控规则 |
| **risk_metrics** | 风险指标表：个体/组合风险度量 |
| **stop_loss_rules** | 止损规则表：个股止损/移动止损 |
| **approval_rules** | 审批规则表：交易审批自动化规则 |

---

## 📊 市场数据表（6张）

### 5. K线数据（3张）

| 表名 | 说明 | 用途 |
|------|------|------|
| **daily_klines** | 日K线数据表 | 前复权OHLCV数据 |
| **minute_klines** | 分钟K线数据表 | 日内短线分析 |
| **raw_klines** | 原始K线数据表 | 未清洗的原始数据 |

### 6. 基础数据（3张）

| 表名 | 说明 |
|------|------|
| **stocks** | 股票基本信息表 |
| **trading_calendar** | 交易日历表：A股交易日标记 |
| **stock_fund_flow** | 股票资金流向数据（缓存表）|

---

## 🤖 机器学习表（3张）

| 表名 | 说明 |
|------|------|
| **ml_models** | ML模型注册表：XGBoost/LightGBM训练记录 |
| **ml_predictions** | 模型预测记录表：每次predict结果 |
| **factors** | 因子值表（v1 legacy）|
| **factor_values** | 因子值表（v2）|

---

## 🎮 Agent与自动化表（7张）

| 表名 | 说明 |
|------|------|
| **agent_decisions** | Agent决策日志：记录决策上下文 |
| **agent_knowledge** | Agent知识库：经验规则和模式 |
| **agent_logs** | Agent操作日志表 |
| **automation_tasks** | 自动化任务定义表 |
| **automation_runs** | 自动化任务执行历史 |
| **automation_logs** | 自动化任务执行日志 |
| **data_snapshots** | 数据快照表：Agent调用数据缓存 |

---

## 📅 任务调度表（5张）

| 表名 | 说明 |
|------|------|
| **scheduler_tasks** | 定时任务定义表 |
| **scheduler_runs** | 定时任务执行记录表 |
| **scheduler_task_configs** | 定时任务配置表 |
| **apscheduler_jobs** | APScheduler作业表 |
| **task_dependencies** | 任务依赖关系 |
| **jobs** | 异步任务表：后台数据处理任务 |

---

## 🎲 博弈与风格表（7张）

| 表名 | 说明 |
|------|------|
| **stock_pools** | 股票池管理表：静态池和动态池 |
| **pool_change_log** | 池子变更日志 |
| **pool_game_metrics** | 池子博弈指标 |
| **pool_health_history** | 池子健康度历史 |
| **market_style_state** | 市场风格状态表 |
| **opponent_behavior_snapshot** | 对手行为快照 |
| **manipulation_events** | 操纵事件记录 |

---

## 📊 财务数据表（3张）

| 表名 | 说明 |
|------|------|
| **income_statements** | 利润表：季度营收/利润/EPS |
| **balance_sheets** | 资产负债表：资产/负债/权益 |
| **cash_flows** | 现金流量表：经营/投资/筹资CF |

---

## 🔧 其他辅助表（4张）

| 表名 | 说明 |
|------|------|
| **watchlist** | 自选股表 |
| **condition_monitors** | 条件监控器配置 |
| **signal_test_log** | 信号测试日志表 |
| **schema_migrations** | 数据库迁移版本记录 |

---

## 🎯 V13模拟交易使用的表

### 当前使用（3张）

```
1. simulation_account
   ├─ 存储：账户余额、总资产、收益率
   └─ 问题：total_value计算错误

2. simulation_positions
   ├─ 存储：当前持仓明细
   └─ 问题：缺少6/22建仓的4只股票

3. simulation_trades
   ├─ 存储：所有交易记录
   └─ 问题：300342重复卖出3次
```

### 应该增加使用（可选）

```
4. simulation_daily_reports
   └─ 用途：每日账户快照，绘制收益曲线

5. account_balance
   └─ 用途：每日资产记录

6. risk_metrics
   └─ 用途：风险指标监控

7. strategy_performance
   └─ 用途：策略表现追踪
```

---

## 📋 表关系图（核心）

```
┌─────────────────────────────────────────────────────────────┐
│                    模拟交易系统                               │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  simulation_account (账户)                                    │
│      ├── cash: 现金                                           │
│      ├── total_value: 总资产 ❌ 计算错误                      │
│      ├── cumulative_return: 累计收益率                        │
│      └── max_drawdown: 最大回撤                               │
│           │                                                   │
│           ├─► simulation_positions (持仓) ⚠️ 数据不完整       │
│           │      ├── symbol: 股票代码                         │
│           │      ├── shares: 持仓数量                         │
│           │      ├── avg_price: 成本价                        │
│           │      └── market_value: 市值                       │
│           │                                                   │
│           └─► simulation_trades (交易记录) ✅ 完整            │
│                  ├── trade_date: 交易日期                     │
│                  ├── symbol: 股票代码                         │
│                  ├── action: BUY/SELL                         │
│                  ├── shares: 数量                             │
│                  ├── filled_price: 成交价                     │
│                  └── total_revenue: 收入支出                  │
│                                                               │
└─────────────────────────────────────────────────────────────┘

           ↓ 应该使用但未使用

┌─────────────────────────────────────────────────────────────┐
│              其他相关表（建议集成）                            │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  account_balance (账户余额快照)                               │
│      └── 每日记录总资产，用于绘制收益曲线                     │
│                                                               │
│  strategy_performance (策略表现)                              │
│      └── 追踪V13策略的实盘表现                                │
│                                                               │
│  risk_metrics (风险指标)                                      │
│      └── 监控夏普比率、最大回撤等                             │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔍 数据流向

```
V13策略运行
    ↓
计算因子 → factors / factor_values
    ↓
模型预测 → ml_predictions
    ↓
生成信号 → signals
    ↓
执行交易 → simulation_trades ✅
    ↓
更新持仓 → simulation_positions ⚠️（不完整）
    ↓
计算账户 → simulation_account ❌（错误）
```

---

## 📊 统计摘要

| 类别 | 表数量 | 主要用途 |
|------|--------|----------|
| **交易记录** | 8张 | 模拟交易、实盘交易 |
| **策略信号** | 9张 | 策略配置、信号生成执行 |
| **账户资金** | 3张 | 账户余额、持仓快照 |
| **策略评估** | 4张 | 回测、实盘表现 |
| **风控** | 4张 | 风险配置、止损规则 |
| **市场数据** | 6张 | K线、基础数据 |
| **机器学习** | 3张 | 模型、预测、因子 |
| **Agent自动化** | 7张 | 决策、知识、任务 |
| **任务调度** | 5张 | 定时任务、异步任务 |
| **博弈风格** | 7张 | 股票池、市场风格 |
| **财务数据** | 3张 | 利润表、资产负债表 |
| **其他** | 9张 | 自选股、监控、日志 |
| **总计** | **68张** | - |

---

## ✅ 核心结论

### V13模拟交易当前使用

**仅使用3张表**：
- simulation_account
- simulation_positions
- simulation_trades

**存在的问题**：
1. ❌ simulation_account.total_value 计算错误
2. ⚠️ simulation_positions 数据不完整（缺4只股票）
3. ❌ simulation_trades 有重复记录（300342×4）

**建议改进**：
1. 增加使用 account_balance（每日快照）
2. 增加使用 strategy_performance（策略追踪）
3. 修复数据同步逻辑
4. 实现从 simulation_trades 计算真实持仓的逻辑

---

**报告生成**: Claude (Kiro)  
**生成时间**: 2026-06-29 13:15
