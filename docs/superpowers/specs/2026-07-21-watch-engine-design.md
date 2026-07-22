# 实时盯盘系统设计（WatchEngine）

**日期**: 2026-07-21
**状态**: 已实现（2026-07-22）
**范围**: quantsys-v2（引擎 + API + 存储）、agent-ts（watch_manage 工具）、web-frontend（WS 展示，复用现有频道）

## 背景与现状

系统当前**没有真正的实时盯盘**：

- `quantsys-v2/application/services/intraday_monitor.py` 每 30 分钟检查持仓，但 `_get_realtime_prices()` 取的是日 K 收盘价（盘中拿到的可能是昨收），且止损触发后不通知 Agent
- WS 5003 是通用 pub/sub hub，`market_data` 频道的行情推送任务是写死的假数据且被注释掉
- agent-ts 无任何 WS 客户端，盘中最高频任务是 30 分钟一次的 LLM 轮询（`realtime_quick_check`）

**可复用资产**：

| 资产 | 位置 |
|---|---|
| 实时报价 5 源 failover（腾讯→东财→新浪→AkShare→网易），5s 缓存 + 60s 熔断 | `quantsys-v2/application/services/realtime_quote_service_v2.py` |
| Agent 唤醒通道（已联通） | `agent-ts/src/api/wake-channel.ts` (`POST /wake`) ↔ `quantsys-v2/application/services/agent_notification_service.py:32` `notify_agent(event, data)` |
| WS 频道广播 hub（`market_data` / `game_alerts` 等频道 + `POST /broadcast/{channel}`） | `quantsys-v2/adapters/inbound/fastapi_app/websocket_server.py` |
| 常驻调度守护进程 | `quantsys-v2/scheduler_daemon.py` |

## 已确认的需求决策

1. **触发后行为**: v2 判断价格变动并发出通知，唤醒 Agent 决策（不自动卖出）
2. **监控范围**: Agent 动态添加监视（规则由 Agent 通过工具创建/管理，持仓股盯盘也由 Agent 主动注册规则实现）
3. **轮询频率**: 自适应（常规 1 分钟，接近阈值自动加密到 10 秒级），仅交易时段运行
4. **触发条件**: 价格上下破、涨跌幅/盈亏%、量能异动、瞬时涨速全部支持，Agent 创建规则时自行选择和组合，并可指定盯盘时段
5. **引擎形态**: 新建独立 WatchEngine 服务，旧 IntradayMonitor 不动（并行运行，后续可迁移）

## 架构与数据流

```
agent-ts                          quantsys-v2
┌──────────────────┐             ┌─────────────────────────────────┐
│ watch_manage 工具 │──HTTP CRUD─→│ /api/watch/rules (Flask+FastAPI)│
│ (增删改查监视规则)│             │              ↓                  │
└──────────────────┘             │  watch_rules 表 (PostgreSQL)    │
                                 │              ↓                  │
┌──────────────────┐  /wake      │  WatchEngine (asyncio 常驻)     │
│ wake-channel     │←────────────│  ├ 自适应频率轮询调度            │
│ 唤醒 Agent 决策   │  'watch_    │  ├ RealtimeQuoteServiceV2 取价  │
└──────────────────┘   triggered'│  │  (5源failover+熔断+缓存)     │
                                 │  ├ 条件判定器（可插拔）          │
                                 │  └ Notifier: 冷却去重           │
                                 │         ↓ notify_agent          │
                                 │  watch_triggers 表(审计)        │
                                 │         ↓ WS broadcast          │
                                 └─────────────┬───────────────────┘
                                               ↓
                                        web-frontend (market_data 频道)
```

关键决策：

- 引擎在 v2 侧（贴近数据源与熔断/缓存体系），agent-ts 只通过 `watch_manage` 工具管理规则 + 被唤醒决策
- 复用 `RealtimeQuoteServiceV2`，不新写取价逻辑
- 规则存 PostgreSQL 而非 agent-ts 内存（agent scheduler 是内存版，重启丢失；盯盘规则必须持久）
- 旧 `IntradayMonitor` 不动，与新引擎并行运行，后续可迁移

## 数据模型

### watch_rules 表

一条规则 = 一只股票 + 一组条件。

| 字段 | 类型 | 说明 |
|---|---|---|
| id | serial PK | |
| symbol | text | 股票代码，如 `600519.SH` |
| enabled | boolean | 开关 |
| conditions | JSONB | 条件数组，每项含 `type / params / cooldown_sec`（cooldown 默认 300s） |
| context | text | Agent 创建时填的监视理由，触发时原样回传，作为 Agent 决策上下文 |
| cost_price | numeric, 可空 | `pnl_pct` 条件的成本基准 |
| active_window | JSONB, 可空 | 盯盘时段，如 `["09:30-10:30","14:30-15:00"]`；空 = 全交易时段 |
| expires_at | timestamptz, 可空 | 规则过期时间，过期自动停用 |
| created_by | text | 创建者（如 `agent`），审计用 |
| created_at / updated_at | timestamptz | |

### 条件类型（可插拔 evaluator）

| type | params | 语义 |
|---|---|---|
| `price_break` | `{direction: above\|below, price}` | 上破/下破指定价 |
| `pct_change` | `{direction, pct}` | 相对昨收涨/跌超 X% |
| `pnl_pct` | `{direction, pct}` | 相对 `cost_price` 盈亏超 X%（止损止盈语义） |
| `velocity` | `{pct, window_min}` | N 分钟内任一方向波动超 X%（瞬时拉升/跳水，取绝对值，不区分方向） |
| `volume_surge` | `{multiple}` | 当日累计成交量超历史同期均量 N 倍（量能异动；均量 = 近 20 日日均成交量按当日已过交易时间比例折算） |

### watch_triggers 表（审计/学习）

每次触发写一条：`id, rule_id, symbol, condition (JSONB), trigger_price, triggered_at, agent_response (JSONB, 可空, Agent 决策后回填)`。

## 自适应频率与判定

- **基准 60s**；当某只股票"接近触发"（现价进入阈值缓冲带，缓冲带 = 当前价与阈值距离的 20%）→ 该股进入 **10s 高频档**；脱离缓冲带回落 60s
- 仅交易时段运行 9:30–11:30 / 13:00–15:00；规则的 `active_window` 可进一步收窄
- 判定循环：取启用规则（过滤过期/不在 active_window）→ 按 symbol 分组批量取价 → 逐条件判定 → 命中且过冷却 → 触发
- `velocity` / `volume_surge` 需要短时窗口：engine 内存维护每股 ring buffer（最近 30 分钟快照）；重启后窗口冷启动为空，这两类条件在窗口积累足够数据前不判定（价格类条件不受影响）
- **冷却去重**：每个条件独立 `cooldown_sec`（默认 300s），冷却期内同一条件不重复唤醒 Agent

## 触发通知

触发时调用 `notify_agent('watch_triggered', {...})`，payload 含：

- symbol、当前价、相对昨收涨跌幅
- 命中的条件（type + params）
- 相对成本盈亏（如有 cost_price）
- `context`（Agent 当初写的监视理由）

Agent 被 wake-channel 唤醒后拿到完整上下文即可决策（卖出/继续持有/调整规则），无需再查行情。

同时：

- WS broadcast 到 `market_data` 频道，供 web-frontend 展示
- 写 `watch_triggers` 审计记录

## API 与工具

- **v2 API**: `/api/watch/rules` CRUD（GET 列表 / POST 创建 / PATCH 更新 / DELETE 删除），Flask 与 FastAPI 双实现，遵循仓库既有 parity 模式
- **agent-ts 工具**: `watch_manage`（add / list / update / remove），在 V2_ROUTES 注册命令名（注意：参照既有 bug 教训，工具发送的命令名必须与 `quant-v2-client.ts` 映射表完全一致）

## 错误处理

- 五个数据源全部失败 → 走现有熔断机制，记日志 + 低频重试，**不唤醒 Agent**（避免垃圾告警）
- `notify_agent` 失败重试 3 次，仍失败则落库待补发
- 引擎异常退出由 scheduler_daemon 守护重启（规则在 PG，重启不丢）

## 测试

- 条件 evaluator 为纯函数，逐类型单测（含边界：恰好等于阈值、direction 反向、窗口数据不足）
- engine 用 fake quote service 做集成测试：触发路径、冷却去重、自适应频率升降档、过期规则过滤
- API 走仓库既有 Flask↔FastAPI parity 测试模式

## 明确不做（YAGNI）

- 不做自动卖出（触发只通知 Agent 决策）
- 不做 tick 级推送流（快照轮询已满足 LLM 决策的时效）
- 不改造旧 IntradayMonitor（并行运行，迁移另立项）
- web-frontend 不新建页面（复用现有 WS 频道，前端展示另立项）
