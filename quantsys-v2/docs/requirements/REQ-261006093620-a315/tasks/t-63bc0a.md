# t-63bc0a 判据真源：trading_day_gate 模块与策略入口

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
判据真源：trading_day_gate 模块与策略入口

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果
./venv/bin/python -m pytest tests/test_scheduler_trading_day_gate.py -q 全过（13 行真值表 + 反例锁）；./venv/bin/python -c "from application.services.trading_day_gate import should_skip as s; print(s('always')[0], s('holiday')[0])" 输出 False False（缺省与未知策略都不跳，fail-open）。

## 实施方案（implementation）
新建 application/services/trading_day_gate.py：把 adapters/inbound/fastapi_app/daily_jobs/gate.py 的三个函数（verdict_info / skip_non_trading_day / is_non_trading_day）原样搬入，签名逐字不变；新增 POLICY_ALWAYS/POLICY_TRADING_DAYS/POLICY_HOLIDAYS、KNOWN_POLICIES 与 should_skip(policy, now=None)->(bool, dict)：always 不跳；trading-days 判 (not is_trading_day) and (not degraded)；holidays 判 source=='trading-calendar-holiday' and (not degraded)；未知/None 不跳且 info 带 policy_unknown=True 并记 warning。判据只用 TradingDayGuard.check(now)，函数永不抛（自身异常 → (False, {'source':'gate-error','degraded':True})）。新建 tests/test_scheduler_trading_day_gate.py：13 行真值表（含 holidays+weekend 必须不跳、holidays+降级必须不跳两行核心断言），桩打在 application.services.trading_day_gate.TradingDayGuard；另加 future 反例锁断言 TradingDayGuard.check('2026-10-08').source=='future'。

## 上游产出摘要（dependsSummary）
- （无依赖）

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-10-06T01:50:23.287Z，窗口 session-35ba53fd-df95-40fa-92df-639ba03cba4d）

新建 application/services/trading_day_gate.py 作为交易日判据的唯一真源：把 ③ 的三个函数原样搬入并新增三值策略入口 should_skip，全程 fail-open、永不抛；新增 21 条单测全过。

### 完成项

- 判据真源模块落盘：三值策略 always / trading-days / holidays 与 should_skip 入口
- 判据只用 TradingDayGuard.check(now)，永不抛；自身异常返回 source=gate-error
- 未知策略按 always 照跑，并带 policy_unknown=True 与 warning（不静默）
- 降级来源（weekday_fallback / unavailable）一律照跑并带 source / degraded
- ③ 的三个函数签名逐字保留，skip_non_trading_day 改为委托 should_skip
- 新增 21 条单测全过：14 行真值表 + future 反例锁 + 兜底与兼容断言
- 两条核心断言在场：holidays+周末必须不跳；holidays+降级必须不跳
- 反例锁改用远期日期而非 2026-10-08，避免用例在复市当天自红
- 实测今日读数：trading-days 与 holidays 判跳、always 照跑；10-08 按 resolver 判为交易日
- notify-guard 读数 intercepted=0 egress=0

### 改动文件

- `application/services/trading_day_gate.py`
- `tests/test_scheduler_trading_day_gate.py`

### 下一步

t2 数据契约（t-e05ce2）：给 quant.scheduler_tasks 加 trading_day_policy 列与 CHECK、回填 8 行、ORM 同列、两库都跑迁移。

---
