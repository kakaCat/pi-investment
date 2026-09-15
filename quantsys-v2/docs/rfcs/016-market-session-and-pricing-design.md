# RFC 016 · 统一市况（开市/非开市）与两态取价

| 项 | 值 |
|---|---|
| 编号 | 016 |
| 状态 | 提案（待实现） |
| 日期 | 2026-09-12 |
| 范围 | quantsys-v2 |
| 关联 | `docs/architecture/scheduler-architecture.md`、`docs/realtime-data-support.md`、`docs/volume-and-minute-apis.md`、`application/services/trading_day_guard.py`（2026-09-11「交易日判断唯一入口」w-f4aa1f6a） |

---

## 1. 背景与问题

### 1.1 触发事件：看板在休市日"转空"，并冻住整个进程

2026-09-12（周六，非交易日）持仓看板 `/api/simulation/accounts/agent_virtual` 返回全 0（`positions: []`、`totalValue: 0`）。排查结论：

- **v2 没有卡死，是周期性阻塞**。09-12 15:00–20:00 期间，日志里 11 个互不相关的端点（`/api/health`、`/api/health/db`、`/api/memory/search`、`/api/scheduler/tasks`、`/api/market/perception/*`、`/api/watch/rules`、`/api/simulation/accounts*`）**在同一秒开始、同一秒结束**，各耗时 32.6s —— 典型的事件循环被独占、请求整体排队。
- 冻结窗口的日志把 33s 拆得清清楚楚：
  ```
  15:56:46  Fetching quote for 300677
  15:56:54  Successfully fetched quote for 300677 from tencent   ← 单条行情 8.0s
  15:56:54  Fetching quote for 600887
  15:57:02  Successfully fetched quote for 600887 from tencent   ← 又 8.0s
  15:57:02  获取指数历史: symbol=sh000300 ...
  15:57:19  指数历史数据: 29 条                                  ← 17.0s
  15:57:19  上述 11 个端点同时返回（均 32.6s）
  ```
- 即：**同一条请求链路里串行执行了 3 个慢同步外部调用**（2×行情 8s + 1×指数历史 17s）。
- 恢复发生在 **20:00 前后**（20:05 起 0 慢请求），**早于 20:14:54 的重启** —— 是外部源自行恢复，重启不是解药。
- 看板插件侧 HTTP 超时 4s → 那 33s 里它的 5 个取数请求全部超时，`Promise.allSettled` 回退成空值。

**根因一句话**：休市日仍走网络取价，且这些调用**同步、串行、无缓存**地跑在请求链路里，而承载它的 FastAPI 路由是 `async def` 却直接调用同步方法 —— 既慢又阻塞整个进程。

### 1.2 深层问题：市况判断分散成 40 处，且互相矛盾

| 类别 | 现状 | 锚点 |
|---|---|---|
| **日级两套真源** | `TradingDayGuard`（8 个调用方，2026-09-11 收敛）vs `TradingCalendarService`（6 个生产调用方） | `application/services/trading_day_guard.py`；`application/services/trading_calendar_service.py` |
| **假日历被当真相缓存** | `TradingCalendarService` provider 失败时静默降级为"周一~周五"，并把该错误日历按 **24h TTL 写进 Redis + 内存** → 法定节假日被当交易日 | `trading_calendar_service.py:108-134` |
| **时段常量 6 份复制** | `(9:30,11:30),(13:00,15:00)` 各自复制 | `account_trading_service.py:29-32`、`trade_guard_service.py:60-63`、`intraday_monitor.py:137-141`、`watch_engine/engine.py:118-119`、`watch_engine/digest_service.py:53-57`、`orchestrator_bootstrap.py:30-33` |
| **另一套相位模型** | `Phase` 枚举 + `PHASE_SCHEDULE`（08:30/09:25/09:35/15:00/15:05/15:30/16:30） | `daily_orchestrator.py:37-66` |
| **同一时刻结论相反** | `Phase.INTRADAY(9:35–15:00)` 把午休算作盘中；`market_monitor_scheduler` 把 11:30–13:00 当静默宵禁 | `daily_orchestrator.py:51` vs `market_monitor_scheduler.py:86-90` |
| **午休三种口径** | 11:30–13:00 / 无午休 / 以 12:00 为界 | `market_monitor_scheduler.py:87`；`daily_orchestrator.py:51`；`strategy_code_service.py:1476` |
| **时区** | ≥14 处 naive `datetime.now()`；唯一正确处在 scheduler，但同文件混用 UTC | `scheduler.py:191-214` vs `:335/341/367/415/481` |
| **行情双轨** | v1 走 `DataProviderManager`（无缓存无熔断，看板/下单在用）；v2 自建 provider **绕开 `DataProviderManager`**（仅盯盘） | `realtime_quote_service.py`；`realtime_quote_service_v2.py`；`application/services/quote_providers/` |
| **幽灵调用** | `realtime_signal_service.py:55` 调 `MarketDataService.get_realtime_quote`，该方法**不存在** → AttributeError 被 `:72` 吞 → 静默"无法获取实时价格" | 已复核 |
| **孤儿表** | `quant.daily_quotes` 全仓零引用（无 DDL、无 ORM、无读写） | 已复核 |

**已造成过的真实事故**（`trading_day_guard.py` 模块 docstring 自陈）：2026-08-08 周六 5 个账户被写入净值快照；2026-08-12 用"当日日K是否落库"当唯一判据导致 v13/v14 调仓永不执行却记 success；`fund_flow_update_job.py:113` 拿墙钟当 `trade_date` 两次污染。

**并行事实（本 RFC 的一处注意点）**：`quant.index_daily`（2026-09-11 从日线拆出）当前 **2497 行、最新 `2026-09-10`**，比个股日线（`quant.daily_klines` 最新 09-11）**晚一天**。基准改读本地时须处理这一天差（见 D7）。

---

## 2. 目标与非目标

**目标**
1. 把"市况判断"收敛为**唯一入口**，对外只回答：现在是什么相位、是否开市、价格是否需要新鲜。
2. 取价按**开市 / 非开市两态**分流：非开市**只读本地、绝不联网**；开市优先本地分钟收盘，网络仅作**请求路径之外**的有界刷新。
3. 消除请求链路里的同步阻塞（`async def` 直接调同步方法）。
4. 基准指数改读本地表，消掉那 17s。
5. 行情双轨收敛为一条（**删除 v2，归一到 `DataProviderManager`**）。
6. 给"价格是否陈旧"以正确语义（休市日读到上一交易日收盘价 **不是** 陈旧）。

**非目标（明确不做，避免扩大重构）**
- 不修 `infrastructure/scheduler/scheduler.py` 内部 UTC/北京混用（与市况无关，单独排期）。
- 不改回测/契约工具（`tools/check_data_contracts.py`、`domain/backtest/stages/.../time_alignment_stage.py`）——误判只影响离线产物。
- **不改 `Phase` 枚举成员名**（其**值**已落库在 `daily_orchestrator_state.current_phase`）。
- 不新增指数 provider（`quant.index_daily` 已存在且可读）。
- **不改 agent-dh（跨仓）**：`packages/genome/src/guard.ts:155-183` 的自算时段与各处写死文案属**跨仓后续工作线**；本方案只改 quantsys-v2。
- 本工作线**只产出本文档**，不改代码。

---

## 3. 决策

### D0 限界上下文与统一语言（统摄 D1–D3、D10）
- **限界上下文**：复用**已存在**的 `domain/trading/`（RFC 015 §1 明确"复用已存在的 trading 限界上下文"），不新开上下文。
- **统一语言**：市况（MarketSession）、相位（SessionPhase）、开市（open）、价格新鲜窗口（price fresh window）。此后全仓不得再用裸常量"9:30–11:30 / 13:00–15:00"表达市况。
- **领域层纪律**（对齐 RFC 015 §1）：领域层零外部依赖（仅 `abc`/`typing`/标准库）；应用层构造函数**局部导入**具体实现（DI），类型注解一律用端口 ABC；`grep -rn "adapters.outbound" domain/ application/` 须零命中（ADR-001 红线）。

### D1 午休唯一口径：11:30–13:00 不属于盘中
- `MORNING=[09:30,11:30]`、`LUNCH_BREAK=(11:30,13:00)`、`AFTERNOON=[13:00,15:00]`。
- `is_market_open()` 仅 MORNING/AFTERNOON 为真 → 与既有硬护栏 `TRADING_SESSIONS` 各实现**逐字一致**。
- 边界闭合沿用 `start<=t<=end`（11:30 与 15:00 算盘中），**不改语义**，以免打翻 `tests/test_trading_window_guard.py` 的既有断言。
- `PHASE_SCHEDULE` 窗口**不动**（它是编排器状态机）；只把 `daily_orchestrator` 内"是否该跑盘中任务"改为查 `MarketSession`。撮合硬门槛 `>=9:31`（`:166/357`）保持不动。

### D2 DDD 分层：值对象 + 领域策略在 domain，编排在 application
沿用仓库既有形态——`TradingStatus`（冻结 VO，`domain/trading/models/trading_status.py`）与 `TradingStatusPolicy`（领域策略，`domain/trading/services/trading_status_policy.py`）：

| 层 | 构件 | 落点 |
|---|---|---|
| domain（值对象） | `SessionPhase(str, Enum)` + `@dataclass(frozen=True) MarketSession` | `domain/trading/models/market_session.py` |
| domain（领域策略） | `MarketSessionPolicy.evaluate(now, is_trading_day, *, day_source, day_degraded) -> MarketSession`；边界常量**唯一出处** `SESSION_BOUNDS` | `domain/trading/services/market_session_policy.py` |
| domain（端口） | `IMarketClock`（新增）；`ITradingCalendar`（**已存在，签名零改动**） | `domain/trading/ports/` |
| application（编排） | `MarketSessionService`：取日级判定 + 取时钟 → 调策略 → 按 RFC 015 契约输出 | `application/services/market_session_service.py` |
| adapters（出站） | `BeijingClock(IMarketClock)` | `adapters/outbound/clock/beijing_clock.py` |

判定的**唯一实现**在 `MarketSessionPolicy`（纯函数、零 IO、可单测）；应用层只做编排，**不得再自算时段或 weekday**。

### D3 值对象形状（对标 `TradingStatus`）
```python
@dataclass(frozen=True)
class SessionWindow:            # 值对象：相位开始/结束 —— "开始时间"的唯一出处
    phase: SessionPhase
    start: time
    end: time

@dataclass(frozen=True)
class MarketSession:
    at: str                     # 判定时点 ISO8601（对齐 TradingStatus.as_of）
    day: str                    # YYYY-MM-DD
    phase: SessionPhase
    is_trading_day: bool
    is_market_open: bool        # 注意：不叫 is_open —— 该名已被熔断器占用（circuit_breaker.is_open / manager.py:531）
    is_price_fresh_window: bool
    phase_start: str            # 当前相位开始 HH:MM（= SessionWindow.start）
    phase_end: str              # 当前相位结束 HH:MM
    next_boundary_at: str       # 下一相位边界 ISO8601
    elapsed_trading_minutes: int
    session_progress: float     # elapsed/240，0~1
    source: str                 # 'clock' + 透传日级 source（kline-data / intraday-recent-market / ...）
    degraded: bool              # 任一环节降级必须可见（R-013）
    reason: str                 # 人可读、可复核（对齐 TradingStatusPolicy 的 reason 组装风格）
    def to_dict(self) -> dict: ...
    def price_is_fresh(self, as_of: str) -> bool: ...   # D4 的判定也属领域规则，不下沉到应用层
```
- `is_price_fresh_window` = 交易日 且 `CALL_AUCTION <= phase <= AFTERNOON`（09:15–15:00 + 收盘后 5 分钟宽限）——比 `is_market_open` 宽，因为集合竞价期间价格已在变。
- `reason` 必须写明判定依据与降级原因。

### D4 价格"新鲜"的正确定义（看板空值的真正修法）
- `expected_price_date` = 最近一个交易日（`TradingDayGuard` 判定）。
- **非开市**：`stale = (as_of_date < expected_price_date)`。**休市日读到上一交易日收盘价 → `stale=False`**（"已收盘最终价"）。现有 `simulation_service.py:196` 把"没联网取到"一律标 stale，语义错。
- **开市**：`stale = 分钟K新鲜度超阈值 或 无分钟K`（默认阈值 5 分钟，可配）。

### D5 两态取价门面（`application/services/market_price_facade.py`）
- `get_prices(symbols, now=None) -> Dict[str, PricedQuote]`，`PricedQuote(symbol, price, as_of, as_of_source, source, stale, phase, fetched_at)`。
- **非开市 → 只读本地，绝不联网**：批量 `kline_repository.get_latest_daily_klines_batch(symbols)`（`adapters/outbound/repositories/kline_repository.py:484`）一次查回（避免 N+1）；缺口回退 `chip_repository.get_latest_close(symbol)`（`:68`）；`as_of=trade_date`。
- **网络侧批量接口已存在**：`domain/ports/datasource_ports.py:31` 的 `IQuoteProvider.get_batch_quotes(symbols) -> Dict[str, QuoteData]` —— 开市态的有界刷新接此端口，**不新造批量接口**。
- **开市 → 优先本地分钟收盘** `kline_repository.get_latest_minute_kline(symbol)`（`:786`），`as_of=trade_datetime`；达标即返回，**零网络**。
- **网络只作有界刷新、不在请求路径**：由既有 `minute_kline_sync`（`application/jobs/refresh_jobs.py:85`，已在采"持仓∪盯盘"标的写 `quant.minute_klines`）承担。
- 消除 `simulation_service._price_timestamps` 的**实例副作用**（`:175/258`，并发请求互相覆盖）；as-of 由返回值携带。注意 `QuoteData.timestamp` 是 `str`，**不要**从它反解析。

### D6 行情双轨收敛：删除 v2，归一到 `DataProviderManager`
- 把 `realtime_quote_service_v2.py:29-125` 的 `CircuitBreaker`(60s) 与 `QuoteCache`(5s) **原样搬到** `application/services/quote_infra.py` 给 v1 装上；v1 保持 `DataProviderManager.get_quote`（`manager.py:621-630`）为唯一出口。门面层熔断位于 manager 的 10 次/300s（`:235-237`）**之前**。
- `watch_engine/factory.py:14/116` 由 `RealtimeQuoteServiceV2()` 改 `RealtimeQuoteService()`；随后**删除** `realtime_quote_service_v2.py` 与 `application/services/quote_providers/`。仓库规则禁止 `_v2` 并行文件，故是"删除"而非"并存"。
- 顺带**获得可观测性**：v2 的 `get_stats()` 此前无路由暴露，收敛后统一由 `GET /api/provider/health` 观察。
- 修幽灵调用：`realtime_signal_service.py:55` 改调门面（不要"补上" `MarketDataService.get_realtime_quote`）。

### D7 基准指数改读本地（去掉 17s，**不需要新 provider**）
- `quant.index_daily` 已存在，`kline_repository.get_index_daily_klines(symbol,start,end)`（`:312`）已实现读取。`benchmark_comparison.fetch_benchmark_klines`（`application/services/benchmark_comparison.py:124-151`）改为**先读本地**；`'sh000300'` 需规范化为 `'000300.SH'`（`utils/symbol_classifier.resolve_index_symbol`）。
- **注意一天差**：`quant.index_daily` 当前最新 `2026-09-10`，落后个股日线一天。因此需补一个写入任务（`index_daily_sync`，复用 `manager.get_index_daily`，`manager.py:861-863`）保证与日线同步；对齐失败时基准块降级为 `None`（既有行为）。
- 本地不足才回退网络，且 `allow_network: bool = False` 为默认 —— **请求路径永不联网**。
- 修缓存键缺陷：`:135` 的 `symbol|start|end` 会随 `series[-1][0]` 漂移使日缓存形同虚设 → 改按 `(account, 最后快照日)` 缓存 + 5 分钟 TTL。

### D8 解除事件循环阻塞（机制已验证）
- `adapters/inbound/fastapi_app/routes/simulation_async.py:264` 的 `async def get_account` → **改为 `def get_account`**。依据：`main.py:442-479 install_sync_session_cleanup()` 给**同步**端点包 `run_in_threadpool` + `finally close_session()`，且 `:473` 显式 `if asyncio.iscoroutinefunction(call): continue` **跳过 coroutine 端点** → 改 `def` 既离开事件循环，又免费拿到 session 清理。同批处理 `:235 run_strategy`。
- 备选（须保留 async 签名时）：`await run_in_threadpool(get_service().get_account_status, account_name)`。

### D9 日级收敛与缺陷修复
- `TradingCalendarService` 的 6 个生产调用方改走 `MarketSession`；区间语义（`get_trading_days`）由新增 `MarketSession.trading_days_in_range(start,end)` 承接（逐日走 `TradingDayGuard`，返回 `List[str]` 不变）。
- **必须修掉** `trading_calendar_service.py:108-134`：降级结果**不得落缓存**（或 TTL 降到 60s 且带 `degraded` 标记）。
- `ITradingCalendar` 端口（`domain/trading/ports/ITradingCalendar.py`）**签名零改动**（`str` 入参，且被 `tests/integration/test_data_completeness.py` 9 处 patch）；新建 `application/services/trading_calendar_guard_adapter.py` 适配，`TradingCalendarService` 标 deprecated 并退出生产路径。

### D10 唯一北京时间时钟：**端口**而非工具函数
`domain/trading/ports/IMarketClock.py`（新增）：`now() -> datetime`、`today() -> date`，语义固定为 Asia/Shanghai。
- 出站适配器 `adapters/outbound/clock/beijing_clock.py` 实现之（`ZoneInfo("Asia/Shanghai")`，写法同 `scheduler.py:207`）。
- 领域策略**不取系统时间**——`now` 一律由调用方注入，保持纯函数与可单测（对齐 `TradingStatusPolicy` 的显式入参风格）；测试注入固定时钟，避免"非交易时段跑必假失败"。
- **分批替换**关键路径：守卫、编排器（`daily_orchestrator.py:119`）、watch（`engine.py:132`）、下单（`account_trading_service.py:119`）、门面新鲜度判定；其余 ~14 处 naive `now()` 按 grep 输出分批，每批独立 PR + 单测。
- 现状：领域层**尚无**时钟端口（`domain/ports/` 仅 `datasource_ports`/`ml_model_port`/`repository_ports*`），`domain/trading/ports/` 亦无；本端口为新增。

### D11 `Phase` 兼容红线
- 已复核 `Phase`/`PHASE_SCHEDULE` **无外部消费者**，但 `daily_orchestrator_state.current_phase` **落库的是枚举值字符串** → **成员名冻结**，只改窗口与语义，并在模块 docstring 与 `_determine_phase`（`:596-608`）注明 `INTRADAY` 语义收窄。

### D12 对齐 RFC 015 的既有硬约束（不另立一套）
市况/取价是本仓已存在能力的**补强**，须复用 RFC 015 已定的口径，而非并存第二套：
- **响应契约**（RFC 015 §1.5.3）：输出统一带 `source` / `degraded` / `stale` / `as_of`；市况 VO 的 `at` 即 `as_of`。
- **本地 DB 兜底作为最后一级**（RFC 015 §1.5.2 第 4 条）："非开市只读本地"正是 `stale-while-error` 档位，须**显式标 `stale`** 而非静默当作实时。
- **失败与空结果语义分离**（RFC 015 §1 纪律第 4 条）：`TradingCalendarService` 的"静默降级为周一~周五"直接违反该条，D9 的修复即为此。
- **不新开限界上下文、不新起并行链路**（RFC 015 §1/§1.5.2 第 2 条）。

### D13 命名红线（已核实占用情况，避免二次撞名）
- **`market_phase` 不可用**：该名在 v2 **已被占用**，含义是 **Wyckoff 市场阶段**（`accumulation`/`markup`/`distribution`/`markdown`，见 `battlefield_assessor.py:447-497`、`opponent_behavior_service.py`、`market_sentiment_service.py`），且 **agent-dh 的 `OpponentBehaviorTool` 已在消费它**。本设计的对外字段一律用 **`session_phase`**（值 `morning`/`lunch_break`/`afternoon`/…）。
- **`is_open` 不可用于对外字段/方法名**：已被熔断器占用（`adapters/outbound/datasources/circuit_breaker.py:110`、`manager.py:531`、`datasource_ports.py:423`）。本设计用 **`is_market_open`**。
- **`is_trading_time` 是要被替换掉的旧名**（`intraday_monitor.py:137`、`watch_engine/engine.py:118`、`watch_engine/digest_service.py:53` 共 7 处），收敛后不再新增。
- 已核实**零占用**可安全使用的名：`session_phase` / `trade_session` / `market_session` / `trading_phase` / `session_state`。

---

## 4. 分层与新增模块（DDD / 六边形）

```
domain/trading/models/market_session.py            # 值对象：SessionPhase + SessionWindow + MarketSession（冻结，含 to_dict/price_is_fresh）
domain/trading/services/market_session_policy.py   # 领域策略：市况判定的唯一实现（纯函数，零 IO）
domain/trading/ports/IMarketClock.py               # 端口：北京时间时钟（新增）
domain/trading/ports/ITradingCalendar.py           # 端口：日级真源（已存在，签名零改动）
adapters/outbound/clock/beijing_clock.py           # 出站适配器：IMarketClock 实现
application/services/market_session_service.py     # 应用层：编排（日级判定 + 时钟 → 领域策略）
application/services/quote_infra.py                # QuoteCache / CircuitBreaker（自 v2 原样搬入）
application/services/market_price_facade.py        # 两态取价门面（应用层编排）
application/services/trading_calendar_guard_adapter.py  # ITradingCalendar 适配器（端口签名不变）
```

**依赖方向**：`adapters/inbound → application → domain ← adapters/outbound`（DIP）。
**红线**：`domain/` 不得 import `application/` 或 `adapters/`；领域层零外部依赖。新增模块均须通过 `grep -rn "adapters.outbound" domain/ application/` 零命中的检查。

---

## 4.5 领域设计详表（接口 / 用例 / 开始时间 / 上下文关系）

### 4.5.1 接口（端口）清单

| 接口 | 位置 | 方法签名 | 实现方 | 状态 |
|---|---|---|---|---|
| `IMarketClock` | `domain/trading/ports/` | `now() -> datetime`（tz-aware，Asia/Shanghai）、`today() -> date` | `adapters/outbound/clock/beijing_clock.py` | **新增** |
| `ITradingCalendar` | `domain/trading/ports/ITradingCalendar.py` | `is_trading_day(day_str) -> bool`、`get_trading_days(start,end,exchange) -> List[str]` | `trading_calendar_guard_adapter.py` | **复用，签名零改动**（9 处测试 patch 依赖它） |
| `IQuoteProvider` | `domain/ports/datasource_ports.py:31` | `get_quote(symbol)`、**`get_batch_quotes(symbols) -> Dict[str, QuoteData]`** | `DataProviderManager` 下各 provider | **复用**——批量取价接此端口，**不新造** |
| `IMinuteKlineRepository` | `domain/trading/ports/` | `get_latest_minute_kline(symbol) -> Optional[MinuteKline]`、`get_minute_klines(...)`、`save_minute_klines(...)` | `adapters/outbound/repositories/minute_kline_repository.py` | **复用** |
| `IKlineRepository` | `domain/ports/repository_ports.py:19` | `get_kline_data(...)`、`batch_get_kline(...)`、`get_index_daily_klines(...)`（`kline_repository.py:312`） | `adapters/outbound/repositories/kline_repository.py` | **复用** |
| `ITradingStatusRepository` | `domain/trading/ports/` | `get_stock_status(symbol) -> Optional[dict]` | 现有 | 复用（下单 fail-closed 链路） |

**领域服务（无端口、纯函数、零 IO）**：`MarketSessionPolicy`。
**应用服务（只做编排）**：`MarketSessionService`。

### 4.5.2 业务/用例清单（谁要什么）

| 用例（`MarketSessionService` 方法） | 语义 | 消费方（锚点） |
|---|---|---|
| `current(now=None) -> MarketSession` | 市况快照（相位/开市/价格新鲜窗口/降级） | 看板、监控、编排器 |
| `is_market_open(now=None) -> bool` | 连续竞价中（下单硬约束） | `watch_engine/engine.py:133/186`；`account_trading_service._check_trading_window:89-110`；`domain/trading/services/trade_guard_service.py:94-127` |
| `session_start_of(phase) -> time` | **相位开始时刻** | `daily_orchestrator.py:730-731`（补跑判据 `now.time() >= phase_start`） |
| `elapsed_trading_minutes(now) -> int` | 当日已交易分钟（午休不计，满 240） | `watch_engine/engine.py:30-45` 的 `elapsed_trading_fraction` 迁移至此 |
| `session_progress(now) -> float` | `elapsed/240`（0~1） | 同上（volume_surge 同期均量折算，`engine.py:439`） |
| `next_boundary_at(now) -> datetime` | 下一相位边界 | 编排器相位流转、调度对齐 |
| `is_price_fresh_window(now=None) -> bool` | 报价是否在变（09:15–15:00） | 取价门面 |
| `expected_price_date(now=None) -> date` | 期望价日期 = 最近交易日 | 取价门面（D4 的 `stale` 判据） |
| `trading_days_in_range(start,end) -> List[str]` | 区间交易日 | `data_gap_detector`、`data_quality_service`、`signal_tracking_service`、`manager.py:1304-1306` |
| `assert_can_trade()` | 下单前置 fail-closed | `portfolio_trade` 链路 |
| `assert_daily_write_allowed() -> bool` | 净值快照守卫（**唯一真源**，复用 `TradingDayGuard.should_write_daily` 语义） | `live_trading/simulation_trader.py:389` |

### 4.5.3 "开始时间"的领域设计（本次新增的一等概念）

**问题**：现有代码把"开始"混为一谈，至少 3 处不一致——

- `watch_engine/engine.py:27-45`：硬编码 `TOTAL_TRADING_MINUTES=240`，用 09:30 / 13:00 作起点；
- `daily_orchestrator.py:48-55`：`PHASE_SCHEDULE` 以 **09:25** 作 `MARKET_OPEN` 起点，却在 `:166/:357` 用 `>= 9:31` 硬门槛兜"进了阶段但不撮合"；
- `tools/register_jobs_to_agent_os.py:286-305`：风控窗口 **10:00–14:30**（只在 cron 表达）。

**建模**：新增值对象 `SessionWindow(phase, start: time, end: time)`，由 `SESSION_BOUNDS` **唯一持有**；`MarketSessionPolicy.window_of(phase) -> SessionWindow`。

**必须区分三种"开始"**（现有 `Phase` 把三者揉在一起，才需要 9:31 硬门槛兜）：

| 语义 | 时刻 | 谁需要 |
|---|---|---|
| 可报价开始（集合竞价） | **09:15** | `is_price_fresh_window` 起点（价格已在变） |
| 可撮合开始（开盘） | **09:25** | `daily_orchestrator` 的 `Phase.MARKET_OPEN` |
| 可连续交易开始 | **09:30** | `is_market_open`（下单硬约束）、`elapsed_trading_minutes` 起点 |

**`MarketSession` 承载开始/边界字段**（各处不再自算）：
```
phase_start: str              # 当前相位开始 HH:MM（= SessionWindow.start）
phase_end: str                # 当前相位结束 HH:MM
next_boundary_at: str         # 下一相位边界 ISO8601
elapsed_trading_minutes: int
session_progress: float       # elapsed/240
```

**交易分钟口径**（唯一出处）：以 09:30 / 13:00 为相位起点，上午/下午各 120，全日 240；**午休不计**；非交易日与盘前为 0，收盘后为 240。

**收敛动作**：`PHASE_SCHEDULE` 保留为"编排器生命周期"（含盘后 15:30/16:30/17:30），但其**市况相关边界（09:25–15:00）改为引用 `SESSION_BOUNDS`**；10:00–14:30 归**调度层窗口**（cron 表达）——不引入领域概念，只要求与 `SESSION_BOUNDS` 一致并加断言。

### 4.5.4 上下文关系图（Context Map）

```
                  ┌───────────────────────────────────────────────┐
                  │ domain/trading/   ← 共享内核（Shared Kernel）  │
                  │  MarketSession (VO) + MarketSessionPolicy     │
                  │  依赖端口：IMarketClock / ITradingCalendar     │
                  └───────────────────────────────────────────────┘
                     ▲                ▲                 ▲
        同进程直接依赖 │                │                 │
        ┌────────────┘                │                 └────────────┐
   domain/watch              domain/portfolio                 application/*
   （盯盘 tick /                （估值 / 净值快照守卫）        （取价门面 / 明细 / 风控调度）
     均量折算）
                                                                    │
                                          发布语言（Published Language）│ /api 契约
                                                                    ▼
                                                    agent-dh 工具层（跨仓）
                                                    session_phase / is_market_open / price_fresh / as_of
```

**三种关联关系，各自的口径：**

1. **共享内核（同进程，v2 内）**：`domain/{watch,portfolio,risk,backtest}` 与应用层**直接 import** `domain/trading/` 的 VO 与策略（同语言、同进程）。**不设应用层包装器** —— 否则就是第二套判定。
2. **发布语言（跨仓 → agent-dh）**：经 `/api` 响应暴露 `session_phase` / `is_market_open` / `price_fresh` / `as_of`，供 agent-dh 消费。
   **本方案不改 agent-dh**（跨仓，另开工作线）。此处仅记录待办依据：`packages/genome/src/guard.ts:155-183` 的 `checkTradingHours()` 是第 4 套独立实现且与 v2 有边界分歧（它对 11:30 判否，`intraday_monitor` 判是），另有写死文案（`genome/src/index.ts:211`、`evolver/.../PromptEvolverTool.ts:293`、`trading/.../PortfolioTradeTool/prompt.ts:68`）。
3. **调度层（cron）**：`tools/register_jobs_to_agent_os.py` 的窗口（如风控 10:00–14:30）与市况是**对齐关系**，不是依赖关系——领域层**不得**反向依赖调度。

---

## 5. 实施路线图（供后续工作线，每阶段独立 commit）

### 阶段 1 · 地基（纯新增，行为等价，可独立合入）
顺序：`domain/trading/models/market_session.py`（VO）→ `domain/trading/services/market_session_policy.py`（策略）→ `domain/trading/ports/IMarketClock.py` + `adapters/outbound/clock/beijing_clock.py`（端口与适配器）→ `application/services/market_session_service.py`（编排）；`trading_day_guard.py` 两处 `now()` 改走时钟注入。
- 验证：新增 `tests/test_market_session_policy.py`（**纯函数单测**：午休、9:15/9:25/9:30/11:30/13:00/14:57/15:00 边界、周末、`is_price_fresh_window` 与 `is_market_open` 差异、`reason` 含降级原因），范式抄 `tests/test_trading_day_guard.py`（打桩数据源，不碰真实 DB）。
- 回滚：纯新增 + 两处等价替换，单 commit revert。

### 阶段 2 · 止阻塞 + 取价统一 + 看板修复（用户可见收益）
`simulation_async.py:235/264` 改 `def`；新增 `quote_infra.py` + `market_price_facade.py`；`simulation_service.py:136-275` 改走门面并重定义 `price_stale`；`benchmark_comparison.py` 改读本地；修 `realtime_signal_service.py:55`。
- 验证：见 §6。
- 回滚：门面加 `MARKET_PRICE_FACADE_ENABLED`（默认 true），置 false 时回退老路径；路由 `def` 改动单独 commit。

### 阶段 3 · 日级收敛 + 判定点批量替换 + 删双轨
`TradingCalendarService` 6 个调用方 → `MarketSession`；修其降级缓存缺陷；`ITradingCalendar` 走适配器；6 份时段常量与 naive 时钟分批替换；删除 `realtime_quote_service_v2.py` 与 `quote_providers/`（删前跑 `grep -rn "RealtimeQuoteServiceV2\|quote_providers"` 与全量 pytest）。
- 验证：`venv/bin/pytest -q`；巡检 `grep -rn "datetime.now()\|date.today()" domain/trading/services/market_session_policy.py application/services/market_session_service.py` 期望 0 命中（时间一律经 `IMarketClock` 注入）。

---

## 6. 验收标准

**功能**
```
curl -s -w '\n%{time_total}s\n' 'http://127.0.0.1:5001/api/simulation/accounts/agent_virtual'
```
休市日期望：**<1s**、`price_stale=false`、`session_phase='after_hours'`、`positions[].price_updated_at` 非空、`positions` 有值。

**契约（必须写成测试）**
- 非开市日 monkeypatch `DataProviderManager.get_quote` 抛异常 → 门面**不抛**、返回本地价、`stale=False`。（"休市日不联网"的守护）
- 开市日不发起网络（本地分钟K达标即返回）。
- 时间依赖用例必须注入固定 `now_fn`（范式：`tests/test_multi_account_domain.py:9-23`），否则非交易时段必假失败。

**回归**
```
cd quantsys-v2 && source activate-py313.sh
venv/bin/pytest tests/test_trading_day_guard.py tests/test_trading_window_guard.py \
  tests/services/test_simulation_service_contract.py tests/integration/test_data_completeness.py -v
venv/bin/pytest -q
```

**运维**：`GET /api/provider/health`（行情源健康）、`GET /api/jobs/inprocess/status`（当日任务）、`GET /api/health/routes`（路由降级可见性）、`GET /api/risk/circuit-breaker`；日志 `logs/launchd-stdout.log` 查 `market_session_*` / `price_facade_*` 事件。

---

## 7. 兼容性与风险

| 风险 | 说明 | 缓解 |
|---|---|---|
| `ITradingCalendar` 端口被 9 处测试 patch | 改签名会连带炸测试 | 端口签名**零改动**，用适配器包装 |
| `daily_orchestrator_state.current_phase` 落库字符串 | 改枚举成员名会让存量行读不出 | 成员名冻结，只改窗口与语义 |
| `should_write_daily` 是净值快照唯一守卫（2026-08-08 事故） | 引入第二日级真源，节假日又会被写快照 | `MarketSession` 日级判定**必须**委托 `TradingDayGuard.check`，禁止自算 weekday |
| 删除 v2 行情实现 | 可能漏掉非 grep 命中的动态引用 | 删前复核 + 全量 pytest；已核实仅 `watch_engine/factory.py` 在用 |
| `def` 改造影响同文件其他端点 | 签名不一致 | 只改 `:235/:264`，其余轻端点保持 `async` |
| 非开市"不联网"可能让分钟K停更 | 分钟K靠 `minute_kline_sync` 采集 | 其调度应只落交易日（若非，顺手加 `TradingDayGuard` 守卫） |
| `quant.index_daily` 落后日线一天 | 基准对齐可能少一天 | 补 `index_daily_sync` 写入任务；不足时基准块降级为 `None`（既有行为） |
| `price_stale` 语义变化影响前端 | 休市日从"空值"变"有值 + 明确 as-of" | 响应新增 `price_as_of`/`session_phase`；`price_stale` 只放宽不收紧（休市日 true→false 是修复） |

---

## 8. 交易时段判定点清单（**仅 quantsys-v2**）

> **范围**：本节只列"交易时段 / 交易日"判定点，且**只含 v2 路径**（跨仓的 agent-dh 见 §4.5.4，属范围外）。
> **非时段类改动**（请求路径阻塞、两态取价、基准指数、行情双轨）见 D5/D6/D7/D8，**不在本节**（清单见 §8.4）。
> 每一行都已核实**是活代码**（调用方已验证，非静态死代码）。

### 8.1 时段常量 → 收敛到 `SESSION_BOUNDS`（10 处 · **要改**）

| # | 站点 | 现状（常量/判定） | 消费方（活） |
|---|---|---|---|
| 1 | `application/services/account_trading_service.py:29-31`（`:99` 使用） | `TRADING_SESSIONS = (9:30,11:30),(13:00,15:00)` | 下单闸门 `_check_trading_window` |
| 2 | `domain/trading/services/trade_guard_service.py:60-62`（`:122` 使用） | 同上 | `validate_trading_window` |
| 3 | `application/services/intraday_monitor.py:137-141` `_is_trading_time` | `9:30–11:30 / 13:00–15:00` | `check():59` |
| 4 | `application/services/watch_engine/engine.py:118-119` `is_trading_time` | 同上 | `:133`、`:186` |
| 5 | `application/services/watch_engine/engine.py:27-45` `TOTAL_TRADING_MINUTES=240` + `elapsed_trading_fraction` | 09:30 / 13:00 起点折算 | `:439`（volume_surge） |
| 6 | `application/services/watch_engine/digest_service.py:53-57` | 同上 + 周末 | `:252` |
| 7 | `application/services/daily_orchestrator.py:48-55` `PHASE_SCHEDULE`（+`:596-608`、`:730`） | 8 个边界；`INTRADAY 9:35–15:00` **跨午休** | `_determine_phase` / 补跑判据 |
| 8 | `application/services/market_monitor_scheduler.py:86-90` `_is_silent_time` | 午休 `11:30–13:00` | `:58` |
| 9 | `adapters/inbound/fastapi_app/orchestrator_bootstrap.py:25-35` | `8–17` 点纯 weekday / 简化时段 | `:45`、`:47` |
| 10 | `application/services/strategy_code_service.py:1476`（+`:1449`） | 以 `'12:00:00'` 作上午判据 | K 线聚合 flush |

**第 7 项待拍板**：窗口保留、只把市况相关边界改为引用 `SESSION_BOUNDS`（**我的主张**——`Phase` 值已落库、成员名冻结）；还是连窗口一并重构。

### 8.2 日级（4 处）

| # | 站点 | 处置 |
|---|---|---|
| 11 | `application/services/trading_calendar_service.py:159`（含 `:108-134` **假日历缓存 24h 缺陷**） | **要改**：收敛到统一入口 + 修缓存缺陷；保留为 `ITradingCalendar` 适配器 |
| 12 | `application/services/trading_day_guard.py:166` | **保留**为唯一日级真源（仅换时钟） |
| 13 | `domain/trading/ports/ITradingCalendar.py:15` | **保留**：端口签名零改动（9 处测试 patch 依赖） |
| 14 | `infrastructure/jobs/verification_job.py:46` | **保留**：已委托 Guard（`:55`），仅包装 |

**第 15 项待拍板**：`adapters/inbound/fastapi_app/daily_jobs_bootstrap.py:233 _last_trading_day`（纯 weekday 排除法；调用方 `:140`、`:278`、`application/services/scheduler_tasks.py:71/76`）——纳入本次收敛，还是留 C 类？

### 8.3 明确不改（已核实，均为 v2 内）

| 站点 | 依据 |
|---|---|
| `domain/backtest/engine/risk_rules.py:878-927` `check_trading_hours` | **仅 `tests/test_risk_engine.py` 引用，无生产调用方** → 回测专用 |
| `tools/check_data_contracts.py:239-261` | 离线契约工具，误判只影响产物 |
| `infrastructure/scheduler/scheduler.py`（`:335/341/367/415/481` UTC/北京混用） | 与市况无关，单独排期 |

### 8.4 非时段类改动（**不在本节**，见对应决策）

| 类别 | 决策 | 主要站点 |
|---|---|---|
| 请求路径阻塞 | D8 | `adapters/inbound/fastapi_app/routes/simulation_async.py:235/264` |
| 两态取价 | D5 | `application/services/simulation_service.py:136-275`、`market_price_facade.py`（新增） |
| 基准指数 | D7 | `application/services/benchmark_comparison.py:124-151` |
| 行情双轨收敛 | D6 | `realtime_quote_service.py` / `realtime_quote_service_v2.py` / `application/services/quote_providers/`、`watch_engine/factory.py:14/116` |
| 取价消费方 | D5 | `account_trading_service.py:44-49`、`live_trading/simulation_trader.py:1188-1196`、`realtime_signal_service.py:55`（幽灵调用） |

---

## 附：本文档的复核记录

以下 5 条"现状"断言在成文时已逐条复核：`Phase`/`PHASE_SCHEDULE` 无外部消费者（唯一命中是 `domain/factors/library/cycle.py:109` 的 Hilbert Phase 注释，无关）；`quant.daily_quotes` 全仓零引用；`MarketDataService.get_realtime_quote` 不存在；`quant.index_daily` 存在（2497 行，max `2026-09-10`）且 `kline_repository.get_index_daily_klines` 在 `:312`；`main.py:442-479 install_sync_session_cleanup` 覆盖同步端点、`:473` 跳过 coroutine。
