---
req_id: REQ-261004102115-d3de
title: 解析器接口、探针输出契约与降级语义
doc: design/interfaces
serves: FR-1, FR-2, FR-3
---

# 接口设计（REQ-261004102115-d3de）

## 核心 API（serves: FR-1）

新增 `application/services/trading_day_resolver.py`：

```python
@dataclass(frozen=True)
class TradingDayResult:
    date: datetime.date      # 最近一个「已收盘」的交易日
    source: str              # 'calendar_table' | 'provider' | 'weekday_fallback'
    degraded: bool           # source == 'weekday_fallback'

def last_closed_trading_day(
    ref: datetime | None = None,          # 缺省 now()；时区按本机（Asia/Shanghai）
    *,
    cutoff: dtime = dtime(15, 30),        # 收盘基准，与现状一致
    provider_lookback_days: int = 30,     # ② 的查询窗口（覆盖春节最长休市）
) -> TradingDayResult
```

**语义（唯一口径）**：`anchor = ref 当天的 15:30 前 ? ref.date()-1 : ref.date()`，
结果 = 交易日历中 `<= anchor` 的**最大**交易日。周末与节假日由日历天然排除，
不再需要"周末回退"的显式循环。

**错误语义**：除 `ref` 类型非法（`TypeError`）外**一律不抛**。
表不可读 / provider 超时 / 返回空 → 逐级降级，末级 `weekday_fallback`。

**幂等与纯函数性**：同一 `ref` 在日历源不变时恒返回同一结果；不写任何状态（无落库、无文件）。

## 探针输出契约（serves: FR-2）

`tools/health_probe.py` 的 `probe_freshness()` 返回体**只做增量**：

| 字段 | 类型 | 变化 | 说明 |
|---|---|---|---|
| `expected` | `str` | 语义修正（值可能变） | 现在是"最近已收盘交易日" |
| `kline_latest` / `factor_latest` / `max_lag_days` | 原样 | 不变 | 下游/历史日志兼容 |
| `lag_days` | `int` | 语义修正 | `(expected - kline_latest).days`（自然日，同现状） |
| `expected_source` | `str` | **新增** | `calendar` \| `weekday_fallback` |
| `expected_degraded` | `bool` | **新增** | 是否走了降级口径 |

告警正文：在现有"（K线最新 X / 应有 Y，滞后 N 天）"后**追加以降级标注**
（仅当 `expected_degraded` 为真时追加"（⚠️ 交易日历不可用，按工作日口径判定）"），
正常路径正文与现状逐字一致。

## `freshness_guard` 调用点契约（serves: FR-3）

`adapters/inbound/fastapi_app/daily_jobs/pipeline.py`：

- `_last_trading_day(ref: datetime) -> str` **签名与返回类型不变**（44 个模块仍在导入它），
  实现改为 `last_closed_trading_day(ref).date.isoformat()`；
- 行 177 的"次日基准"保持 `ref = now - 1 天` 的既有输入；
- `result` 字典**新增** `expected_source`（字符串），既有键不动——
  `quant.inprocess_job_runs.result` 是 jsonb，加键不需迁移。

## 日历真源接口（serves: FR-1）

① 表（只读）：

```sql
SELECT max(trade_date) FROM quant.trading_calendar
 WHERE trade_date <= :anchor AND is_trading_day IS NOT FALSE;
```

- 覆盖判定：另查 `SELECT max(trade_date) FROM quant.trading_calendar`，`>= anchor` 才算"表能回答"；
- `IS NOT FALSE`（NULL 视为交易日）与 `tools/check_data_contracts.py:252` 同口径；
  `TradingCalendarORMRepository.list_trading_days` 用的是 `IS TRUE`——**本设计显式采用前者**，
  并要求回填脚本只写 TRUE/FALSE、不写 NULL，使两种口径等价（见 `data-model.md`）；
- `exchange` 维度：`max()` 不受 SSE/SZSE/ALL 三份重复影响，故**不按 exchange 过滤**（避免了 repo 的单 exchange 限制）。

② provider（只读，已有入口）：

```python
ServiceFactory.get_data_provider_manager().get_trading_calendar(start, anchor)
# 返回 {'success': bool, 'source': 'akshare', 'data': StockData|list[dict]，元素含 'trade_date'}
```

失败/空/异常 → 降级③。**本模块不写库**（写回是刷新脚本的职责，见 `data-model.md`）。
