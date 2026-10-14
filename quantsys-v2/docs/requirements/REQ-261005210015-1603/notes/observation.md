# 真实观察与回滚演练（REQ-261005210015-1603 t-ad4340，FR-7）

**观察日期**：2026-10-05 21:20（CST）
**观察对象**：`evolution_fitness` 的真实读数 + 宿主消息渲染 + 全套回归

## 1. 真实读数（生产库 quant_investment）

**方法（可复核）**：跑**真实 handler**（`daily_jobs.pipeline._job_evolution_fitness`），
其内部服务走真实仓储（与 `daily_orchestrator` 的构造方式一致：`SimulationORMRepository` +
`EvolutionFitnessORMRepository`）。该路径**不发送任何通知**，只做与夜间任务相同的幂等 upsert。

```
$ ./venv/bin/python - <<'PY'   # 见本文件末「复现脚本」
evolution_fitness computed  accounts_total=5 computed_ok=0 states={'no_trades': 3, 'insufficient_sample': 2} window_end=2026-10-05

detail    : {'window_end': '2026-10-05', 'accounts_total': 5, 'computed': 5, 'computed_ok': 0,
             'insufficient_sample': 2, 'no_trades': 3, 'data_gap': 0, 'other': 0, 'aligned_days': 10}
no_output : True
summary   : 有效 0（样本不足 2 / 无成交 3 / 数据缺口 0）｜已连续 2 次无有效产出（最近有效：2026-09-12）
失败判定   : find_result_failure(result) → None（不得被误判为失败）
```

**读数与台账一致**：`quant.evolution_fitness` 中 10-05 与 10-02 的 `ok` 计数均为 0，
最近一次有效产出为 2026-09-12（只读查询两次，见 task t-735131 的联调记录）。

## 2. 卡片文本：改造前 vs 改造后（同一批数据）

```
改造前（2026-10-05 20:35 实发）                 改造后（同一 result 渲染）
------------------------------------------     ------------------------------------------
✅ 每日任务完成：evolution_fitness              ⚠️ 每日任务完成（无有效产出）：evolution_fitness
<description>                                  <description>
耗时: 0.0 分钟           ← 实为 1.21 秒         耗时: 1.2 秒
detail[computed=5]       ← 读不出"0 条有效"     有效 0（样本不足 2 / 无成交 3 / 数据缺口 0）
                                               ｜已连续 2 次无有效产出（最近有效：2026-09-12）
```

**渲染方式**：桩打在 `runtime` 模块（`runtime._send_feishu`）后跑 `_run_job`，
记录器捕获到上面右侧文本；台账 `_mark_done` 收到 `status='success'`（未改判）。

## 3. 回归证据

```bash
./venv/bin/python -m pytest tests/test_daily_jobs_bootstrap.py tests/test_false_success_guard.py \
  tests/e2e/test_evolution_pipeline.py tests/services/evolution/test_evolution_fitness_service.py \
  tests/repositories/test_evolution_fitness_repository.py tests/test_daily_jobs_notify_truthfulness.py -q
# → 68 passed, 1 skipped；notify-guard intercepted=0 egress=0 offenders=[]
```

覆盖：耗时格式（FR-1）、摘要状态分布（FR-2）、⚠️/✅ 语气（FR-3）、四类计数不变式与兼容键（FR-4）、
空转三态与降级（FR-5）、失败判定不变式与台账 status（FR-6）、既有回归（FR-7）。

## 4. 回滚演练（**偏离如实记录**）

- **应做**：`git stash` / `git revert` 后确认卡片文本回落为改造前形态，恢复后再验证。
- **实做**：**未执行 `git stash`**——原因具体且可核：同一时段另一窗口的需求
  **REQ-261005203907-2b8c** 正在改**同一个文件** `runtime.py`（其交易日门代码于 21:15:42 落盘），
  对该文件做 stash/revert 会连带回退**别人的在途改动**，属破坏性动作，故改为等价的安全验证：
  ① 用**旧结果形状**（无 `summary`/`no_output`）跑 `_summarize_result` →
  输出逐字等于改造前（`kline_sync[updated=3, status=success]`，用例
  `test_other_job_summary_unchanged`）；② 新键缺失时 `_run_job` 走 `✅` 分支（用例
  `test_nonzero_output_keeps_success_title` 覆盖同一条逻辑）。
- **真实回滚路径**：无 DDL、无数据回填、无对外契约变化 → `git revert` 本需求的提交即可；
  新键消失后消费方自动回落（`summary` 不存在 → 回到白名单 + 子字典的旧渲染）。

## 5. 观察窗口可能被邻居的门改变（预先声明，不算未完成）

2026-10-06 / 10-07 为国庆休市（`last_closed_trading_day` = 2026-09-30）。邻居需求
**REQ-261005203907-2b8c** 的交易日门会在休市日把 `evolution_fitness` 判 `skipped`
（其 FR-3：跳过时不发通知）。若这两天的夜间运行没有卡片，属**门生效**，不是本需求未完成；
复市首日（10-08）恢复后，卡片文本应与本文第 2 节右侧一致。

## 复现脚本

```python
import sys; sys.path.insert(0, '.')
from adapters.outbound.repositories.simulation_repository import SimulationORMRepository
from adapters.outbound.repositories.evolution_fitness_repository import EvolutionFitnessORMRepository
from application.services.evolution import evolution_fitness_service as svcmod
from adapters.inbound.fastapi_app.daily_jobs import pipeline

_orig = svcmod.EvolutionFitnessService.__init__
svcmod.EvolutionFitnessService.__init__ = lambda self, **kw: _orig(
    self, sim_repo=SimulationORMRepository(), fitness_repo=EvolutionFitnessORMRepository())
r = pipeline._job_evolution_fitness()          # 真实读数；不发通知
print(r['summary'], r['no_output'])
```
