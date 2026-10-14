# 评审报告（REQ-261005203907-2b8c）

> 评审对象：本次交付的全部代码与文档改动。评审方式：**读改动 + 跑命令 + 对照设计逐条核**，
> 不以提交者自述为据（本仓验收纪律：不接受口头描述）。
> 对照基线：[`../design/interfaces.md`](../design/interfaces.md)（契约）、
> [`../design/architecture.md`](../design/architecture.md)（落点与回滚）、
> [`../requirement.md`](../requirement.md)（6 条 FR 与 D-1/D-2）。

## 1. 改动清单（逐文件，含职责）

| 文件 | 动作 | 评审要点 |
|---|---|---|
| `adapters/inbound/fastapi_app/daily_jobs/gate.py` | 新建（104 行） | 判据唯一、fail-open、永不抛、注解五键 |
| `adapters/inbound/fastapi_app/daily_jobs/defs.py` | 改（+6 行） | 字段必须是**末位且带默认值**（位置参数构造兼容） |
| `adapters/inbound/fastapi_app/daily_jobs/registry.py` | 改（+19/-…） | 恰好 3 个任务置位，另 5 个不动；注释说明为何 evening_pipeline 例外 |
| `adapters/inbound/fastapi_app/daily_jobs/runtime.py` | 改（+50/-…） | 早退点在**开始通知之前**；写 skipped；不观测 duration；降级记 warning |
| `adapters/inbound/fastapi_app/daily_jobs/pipeline.py` | 改（因子段 +19/-4） | 判据是「与」；K 线段与 error 上抛零改动 |
| `tests/test_daily_jobs_trading_day_gate.py` | 新建（27 例） | 真值表 / 宿主接线 / 兼容判据 |
| `tests/test_evening_pipeline_holiday_gate.py` | 新建（6 例） | 六行真值表 + 交易日回归锁 |

## 2. 逐条对照设计（结论：无偏离）

| 设计条目 | 核验方式 | 结论 |
|---|---|---|
| 判据 `skip = (not is_trading_day) and (not degraded)` | 读码 + `test_degraded_runs_fail_open` | ✅ 是「与」不是「或」 |
| 门永不抛 | 读码（双层 try）+ `test_gate_error_runs` | ✅ |
| 注解五键 | 读码 + `test_returns_annotation_shape` | ✅ |
| 早退点在通知之前 | 读码（runtime.py:104-124 vs :126） | ✅ |
| 跳过不观测 duration | 读码 + `test_skip_does_not_observe_duration` | ✅ |
| 降级不许静默 | 读码（照跑路径补注解 + warning）+ 用例 | ✅ |
| 3 个任务置位、evening_pipeline 例外 | 读码 + `TestRegistryScope`（3 条） | ✅ 集合恰好相等 |
| 因子段判据「非交易日 且 K 线无更新 且 非 error」 | 读码 + 六行真值表 | ✅ |
| K 线段零改动 | `git diff` 中探活/覆盖度/批大小/修复/上抛符号 0 条增删 | ✅ |
| 零 DDL / 零迁移 | `notes/compat-rollback.md` §2（information_schema + pg_constraint + ORM） | ✅ |
| 回滚可照做 | `notes/compat-rollback.md` §4（三步 + 无需清理） | ✅ |

## 3. 独立证据（复跑命令，非自述）

```console
$ ./venv/bin/python -m pytest tests/test_daily_jobs_trading_day_gate.py \
    tests/test_evening_pipeline_holiday_gate.py tests/test_daily_jobs_bootstrap.py \
    tests/test_false_success_guard.py tests/test_pool_refresh_daily.py -q
70 passed, 1 warning in 2.08s
notify-guard intercepted=0 egress=0 offenders=[]

$ ./venv/bin/python tools/check_undefined_names.py | grep -E "daily_jobs/(gate|runtime|registry|pipeline)\.py"
（无输出 → 0 命中）
$ ./venv/bin/python tools/analyze_layer_violations.py | grep -E "daily_jobs/(gate|runtime|registry|pipeline)\.py"
（无输出 → 0 违规）
```

## 4. 发现与处置（含未修项，如实登记）

| # | 发现 | 处置 |
|---|---|---|
| R-1 | **子卡验收标准是 JS 栈模板**（`npx vitest` / `pnpm test` / `npx tsc`），本仓是 Python | 5 张子卡开卡时逐张修订为等价 pytest 命令（`reqboard_task_move` 的 acceptance 修订入口），留痕在卡文档 |
| R-2 | 设计未列 `pipeline._last_trading_day` 打桩点，真实调用会连库/联网 | 实现期补上（测试零网络零 DB）；已在 t-e11789 汇报中登记 |
| R-3 | 选择集 `-k "evening_pipeline or daily_jobs or freshness"` 有 1 条 **order-dependent** 失败（`test_streak_query_failure_degrades_loudly` 的 capsys 断言） | **不在本需求范围**：单跑通过、失败点在本需求代码之前、排除本需求两个新测试文件后仍复现（既有问题）；已在 t-4dec18 与 `notes/holiday-observation.md` §4 留证 |
| R-4 | **门需重启宿主才生效**（服务进程 2026-10-05 09:09:10 启动，早于改动落盘） | 未擅自重启生产服务（会连带加载工作区其它未提交改动）→ 登记为阻塞项，命令写在 `notes/holiday-observation.md` §3.1 |
| R-5 | fail-open 降级路径只有单元验证 | 登记为已知缺口（制造真实日历故障会污染生产读取），见 §4 同文件 |

## 5. 评审结论

- **接口与数据契约**：与设计一致，无偏离（§2 逐条）。
- **兼容性**：新增 `skipped` 状态对 7 个既有消费者的行为逐行核对（4 行直接断言、3 行读码并说明），
  零 DDL 已用 `information_schema` / `pg_constraint` / ORM 三处交叉核过。
- **可回滚**：撤标志 + 撤判定 + 重启，三步；`skipped` 历史行无需清理。
- **不阻塞验收的遗留**：R-3（既有 flake）。
- **阻塞验收的遗留**：R-4（重启生效）、窗口未到的真实观察（10-06/10-07/10-08）。
