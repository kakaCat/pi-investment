# t-f235bc 拆两个文件级上帝·研发

> 需求：REQ-261001145152-3982 V2 项目全面审查与优化梳理

## 在做什么
拆两个文件级上帝·研发

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果
`npx vitest run <本卡改动涉及的测试文件>` → 全绿；并附 `git diff --stat` 摘要

---
## 汇报 1（2026-10-02T00:18:30.727Z，窗口 session-7fc133ad-e896-4aa2-9cb5-443ac7c5af22）

研发段：**两个"什么都往里塞"的超大文件被按职责拆开了**——一个 1607 行、一个 1147 行，现在各自变成一组 400 行以内的小模块加一个只负责转发的薄壳，原来 60 多处引用它们的地方一行都不用改；而且"拆完行为没变"有硬证据：任务清单（9 条）内容与顺序逐字段一致、命令注册表（25 条）映射完全一致、验收测试拆分前后逐条相同。

### 完成项

- **卡面前提逐条核实**：`scheduler_tasks.py` 1607 行 / 35 个顶层函数 ✓；`daily_jobs_bootstrap.py` 1147 行 / 42 个顶层函数 ✓；JOBS 在第 668 行且是全模块唯一注册表 ✓
- **拆分方式：纯文件级搬运，函数体与签名逐字未改**，原文件保留为**转发壳**（113 行 / 120 行），既有 60+ 处导入路径全部不变（含 `from ...daily_jobs_bootstrap import JOBS` 这类）
- ① `scheduler_tasks.py`（1607 行）→ 10 个模块：common / data / signals / reports / factors / training_guard / models / strategy / runtime / registry；注册表 `_TASK_HANDLERS`（25 条命令）迁入 registry
- ② `daily_jobs_bootstrap.py`（1147 行）→ 包 `daily_jobs/`：defs / alerting / pipeline / pools / health / interval / runtime / registry（+ `__init__`）；JOBS（9 条）迁入 registry
- **关键等价性证据（不是"看起来没问题"）**：JOBS 的 `job_id/handler/run_at/weekdays/description` **内容与顺序逐字段一致**（脚本比对 JSON，`True`）；3 条间隔任务一致；`_TASK_HANDLERS` **键集合与 键→处理器 映射完全一致**（25/25，差异字典为空）、`list_available_commands()` 顺序一致、未知命令报错仍列出可用命令
- **拆分前先建基线**（避免事后无对照）：验收命令拆分前就是 **32 failed / 126 passed / 11 skipped / 2 errors**；拆分后**逐条一致**（FAILED 清单 diff 为空）
- **过程中自查并修掉两类问题**：① 第一版生成器 docstring 后少换行 → 语法错误（已还原重生成）；② 依赖分组算错导致 `alerting ↔ registry` **循环导入**——改为对注册表（JOBS / _TASK_HANDLERS）一律**函数内惰性导入**，并把依赖按 owner 正确分组后重跑
- **每个模块均 < 400 行**（最大：scheduler_tasks_models 311、daily_jobs/runtime 306）；两个原文件分别降到 113 / 120 行
- **测试适配 3 处（拆分的必然代价，已逐条注明）**：`tests/test_false_success_guard.py` 中两个用例把 `_mark_running/_mark_done/_send_feishu` patch 在宿主模块上（实现搬走后 patch 落空）→ 改为 patch `daily_jobs.runtime` / `daily_jobs.alerting`；另一个用例**直接读宿主模块源文件**切片断言 → 改读 `daily_jobs/runtime.py`。**断言内容与行为未改**
- **更广回归对照**：`-k "scheduler or daily_jobs or false_success or job_run or job_executor"` 拆分前后均 **23 条失败/错误**，清单 diff **为空**（零新增）

### 改动文件

- `application/services/scheduler_tasks.py`
- `application/services/scheduler_tasks_common.py`
- `application/services/scheduler_tasks_data.py`
- `application/services/scheduler_tasks_signals.py`
- `application/services/scheduler_tasks_reports.py`
- `application/services/scheduler_tasks_factors.py`
- `application/services/scheduler_tasks_training_guard.py`
- `application/services/scheduler_tasks_models.py`
- `application/services/scheduler_tasks_strategy.py`
- `application/services/scheduler_tasks_runtime.py`
- `application/services/scheduler_tasks_registry.py`
- `adapters/inbound/fastapi_app/daily_jobs_bootstrap.py`
- `adapters/inbound/fastapi_app/daily_jobs/__init__.py`
- `adapters/inbound/fastapi_app/daily_jobs/defs.py`
- `adapters/inbound/fastapi_app/daily_jobs/alerting.py`
- `adapters/inbound/fastapi_app/daily_jobs/pipeline.py`
- `adapters/inbound/fastapi_app/daily_jobs/pools.py`
- `adapters/inbound/fastapi_app/daily_jobs/health.py`
- `adapters/inbound/fastapi_app/daily_jobs/interval.py`
- `adapters/inbound/fastapi_app/daily_jobs/runtime.py`
- `adapters/inbound/fastapi_app/daily_jobs/registry.py`
- `tests/test_false_success_guard.py`

---
