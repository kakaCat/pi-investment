---
req_id: REQ-261005203907-2b8c
title: 接口与契约——交易日门（gate.py / JobDef / _run_job / evening_pipeline）
doc: design/interfaces
serves: FR-1, FR-2, FR-3, FR-4, FR-5
---

# 接口设计（REQ-261005203907-2b8c）

> 落点与理由见 [`architecture.md`](architecture.md)；表与 JSONB 见 [`data-model.md`](data-model.md)。

## 1. `daily_jobs/gate.py`（新增模块，唯一判定消费点）（serves: FR-1, FR-2）

```python
# adapters/inbound/fastapi_app/daily_jobs/gate.py
def skip_non_trading_day(now: datetime | None = None) -> tuple[bool, dict]:
    """返回 (是否跳过, 判定注解)。**永不抛异常**；任何异常 → (False, 注解 source='gate-error')。"""

def is_non_trading_day(now: datetime | None = None) -> bool:
    """局部跳过用（evening_pipeline 因子段）。语义 = skip_non_trading_day()[0]。永不抛。"""

def verdict_info(now: datetime | None = None) -> dict:
    """仅取判定注解（照跑路径也要把来源带进 result）。永不抛。"""
```

**判据（唯一，两处调用共用）**：

```python
v = TradingDayGuard.check(now)            # use_cache 默认 True（60s TTL，按日期缓存）
skip = (not v.is_trading_day) and (not v.degraded)
```

**返回注解字段表**：

| 键 | 类型 | 必填 | 约束 / 取值 |
|---|---|---|---|
| `day` | str | 是 | `YYYY-MM-DD`（判定对象日，= `v.day.isoformat()`） |
| `is_trading_day` | bool | 是 | 判定结论 |
| `source` | str | 是 | `trading-calendar` / `trading-calendar-holiday` / `weekend` / `future` / `weekday_fallback` / `unavailable` / `compute-error` / `gate-error` |
| `degraded` | bool | 是 | 是否走了降级链（True ⇒ **不跳过**） |
| `reason` | str | 是 | 判定器原文（如「周末」「该日不在交易日历中」）；`gate-error` 时为异常摘要（截断 ≤200） |

**错误语义**：本模块**不定义也不抛**业务错误码——它只做取舍。`TradingDayGuard.check` 自身的契约
是"数据源不可用 → 保守判非交易日 + `degraded=True`，绝不抛给调用方"（`trading_day_guard.py:222-264`），
本模块只兜**它之外的**意外（如 import 失败）：捕获后 `logger.warning('trading_day_gate_error', ...)`
并返回"照跑"。

## 2. `JobDef` 字段追加（serves: FR-1）

`adapters/inbound/fastapi_app/daily_jobs/defs.py`

| 字段 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `job_id` | str | 是 | — | 既有 |
| `run_at` | `datetime.time` | 是 | — | 既有 |
| `weekdays` | tuple[int, ...] | 是 | — | 既有（0=周一） |
| `handler` | `Callable[[], dict]` | 是 | — | 既有（**签名不变**，不传判定结果） |
| `description` | str | 是 | — | 既有 |
| `trading_days_only` | bool | 否 | `False` | **新增，必须是最后一个字段并带默认值** |

**兼容契约（硬约束）**：
- 追加在**末尾**且带默认值——仓内多处按**位置参数**构造（`tests/test_daily_jobs_bootstrap.py:15`、
  `tests/test_false_success_guard.py:162`、`tests/test_financial_auto_rerun.py:122`），插在中间会全炸。
- 导出路径不变：`JobDef` 已由 `daily_jobs/__init__.py` 导出、`daily_jobs_bootstrap.py` 转发；
  新增**字段**不改符号表，`__all__` 无需改动（44 个模块的既有导入路径零影响）。
- `handler` 签名保持 `() -> dict`：**不**把判定结果传进 handler（20+ 个 handler 与测试会连带改动）。
  `evening_pipeline` 需要判定时**自己调** `is_non_trading_day()`（同一个模块、同一份判据）。

## 3. `_run_job` 门分支（serves: FR-2, FR-3）

`adapters/inbound/fastapi_app/daily_jobs/runtime.py`（早退点必须在 `_send_feishu` **之前**）

```python
_mark_running(job.job_id, run_date)
skip, info = (False, {})
if job.trading_days_only:
    skip, info = skip_non_trading_day()
if skip:
    result = {'skipped': True,
              'reason': f'非交易日（{info["day"]}）：{info["reason"]}',
              'trading_day': info}
    _mark_done(job.job_id, run_date, 'skipped', result=result)
    scheduler_job_runs_total.labels(job=job.job_id, status='skipped').inc()
    logger.info('inprocess_job_skipped', job=job.job_id, date=run_date,
                source=info['source'], degraded=info['degraded'])
    return                                    # ← 无开始/完成通知、无 duration 观测
result = job.handler()
if job.trading_days_only and isinstance(result, dict) and 'trading_day' not in result:
    result['trading_day'] = info              # 照跑路径也带来源（degraded 时另记 warning）
    if info.get('degraded'):
        logger.warning('inprocess_job_trading_day_degraded', job=job.job_id, source=info['source'])
```

**指标契约**：
- `scheduler_job_runs_total{job, status}`：跳过时 `status='skipped'`（新增标签值，标签集无注册校验）。
- `scheduler_job_duration_seconds{job, phase}`：跳过时**不观测**——跳过不是"执行耗时"，
  观测进去会污染耗时直方图的低分位（决策，非疏漏）。

**成功/失败语义不变**：跳过走的是**独立早退分支**，不经过 `find_result_failure`；
`result.skipped=True` 的写法沿用仓内既有约定（`job_executor.py:157`：显式 skipped 不算失败）。

## 4. `_job_evening_pipeline` 因子段判定（serves: FR-4）

`adapters/inbound/fastapi_app/daily_jobs/pipeline.py`：入口取一次判定，K 线段**原样保留**，
因子段按下表决定（`kline_sync` 形状见 [`data-model.md`](data-model.md) §3）：

| 判定为非交易日 | `kline_sync` 结果 | 因子段 | 说明 |
|---|---|---|---|
| 是 | `status='skipped'`（覆盖度已新鲜） | **跳过** | 本需求要消灭的那次"全市场重算冻结快照" |
| 是 | `status='success'` 且 `success>0` | **照跑** | 休市日修复了 K 线 → 必须把修复结果算进因子，避免留空洞 |
| 是 | `status='success'` 且 `success==0` | **跳过** | 无任何新数据；且此形态会被判"假成功"为 failed（a7cd t-322d78） |
| 是 | `status='error'` | **照跑** | 保持既有语义：先按现有数据算完因子，再上抛失败（`pipeline.py:124-130`） |
| 否（交易日或降级） | 任意 | **照跑** | **交易日行为逐字不变** |

```python
non_trading = is_non_trading_day()
kline = results.get('kline_sync') or {}
kline_changed = kline.get('status') != 'skipped' and (kline.get('success') or 0) > 0
if non_trading and not kline_changed and kline.get('status') != 'error':
    results['factor_compute'] = {'status': 'skipped', 'skipped': True,
                                 'reason': f'非交易日（{expected} 基准）且 K 线本次无更新'}
else:
    results['factor_compute'] = handle_factor_compute({'max_symbols': 6000})
```

⚠️ **不许用"K 线段是否 skipped"单独判定因子段**：交易日若 K 线已由别的路径同步过，
`kline_sync` 同样是 `skipped`，但**当日因子还没算** —— 那样写会在正常交易日漏算因子。
故判据是 `non_trading and not kline_changed`（与，不是或）。

## 5. 与既有消费者的兼容矩阵（serves: FR-3, FR-5）

| 消费者 | 现行为 | `status='skipped'` 下的行为 | 结论 |
|---|---|---|---|
| `is_due`（当日记录） | `success`→False、`running`→僵死判定、`failed`→冷却 2h、其余→False | 落 `return False`（其余分支） | 当日**不重跑**，幂等 |
| `catchup_due` | 仅 `last is None` 时评估、且需近 3 日有 failed | 有 skipped 行 ⇒ `last is not None` ⇒ 不评估 | **不触发补跑**（FR-5） |
| `_reap_orphan_runs` | 只看 `running` | 不匹配 | 跳过行不会被判死 |
| `_job_failure_watch` | 只看 `failed` | 不匹配 | 跳过**不告警** |
| `trigger_job(force=False)` | 仅对 `running` / `success` 拒绝 | `skipped` 不拒绝 ⇒ **可人工重跑** | 有意为之（FR-5） |
| `list_today_runs()` | 透传 status | 多出 `skipped` | 展示层增量，无契约破坏 |
| `find_result_failure` | `skipped=True` 直接判"非失败" | 早退分支根本不到这里 | 无冲突 |

**对外 HTTP 契约**：无变化（无新增/变更路由、无字段删除；仅状态取值集合新增一项）。
**数据库契约**：无 DDL（`status` 是 `text`，无 CHECK 约束），详见 [`data-model.md`](data-model.md)。
