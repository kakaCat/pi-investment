---
id: rfc-017-holdings-api-decomposition
title: RFC 017：账户持仓业务接口拆分设计
type: rfc
status: living
updated: 2026-10-27
owners: [w-7e3880c6]
tags: [rfc, holdings, api-decomposition, performance, graceful-degradation]
---

# RFC 017：账户持仓业务接口拆分设计

- **状态**：Draft（待评审）
- **创建**：2026-09-12
- **本次重构**：2026-10-27
- **作者**：PI 投资顾问·投资脑（investor）/ w-7e3880c6
- **范围**：quantsys-v2 账户与调度 API、agent-dh 持仓聚合服务、DSH 账户持仓看板
- **文档沿革**：本文取代 2026-09-12 同名 RFC 的早期优化方案；保留原编号与性能基线，旧方案中的 Redis、直接按账户过滤调度任务等建议不再作为默认实施路径。

---

## 0. 设计结论

本次不是给现有大接口增加缓存或放宽超时，而是把「账户持仓」拆成四条可独立加载、独立失败、独立刷新业务链路：

| 链路 | 核心内容 | 设计结论 |
|---|---|---|
| **core** | 账户列表、当前账户摘要、持仓、合规派生值 | 只读数据库快照；不同步访问外网；账户切换的唯一阻塞链路 |
| **automation** | v2 调度任务、Agent OS 例行任务 | 独立加载；列表只返回摘要，不返回完整运行结果 |
| **activity** | 今日成交、历史成交 | 独立加载与分页；失败不影响持仓展示 |
| **watch** | 盯盘规则 | 独立加载；保留跨账户视图所需的数据口径 |

同时确立两条不可破坏的业务契约：

1. **真实空仓与查询失败必须可区分**。核心数据不可用时返回错误或显式陈旧数据，禁止用空持仓、零资产和 `success=true` 冒充成功。
2. **看板快照不是交易定价依据**。交易、止损与风控继续使用各自的实时行情和交易宪法校验，本 RFC 不降低任何交易安全要求。

---

## 1. 背景与实测证据

### 1.1 当前调用链

账户切换时，客户端固定发起全量请求：

```text
switchAccount(account)
  └─ GET /dashboard/api/holdings?account=<account>       # full
       ├─ GET /api/simulation/accounts
       ├─ GET /api/simulation/accounts/{account}         # DB + 外网行情 + 写库 + benchmark
       ├─ GET /api/simulation/trades?account_name=...
       ├─ GET /api/watch/rules
       ├─ GET /api/scheduler/tasks?pageSize=200
       └─ Agent OS /tasks + /tasks/stats
```

相关实现：

- [board-mount.ts](../../agent-dh/packages/web/holdings/src/client/board-mount.ts)：`switchAccount()` 直接调用全量 `fetchAndRender()`。
- [portfolio-aggregation.ts](../../agent-dh/packages/web/holdings/src/services/portfolio-aggregation.ts)：六个上游通过 `Promise.allSettled()` 聚合。
- [simulation_async.py](../../quantsys-v2/adapters/inbound/fastapi_app/routes/simulation_async.py)：账户路由为 `async def`，内部直接执行同步 DB/行情调用。
- [simulation_service.py](../../quantsys-v2/packages/qs_trading/qs_trading/application/services/simulation_service.py)：`get_account_status()` 拉取行情并回写持仓价格。
- [scheduler_async.py](../../quantsys-v2/adapters/inbound/fastapi_app/routes/scheduler_async.py)：任务列表读取运行记录并返回完整 `lastRun.payload`。

### 1.2 2026-10-26 实测

以下数据来自本机 `curl` 对运行中服务的顺序探测；响应大小为未压缩口径。

| 探测项 | 实测结果 | 结论 |
|---|---:|---|
| `agent_brain` 账户状态 | 11.140s | 日志显示约 11.10s 位于实时价格更新区间 |
| `v13_simulation` 账户状态 | 18.009s | 日志显示约 17.97s 位于实时价格更新区间 |
| 同一账户接口恢复后 | 0.243s；缓存命中 0.037s | 不是固定慢 SQL；外部行情路径存在明显抖动 |
| holdings hot/full（慢时） | 均约 4.004s | 聚合层 4s 超时成为用户可见等待 |
| holdings hot（恢复后） | 2.366s | 正常路径仍受辅助数据影响 |
| `/api/scheduler/tasks?pageSize=200` | 79 个任务、13,684,813B、约 2–7.4s | 任务列表响应过大 |
| 其中 `lastRun.payload` | 12,902,404B，约 99.5% | 大字段是调度响应的主要组成 |
| `/api/health/db` | 约 4.5ms | 数据库整体健康，不是全局慢查询 |
| `/api/simulation/accounts` | 约 16ms | 账户列表自身不是瓶颈 |
| Agent OS tasks/stats | 各约 5ms | Agent OS 不是本次主瓶颈 |

慢时的聚合响应还存在数据正确性问题：HTTP 为 200、`success=true`，但 `accounts=[]`、`positions=[]`；直接查询同一账户却有 2 只持仓。恢复后，同一 hot 请求返回 8 个账户和 2 只持仓。

### 1.3 根因归类

1. **职责混合**：账户查询同步承担实时取价、写库、持仓查询和基准计算。
2. **事件循环阻塞**：`async` 路由内执行阻塞 I/O，一个慢账户请求会拖住其他请求。
3. **聚合边界错误**：核心的账户持仓与辅助的交易、盯盘、调度信息共享等待与失败边界。
4. **列表/详情不分**：调度列表携带完整运行结果，并存在每任务读取 100 条 runs 的 N+1 模式。
5. **降级语义错误**：超时、上游失败和真实空数据被统一转换为空数组/零值。
6. **放大机制**：账户切换固定 full，轮询与多窗口进一步放大慢请求和重复取数。

---

## 2. 目标与非目标

### 2.1 目标

- 账户切换只依赖 core，首屏不被 automation/activity/watch 阻塞。
- core 只读持久化快照，不同步调用外部行情源，不在 GET 中回写持仓。
- 单个辅助模块失败时，其他模块仍可用，且失败位置对用户可见。
- 调度任务列表的查询数与响应大小不再随运行结果体积膨胀。
- 保留现有交易、风控、T+1、止损与数据新鲜度纪律。
- 保留旧接口的兼容期，支持快速回滚，避免一次性重写全部消费者。

### 2.2 非目标

- 不修改交易定价、下单、止损、熔断、仓位与试单授权规则。
- 不更换行情 provider，不在本 RFC 内重做多源 Provider 框架。
- 不要求首期引入 Redis 或新的基础设施。
- 不要求首期修改 Agent OS Go 服务；其现有接口只在 automation 链路使用。
- 不一次性废弃旧账户状态接口和旧 holdings full/hot 契约。
- 不把看板快照作为交易、风控或止损的实时价格来源。

---

## 3. 设计原则与不变量

1. **核心优先**：账户摘要与持仓是 core；其他信息不得阻塞 core。
2. **读写分离**：查询返回已知快照；实时行情刷新是独立命令/后台任务。
3. **列表与详情分离**：列表只提供摘要，完整运行结果按需查询。
4. **按块成功、按块失败**：不得让辅助模块失败清空核心数据。
5. **诚实新鲜度**：所有快照携带数据时点；陈旧可以展示，但必须标记。
6. **空与失败分离**：`[]` 只能表示服务端已确认的真实空集合。
7. **兼容演进**：新增契约先行，旧契约灰度退出，不做静默语义替换。
8. **有界资源**：HTTP 请求、后台刷新、DB 查询与缓存均有超时、大小或并发上限。

---

## 4. 目标架构

```text
                         ┌──────────────────────────────┐
                         │ DSH 账户持仓看板             │
                         │ A/B 账户切换、分卡片渲染      │
                         └──────────────┬───────────────┘
                                        │
                 ┌──────────────────────┼──────────────────────┐
                 │ core                 │ automation/activity  │ watch
                 │ 必须先展示            │ 独立加载、独立错误     │
                 ▼                      ▼                      ▼
┌──────────────────────────┐  ┌────────────────────┐  ┌──────────────────┐
│ v2 AccountOverviewQuery │  │ Scheduler Summary  │  │ Trades / Watch   │
│ 只读账户与持仓快照         │  │ 固定查询数、无大payload│  │ 现有独立查询      │
└─────────────┬────────────┘  └────────────────────┘  └──────────────────┘
              │ DB only
              ▼
┌──────────────────────────┐         ┌───────────────────────────────┐
│ PostgreSQL 最后有效快照   │◀────────│ QuoteRefreshService           │
│ account / positions      │ 异步写  │ 单飞、限时、多源、记录数据时点 │
└──────────────────────────┘         └───────────────┬───────────────┘
                                                      │
                                                      ▼
                                             外部行情 Provider
```

关键变化：**外部行情只出现在异步刷新链路，不再位于 core 的请求关键路径。**

---

## 5. 业务接口设计

### 5.1 新增账户概览查询

```http
GET /api/simulation/accounts/{account_name}/overview
```

#### 职责

返回当前账户的账户信息、资产摘要与持仓快照，供看板和只读工具使用。

#### 必须满足

- 只读数据库；不调用外部行情 provider。
- 不回写 `current_price`、`price_updated_at` 或其他持仓字段。
- 不同步计算需要外部数据的 benchmark；绩效/基准由独立 performance 查询承担。
- 使用同步 `def` 路由由 FastAPI 线程池执行，或使用等价的线程池封装；禁止在 `async def` 中直接跑阻塞 ORM。
- 复用现有 ORM session 清理机制；不新增跨请求共享的 DB Session。

#### 响应示例

```json
{
  "success": true,
  "data": {
    "account": {
      "account_name": "agent_brain",
      "display_name": "投资脑自营盘",
      "account_type": "agent",
      "strategy_name": "genome-g47",
      "status": "active"
    },
    "summary": {
      "cash_available": 490008.31,
      "position_value": 8852.0,
      "total_value": 498860.31,
      "cumulative_return": -0.0023,
      "positions_count": 2
    },
    "positions": [
      {
        "symbol": "002007",
        "name": "华兰生物",
        "shares_total": 600,
        "shares_available": 600,
        "avg_cost": 13.27,
        "current_price": 13.15,
        "market_value": 7890.0,
        "profit_total": -72.0,
        "profit_total_rate": -0.009,
        "price_updated_at": "2026-10-26T17:56:34+08:00"
      },
      {
        "symbol": "600000",
        "name": "浦发银行",
        "shares_total": 100,
        "shares_available": 100,
        "avg_cost": 9.03,
        "current_price": 9.62,
        "market_value": 962.0,
        "profit_total": 58.99,
        "profit_total_rate": 0.0653,
        "price_updated_at": "2026-10-26T17:56:34+08:00"
      }
    ]
  },
  "meta": {
    "request_id": "req_01J...",
    "source": "db_snapshot",
    "snapshot_as_of": "2026-10-26T17:56:35+08:00",
    "price_as_of": "2026-10-26T17:56:34+08:00",
    "price_stale": false,
    "stale_reason": null
  }
}
```

#### 契约约束

- 真实空仓：`positions=[]`，`positions_count=0`，同时必须存在真实账户和资产摘要。
- 账户不存在：404。
- 快照不可用：503；不得返回零资产摘要。
- 价格未知：对应字段为 `null` 并附原因，不能用 0 代替。
- `price_stale=true` 时必须同时提供 `price_as_of` 与 `stale_reason`。
- `shares_available` 继续遵循 T+1 口径，不在概览层重新推算。

### 5.2 行情刷新独立为命令

新增内部刷新用例 `QuoteRefreshService`，首版可由后台调度执行；手动刷新能力作为后续可选项：

```http
POST /api/simulation/accounts/{account_name}/quotes/refresh
→ 202 Accepted
```

```json
{
  "success": true,
  "data": {
    "refresh_id": "qref_01J...",
    "status": "accepted",
    "requested_at": "2026-10-27T09:30:00+08:00"
  }
}
```

约束：

- POST 只触发刷新，不承担下单或改变交易状态。
- 同一账户/同一标的集合采用 single-flight，重复请求复用进行中的刷新，不制造请求风暴。
- provider 必须有明确的连接/读取超时与整批 Deadline；后台刷新不能无限等待。
- 刷新成功后一次性更新价格与 `price_updated_at`；失败保留最后有效快照并记录失败原因。
- 前台 GET 不等待刷新结果；用户通过下一次 core 轮询读取新快照。
- 刷新时间戳必须来自实际行情数据时点，不得用“任务完成时间”冒充行情时点。

> 首版不要求新增持久化刷新任务表；内存 single-flight 与结构化日志足够。若后续要求跨进程查询刷新状态，再增加持久化 refresh job 契约。

### 5.3 旧账户状态接口的处理

保留一段兼容期：

```http
GET /api/simulation/accounts/{account_name}
```

- 不直接改成与 overview 相同的陈旧快照语义，避免静默改变既有调用方。
- P0 先消除事件循环阻塞和共享可变状态，再考虑内部复用 `AccountOverviewQuery + QuoteRefreshService`。
- `SimulationService._price_timestamps` 当前保存在单例服务上。迁移到线程池前必须改为局部变量或随 `_fetch_current_prices()` 的返回值传递，禁止多个账户请求共享可变的临时字典。
- 交易前价格确认仍走现有实时行情与交易守卫；不得因 overview 上线而改成读取看板快照下单。

### 5.4 新增调度任务摘要接口

```http
GET /api/scheduler/tasks/summary?page=1&pageSize=100
```

#### 响应示例

```json
{
  "success": true,
  "contract_version": 2,
  "tasks": [
    {
      "id": "123",
      "name": "v13_daily_check",
      "enabled": true,
      "scheduleExpr": "0 9 * * 1-5",
      "command": "v13_daily_check",
      "description": "V13 每日检查",
      "strategy": "v13",
      "lastStatus": "failed",
      "lastStatusSource": "inner_result",
      "lastAt": "2026-10-27T09:00:00+08:00",
      "lastError": "示例错误，服务端截断",
      "nextRunAt": "2026-10-28T09:00:00+08:00",
      "todayTriggered": 1,
      "todaySuccess": 0
    }
  ],
  "count": 79,
  "page": 1,
  "pageSize": 100
}
```

#### 查询与字段约束

- 任务列表、每任务最新 run、当日统计采用集合查询：
  1. 查询任务页；
  2. 查询这些任务的最新 run（窗口函数或 `DISTINCT ON`）；
  3. 按 `task_id` 聚合当日次数与成功数。
- 查询数固定为常数，禁止逐任务 `list_runs(limit=100)`。
- 不返回 `lastRun.payload`、完整 `result`、回测明细、事件列表或日志正文。
- `lastError` 服务端截断，建议上限 2 KB；完整错误进运行详情。
- 保留现有[运行详情接口](../../quantsys-v2/adapters/inbound/fastapi_app/routes/scheduler_async.py) `/api/scheduler/tasks/{task_id}/runs` 的分页查询；需要完整结果时再增加单 run 详情，不把详情塞回列表。

#### 状态真实性是硬契约

当前客户端通过 `payload.details.details.status/error` 纠正外层“调度成功但业务失败”的假成功。新接口不能只删 payload 后退回外层状态：

- 后端在生成 summary 时完成与现有 `resolveLastRun()` 等价的归一化。
- 返回 `lastStatus` 和 `lastStatusSource=inner_result|scheduler|none`。
- `completed` 的归一规则、内层 details 的两层/单层兼容必须与旧客户端契约测试对齐。
- 新客户端在 `contract_version=2` 的摘要响应中信任服务端 `lastStatus`；旧响应才使用原有 `resolveLastRun()` 兜底。
- 用真实 run fixture 覆盖“外层 success + 内层 failed/skipped”的场景，禁止只做字段存在性测试。

#### 账户过滤的边界

首版**不承诺** `account_name` 过滤。现有账户归属由 host 侧策略绑定和 Agent OS 白名单推导，并不是 v2 调度表的统一字段；直接增加过滤参数容易返回“看似过滤、实际错配”的结果。

过渡方案：摘要接口返回轻量任务集合，host 继续执行现有 `_resolve_execution_line()` 和白名单映射。待任务 ownership 统一建模后，再增加服务端账户过滤。

### 5.5 成交与盯盘接口

#### activity

复用现有：

```http
GET /api/simulation/trades?account_name={account}&limit=50
```

- 股票名称继续由后端一次 `IN` 查询补齐，不能退回前端逐只 search。
- 首期保留 limit；历史量增加后再以 `(created_at,id)` 做稳定游标分页。
- 今日成交由同一数据集按本地日期派生，不能分别调用两个全量接口。

#### watch

复用现有 `/api/watch/rules`，但从 core 移除。

当前客户端的盯盘中心包含跨账户 tab，host 全量取规则是现行业务口径，不能简单按当前账户过滤后导致其他 tab 消失。后续若需要减量，应先定义：

- `scope=current`：当前账户规则 + 通用观察；
- `scope=all`：跨账户盯盘中心；
- 规则大字段与摘要字段分离。

### 5.6 DSH holdings 聚合分块

复用已有 `parts` 机制，不新增另一套聚合路由体系。

| parts 预设 | 数据内容 | 上游 | 前台策略 |
|---|---|---|---|
| `core` | accounts、currentAccount、summary、positions、可用的 compliance | accounts + 新 overview | 切换账户立即请求；15s 轮询 |
| `automation` | 当前账户自动化任务 | 新 scheduler summary + Agent OS | core 后独立加载；60s 或手动刷新 |
| `activity` | todayTrades、tradeHistory | trades | 卡片可见时加载；分页 |
| `watch` | watchRules | watch rules | 盯盘卡片打开时加载；低频刷新 |

示例：

```http
GET /dashboard/api/holdings?account=agent_brain&parts=core
GET /dashboard/api/holdings?account=agent_brain&parts=automation
GET /dashboard/api/holdings?account=agent_brain&parts=activity&limit=50
GET /dashboard/api/holdings?account=agent_brain&parts=watch
```

兼容规则：

- 旧 `parts=hot` 与 full 在迁移期保留，由旧客户端使用。
- 新客户端只使用 core/automation/activity/watch。
- `core` 不返回 automation；hot 在旧契约中的语义不因新客户端而静默变化。
- 服务端 `parts` 回显仍是客户端合并依据；未请求的数据块不得用空数组覆盖本地有效数据。

---

## 6. 响应、降级与新鲜度契约

### 6.1 统一元数据

新分块响应增加可选 `meta`，保持原 `success/data` 信封：

```json
{
  "success": true,
  "data": {
    "currentAccount": "agent_brain",
    "summary": {},
    "positions": [],
    "parts": ["core"]
  },
  "meta": {
    "request_id": "req_01J...",
    "account": "agent_brain",
    "parts": ["core"],
    "as_of": "2026-10-27T09:30:00+08:00",
    "stale": false,
    "errors": {}
  }
}
```

### 6.2 状态判定表

| 场景 | HTTP / success | 数据契约 | 前端行为 |
|---|---|---|---|
| 真实空仓 | 200 / true | 真实账户与摘要 + `positions=[]` | 显示“当前账户暂无持仓” |
| 账户不存在 | 404 / false | 不返回伪造账户或零摘要 | 显示账户不可用 |
| core DB 不可用且无缓存 | 503 / false | `summary=null` 或无 data | 保留上次有效数据；无缓存则显示加载失败 |
| core 有陈旧快照 | 200 / true | 快照 + `stale=true` + 时点/原因 | 展示数据并显示陈旧横幅 |
| automation 失败 | core 仍可 200 / true | `meta.errors.automation` | 仅自动化卡片显示失败与重试 |
| activity/watch 失败 | core 仍可 200 / true | 对应块错误，不擦除旧块 | 对应卡片独立降级 |
| 上游空集合 | 200 / true | 已确认的空数组 | 正常空态，不当作故障 |

> 不使用 HTTP 206 表示业务模块降级；206 有既有范围请求语义。部分模块状态通过 `meta.errors` 明确表达。

### 6.3 错误信封

为兼容现有客户端，`error` 保持字符串，新增机器可读字段：

```json
{
  "success": false,
  "error": "账户概览暂时不可用",
  "error_code": "CORE_DATA_UNAVAILABLE",
  "retryable": true,
  "request_id": "req_01J..."
}
```

禁止行为：

- 用 `getDefaultSummary()` 生成全零资产并标记当前时间为 `lastUpdated`。
- 把上游超时转换为 `accounts=[]` 或 `positions=[]`。
- 把 A 账户的旧数据展示为 B 账户数据。
- 用请求完成时间替代数据实际时点。

---

## 7. 缓存与刷新策略

### 7.1 后端快照

- PostgreSQL 中的账户/持仓是 core 的最后有效快照。
- 现有 5 秒行情缓存只用于降低刷新压力，不是 core 的可用性前提。
- 刷新失败时保留旧快照并标记 stale；不得清空价格或持仓。
- 同一账户/标的集合采用 single-flight，避免 15s 轮询与多窗口形成同步穿透。

### 7.2 前端按账户缓存

每个账户分别保存：

```text
AccountViewState = {
  core?: CoreData & { receivedAt, asOf },
  automation?: AutomationData & { receivedAt },
  activity?: ActivityData & { receivedAt },
  watch?: WatchData & { receivedAt },
  errors: Record<Part, ErrorState | null>
}
```

- 切回已访问账户时先渲染该账户的最后有效 core，再后台刷新。
- 只合并本次实际请求且成功的 parts。
- 某块失败只更新该块 error，不重置其他块。
- 请求序号与账户双重校验继续保留，并配合 `AbortController` 取消旧请求。

### 7.3 新鲜度建议

- core 轮询沿用 15s；automation 60s；activity/watch 按卡片可见性与手动刷新。
- 价格陈旧阈值必须配置化。建议初始展示口径：交易时段 15s，非交易时段允许使用最近收盘快照并明确时点。
- 上述阈值只用于看板展示，不修改交易风控的实时性要求，也不作为止损判据。

### 7.4 首期不引入 Redis

理由：

- 当前主要问题是接口职责和阻塞边界，不是缺少分布式缓存。
- 本地 DB 快照与前端按账户缓存已能覆盖首期需求。
- Redis 不能修复假空数据、N+1 或事件循环阻塞，反而增加一致性与运维复杂度。

---

## 8. 并发与资源隔离

### 8.1 FastAPI 路由

- 同步 ORM/HTTP 代码使用 `def` 路由或显式 `run_in_threadpool()`。
- 不允许仅在 `async def` 内包一层直接调用，就把阻塞工作留在事件循环。
- 保留同步路由的 worker 线程 session 清理；异步路由与同步路由不得混用同一个 thread-local session。
- 迁移前移除 `SimulationService` 单例上的请求级可变字段，尤其是 `_price_timestamps`。

### 8.2 有界刷新

- provider 连接、读取与整批刷新都有 Deadline。
- 刷新队列与线程池大小有上限；不得为每次超时创建无法回收的后台线程。
- core 不创建 provider 任务，因此 provider 故障不能转化为 core 的队头阻塞。
- 辅助上游采用独立超时；Agent OS/scheduler 超时不得延长 core 响应。

### 8.3 数据库

- overview 使用固定数量查询，避免逐持仓查询名称或快照。
- scheduler summary 固定为任务、最新 run、当日聚合三类集合查询。
- 验收中使用 SQL 计数器证明不存在 N+1，而不只看单次耗时。

---

## 9. 前端加载流程

```text
用户切换 A → B
  1. currentAccount=B，作废旧请求
  2. 若 B 有缓存：立即展示 B 的 core，并标记正在刷新
     否则：展示骨架屏，不展示 A 的数据，不显示零资产
  3. 请求 parts=core
  4. core 成功：渲染 B 的账户摘要与持仓
     core 失败：保留 B 旧快照或显示明确错误
  5. 并行/空闲时请求 automation、activity、watch
  6. 每个卡片独立渲染、独立重试、独立显示数据时点
```

轮询只刷新可见页面和已加载分块；页面隐藏或 tab 非激活时继续沿用现有暂停机制。

---

## 10. 分阶段实施与回滚

### P0：止损性修复

- 修正 core 超时后的假空数据与零摘要。
- 消除账户路由事件循环阻塞；先处理 `_price_timestamps` 共享状态。
- 增加分阶段耗时与 provider 日志。
- 保留旧 API，只修复明确缺陷。

### P1：调度摘要与 automation 解耦

- 上线 `/api/scheduler/tasks/summary`。
- 用集合查询替代每任务 100 runs。
- 服务端完成 lastStatus 归一化，列表不再输出完整 payload。
- holdings 新客户端将 automation 从 core 关键路径移除。
- Agent OS 继续只在 automation 中调用。

### P2：账户快照与 core 上线

- 上线账户 overview 与 `QuoteRefreshService`。
- holdings 增加 core/automation/activity/watch 分块。
- 前端按账户缓存、分卡片降级与独立刷新。
- 通过开关灰度新旧客户端。

### P3：消费者迁移与旧契约收敛

- 评估 `account_info`、`position_list` 等只读工具迁移到 overview；交易前实时价格确认保持独立。
- 观察兼容期指标后，停止新消费者使用 full。
- 旧 full/hot 与旧账户状态接口在确认无消费者后再标记废弃，不在本 RFC 中预设强制删除日期。

### 回滚

- 使用 `HOLDINGS_SPLIT_API_ENABLED`、`SCHEDULER_SUMMARY_API_ENABLED` 等开关切换新旧路径。
- 回滚只切调用路径，不回滚数据；P0/P1 不要求破坏性 DB migration。
- 保留旧接口直到跨窗口、定时任务和工具消费者完成核验。

---

## 11. 性能与正确性验收

### 11.1 性能 SLO

以下指标在本机开发/运行环境、79 个调度任务规模下验收；生产环境若有差异需另记基线。

| 指标 | 验收目标 |
|---|---:|
| core 正常响应 p95 / p99 | < 500ms / < 1s |
| 行情 provider 人为阻塞 30s 时 core p95 | 仍 < 1s，返回快照并显式 stale |
| 未缓存账户切换至核心内容可见 | < 1s |
| 有缓存账户切换至旧快照可见 | < 300ms |
| scheduler summary p95 | < 1s |
| scheduler summary 响应大小 | < 256KB |
| scheduler summary 查询数 | 常数级，不随任务数逐项增加 |
| automation/activity/watch 故障 | 不增加 core 等待，不清空 core |

### 11.2 必测故障注入

| 故障 | 预期 |
|---|---|
| 行情 provider 挂起 | core 仍快速返回；刷新后台超时；旧快照带 stale |
| DB 查询失败 | 无缓存时 503；不得返回零资产成功 |
| scheduler 大 payload（两条 >1MB run） | summary 仍小于 256KB，不传输大字段 |
| 外层 run=success、内层 failed/skipped | summary 的 lastStatus 与旧契约一致，来源可追踪 |
| automation 超时 | core 正常，自动化卡片独立报错 |
| 真实空仓 | 返回已确认空数组，页面显示正常空态 |
| 账户不存在 | 404，不显示零资产 |
| A→B→A 快速切换且响应乱序 | 不串账户，不用旧响应覆盖新选择 |
| 多窗口同时刷新同一账户 | single-flight 生效，无等比例 provider 放大 |
| SQL 计数 | scheduler summary 不出现每任务 runs 查询 |

### 11.3 契约与端到端测试

- 使用真实响应 fixture，不只使用理想 mock。
- 对比新旧 core 的账户、持仓数量、现金、市值、可卖数量与数据时点。
- 对快照与实时价差异按 `price_as_of` 解释，不做脱离时点的绝对相等断言。
- 浏览器完成 A/B 多轮切换、冷/热缓存、单卡片失败与恢复测试。
- 线上验证以实际绑定接口和页面为准，源码级测试通过不等于部署生效。

---

## 12. 可观测性

每个请求/刷新记录：

- `request_id`、account、part、http status、总耗时。
- core：`db_ms`、快照时点、stale 与原因。
- 刷新：provider、attempted_sources、各源耗时、整批 Deadline、成功/缺口/失败。
- scheduler：任务数、SQL 次数、查询耗时、响应字节数、被截断错误数。
- 聚合层：各上游耗时与失败码，不只记录最外层 4s 超时。

建议指标：

```text
holdings_part_duration_seconds{part,result}
holdings_part_payload_bytes{part}
holdings_snapshot_stale{part}
quote_refresh_duration_seconds{provider,result}
scheduler_summary_query_count
```

告警针对“核心数据不可用、持续陈旧、异常放大”，不对单次辅助模块抖动做高优告警。

---

## 13. 备选方案与取舍

| 方案 | 结论 | 原因 |
|---|---|---|
| 只把 4s 超时调到 20s | 否决 | 用户等待更久，事件循环阻塞与假空数据仍存在 |
| 只加 Redis 缓存整个 holdings | 否决 | 无法修复契约与 N+1，并引入缓存穿透和一致性问题 |
| 只做 async→sync/线程池 | 作为 P0，不是终态 | 能缓解队头阻塞，但账户切换仍拉取无关大数据 |
| 一次性重写所有账户接口和消费者 | 否决 | 交易工具与定时任务面广，回归风险高 |
| 新增强依赖 GraphQL/BFF 查询层 | 否决 | 当前 parts 已能表达分块，新增体系收益不足 |
| 调度列表直接删除 payload | 否决 | 会丢失内层业务失败状态，必须先后端归一化 |
| **core/辅助拆分 + 快照/刷新分离** | **采用** | 同时解决性能、可用性与数据诚实性，且可灰度回滚 |

---

## 14. 风险与缓解

| 风险 | 缓解 |
|---|---|
| 快照让用户误以为价格实时 | 明示 `price_as_of` 和 stale；交易链路不使用看板快照定价 |
| 旧消费者仍依赖旧接口实时副作用 | 保留兼容期；先盘点消费者再迁移，不静默改变旧接口语义 |
| 简单移入线程池引入共享状态竞态 | 先移除 `_price_timestamps` 等请求级单例字段，再做并发故障测试 |
| scheduler 状态归一化前后不一致 | 共享契约 fixture；覆盖内外层状态冲突与 details 两种形状 |
| 后台刷新形成新的请求风暴 | single-flight、有界队列、整批 Deadline、多窗口压力测试 |
| 多分块导致请求数增加 | core 保持一次请求；辅助块按可见性/低频加载；不为每只持仓另发请求 |
| 部分失败被忽略 | 每块显式 error、陈旧横幅、独立重试与结构化日志 |

---

## 15. 实施文件清单

### quantsys-v2

- [simulation_async.py](../../quantsys-v2/adapters/inbound/fastapi_app/routes/simulation_async.py)：新增 overview；旧路由兼容与阻塞修复。
- [simulation_service.py](../../quantsys-v2/packages/qs_trading/qs_trading/application/services/simulation_service.py)：拆分查询/刷新用例，移除请求级单例状态。
- [scheduler_async.py](../../quantsys-v2/adapters/inbound/fastapi_app/routes/scheduler_async.py)：新增摘要路由与集合查询。
- Scheduler repository/service：最新 run、当日聚合、状态归一化与 SQL 计数测试。
- 行情 provider 刷新路径：复用现有多源框架，不另建数据源体系。

### agent-dh

- [portfolio-aggregation.ts](../../agent-dh/packages/web/holdings/src/services/portfolio-aggregation.ts)：core 与辅助块独立聚合、错误元数据、删除零值伪降级。
- [parts.ts](../../agent-dh/packages/web/holdings/src/services/parts.ts)：新增分块预设与兼容映射。
- [board-mount.ts](../../agent-dh/packages/web/holdings/src/client/board-mount.ts)：账户切换先 core、辅助块独立加载。
- [types/index.ts](../../agent-dh/packages/web/holdings/src/types/index.ts)：分块状态、meta、nullable/陈旧契约。
- `tests/`：契约、竞态、故障注入与前端合并测试。

---

## 16. 评审时需确认的决策点

默认值已写入本文，评审重点是确认而不是重新开放式设计：

1. **看板价格新鲜度阈值**：默认交易时段 15s、非交易时段最近收盘快照；仅用于展示，不改交易风控。
2. **旧接口兼容期退出条件**：以消费者盘点和线上指标为准，不按固定日期强删。
3. **调度 ownership 统一建模**：首版沿用 host 映射，是否另立需求统一账户归属字段。
4. **手动行情刷新是否对外开放**：首版只做内部命令/后台刷新；如需页面按钮，再评审频控与权限。

---

## 附录 A：2026-09-12 历史基线

旧版 RFC 记录 `/dashboard/api/holdings` 为 4.010s、599B，当时推测主要等待 Agent OS。2026-10-26 的逐上游实测表明，当前主要瓶颈已变为账户实时行情阻塞和 v2 调度大响应；因此旧版“统一 Redis 缓存、直接按账户过滤任务”等建议不再作为默认方案。

## 附录 B：相关页面

- [项目说明书](../architecture/project-manual.md)
- [RFC 011：双调度系统三层监控体系](011-scheduler-observability.md)
- [RFC 015：三项数据能力补强的 DDD 方案](015-data-capability-ddd-design.md)
- [ADR 002：调度器归属拆分](../adr/002-scheduler-ownership-split.md)

---

**审批**：待评审  
**实施负责人**：待指定  
**验收证据要求**：性能报告、SQL 计数、故障注入结果、浏览器切换录屏/网络记录、兼容与回滚结果
