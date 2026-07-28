# Portfolio 页面多账户适配 — 设计文档

日期：2026-07-28
状态：已获用户批准（账户切换器方案 + simulation trade API + 顺带修 Dashboard）

## 背景与问题

多账户股票账户域（2026-07-21 上线）把后端持仓/汇总接口改为 `account_name` 必填：

- `GET /api/portfolio/positions` — 缺 `account_name` 返回 400，账户不存在返回 404（[orders.py:276](quantsys-v2/adapters/inbound/api/routes/orders.py#L276)）
- `GET /api/portfolio/summary` — 同上（[orders.py:311](quantsys-v2/adapters/inbound/api/routes/orders.py#L311)）

web-frontend 的 Portfolio 页面与 Dashboard 未同步改造，现状：

1. `tradingApi.getPositions()` / `getPortfolioSummary()` 不带 `account_name` → 页面 400 报错，数据加载失败
2. portfolio store 的字段映射按旧的 camelCase（`avgCost`/`currentValue`/`profitLoss`）取值，后端现返回 snake_case（`avg_cost`/`current_value`/`profit_loss`）→ 即使请求通了字段也全错位
3. 页面交易按钮走旧 `/api/orders/create`（无账户概念的旧订单体系，与 simulation 账户两套账本）
4. Dashboard `fetchPortfolioSummary` 同样无账户调用 → 400

## 设计决策（用户已确认）

- **页面定位**：顶部加 AccountSwitcher，按选中账户查看持仓（与 SimulationTrading 页同一交互模式）
- **交易按钮**：加仓/卖出改走 `simulationApi.trade`（`/api/simulation/accounts/<name>/trade` 立即成交），移除「+ 新建订单」（旧 orders 账本）
- **范围**：一并修复 Dashboard 的 summary 调用

## 改动清单

### 1. API 层 — `web-frontend/src/services/api/trading.ts`

```ts
getPositions(accountName: string) {
  return apiClient.get('/api/portfolio/positions', { params: { account_name: accountName } })
}
getPortfolioSummary(accountName: string) {
  return apiClient.get<PortfolioSummaryResponse>('/api/portfolio/summary', { params: { account_name: accountName } })
}
```

### 2. Store — `web-frontend/src/stores/portfolio.ts`

- 新增 state：`currentAccount: string`（空串 = 未选账户）
- `fetchSummary(accountName)` / `fetchPositions(accountName)` / `fetchAll(accountName)`：透传账户名；账户名为空时直接跳过（不发 400 请求）
- `fetchAll` 内部记录 `currentAccount`
- **字段映射修正**为后端现行 snake_case 契约：
  - `quantity` ← 响应字段 `quantity`（后端赋值为 `shares_total`）
  - `sharesAvailable` ← 响应字段 `shares_available`
  - `avgCost` ← `avg_cost`，`currentPrice` ← `current_price`
  - `marketValue` ← `current_value`，`totalCost` ← `total_cost`
  - `profit` ← `profit_loss`，`profitPercent` ← `profit_loss_pct`
  - `name` 后端返回空串 → fallback 为 symbol

### 3. 页面 — `web-frontend/src/views/Portfolio/index.vue`

- 顶部工具条加 `<AccountSwitcher>`（复用 [AccountSwitcher.vue](web-frontend/src/components/AccountSwitcher.vue)，支持 `?account=` URL 预选，模式照抄 SimulationTrading 页）
- `onAccountChange(name)` → `store.fetchAll(name)` + 退订旧行情、订阅新持仓 symbol 的 WebSocket quote
- 表格调整：
  - 「持仓量」列显示 总量，附加 可用（`shares_available`，T+1）
  - 移除「买入理由」列（simulation 体系无此数据）
  - 移除「目标价」列（无数据源）
  - 止损价列保留（riskApi 止损规则为 symbol 级，与账户无关，保持现状）
- 交易对话框：
  - 加仓 → `simulationApi.trade(currentAccount, { action: 'buy', symbol, shares, reason: '手动加仓' })`；限价时传 `price_limit`
  - 卖出 → 数量上限取 `shares_available`（T+1 约束）；`reason: '手动卖出'`
  - 成功后 `ElMessage` 提示并刷新持仓
- 移除「+ 新建订单」按钮

### 4. Dashboard — `web-frontend/src/views/Dashboard/index.vue`

- `fetchPortfolioSummary` 改为：先 `simulationApi.listAccounts()`，优先选 `agent_virtual`，否则取列表第一个账户；再 `tradingApi.getPortfolioSummary(account)`
- 无可用账户时静默显示 0（不弹错误）

### 5. 测试

- 更新 `web-frontend/tests/unit/DashboardPendingTasks.test.ts` 受影响的 mock（apiClient 信封解包后的形状，见 memory: apiclient-envelope-unwrap）
- 新增 portfolio store 测试：account_name 透传 + snake_case 字段映射
- 全部前端测试跑绿后在 worktree 内合并回 main

## 明确不做（YAGNI）

- 持仓股票名称 enrich（后端 `name` 返回空串，先显示代码，另开任务）
- 止损规则账户化（现为 symbol 级，保持现状）
- 多账户聚合视图 / 账户间对比
- 旧 `/api/orders/create` 体系的清理（超出本任务范围）

## 风险与备注

- apiClient 响应拦截器解包 `{success, data}` 信封，调用方和测试 mock 必须用解包后形状
- worktree 开发：`.claude/worktrees/portfolio-multi-account`，分支 `worktree-portfolio-multi-account`，验证后合回 main
