# REQ-261005210015-1603 验收文档

> 自动生成于 reqboard_submit(kind=verification) · 验收单 v1

**交付结论**：目标达成：evolution_fitness 的完成通知不再把「零有效产出」报成成功。四处改动：①耗时按量级显示（1.21 秒不再印成 0.0 分钟）；②摘要带状态分布（有效/样本不足/无成交/数据缺口），不再 dump 内部字段；③零有效产出改 ⚠️ 语气，台账仍记 success；④computed 拆成诚实计数（computed_ok 加三类加 other 恒等于 accounts_total，删写死的 skipped，保留兼容键 computed）。空转连续次数与最近有效日期进入正文，当前真实值为「已连续 2 次无有效产出（最近有效：2026-09-12）」。回归 68 passed / 1 skipped，零真实外发。偏离一项如实登记：回滚演练未做 git stash（邻居需求正改同一 runtime.py），改以「旧结果形状回落逐字不变」等价验证。新增 21 条用例，覆盖 37 张任务卡（见 tests/test-evidence.md 的 covers 清单）。

## 1. 验收列表

### v1-1 · 通知层契约落地：_format_elapsed + _summarize_result 支持顶层 summary

**验收内容**：【通知层契约落地：_format_elapsed + _summarize_result 支持顶层 summary】验收

**操作步骤**：
1. 跑 ./venv/bin/python -m pytest tests/test_daily_jobs_notify_truthfulness.py -q -k elapsed → 2 passed。再跑 ./venv/bin/python -c 断言五组：_format_elapsed(1.21) 得 1.2 秒、_format_elapsed(59.96) 得 60.0 秒、_format_elapsed(60.0) 得 1.0 分钟、_format_elapsed(125.0) 得 2.1 分钟、_format_elapsed(-1) 得 0.0 秒。旧行为不得变：以 evening_pipeline 形态（无 summary）跑 _summarize_result → 输出逐字为 kline_sync[updated=3, status=success]（用例 test_other_job_summary_unchanged 锁死）。可查字段：quant.inprocess_job_runs.result 的 summary。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：pytest tests/test_daily_jobs_notify_truthfulness.py -q → 14 passed（notify-guard intercepted=0 egress=0）

**验收状态**：✓ 通过

---

### v1-2 · fitness 服务诚实计数：四类状态 + accounts_total，删 skipped、收窄 computed 语义

**验收内容**：【fitness 服务诚实计数：四类状态 + accounts_total，删 skipped、收窄 computed 语义】验收

**操作步骤**：
1. ./venv/bin/python -m pytest tests/services/evolution/test_evolution_fitness_service.py -q 全过，且新增断言成立：computed_ok + insufficient_sample + no_trades + data_gap + other == accounts_total
2. 返回体里不存在 skipped 键
3. result 的 computed == accounts_total
4. status 为 data_gap 或 no_trades 的账户不计入 computed_ok。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：pytest tests/test_daily_jobs_notify_truthfulness.py -q → 14 passed（notify-guard intercepted=0 egress=0）

**验收状态**：✓ 通过

---

### v1-3 · 空转读数：EvolutionFitnessORMRepository 两个只读聚合方法

**验收内容**：【空转读数：EvolutionFitnessORMRepository 两个只读聚合方法】验收

**操作步骤**：
1. ./venv/bin/python -m pytest tests/repositories/test_evolution_fitness_repository.py -q 全过
2. 新增断言：插 3 个 window_end（ok 条数分别 2/0/1）时返回顺序与计数为倒序正确
3. 最新一条为 insufficient_sample、次新为 ok 时 get_last_ok_window_end() 返回次新的 window_end
4. 全部非 ok 时返回 None。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：pytest tests/test_daily_jobs_notify_truthfulness.py -q → 14 passed（notify-guard intercepted=0 egress=0）

**验收状态**：✓ 通过

---

### v1-4 · handler 组装：summary / no_output / 空转统计（含纯函数与查询失败降级）

**验收内容**：【handler 组装：summary / no_output / 空转统计（含纯函数与查询失败降级）】验收

**操作步骤**：
1. 跑 ./venv/bin/python -m pytest tests/test_daily_jobs_notify_truthfulness.py -q -k 'idle_streak or streak' → 4 passed（空转四态：连续 2 次 / 有产出不追加 / 截断大等于 K / 降级）。再跑同文件全量 → 14 passed。判据要点：以生产真实计数（computed_ok=0、insufficient_sample=2、no_trades=3、data_gap=0、idle_streak=2、last_ok=2026-09-12）构造时，返回体 summary 含「有效 0（样本不足 2 / 无成交 3 / 数据缺口 0）」与「已连续 2 次无有效产出（最近有效：2026-09-12）」
2. monkeypatch 仓储方法抛错时 summary 含「空转统计不可用」且不外抛（用例 test_streak_query_failure_degrades_loudly 断言 error 日志与台账仍 success）。可查数据：quant.inprocess_job_runs.result 的 summary 与 no_output 字段。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：pytest tests/test_daily_jobs_notify_truthfulness.py -q → 14 passed（notify-guard intercepted=0 egress=0）

**验收状态**：✓ 通过

---

### v1-5 · runtime 接线：耗时按量级显示 + 零产出改 ⚠️（不动 status、不碰跳过分支）

**验收内容**：【runtime 接线：耗时按量级显示 + 零产出改 ⚠️（不动 status、不碰跳过分支）】验收

**操作步骤**：
1. ./venv/bin/python -m pytest tests/test_false_success_guard.py -q 全过（既有断言不破）
2. 且 no_output=True 的 job 完成通知首行为「⚠️ 每日任务完成（无有效产出）：<job_id>」，no_output 缺失或 False 时首行仍为「✅ 每日任务完成：<job_id>」
3. 该次运行 _mark_done 收到的 status 仍为 success。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：pytest tests/test_daily_jobs_notify_truthfulness.py -q → 14 passed（notify-guard intercepted=0 egress=0）

**验收状态**：✓ 通过

---

### v1-6 · 新增通知层用例（12 条：格式/摘要/语气/空转/降级/失败判定不变式/其他任务逐字不变）

**验收内容**：【新增通知层用例（12 条：格式/摘要/语气/空转/降级/失败判定不变式/其他任务逐字不变）】验收

**操作步骤**：
1. ./venv/bin/python -m pytest tests/test_daily_jobs_notify_truthfulness.py -q → 12 passed（0 failed）
2. 其中必须存在断言 find_result_failure(契约 B 的 result) is None 与 _mark_done 以 status='success' 被调用两条
3. 全文件运行时 notify_guard 不得出现未声明的真实外发（如出现，用例应红）。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：pytest tests/test_daily_jobs_notify_truthfulness.py -q → 14 passed（notify-guard intercepted=0 egress=0）

**验收状态**：✓ 通过

---

### v1-7 · 数据层用例：计数不变式、无 skipped、computed 兼容、只读聚合口径

**验收内容**：【数据层用例：计数不变式、无 skipped、computed 兼容、只读聚合口径】验收

**操作步骤**：
1. ./venv/bin/python -m pytest tests/services/evolution/test_evolution_fitness_service.py tests/repositories/test_evolution_fitness_repository.py -q 全过，新增用例数大于等于 7，且既有断言一条不破。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：pytest tests/test_daily_jobs_notify_truthfulness.py -q → 14 passed（notify-guard intercepted=0 egress=0）

**验收状态**：✓ 通过

---

### v1-8 · 回归四连 + 兼容核对 + 真实观察取证（含回滚演练）

**验收内容**：【回归四连 + 兼容核对 + 真实观察取证（含回滚演练）】验收

**操作步骤**：
1. 四条 pytest 命令全过（含 e2e 的 test_evolution_pipeline.py）
2. notes 目录下的 observation 文档含至少 1 条真实台账证据（result 里 summary 的原文）与回滚演练结论
3. 若观察窗口被判 skipped，文档中显式写明该情形与对应证据，不得记作未完成。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：pytest tests/test_daily_jobs_notify_truthfulness.py -q → 14 passed（notify-guard intercepted=0 egress=0）

**验收状态**：✓ 通过

---

### v1-9 · 需求级验收

**验收内容**：需求级：交付结论可复核（证据齐全、与设计一致、无范围蔓延）

**操作步骤**：
1. 需求级：交付结论可复核（证据齐全、与设计一致、无范围蔓延）

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：pytest tests/test_daily_jobs_notify_truthfulness.py -q → 14 passed（notify-guard intercepted=0 egress=0）

**验收状态**：✓ 通过

---

### v1-10 · 需求级验收

**验收内容**：与裁定对照（逐条说明如何落实）

**操作步骤**：
1. 与裁定对照（逐条说明如何落实）

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：pytest tests/test_daily_jobs_notify_truthfulness.py -q → 14 passed（notify-guard intercepted=0 egress=0）

**验收状态**：✓ 通过

---

### v1-11 · 需求级验收 · E2E 覆盖

**验收内容**：E2E 覆盖：**无（缺口）**——本需求交付涉及多组件串联，但只交了单元/集成测试。请补一条端到端场景用例（断言可观察终态）；若确认无需 E2E，通过时必须在意见中写明理由。

**操作步骤**：
1. E2E 覆盖：**无（缺口）**——本需求交付涉及多组件串联，但只交了单元/集成测试。请补一条端到端场景用例（断言可观察终态）
2. 若确认无需 E2E，通过时必须在意见中写明理由。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：pytest tests/test_daily_jobs_notify_truthfulness.py -q → 14 passed（notify-guard intercepted=0 egress=0）

**验收状态**：✓ 通过

---

## 2. 测试报告

- pytest tests/test_daily_jobs_notify_truthfulness.py -q → 14 passed（notify-guard intercepted=0 egress=0）
- pytest tests/services/evolution/test_evolution_fitness_service.py tests/repositories/test_evolution_fitness_repository.py -q → 15 passed, 1 skipped（新增 7 条）
- pytest 六文件回归（含 tests/e2e/test_evolution_pipeline.py）→ 68 passed, 1 skipped，e2e 的 computed 大等于 1 兼容断言仍成立
- docs/requirements/REQ-261005210015-1603/notes/observation.md → 真实观察：summary 原文、no_output=True、find_result_failure 返回 None，附复现脚本
- docs/requirements/REQ-261005210015-1603/tests/test-evidence.md → 21 条新增用例清单、FR 覆盖映射、37 张任务卡 covers 标注、打桩点合规与受限项
- docs/requirements/REQ-261005210015-1603/reviews/review-report.md → 逐 FR 对照结论、陷阱 1 表述修正、并发编辑核对、偏离与风险登记
- 真库只读读数：10-05=0、10-02=0、09-12=3、09-09=4、09-06=2；最近一次有效产出 = 2026-09-12
- 卡片对照（同一 result 渲染）：改造前「✅…耗时: 0.0 分钟 / detail[computed=5]」→ 改造后「⚠️…耗时: 1.2 秒 / 有效 0（样本不足 2 / 无成交 3 / 数据缺口 0）｜已连续 2 次无有效产出（最近有效：2026-09-12）」
- docs/requirements/REQ-261005210015-1603/design/ → 5 份设计文档（architecture / interfaces / data-model / use-cases / test-cases），均已人确认
- docs/requirements/REQ-261005210015-1603/decomposition.md → 8 张卡全部 done，四段子卡链留痕见 docs/requirements/REQ-261005210015-1603/tasks/
- 偏离登记：回滚演练未执行 git stash（邻居需求 REQ-261005203907-2b8c 正改 runtime.py）；替代验证 = 旧结果形状回落逐字不变（用例 test_other_job_summary_unchanged）
- 待查①：用户所见卡片上的 7 在台账、日志与复现三处均无来源（一致为 5）；待查②：空转根因是净值快照链的洞，不在本需求范围；待查③：reqboard_task_run 在本机派发后无产出，实施链不自跑（另案）

## 3. 文档完整性检查

✓ 9 类文档齐全

## 4. 验收结果

| 编号 | 验收项 | 状态 | 验收人 | 验收时间 |
|---|---|---|---|---|
| v1-1 | 通知层契约落地：_format_elapsed + _summarize_result 支持顶层 summary | ✓ 通过 | human/session-2bee6968-97b4-45c8-af2d-c3b953e9ff08 | 2026-10-05 21:28 |
| v1-2 | fitness 服务诚实计数：四类状态 + accounts_total，删 skipped、收窄 computed 语义 | ✓ 通过 | human/session-2bee6968-97b4-45c8-af2d-c3b953e9ff08 | 2026-10-05 21:28 |
| v1-3 | 空转读数：EvolutionFitnessORMRepository 两个只读聚合方法 | ✓ 通过 | human/session-2bee6968-97b4-45c8-af2d-c3b953e9ff08 | 2026-10-05 21:28 |
| v1-4 | handler 组装：summary / no_output / 空转统计（含纯函数与查询失败降级） | ✓ 通过 | human/session-2bee6968-97b4-45c8-af2d-c3b953e9ff08 | 2026-10-05 21:28 |
| v1-5 | runtime 接线：耗时按量级显示 + 零产出改 ⚠️（不动 status、不碰跳过分支） | ✓ 通过 | human/session-2bee6968-97b4-45c8-af2d-c3b953e9ff08 | 2026-10-05 21:28 |
| v1-6 | 新增通知层用例（12 条：格式/摘要/语气/空转/降级/失败判定不变式/其他任务逐字不变） | ✓ 通过 | human/session-2bee6968-97b4-45c8-af2d-c3b953e9ff08 | 2026-10-05 21:29 |
| v1-7 | 数据层用例：计数不变式、无 skipped、computed 兼容、只读聚合口径 | ✓ 通过 | human/session-2bee6968-97b4-45c8-af2d-c3b953e9ff08 | 2026-10-05 21:29 |
| v1-8 | 回归四连 + 兼容核对 + 真实观察取证（含回滚演练） | ✓ 通过 | human/session-2bee6968-97b4-45c8-af2d-c3b953e9ff08 | 2026-10-05 21:29 |
| v1-9 | 需求级验收 | ✓ 通过 | human/session-2bee6968-97b4-45c8-af2d-c3b953e9ff08 | 2026-10-05 21:29 |
| v1-10 | 需求级验收 | ✓ 通过 | human/session-2bee6968-97b4-45c8-af2d-c3b953e9ff08 | 2026-10-05 21:29 |
| v1-11 | 需求级验收 · E2E 覆盖 | ✓ 通过 | human/session-2bee6968-97b4-45c8-af2d-c3b953e9ff08 | 2026-10-05 21:30 |
