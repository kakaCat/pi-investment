# 多账户股票账户域设计（多账户隔离方案）

- 日期：2026-07-19
- 状态：已确认（用户逐段审批通过）
- 范围：quantsys-v2（后端）、agent-ts（AI 员工）、web-frontend（监控面板）

## 1. 背景与问题

v2 底层有多账户机制（`simulation_*` 表按 `account_name` 隔离），但上层四条链路把数据全部漏斗进公共 `default` 账户，且服务端无任何强制：

1. v13 策略配置 `account_name: "default"`（v14/v15 有独立账户）→ v13 的 19 笔交易混入 default
2. agent-ts 全链路不传账户标识，portfolio 工具硬编码查询 `accounts/default`
3. v2 API 层把 `'default'` 当兜底（simulation 路由、orders.py 的 `'Default Account'` 硬编码）
4. 零认证零授权（JWT 是 demo，无路由启用鉴权）
5. 附带问题：agent 的 `POST /api/portfolio/trade` 在 v2 不存在（交易链路断裂）；存在三套并行账户体系（`simulation_*`、`accounts/positions`、risk balance）互不相通

## 2. 已确认的决策

| 决策点 | 结论 |
|--------|------|
| 账户语义 | 按策略/用途维度隔离（v13_simulation、v14_simulation…），非多用户 |
| 强制程度 | 仅账户显式化，不做真实 JWT 认证 |
| 体系 | 统一到 `simulation_*` 体系；`accounts/positions` 旧表只读保留 |
| Agent 角色 | 代管策略账户，交易工具必须显式传 account_name；修复断裂的交易链路 |
| 历史数据 | `default` 改名为 `v13_simulation`（三表），补建 v15_simulation |
| Web 交互 | 统一模拟交易页 + 账户切换器；V14Trading 页下线 |
| 域模型 | 参考成熟券商模型：委托/成交分离、资金流水、持仓可用/总量分离 |
| 方案 | 方案 A：账户注册表 + 显式参数贯穿三层 |

## 3. 账户域模型（6 张表）

```
┌─────────────────────────────────────────────────────────┐
│ simulation_account  账户主表（资金两态 + 绩效基准）        │
└───────┬─────────────────────────────────┬───────────────┘
        │ 1:N                             │ 1:N
┌───────▼──────────┐            ┌─────────▼────────────┐
│ simulation_order  │ 1:N        │ simulation_cash_flow │
│ 委托单（状态机）   ├──────────► │ 资金流水（可审计）     │
└───────┬──────────┘  fills    └──────────────────────┘
        │ 1:N
┌───────▼──────────┐            ┌──────────────────────┐
│ simulation_trade  │            │ simulation_position  │
│ 成交回报（含费用） │──────────► │ 持仓（总量/可用分离） │
└──────────────────┘  更新       └──────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ simulation_equity_snapshot  日终结算快照（账户×日期唯一） │
└─────────────────────────────────────────────────────────┘
```

### 3.1 simulation_account — 账户主表（扩充）

| 列 | 类型 | 说明 |
|------|------|------|
| `cash_available` | Numeric(15,2) | 可用资金（拆分自原 cash） |
| `cash_frozen` | Numeric(15,2) | 冻结资金（挂单占用） |
| `total_value` / `position_value` | Numeric(15,2) | 总资产 / 持仓市值 |
| `initial_capital` | Numeric(15,2) | 初始资金（绩效基准，持久化，不再反推） |
| `peak_value` / `cumulative_return` / `max_drawdown` | Numeric | 绩效指标（保留） |
| `display_name` | String(100) | 显示名，如 "V13 多因子模拟仓" |
| `strategy_name` | String(50), 可空 | 绑定策略；空 = 非策略账户 |
| `status` | String(20) | `active` / `archived`（归档只读） |

`account_name` 保持唯一键。命名规范：策略账户 `{策略名}_simulation`；非策略账户自由命名；**禁止 `default`**。

### 3.2 simulation_order — 委托单（新增）

| 列 | 说明 |
|------|------|
| `order_id` | 主键 |
| `account_name` | 所属账户 |
| `action` / `order_type` | buy/sell；market/limit |
| `symbol` / `shares` / `price_limit` | 委托内容 |
| `status` | `submitted → filled / partially_filled / cancelled / rejected` |
| `filled_shares` / `avg_filled_price` | 成交汇总 |
| `reason` | 决策理由（agent 必填，审计+学习） |
| `strategy_name` / `signal_id` | 来源策略/信号（对接已有信号追踪） |
| `created_at` / `updated_at` | 时间戳 |

MVP：市价单同一事务内立即成交（order+trade 1:1）；限价单状态机留扩展位。

### 3.3 simulation_trade — 成交回报（扩充）

| 新列 | 说明 |
|------|------|
| `order_id` | 关联委托单 |
| `transfer_fee` | 过户费（费用三项之一） |
| `realized_pnl` | 卖出已实现盈亏 = 卖出回款 − 股数×移动加权成本 − 费用 |
| `realized_pnl_rate` | 已实现盈亏率 |
| `reason` | 交易理由（冗余自 order，便于查询） |

费用模型：佣金万 2.5 最低 5 元；印花税卖出 0.05%；过户费 0.001%。买入时 realized 两列为 NULL。

### 3.4 simulation_cash_flow — 资金流水（新增）

| 列 | 说明 |
|------|------|
| `flow_type` | buy_debit / sell_credit / fee / deposit / withdraw / dividend |
| `amount` | 有符号变动额 |
| `balance_after` | 变动后余额 |
| `ref_order_id` / `ref_trade_id` | 来源单据 |
| `account_name` / `created_at` | 所属账户 / 时间 |

**不变式（服务端强制）**：任意时刻 `Σ cash_flow.amount == cash_available + cash_frozen`。所有资金变动必须经流水写入，禁止直接 UPDATE cash。这是之前"账目双重计数"bug 的根治手段。

### 3.5 simulation_position — 持仓（改造）

| 列 | 说明 |
|------|------|
| `shares_total` / `shares_available` | T+1 分离：今日买入计入 total，次日结转 available；卖出校验只看 available |
| `avg_cost` | 移动加权成本价（A股口径） |
| `current_price` / `market_value` | 市值 |
| `profit_total` / `profit_total_rate` | 持仓盈亏（浮动） |
| `profit_today` | 当日盈亏 = (current − prev_close) × shares |

唯一键 (account_name, symbol) 不变。

### 3.6 simulation_equity_snapshot — 日终结算快照（新增）

(account_name, date) 联合唯一：cash、position_value、total_value、daily_return、cumulative_return、drawdown。
写入时机：策略 daily-check、手工 trade、价格刷新任务后 upsert 当日快照。

### 3.7 盈亏口径

| 口径 | 定义 | 来源 |
|------|------|------|
| 持仓盈亏（浮动） | (现价 − 成本) × 持仓 | position.profit_total |
| 已实现盈亏 | 卖出回款 − 成本 − 费用 | trade.realized_pnl |
| 当日盈亏 | (现价 − 昨收) × 持仓 | position.profit_today |
| 账户绩效 | 净值曲线/回撤 | equity_snapshot |

### 3.8 交易事务流（一次买入）

```
校验(账户active/资金足够/风控) → 创建 order(submitted)
  → 冻结资金 cash_available→cash_frozen
  → 成交: 写 trade(费用三项) + cash_flow(buy_debit+fee)
  → 更新 position(shares_total+, 移动加权成本)
  → 解冻并扣款 → order=filled → upsert 当日 snapshot
全部在一个 DB 事务内，失败整体回滚
```

### 3.9 隔离规则（服务端强制）

1. 所有账户相关端点 `account_name` 必填，缺失 → 400 + 可用账户列表
2. 账户不存在 → 404 + 可用账户列表（复用 quant_cli 智能错误提示模式）
3. 策略配置里的 `account_name` 启动时校验必须存在于注册表，否则该策略禁用并告警
4. `archived` 账户拒绝写操作（409）

## 4. quantsys-v2 后端

### 新增端点（Flask `simulation.py`，FastAPI 侧同步 parity）

| 端点 | 说明 |
|------|------|
| `GET /api/simulation/accounts` | 账户发现：所有 active 账户 + 摘要（cash、total_value、positions_count、cumulative_return、strategy_name） |
| `POST /api/simulation/accounts` | 开户：`{account_name, display_name, initial_capital, strategy_name?}` |
| `POST /api/simulation/accounts/<name>/trade` | 手工买卖（agent 代管核心）：`{action, symbol, shares\|amount, price_limit?, reason}`；T+1 校验、风控（单票≤30%、持仓≤策略上限、总仓≤80%）、写 order/trade/cash_flow/position |

### 改造端点

- `GET /trades`、`GET /performance`、`POST /run`、`GET /accounts/<name>`：`account_name` 必填，删 `'default'` 兜底
- `POST /run` 的 `strategy_id or 'v13'` 兜底删除
- `GET /performance` 改读 `simulation_equity_snapshot`（无快照才回退重放）
- `orders.py` 的 `/api/portfolio/*`：数据源从 `quant.accounts` 切到 `simulation_*`，`account_name` 必填；旧表只读保留

### 配置

- `v13.yaml` → `account_name: v13_simulation`

## 5. agent-ts

### 账户感知原则

Agent 是策略账户的操盘手，自身无账户；通过账户发现 API 感知账户，**禁止硬编码账户名**。

### QuantV2Client 扩展

新增：`listAccounts()`、`getAccount(name)`、`getTrades(name)`、`getPerformance(name)`、`executeTrade(name, order)`，accountName 均必填。

### 工具改造

| 工具 | 改动 |
|------|------|
| `portfolio_trade` | 修复断链：改调 `POST /api/simulation/accounts/<name>/trade`；新增必填 `account`；`reason` 保持必填；返回 order_id、成交价费、realized_pnl（卖出时） |
| `portfolio_status` | 扩展 action：`list`（账户发现）/ `get`（指定账户资金两态+持仓+浮动盈亏），`get` 时 `account` 必填 |
| `portfolio_analyze` | 新增必填 `account`，分析净值曲线、已实现盈亏汇总、持仓集中度 |
| `portfolio_account`（新） | 开户/归档：`create`（name、display_name、initial_capital、strategy?）/ `archive` |

### 系统提示

工具 description 明确："交易前必须先用 portfolio_status list 确认目标账户；每笔交易必须指定 account 和 reason"。账户↔策略映射由账户发现数据自带，不进系统提示硬编码。

## 6. web-frontend

### 统一模拟交易页（改造 SimulationTrading/index.vue）

- 顶部账户切换器（el-select）：数据源 `GET /api/simulation/accounts`，显示 display_name + 总资产
- 选中后全部子请求带 `account_name` 刷新：资金两态卡片、持仓表（+当日盈亏、可用/总量）、净值曲线（snapshot）、交易记录（+realized_pnl、费用、reason）
- 开户对话框：名称、显示名、初始资金、绑定策略（可选）
- 清除所有硬编码 `accounts/default`、`strategies/v13`

### V14Trading 页下线

菜单合并到统一模拟交易页；原路由重定向到统一页并预选 `v14_simulation`。

## 7. 数据迁移（一次性脚本，v2 `scripts/`）

1. ALTER 既有表：`simulation_account.cash` 拆分为 `cash_available`（继承原值）+ `cash_frozen`（初始 0）；`simulation_positions.shares` 拆分为 `shares_total` + `shares_available`（历史持仓均已过 T+1，两者同取原值）；trades 表加列；建 order/cash_flow/snapshot 新表
2. `default` → `v13_simulation` 三表（account/positions/trades）重命名
3. 按 v15.yaml 创建 `v15_simulation` 账户（初始资金取配置，缺省 100,000）
4. 历史回填：从既有 trades 重放生成 cash_flow（保证 Σ流水==余额）+ 历史 equity 快照
5. v13.yaml 改 `account_name: v13_simulation`

## 8. 测试

- **v2 pytest**：账户 CRUD；缺 account_name 400；不存在 404+账户列表；流水不变式（随机交易序列后 Σ流水==余额）；T+1 当日买入不可卖；realized_pnl 计算；archived 拒写
- **agent-ts jest**：工具参数校验（缺 account 报错）；client 方法 mock 测试
- **web**：切换器联动手动验证
- **e2e**：agent 代管全流程（发现账户→指定账户交易→查持仓→查绩效）

## 9. 实施分期

- **P0（本次）**：cash_flow 流水 + 持仓 T+1 分离 + realized_pnl + snapshot + 账户注册/发现/trade API + 三层改造 + 数据迁移。order 表建立，市价单即时成交
- **P1（后续）**：限价单挂单撮合、分红入金流水、部分成交、（可选）JWT 真实认证

## 10. 错误处理

| 场景 | 响应 |
|------|------|
| 缺 account_name | 400 + 可用账户列表 |
| 账户不存在 | 404 + 可用账户列表 |
| archived 账户写操作 | 409 |
| 资金不足/风控违反/T+1 不可卖 | 422 + 具体原因 |
| 交易事务失败 | 整体回滚，order=rejected + 原因 |
