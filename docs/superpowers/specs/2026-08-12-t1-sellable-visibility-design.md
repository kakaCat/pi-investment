# T+1 可卖数量透出与卖出拦截反馈设计

日期：2026-08-12
状态：已获用户批准（方案 A）
范围：quantsys-v2（后端错误响应）+ agent-ts（透出、错误翻译、话术）

## 背景与问题

A 股 T+1 规则的正确语义：**仅当日买入的部分不可卖，之前持有的部分随时可卖**。

后端 quantsys-v2 已正确实现该语义：

- `simulation_positions.shares_available` 字段（`infrastructure/persistence/orm/models/simulation.py:157`）与 `shares_total` 分列存储
- 买入不加可卖数（`live_trading/paper_trading_engine.py:386`：`shares_available=旧值`）
- 卖出精确校验（`application/services/account_trading_service.py:206`：`shares > pos.shares_available` 时抛 `TradingError` 422，消息含"可卖 X 股"）
- 每日 9:25 开盘结转（`application/services/daily_orchestrator.py:278`：`settle_t1`，幂等，`available = total − 当日买入量`）
- API 已返回该字段（`adapters/inbound/fastapi_app/routes/v14_trading.py:71`、`application/services/simulation_service.py:384`）

**断裂在 agent 侧**，导致 agent 形成"今天什么都不能卖"的误解：

1. `portfolio_status`（agent 查持仓主工具）的 `computePortfolioView`（`agent-ts/src/infrastructure/tools/portfolio/portfolio-status-tool.ts:100-110`）映射持仓时**丢弃了 `shares_available`**，agent 只知总持仓、不知可卖数量。
2. 卖出被 422 拦截时，错误经 `fetchV2`（`agent-ts/src/infrastructure/adapters/quant/quant-v2-client.ts:696-703`）变成 `HTTP 422: {"success":false,"error":"..."}` 原始报文，agent 读不出"可卖 X 股"。
3. 工具描述与调度 prompt 中 T+1 话术含糊（"今日买入明日才能卖"），未明确"之前持有的可卖"。

## 目标

1. agent 事前可知：查持仓时看到每只股票的 `shares_available`（可卖数量）
2. 事中清晰拦截：超额卖出被后端拒绝时，agent 收到结构化、可直接读懂并自我修正的反馈
3. 话术统一：所有 T+1 文案表达正确语义

非目标（YAGNI）：

- 不改数据库 schema（`shares_available` 已存在且语义正确）
- 不改后端校验逻辑本身（已是唯一权威）
- 不做卖出自动截断（掩盖决策错误，违背审计可追溯原则）
- 不加买入侧限额（用户明确范围仅卖出侧）

## 设计

### 1. 后端：422 响应携带结构化 details（quantsys-v2）

**`application/services/account_trading_service.py`**：`TradingError` 增加可选 `details: dict` 属性；T+1 拦截处（当前 206-208 行及锁内重检 235-237 行，两处）抛出时携带：

```python
raise TradingError(
    f'T+1 可卖数量不足: 可卖 {pos.shares_available} 股，委托 {shares} 股',
    422,
    details={'sellable_shares': pos.shares_available, 'symbol': symbol},
)
```

**`adapters/inbound/fastapi_app/routes/simulation_async.py`**：`/accounts/{account_name}/trade` 路由的 `TradingError` 响应体改为：

```json
{ "success": false, "error": "T+1 可卖数量不足: ...", "details": { "sellable_shares": 600, "symbol": "600519" } }
```

无 `details` 的其他 `TradingError`（如资金不足）响应体**不输出 `details` 字段**（保持现有结构，向后兼容）；对应测试断言响应体中不存在该键。

> 注：Flask 旧路由（`adapters/inbound/api/routes/`）已废弃仅供回滚，本次只改 FastAPI 路由。

### 2. agent-ts 客户端：错误体 JSON 解析

**`src/infrastructure/adapters/quant/quant-v2-client.ts`** `fetchV2`：非 2xx 时尝试将响应文本解析为 JSON，把 `error`（字符串消息）与 `details` 挂到 `QuantV2Error` 新属性上；解析失败保持现有纯文本行为。`QuantV2Error` 增加 `apiError?: string` 与 `details?: Record<string, unknown>` 字段。

### 3. portfolio_status 透出 shares_available

**`src/infrastructure/tools/portfolio/portfolio-status-tool.ts`** `computePortfolioView`：

- `PortfolioHolding` 增加 `shares_available?: number`
- 映射：`h.shares_available != null && Number.isFinite(Number(h.shares_available)) ? Number(h.shares_available) : undefined`——后端缺失时保持 undefined，**绝不用 shares_total 回退造假**（沿用 days_held 契约，见同文件 95-98 行注释模式）
- summary 持仓行展示成对数量，如 `持仓 1000 股 / 可卖 600 股`；`shares_available` 为 undefined 时只展示总持仓（不臆测）

### 4. portfolio_trade 拦截反馈翻译

**`src/infrastructure/tools/portfolio/portfolio-trade-tool.ts`** catch 分支：识别带 `details.sellable_shares` 的 `QuantV2Error`，返回：

```json
{
  "success": false,
  "error": "超出 T+1 可卖数量",
  "sellable_shares": 600,
  "hint": "该持仓今日可卖 600 股（其余为今日买入，明日才可卖）。请用不超过 600 股的数量重试，或先用 portfolio_status 查看 shares_available。"
}
```

非 T+1 错误走现有兜底分支不变。

### 5. 话术澄清（正确 T+1 语义）

统一为："仅当日买入部分不可卖；之前持有的随时可卖，以 portfolio_status 的 shares_available 为准"。涉及：

- `portfolio-trade-tool.ts`：87 行成交 note、109 行功能描述、120 行注意事项
- `src/services/scheduler/tasks/agent-decision-tasks.ts`：41、92、159 行三处调度任务 prompt

### 6. 测试

**pytest（quantsys-v2）**：
- T+1 超额卖出 → 422 且响应体含 `details.sellable_shares` 等于持仓可用数
- 非 T+1 的 TradingError（如资金不足）→ 响应体不含 `details` 键（向后兼容）

**jest（agent-ts，必须 `npm test`，禁裸 npx jest）**：
- `computePortfolioView`：后端返回 `shares_available` 时透出；缺失时 undefined 且不回退
- `fetchV2`/`QuantV2Error`：422 JSON body 解析出 `apiError` 与 `details`；非 JSON body 保持原文行为
- `portfolio_trade`：带 details 的 422 → 结构化 `{sellable_shares, hint}`；普通错误 → 现有格式

## 数据流

```
agent: portfolio_status → v2 API → shares_available 透出 → agent 决策时已知上限
agent: portfolio_trade(sell 1000) → v2 校验 available=600 → 422 + details
  → QuantV2Error 解析 → portfolio_trade 翻译 → agent 收到 "可卖 600，请重试"
  → agent 用 ≤600 重试 → 成交
```

## 部署注意

- 后端改动需重启 5001 FastAPI（主工作区 venv nohup，手动重启）
- agent 改动需重启 agent 进程生效
- 无数据库迁移
