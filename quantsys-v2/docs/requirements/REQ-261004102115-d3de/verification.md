# REQ-261004102115-d3de 验收文档

> 自动生成于 reqboard_submit(kind=verification) · 验收单 v2

**交付结论**：返工已完成：按验收意见补了端到端场景用例（不是写理由豁免）。E2E 用与 launchd 相同的命令驱动真实入口：断言退出码语义、输出契约、脚本与库内唯一口径逐日一致、以及告警确实未发出。全量相关回归仍为 92 passed；E2E 2 passed，notify-guard egress=0。原有交付结论不变：国庆误报消除、口径唯一、日历表覆盖至 2026-12-31。

## 1. 验收列表

### v2-1 · 需求级验收 · E2E 覆盖

**验收内容**：E2E 覆盖：**无（缺口）**——本需求交付涉及多组件串联，但只交了单元/集成测试。请补一条端到端场景用例（断言可观察终态）；若确认无需 E2E，通过时必须在意见中写明理由。

**操作步骤**：
1. E2E 覆盖：**无（缺口）**——本需求交付涉及多组件串联，但只交了单元/集成测试。请补一条端到端场景用例（断言可观察终态）
2. 若确认无需 E2E，通过时必须在意见中写明理由。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：命令：./venv/bin/python tools/health_probe.py --dry-run → healthy=true、expected=2026-09-30、expected_source=calendar，EXIT=0

**验收状态**：✓ 通过

---

## 2. 测试报告

- 命令：pytest tests/e2e/test_health_probe_e2e.py -q → 2 passed（notify-guard intercepted=0 egress=0）
- 场景一：venv/bin/python tools/health_probe.py --dry-run（独立进程）→ 退出码 ∈ {0,2}；expected_source=calendar；脚本 expected == 进程内 last_closed_trading_day 的结果
- 场景二（负向控制）：--max-lag-days <实测lag-1> → 退出码 2、healthy=false、stdout 含「[--dry-run] 以下告警**未发送**」
- 命令：pytest tests/ -q -k "freshness or trading_day or health_probe" → 92 passed
- 命令：./venv/bin/python tools/health_probe.py --dry-run → healthy=true、expected=2026-09-30、EXIT=0
- 文档：verification.md §五（返工处置）、tests/evidence.md §7（E2E 证据 + covers t-391941）、reviews/self-review.md

## 3. 文档完整性检查

✓ 9 类文档齐全

## 4. 验收结果

| 编号 | 验收项 | 状态 | 验收人 | 验收时间 |
|---|---|---|---|---|
| v2-1 | 需求级验收 · E2E 覆盖 | ✓ 通过 | human/session-e4214a80-d4ad-4666-9705-9ee6f7921f01 | 2026-10-04 10:39 |
