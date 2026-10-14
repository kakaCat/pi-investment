# 接口设计（REQ-261006190953-fc43）

契约定死为准；签名里的 `→` 表示返回。**本文件不含实现代码**，只定签名、字段与错误语义。

## 1. 复用既有判据（`application/services/trading_day_gate.py`，不改）（serves: FR-1, FR-2）

本需求**不新增判据函数**，直接消费这三个既有入口（签名逐字照抄现行代码）：

```python
def verdict_info(now: Optional[datetime] = None) -> Dict[str, Any]
    # 五键: day / is_trading_day / source / degraded / reason；**永不抛**

def should_skip(policy: Optional[str], now: Optional[datetime] = None) -> Tuple[bool, Dict[str, Any]]
    # trading-days → 跳过 ⇔ is_trading_day=False 且 degraded=False；未知策略照跑；**永不抛**

def skip_non_trading_day(now: Optional[datetime] = None) -> Tuple[bool, Dict[str, Any]]
    # 等价 should_skip('trading-days', now)
```

**净值写入闸门 = `skip_non_trading_day(day)`**，不新增策略值。

## 2. 新建：`application/services/nav_series.py`（净值序列口径唯一实现）（serves: FR-3, FR-4, FR-5, FR-7）

```python
def trading_day_set(exchange: str = 'ALL', *, force_refresh: bool = False) -> Optional[Set[date]]
    """交易日集合。**不可得返回 None，绝不用空集合表达"不可得"**。

    数据源：TradingCalendarORMRepository().list_trading_days(exchange)。
    进程内 TTL 缓存（默认 300s；交易日历一天最多变一次）。
    读失败/空表 → None + warning（调用方必须按"未校验"处理，禁止当成"没有交易日"）。
    """

def filter_trading_days(
    rows: Sequence[Any],
    trading_days: Optional[Set[date]] = None,
    *,
    date_of: Callable[[Any], date] = _snapshot_date,
) -> List[Any]
    """过滤掉不在交易日集合里的行。`trading_days is None` → **原样返回**（未校验，不静默清空）。"""

def nav_returns_from_snapshots(
    snapshots: Sequence[Any],
    trading_days: Optional[Set[date]] = None,
) -> Tuple[List[float], int]
    """日收益序列 + 有效净值点数。**逐条语义**：

    1) 丢弃 total_value 为空或 <= 0 的行（沿用现行判据）；
    2) `trading_days` 非 None 时丢弃非交易日行（读取端兜底）；
    3) 按 snapshot_date 升序，相邻两点算 (v[i]/v[i-1]-1)；
    4) 返回 (returns, 参与计算的点数)。
    跨节假日的涨跌自然归到"复市首日 vs 上一交易日"这一段——不产生假日"日收益"。
    """

def nav_coverage(
    snapshots: Sequence[Any],
    trading_days: Optional[Set[date]] = None,
    *,
    max_listed: int = 20,
) -> Dict[str, Any]
    """净值序列覆盖率（**缺口口径唯一实现**）。返回："""
    # {
    #   'verified': bool,              # False = 无日历，未做交易日校验（必须显式可见）
    #   'points': int,                 # 落在交易日上的点数
    #   'from': str | None, 'to': str | None,
    #   'missing_trading_days': [str], # 区间内应有而缺失的交易日（最多 max_listed 条）
    #   'missing_count': int,
    #   'basis': str,                  # 人类可读口径说明
    #   'trading_day_source': str,     # 来自 verdict_info 的 source
    # }
```

**口径锁（写进测试）**：`trading_days=None` ⇒ `verified=False` 且 `missing_count=0`（**不是**"全缺失"）；
`trading_days=set()`（空集）⇒ 由 `trading_day_set()` 保证不会出现——空表必须返回 `None`。

## 3. 修改：`SimulationORMRepository`（写入闸门 + 交易日读取）（serves: FR-1, FR-2, FR-4, FR-5）

```python
def upsert_equity_snapshot(
    self, account_name: str, cash: float, position_value: float, total_value: float,
    daily_return: Optional[float] = None, cumulative_return: float = 0.0, drawdown: float = 0.0,
    snapshot_date: Optional[date] = None, commit: bool = True,
    force: bool = False,                      # ← 新增
) -> Optional[SimulationEquitySnapshot]:       # ← 返回类型放宽：None = 本次未写入
    """唯一写入闸门。

    force=False（缺省）且 skip_non_trading_day(day)[0] 为真 → **不落库**、返回 None、
    logger.info('skip_daily_write_non_trading_day', 五键注解)。

    force=True 仅限：运维迁移、从备份表回滚、测试构造历史序列——调用方必须显式书写，
    并在调用点写明理由（禁止把它当"绕过门"的常规开关）。
    """
```

```python
def get_equity_snapshots(
    self, account_name: str, limit: int = 90,
    *, trading_days_only: bool = False,          # ← 新增
    trading_days: Optional[Set[date]] = None,    # ← 新增（注入，仓储不自己查日历）
) -> List[SimulationEquitySnapshot]:
    """`trading_days_only=True` 语义（**与今天的差别写清**）：

    - **先**取该账户全部快照（上限沿用 `SNAPSHOT_DRAWDOWN_SCAN`）→ **再**过滤非交易日 → **最后**取尾部 `limit` 条；
    - 因此 `limit` 的含义由"快照行数"变为**交易日数**；
    - `trading_days is None`（日历不可得）→ **不过滤**并 warning，行为退回今天（不静默清空）。
    """
```

```python
def previous_valid_snapshot(self, account_name: str, before: date,
                           *, trading_days: Optional[Set[date]] = None
                           ) -> Optional[SimulationEquitySnapshot]:
    """基准快照按**交易日历**回退（FR-5）。

    现行实现是"比 before 小的最近一行"（docstring 自称"上一交易日"，实为"上一行"）。
    新增：`trading_days` 非 None 时，跳过非交易日行；None → 退回现行行为。
    残缺判据（total_value<=0 或 total_value<cash）不变。
    """
```

`calculate_daily_return` / `recompute_account_max_drawdown` **签名不变**，
内部改走交易日口径（`previous_valid_snapshot(trading_days=...)`、全序列过滤后再取峰谷）。

## 4. 修改：三个写入入口的返回结构（serves: FR-1, FR-8）

| 入口 | 今天的返回 | 之后（非交易日） |
|---|---|---|
| `DailySnapshotService.snapshot_all_accounts(target_date=None)` | `{'written': n, 'skipped': m, 'date': str}` | 增 `'refused': k`（被闸门拒写的账户数）与 `'trading_day': 五键`；`written` 不计被拒账户 |
| `PaperTradingEngine.take_daily_snapshot()` | 正常返回绩效 dict | `{'skipped': True, 'reason': str, 'trading_day_source': str, 'trading_day': 五键}`（**必须处理 snap=None**，不得 AttributeError） |
| `EquitySnapshotJob.run(target_date=None)` | `{'skipped': bool, 'target_date': str, 'reason'|'result'}` | 形状不变；`_has_bar` 由"交易日代理判据"降级为**"是否已收盘"辅助判据**，交易日判定走闸门；`reason` 文案区分"非交易日"与"未收盘" |

## 5. HTTP 契约：`POST /api/risk/metrics`（serves: FR-4, FR-8）

**请求**（不变）：`{"account_name": "agent_virtual", "days": 20, "benchmark_returns": [...]?}`

**响应 `data` 新增两块**（既有键一个不改）：

```jsonc
{
  "returnsSource": "account_nav",
  "navPoints": 20,                       // ← 语义变更：窗口内**交易日**点数
  "window": {
    "from": "2026-09-01", "to": "2026-09-30",
    "trading_days": 20,                  // 参与计算的交易日数 = navPoints
    "filtered_non_trading": 3,           // 被过滤掉的非交易日行数（读取端兜底计数）
    "trading_day_source": "trading-calendar"
  },
  "nav_coverage": {
    "verified": true, "points": 20, "from": "2026-09-01", "to": "2026-09-30",
    "missing_trading_days": [], "missing_count": 0,
    "basis": "按交易日历逐日核对（来源 calendar_table），周末与法定节假日不计入缺口",
    "trading_day_source": "trading-calendar"
  }
}
```

## 6. HTTP 契约：`GET /api/simulation/performance`（serves: FR-4, FR-7）

```jsonc
{ "success": true, "data": {
    "equity_curve": [ /* 只含交易日；字段与今天一致（date/total_value/cash/market_value/return） */ ],
    "initial_capital": 100000.0, "current_value": 101660.79,
    "cumulative_return": 1.66, "max_drawdown": -2.23,
    "window":        { /* 同 §5 */ },
    "nav_coverage":  { /* 同 §5 —— agent-dh 的缺口探测就吃这一块 */ }
} }
```

- `equity_curve` **只减不加**（行数变少、字段不变）；
- `max_drawdown` 来自 `simulation_account.max_drawdown`，**清理后必须已重算**（见 `data-model.md` §4），
  否则会出现"曲线干净、回撤还是脏的"半修状态。

## 7. agent-dh 侧：`RiskMetricsTool` 消费 v2 口径（跨仓）（serves: FR-3, FR-8）

```ts
// packages/tools/risk/src/tools/RiskMetricsTool/RiskMetricsTool.ts
private async probeNavCoverage(account: string, navPoints: number): Promise<NavCoverage | null>
// 改为：从 /api/simulation/performance 的 data.nav_coverage 取字段（不再自算缺口、不再用 getUTCDay）
```

| 情形 | agent-dh 行为 |
|---|---|
| v2 返回 `nav_coverage` | 原样透出（含 `basis` / `trading_day_source`），文案用"交易日" |
| v2 未返回该字段（旧版本） | `{verified: false, basis: 'v2 未提供 nav_coverage：本轮未做交易日校验'}`——**如实声明，不回退 weekday 自算** |
| v2 返回 `verified=false` | 同上传"未校验"，且 **不得**据此触发补跑 |

`prompt.ts` 中 `window_note` 的 `[缺口] 净值序列缺 N 个工作日` → `[缺口] 净值序列缺 N 个交易日（口径：交易日历）`。

## 8. 错误语义（serves: FR-1, FR-2, FR-8）

| 情形 | 行为 | 禁止 |
|---|---|---|
| 判据可用、答非交易日 | 不写、不参与计算、不计缺口；返回结构化 `skipped` | 禁止静默当作"写成功了" |
| 判据降级（`degraded=True`） | **照写/照算**，注解里带 `degraded=True`，接口显式标注 | 禁止把降级当"休市"；禁止不标注 |
| 判据自身异常（`gate-error`） | 照写 + warning；`source='gate-error'` 与"日历说休市"严格区分 | 禁止把代码 bug 读成"今天休市" |
| 日历读失败（`trading_day_set()` → None） | 不过滤、照算，`nav_coverage.verified=false` | **禁止用空集合表达失败**（会把净值序列清空、指标静默退化） |
| `force=True` 写入 | 允许，但调用点必须写明理由 | 禁止作为常规旁路；禁止在批量路径里默认打开 |
