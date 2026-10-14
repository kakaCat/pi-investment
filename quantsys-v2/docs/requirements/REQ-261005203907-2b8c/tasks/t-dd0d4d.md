# t-dd0d4d 门模块与 JobDef 字段（接口先行）

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
门模块与 JobDef 字段（接口先行）

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果
./venv/bin/python -m pytest tests/test_daily_jobs_trading_day_gate.py -q -k "truth or holiday or degraded" 全过；另断言 JobDef('x', dtime(0,0), (0,), lambda: {}, 'd').trading_days_only is False（位置参数兼容）；断言 skip_non_trading_day 在 check 抛异常时不抛、返回 skip=False。

## 实施方案（implementation）
新建 adapters/inbound/fastapi_app/daily_jobs/gate.py：skip_non_trading_day(now=None)->tuple[bool,dict] / is_non_trading_day(now=None)->bool / verdict_info(now=None)->dict；判据 skip = (not TradingDayGuard.check(now).is_trading_day) and (not verdict.degraded)；永不抛，自身异常返回 (False, {'source':'gate-error',...}) 并记 warning 日志；注解五键 day/is_trading_day/source/degraded/reason。改 adapters/inbound/fastapi_app/daily_jobs/defs.py：JobDef 末尾追加 trading_days_only: bool = False（必须末位带默认值，仓内多处按位置参数构造）。新增 tests/test_daily_jobs_trading_day_gate.py 覆盖 TC-1 真值表：休市日 2026-10-05/06/07 → skip=True；交易日 2026-09-30/2026-10-08 → skip=False；周末 2026-10-03 → skip=True；degraded=True → skip=False（fail-open）；check 抛异常 → skip=False 且 source='gate-error'；注解形状五键齐。打桩点 daily_jobs.gate.TradingDayGuard，零网络零 DB。不改 daily_jobs/__init__.py 与 daily_jobs_bootstrap.py 的导出清单。

## 上游产出摘要（dependsSummary）
- （无依赖）

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-10-05T13:13:33.092Z，窗口 session-b97ce139-00d0-456f-b147-6b897bcb5369）

接口先行落地：新增交易日门模块（fail-open 判定 + 五键注解），JobDef 末尾加 trading_days_only 标志，13 条真值表单测全过。

### 完成项

- 新建 daily_jobs/gate.py：skip_non_trading_day / is_non_trading_day / verdict_info 三入口，判据唯一 skip = (not is_trading_day) and (not degraded)
- 门永不抛：判定器异常时返回 (False, source=gate-error, degraded=True) 并记 warning 日志
- defs.py 的 JobDef 末尾追加 trading_days_only: bool = False（保持位置参数构造兼容）
- 新增 tests/test_daily_jobs_trading_day_gate.py：TC-1 真值表 13 条（休市日 10-05/06/07、交易日 09-30/10-08、周末、降级 fail-open、判定器异常、注解五键、字段默认值与位置参数兼容）
- pytest tests/test_daily_jobs_trading_day_gate.py → 13 passed；notify-guard intercepted=0 egress=0
- 回归：pytest tests/test_daily_jobs_bootstrap.py tests/test_false_success_guard.py tests/test_financial_auto_rerun.py → 47 passed（位置参数构造 JobDef 未被破坏）

### 改动文件

- `adapters/inbound/fastapi_app/daily_jobs/gate.py`
- `adapters/inbound/fastapi_app/daily_jobs/defs.py`
- `tests/test_daily_jobs_trading_day_gate.py`

### 下一步

下一卡 t-075116 宿主接线：runtime._run_job 在开始通知之前早退并写 status=skipped，registry 给 3 个任务置位。

---
