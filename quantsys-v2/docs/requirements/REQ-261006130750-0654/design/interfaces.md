# REQ-261006130750-0654 · 设计：接口与契约

**作用域**：`quantsys-v2/`（backend）
**本文件定死**：新增/改动的**函数签名、返回形状、错误语义、日志事件名**。
拆分阶段与实施阶段**不得**自行改签名；要改先回本设计。

## 1. 复用件：`application/services/trading_day_gate.py`（零改动）（serves: FR-3）

本需求**不改这个文件**，只调用它（它是 ②③ 已落地的唯一真源，E6）。

```python
def should_skip(policy: Optional[str], now: Optional[datetime] = None) -> Tuple[bool, Dict[str, Any]]
def verdict_info(now: Optional[datetime] = None) -> Dict[str, Any]
```

- `policy` 取值：`'always'` / `'trading-days'` / `'holidays'`；**本需求两处调用点一律传 `'trading-days'`**。
- 返回 `(skip, info)`；`info` 五键（外加未知策略时的 `policy_unknown`）：
  `day`(str, `YYYY-MM-DD`) / `is_trading_day`(bool) / `source`(str) / `degraded`(bool) / `reason`(str ≤200)。
- **永不抛**：门自身异常返回 `(False, {… 'source': 'gate-error', 'degraded': True …})` ⇒ 调用方**照跑**。
- **跳过判据（复核用）**：`trading-days` ⇒ `skip ⇔ is_trading_day=False and degraded=False`。
  实测（2026-10-06）：`check('2026-10-06')` → `False / trading-calendar-holiday / degraded=False` ⇒ skip；
  `'2026-09-30'` → `True / trading-calendar` ⇒ run；`'2026-10-07'` → `False / **future**` ⇒ skip
  （**未来日口径，不得当休市日判据**，见 §5 反例锁）。

## 2. 改动件：`adapters/inbound/fastapi_app/orchestrator_bootstrap.py`（serves: FR-1, FR-2, FR-3, FR-4, FR-6）

### 2.1 新增：循环层预过滤 helper（serves: FR-3, FR-6）

```python
def _should_run_today(now: datetime, *, path: str) -> Tuple[bool, Dict[str, Any]]:
    """A 层（循环）日级预过滤。fail-open：只有"日历明确答休市"才返回 (False, info)。

    - 判据唯一来源 = trading_day_gate.should_skip('trading-days', now)；
    - 返回 (run, info)：run = not skip；
    - 跳过时**按 (path, day) 去噪**记一条 info 日志（见 §2.4），不抛、不发通知。
    """
```

- `path` 取值**受控二值**：`'orchestrator_tick'` / `'intraday_monitor'`（同一常量集合，实施时定义在模块内）。
- **契约**：本函数**只有**一个判据来源；实现里出现 `weekday()`、直接读 `trading_calendar`、
  或第二份日历实现 = 违约（静态对账见 test-cases.md T8）。

### 2.2 不变：窗口函数（契约面）（serves: FR-4）

```python
def _in_orchestrator_window(now: datetime) -> bool   # 签名 + 语义（weekday<5 and 8<=hour<=17）逐字不变
def _in_intraday_window(now: datetime) -> bool       # 签名 + 语义（minute∈{0,30} + MarketSessionPolicy）逐字不变
```

### 2.3 改行为，不改签名：主循环（serves: FR-1, FR-2）

```python
def _monitor_loop(stop_event: threading.Event) -> None
```

每轮（60s）内的**判定顺序**（定死）：

```
now = datetime.now()
if _in_orchestrator_window(now):                       # ① 时段（不变）
    run, info = _should_run_today(now, path='orchestrator_tick')   # ② 日级（新增）
    if run: monitor_jobs.daily_orchestrator_tick()
if _in_intraday_window(now):                           # ① 时段（不变）
    run, info = _should_run_today(now, path='intraday_monitor')    # ② 日级（新增）
    if run: monitor_jobs.intraday_monitor_check()
```

- 异常与 session 清理语义**不变**（`try/except` + `finally: close_session()` 保持）。
- `_should_run_today` 自身**不抛**（`should_skip` 已保证）；即便它抛，也由既有 `except` 兜住并记 error，
  **不得**让 tick 线程退出。

### 2.4 新增：日志事件与去噪（serves: FR-6）

| 事件名（structlog `event`） | 级别 | 字段 | 触发 |
|---|---|---|---|
| `orchestrator_trading_day_skip` | `info` | `path` / `day` / `is_trading_day` / `source` / `degraded` / `reason` | 预过滤判 skip |

- 去噪状态：模块级 `_LAST_SKIP_LOG: Dict[str, str]`（key=`path`，value=`day`）；
  同一 `path` + 同一天**只记第一条**；`day` 变化即重置该 key。
- **不得**在 skip 路径发通知（`NotificationFacade` / 飞书 / agent 消息零调用）。

## 3. 改动件：`application/services/intraday_monitor.py`（serves: FR-1, FR-3, FR-5, FR-6）

### 3.1 新增常量（serves: FR-6）

```python
SKIP_REASON_NON_TRADING_DAY = 'non-trading-day'   # 与既有 'not trading time' 明确区分
```

### 3.2 改签名（**向后兼容**）：`check()`（serves: FR-1, FR-3）

```python
def check(self, now: Optional[datetime] = None) -> Dict[str, Any]:
    """now 缺省 = datetime.now()；显式传入仅供确定性单测与旁路调用。"""
```

### 3.3 判定顺序（**严格增量**，定死）（serves: FR-1, FR-3, FR-5）

```
now = now or datetime.now()
① 时段（既有，语义不变）：if not self._is_trading_time(now.time()): → {'status':'skipped','reason':'not trading time'}
② 日级（新增，权威）：      skip, info = should_skip('trading-days', now)
                            if skip: → 早退（不构造 PaperTradingEngine、不读持仓、不读价格、不写持仓市值）
③ 原有逻辑（不变）：持仓 → 价格 → 止损/止盈 → 大盘异动 → 超时 → 更新持仓市值
```

**为什么日级放在时段之后**：这样新分支**只在该函数原本会真干活的情况下**才触发
（原代码在此处已通过时段检查），行为改变面最小、回归风险最低（§5 的用例按此顺序断言）。

### 3.4 返回值形状（定死）（serves: FR-6）

| 情形 | 返回 |
|---|---|
| 非交易时段（既有） | `{'status': 'skipped', 'reason': 'not trading time'}`（**一字不改**） |
| 休市日（新增） | `{'status': 'skipped', 'reason': 'non-trading-day', 'timestamp': <iso>, 'trading_day': {day, is_trading_day, source, degraded, reason}}` |
| 无持仓（既有） | `{'status': 'no_positions', …}` |
| 无价格（既有） | `{'status': 'no_prices', …}` |
| 正常（既有） | `{'status': 'completed', …}` |

- `'skipped'` + `'non-trading-day'` 是与既有 `'not trading time'` **可区分**的第三态（FR-6：跳过必须认得出）。
- **不得**新增异常类型：日级门不抛；原有 `try/except` 包裹范围不变。

### 3.5 不变：`_is_trading_time(current_time: time) -> bool`（serves: FR-4）

保留 `phase_for(..., is_trading_day=True)` 的写法**不改语义**（它表达的是"时段"）；
仅把 docstring 里"日级仍由调用方（外层节拍闸门）把关"改为指向 `check()` 首部的权威日级门。

## 4. 调用方契约（谁调谁、给什么、回什么）（serves: FR-1, FR-2）

| 调用方 | 被调 | 变化 |
|---|---|---|
| `_monitor_loop` | `_should_run_today` → `monitor_jobs.*` | 新增日级预过滤（A 层） |
| `monitor_jobs.intraday_monitor_check()` | `IntradayMonitor.check()` | **签名不变**（`now` 用缺省） |
| `monitor_jobs.daily_orchestrator_tick()` | `DailyOrchestrator.tick()` | **零改动** |
| 旁路（补跑脚本 / 其它窗口 / 将来的新调度） | `IntradayMonitor.check(now=…)` | 被 B 层权威门拦住（返回 skipped） |

**无新增对外接口**：无 HTTP 路由、无 CLI、无环境变量、无配置项（FR-6）。

## 5. 口径与不变量（写死，验收照此判）（serves: FR-5）

1. **当日口径**：门只判 `now` 当天；**永不**把未来日期喂给守卫（`check(未来日).source == 'future'`）。
2. **反例锁**：`TradingDayGuard.check('2026-10-07').source == 'future'` 必须成立——
   谁若拿未来日的 `is_trading_day=False` 当"休市日"判据，用例即红。
3. **复市首日不跳**：`2026-10-08` 当**当天**判 → `quant.trading_calendar` 命中 ⇒ run。
4. **fail-open 不变量**：`degraded=True` ⇒ 两个调用点都必须 **run**，且日志/返回里带 `degraded=True`。
5. **不减少钱路执行**：交易日与降级日，A 层一律放行（与门装之前的调用次数相同）。
6. **唯一真源**：两处调用点各出现 `should_skip` 恰一次；`now.weekday()` 不出现在任何**新**判定逻辑里
   （`_in_intraday_window` 里那处是**既有**时段语义，保留）。
