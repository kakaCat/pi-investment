---
requirement_id: REQ-260926140539-457b
kind: tests
title: RTM YAML 追溯基础设施 · 测试证据
version: 1.0
---

# 测试证据 · REQ-260926140539-457b

> 复跑命令（全部在 `agent-dh/` 下执行）：
> ```bash
> npx vitest run packages/tools/reqboard/tests
> cd packages/tools/reqboard && npx tsc -p tsconfig.json
> cd agent-dh && npx vitest run packages/web/dsh-pmboard/tests
> ```
> 最近一次结果（v1.1 补实现后）：**13 个测试文件 / 95 条测试全绿**；包级 `tsc` exit 0；
> dsh-pmboard 全量回归仍是 **41 失败文件 / 197 失败用例**（与改动前逐一致，零新增）；
> dsh-pmboard 的包级 `tsc` 错误数 149，与改动前一致（新增代码零新增类型错误）。

## 单元 · 类型契约编译门禁
covers: t-8c8edc
validates: FR-1

命令：`cd agent-dh/packages/tools/reqboard && npx tsc -p tsconfig.json`（exit 0）。
断言七个 RTM YAML 结构 + 追溯/覆盖度类型齐备、字段与 design/rtm-schema.md 一致。

## 单元 · RTM 文件读写与版本控制
covers: t-e57e00
validates: FR-1, FR-6, FR-9

文件：`packages/tools/reqboard/tests/rtm/file-io.test.ts`（8 条）。
断言：写后读一致；连续两次写入 version 1→2；读不存在的文件返回 null 且不抛；
YAML 坏掉的宽读留因、严格读抛 `RTM_FILE_PARSE_ERROR`；降级重建；
原子写入不留 `.tmp`。

## 单元 · 文档标注解析
covers: t-25c956
validates: FR-3, FR-4

文件：`tests/rtm/parser.test.ts`（12 条）。
断言：`**FR-N:` 与 `### FR-N:` 两种写法；代码围栏内示例不误判；设计章节同行/次行 `serves:`；
`covers:`/`validates:`；decomposition.md §1 对照表解析。

## 单元 · 四级追溯映射
covers: t-3ca532
validates: FR-4

文件：`tests/rtm/traceability-coverage.test.ts`。
断言：fr_to_design / design_to_tasks / task_to_tests 与间接的 fr_to_tasks / fr_to_tests；
单条 FR 的完整链 `buildTraceabilityChain`。

## 单元 · 三层覆盖度与门禁
covers: t-0bf4ae
validates: FR-5, FR-9

同文件。断言：3 FR 覆盖 2 → 67% 且 uncovered=[FR-3]；5 任务覆盖 2 → 40%；
空集合 100%；门禁阈值 design/decomposing=100、accepting=80，不过时点名缺口。

## 集成 · 六个节点 RTM 生成器
covers: t-93f4da, t-46064e, t-ca2228, t-a30145, t-c4fa59, t-20151a
validates: FR-1, FR-2, FR-6, FR-10, FR-11

文件：`tests/rtm/generators.test.ts`（14 条）。
断言：lifecycle 七阶段骨架与状态派生；brainstorming 提取 3 个 FR；
design 覆盖度 67%；decomposing 实施覆盖度 100% 与 uncovered 暴露；
implementing 汇总统计 + 每任务详情文件 + 按 phase 生成 workflow（backend 跳过 ui）；
任务状态变更后详情与汇总同步；accepting 测试覆盖度 40%；版本号每次 +1。

## 集成 · 七个业务触发点
covers: t-152423, t-6019b3, t-54248f, t-6eeacf, t-eb31cc
validates: FR-2, FR-9

文件：`tests/rtm/triggers.test.ts`（10 条）。
断言：create / submit:requirement / confirm:artifact / submit:design / confirm:plan /
task:status / task:report / submit:verification 各自更新预期文件；
缺 taskId 结构化失败；落盘失败返回 `ok:false` 而不抛（不打断主流程）。

## 集成 · StageOverview 读取与装配
covers: t-cf2b22, t-66d23c
validates: FR-7, FR-9

文件：`tests/rtm/stage-overview.test.ts`（5 条）。
断言：五个读取入口；缺失返回 null；装配出追溯块与三层覆盖度；
快照缺失时用 regenerator 实时重建；无 regenerator 返回空块不抛。

## 端到端 · 完整需求流程
covers: t-37e870
validates: FR-1, FR-2, FR-3, FR-4, FR-5, FR-7, FR-10

文件：`tests/e2e/rtm-yaml-full-flow.test.ts`（3 条）。
断言：7 个触发点逐点生效、七个 RTM 文件齐全；
追溯链 FR-1 → design/architecture.md#1.1 → t-0001 → TC-1；
文件体积（lifecycle/汇总 < 100 行、任务详情 < 50 行）；
热读两个文件 < 5ms（Dive 决策口径）。

## 回归 · dsh-pmboard 全量套件（零新增回归）
covers: t-152423, t-6019b3, t-54248f, t-6eeacf, t-eb31cc
validates: FR-9

命令：`npx vitest run packages/web/dsh-pmboard/tests`。
改动前（git stash 本次改动的 12 个文件后重跑）与改动后：
`Test Files 41 failed | 136 passed | 3 skipped (180)`、`Tests 197 failed | 1750 passed | 19 skipped`；
41 个失败测试文件的集合两次逐一致 → 本次改动零新增回归。
（41 个失败为存量欠债：测试辅助仍在引用已被删除的 `defineMoveTool`/`defineDecomposeTool`、
`ReqboardDiveManager` 桩实现等，与本次交付无关。）

---

# 补实现证据（v1.1 · 2026-09-26）

> 背景：首轮交付按已批准的 20 张卡完成，但卡表漏掉了 requirement.md 明确要求的
> **覆盖度硬门禁**、**节点输入包注入 + 压缩**、**Dive 决策**（见 reviews/self-review.md §4）。
> 本节是补实现后的证据。

## 单元 · 节点输入包装配 + 压缩 + Dive 决策（FR-8）
covers: t-c4fa59, t-eb31cc
validates: FR-8

文件：`packages/tools/reqboard/tests/rtm/dive-integration.test.ts`（12 条）。
断言：`assembleNodeInput` full 注入完整 inputs/outputs/traceability/coverage 与 next_action；
compressed 只留 rate/uncovered（traceability 不下发）且 token 数显著更小；
implementing compressed 给出 `{progress, current_tasks:[id@phase]}`；
RTM 缺失不抛异常、next_action 如实说明；
`makeDiveDecision`：design 67% → 不推进且 blockers=[FR-3]；design 100% → 推进 decomposing；
implementing 未完成 → 列出未完成任务；accepting 40% → 门禁（80%）拦；RTM 缺失不猜。

## 单元 · 测试文档发现口径（FR-4 Level 3 / FR-5）
covers: t-0bf4ae
validates: FR-4, FR-5

同文件末节。断言：`tests/*.md` 里的 `covers:` 标注计入测试覆盖度——
修复前 `RTMContext.testFiles` 只扫 verification.md / design/test-cases.md / tasks/*.md，
本仓测试证据落在 `tests/` 下，导致测试覆盖度**恒为 0%**。

## 门禁 · 真实需求数据端到端读数（FR-2 / FR-5）
covers: t-0bf4ae
validates: FR-2, FR-5

命令（离线跑同一份生成器代码，写临时工作区，不动仓库）：

```bash
npx tsx /tmp/rtm-gate-probe.ts   # 见会话记录；ledger = .dsh-data/dsh-reqboard.json
```

本需求（REQ-260926140539-457b）真实数据读数：

| 门禁 | 读数 | 判定 |
| --- | --- | --- |
| design（阈值 100%） | 100%（11/11 FR） | ✅ 通过 |
| implementation（阈值 100%） | 100%（94/94 设计章节） | ✅ 通过 |
| testing（阈值 80%） | 95%（19/20 任务，仅 t-c010b8 无测试） | ✅ 通过 |

FR-8 决策输出：`can_proceed=true, next_stage=done, reason="测试覆盖度 95%，可以归档"`。

## 回归 · 门禁接线后 dsh-pmboard 全量
covers: t-0bf4ae
validates: FR-9

命令：`npx vitest run packages/web/dsh-pmboard/tests`。
结果：`Test Files 41 failed | 136 passed | 3 skipped (180)`、
`Tests 197 failed | 1750 passed | 19 skipped`——与改动前**逐一致**（新增门禁在存量/直种需求上豁免，
与本仓既有 isLegacy 口径一致）。
