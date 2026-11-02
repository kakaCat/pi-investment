# 投资评价与业绩归因数据契约（A 项第一期）

- 状态：实施契约 v1（2026-11-02）
- 范围：A 股模拟账户的只读评价；调用方必须显式指定账户，不在任务或文档中写死投资账户
- 不改变：信号分级、交易策略、仓位规则、订单撮合与历史成交

## 1. 目标与三个不可混用的口径

### 1.1 账户经济口径

回答账户实际上发生了什么。包含全部成交、费用、持仓市值、外部出入金和资金成本；工程测试造成的盈亏也计入账户经济结果，单列 `engineering_test` 归因，不得从实际经济结果中删除。

### 1.2 投资能力口径

回答投资信号与交易回合是否有效。排除明确标记的 `engineering_test`、无法核验的混合回合与数据不完整回合；输出样本数、胜率、平均盈亏和期望值。排除必须逐条可见，禁止静默过滤。

### 1.3 全局未归属信号口径

`quant.signal_tracking` 当前没有账户、策略回合或决策关联字段。其统计只能标记为 `global_unassigned`，不得自称任何账户的胜率。历史独立分组只能是估算，不能冒充已证明的独立样本。

## 2. 事实源与关联优先级

| 事实 | 首选来源 | 关键字段 |
|---|---|---|
| 成交、费用、实现盈亏 | `quant.simulation_trades` | `id/account_name/order_id/symbol/action/shares/filled_price/realized_pnl/reason/trade_time` |
| 委托、信号关联 | `quant.simulation_order` | `id/signal_id/strategy_name/submitted_by/decision_price/decision_at` |
| 盘前挂单执行质量 | `quant.simulation_pending_orders` | `executed_trade_id/decision_price/decision_at/fill_price/slippage_bps` |
| 当前持仓与浮动盈亏 | `quant.simulation_positions` | `account_name/symbol/shares_total/avg_cost/profit_total` |
| 净值与权益暴露 | `quant.simulation_equity_snapshot` | `account_name/snapshot_date/cash/position_value/total_value/is_synthetic` |
| 外部出入金 | `quant.simulation_cash_flow` | 仅 `deposit/withdraw`；买卖和费用流水不得重复当外部流 |
| 决策与评分 | `quant.agent_decisions` | `decision_id/context.account/parameters/evaluation_result/score` |
| 信号表现 | `quant.signal_tracking` | `id/signal_date/symbol/grade/source/price/return_5d/10d/20d` |

关联优先级：成交 `order_id` → 委托 `id`；成交 `id` → 挂单 `executed_trade_id`。无法关联的记录保留并标记 `unlinked`，禁止按“同股同价”静默猜测关联。

## 3. 工程测试识别

第一期采用保守、可审计的显式标记，只覆盖历史上已有证据的工程单，例如 `测试 submitted_by`、`最终验证 submitted_by`、`工程测试单`。普通“策略验证”“回测验证”等投资语言不得因此被排除。

未来记录可使用精确元数据 `submitted_by=engineering_test|test_only` 或 `strategy_name=engineering_test|test_only`；评价层按 `explicit_metadata` 隔离，不依赖模糊文本。它不改变交易权限，真正防止测试单影响资金与持仓仍需独立测试账户/写路径硬隔离。

输出每个被排除成交的 `trade_id/symbol/rule/reason`。该分类只用于评价，不是新增工程单授权机制。

## 4. 独立交易回合

同一账户、同一标的按成交时间排序：

1. 从空仓后的首笔 BUY 开始回合；
2. 加仓、部分减仓属于同一回合；
3. 净持仓回到 0 时关闭回合；
4. 回合实现盈亏为回合内 SELL 的 `realized_pnl` 合计；
5. 没有任何已核验开仓历史的 SELL 进入 `unmatched`，不得凭空构造回合收益；
6. 回合内若混有工程与投资成交，标为 `mixed` 并排除出投资能力统计，保留在经济统计与数据质量清单中。

胜率、平均盈亏和期望值以关闭回合为样本，不以 SELL 笔数冒充独立样本。开放回合只披露，不参与关闭回合胜率。

## 5. 全局信号分组估算

历史信号按 `symbol + source` 排序，间隔超过 20 个自然日才开启新分组；每组取首条作为代表样本。该规则只用于降低连续重复信号的重复计数，输出：

- `independence_method = symbol_source_20_calendar_day_episode`
- `independence_status = estimated`
- 原始记录数与估算分组数

后续新增信号必须携带账户、决策和回合 ID，才能升级为可核验归属与独立样本。

## 6. 指标公式

### 6.1 回合评价

- `win_rate = 盈利关闭回合数 / 有效关闭回合数`
- `expectancy = 有效关闭回合实现盈亏的算术平均`
- `average_win / average_loss` 分别只对盈利、亏损回合求均值
- 样本为 0 时返回 `null` 与 `insufficient_sample`，禁止返回 0% 或 100%

### 6.2 时间加权收益（TWR）

相邻净值快照区间：

`r_i = (V_i - V_(i-1) - F_i) / V_(i-1)`

其中 `F_i` 为两快照之间的外部净流入（deposit 为正、withdraw 为负）。各区间按 `(1+r_i)` 连乘。分母非正、净值缺口或外部流不完整时标记降级，不输出貌似精确的结果。

历史回填可能使流水 `created_at` 晚于资金在净值中的实际生效日。系统先以流水 `balance_after` 对账快照 `cash`，取不晚于流水日期的最早匹配快照作为生效日；期初已含该余额的入金不重复计为本期外部流。无法匹配时才回退流水日期，并标记 `created_date_fallback_unverified`；若同时出现极端收益区间，TWR 返回降级而非输出错误数字。逐笔对齐过程通过 `external_flow_alignment` 公开。

### 6.3 资金成本

默认年化费率 2%，按实际自然日 `/365` 计提。快照区间以两端总资产的均值作为资本代理；最后快照至报告截止日使用最后总资产代理：

`cost_i = capital_proxy_i × annual_rate × days_i / 365`

该口径是估算，必须返回 `capital_cost_method`、起止日期、年费率和最后净值时点。账户经济损益：

`economic_pnl = end_nav - start_nav - external_net_flow - funding_cost`

### 6.4 当前浮动盈亏

当前持仓浮动盈亏来自持仓表，只放入账户当前状态，不回填到历史关闭回合，不用于投资能力胜率。

## 7. 数据质量与诚实降级

报告必须包含：

- 各事实源时点与记录数；
- 工程排除清单、混合/未匹配回合清单；
- 委托、挂单和信号关联覆盖率；
- 净值合成快照数、缺口和最后净值日期；
- 信号无账户字段及独立分组估算警告；
- 评分样本按账户过滤后的数量；
- 任一聚合的样本数、费用口径与数据范围。

## 8. 第一期 API 与验收

只读接口：`GET /api/evaluation/report?account_name=<调用方账户>&start_date=YYYY-MM-DD&end_date=YYYY-MM-DD&annual_cost_rate=0.02`。

验收最低要求：

1. 部分减仓只形成一个交易回合；
2. 工程亏损计入账户经济结果、排除出投资能力统计；
3. 外部入金不计入投资收益；
4. 无样本返回 `null/insufficient_sample`；
5. 信号报告不能冒充账户业绩；
6. 所有胜率同时带样本数、平均盈亏、数据范围和口径；
7. 报告接口不写库、不触发交易、不修改现有评分。
