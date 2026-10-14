# 拆分计划（REQ-261006010812-cd19）

> 设计依据：[`design/architecture.md`](design/architecture.md) / [`interfaces.md`](design/interfaces.md) /
> [`data-model.md`](design/data-model.md) / [`test-cases.md`](design/test-cases.md) / [`use-cases.md`](design/use-cases.md)。
> 被审对象：[`../REQ-261004154902-a7cd/design/design.md`](../REQ-261004154902-a7cd/design/design.md)（6 份设计文档 + 其声称落点）。

## 1. 目标（一段人能读懂的）

对 a7cd 的那套「V13 链路可信性设计」做一次**独立审计**：把设计的每一条声明与这台机器上的代码、库表、
工具、版本状态**逐条对撞**，给出四档判定与证据；再回答三个现实问题——**照它继续干有没有坑**、
**它写的回滚路径成不成立**、**它没管住的风险还剩哪些**。全程只读，产出是一份能被第三方复核的报告。

## 2. 改动盘点（按设计逐份对照）

> 本需求**不动生产代码**（D-3）：新增的只有审计产物，`live_trading/` `application/` `infrastructure/` `tools/` 一字不改。

| 设计节 | 动作 | 文件（新增 `+`；无修改 `~`、无删除 `-`） | 卡 |
|---|---|---|---|
| architecture §1（面 A/E） | 设计条目清单 + 版本面取证 | `+evidence/a1-design-selfconsistency.md` | t1 |
| architecture §1（面 B）§2（判定链路） | 逐条落点 → 四档判定 → 一致性矩阵 | `+evidence/a2-impl-matrix.md` | t2 |
| data-model §1/§2（面 C）+ test-cases §2（面 D） | 只读库表事实 + 验收命令复跑 | `+evidence/a3-calldb-replay.md` | t3 |
| architecture §2（未覆盖）+ use-cases §3/§4 | 缺口清单 | `+evidence/a4-gaps.md` | t4 |
| interfaces §1~§6 + test-cases §1/§3/§4 | 报告五节 + 三道自检 + 抽查 + 只读回归 | `+audit-report.md` | t5 |
| architecture §3（只读边界） | 约束，不产生文件；自检落在 t5 | — | t5 |

## 3. 任务表

> `DU = files×1 + anchors×0.5 + chars/2000`（容量 16 DU/卡）。全部卡 ≤ 6.1 DU，**无超容量卡**。

| key | 标题 | phase | side | depends_on | FR | files | anchors | chars | DU |
|---|---|---|---|---|---|---|---|---|---|
| t1 | 设计文档自洽性 + 版本面取证 | analysis | doc | — | FR-1 | 2 | 4 | 1500 | 4.75 |
| t2 | 实现一致性矩阵（面 B，逐条落点） | analysis | doc | t1 | FR-2 | 2 | 5 | 2000 | 5.5 |
| t3 | 只读库表事实 + 验收命令复跑 | analysis | doc | t1 | FR-3 | 2 | 6 | 2200 | 6.1 |
| t4 | 设计未覆盖缺口审计 | analysis | doc | t2, t3 | FR-4 | 2 | 4 | 1500 | 4.75 |
| t5 | 报告汇总 + 三道自检 + 抽查复现 | doc | doc | t2, t3, t4 | FR-5, FR-6 | 2 | 6 | 2000 | 6.0 |

## 4. 每卡的实施与验收（摘要；验收均可跑）

- **t1**：读 a7cd 的 6 份设计文档 + `requirement.md`，建「设计条目清单」（每条带 `文档:行`）；
  做四类自洽性检查（跨文档同事实取值、文档间引用有效性、§13 未定决策是否闭环、数值口径）；
  对设计点名的每个文件/工具跑面 E：`git check-ignore -v` / `git ls-files --error-unmatch` / `git log -1 -- <path>` / `git status --porcelain`。
  验收：条目 ≥10 条且每条带两侧 `文档:行`；面 E 对每个点名路径给出「在版本内? + 最近提交」；
  `grep -c '^\[L' a1-design-selfconsistency.md` ≥ 条目数；软判定词 0 命中。
- **t2**：按设计 §1~§11 逐个落点定位实现（`RunOutcome` / `FailureSink.report_failure` /
  `should_have_run` / `trading_day_resolver` / `expired` / `oversell_blocked` / `V13_CHAIN_STRICT` /
  `build_cron_trigger` / `select_channels` / `AgentChannel.supports` / REBALANCE·RISK_ALERT formatter 等），
  读实现核对语义后落四档判定。验收：矩阵行数 ≥ 落点数；证据列全部匹配 `^\[L[1-4]\]`；
  `未实现` 行带搜索命令与命中数；`语义偏离` 行写出两侧取值；软判定词 0。
- **t3**：① 对设计 `data-model.md` §1 的 6 张表跑只读 SQL，记「库名 + 语句 + 时刻」；
  ② 逐条实跑 `design.md` §12 的 7 条命令（C1~C7），记 `实跑/不可跑` + 真实退出码 + ≤80 字摘要，
  不可跑者同行写原因并另给替代判据（标 `L4`）。验收：复跑表 7 行齐全；`实跑` 行退出码为真实整数；
  库证据条目均含库名+语句+时刻；对 E-3（工具缺失）与 E-4（gitignore）给出现场复核结论；
  跑 pytest 前后对生产库同一只读计数比对无变化（证明测试只落 `quant_test`）。
- **t4**：复核 requirement.md 已实测的 E-2/E-3/E-4/E-6，并找**设计未覆盖**但仍在风险中的链路
  （a7cd 的 E15 三条坏链路未排班 / E16 盘中无 V13 止损 / 无提交导致回滚失效 / 休市日的非日检写路径）。
  验收：缺口 ≥4 条且每条带 `[L1-L3]` 级证据；风险等级 ∈ {高, 中, 低}；
  其中 ≥2 条属「设计未覆盖」（非 requirement.md 已列的 E-*）。
- **t5**：汇总 `audit-report.md`（五节契约）；改进项 ≥5 条（五列齐、判据含命令）；
  跑 `test-cases.md` §1 三道自检、§3 抽查 5 行、§4 只读性回归，结果写进附录。
  验收：`grep -c '^## '` ≥5 且五个节名齐；软判定词 0；改进项 ≥5 且「可证伪判据」列非空含命令；
  附录含 5 行抽查结论；`git status --porcelain -- live_trading/ application/ infrastructure/ tools/` 与本轮开审前逐字一致。

## 5. 不在本次范围

- 不修 a7cd 的任何缺陷、不补它缺失的工具、不改它引用的配置（发现即进 t4/t5 的改进项）；
- 不评价 V13 的策略规则与收益（D-2：本次只审链路设计与实现一致性）；
- 不做生产进程动作（`kill -9` 探活验证）与真实外发（D-3）——相关判据以 `L4` 落 `无法判定`；
- 不做表结构变更、不写任何库表、不改写 `v13_simulation` 历史数据。
