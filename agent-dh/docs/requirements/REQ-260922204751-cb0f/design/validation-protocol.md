---
req_id: "REQ-260922204751-cb0f"
title: "实施过程中展示代码 diff（pmboard）· 设计（结论：不需要开发）"
stage: design
status: design
owner: "session-bbfc9a7a"
category: spike
created: "2026-09-22"
serves: SP-1, SP-2, SP-3, SP-4, SP-5, SP-6
---

# 设计：实施过程 diff 展示 —— 结论与证据固化（不需要开发）

> 读者：本需求的复核人，以及日后若重启该功能的执行窗口。
> **决策来源**：G2 确认弹框中的人工意见「我们不需要开发」（2026-09-22）。本设计据此**不规划任何开发**：
> 不实现功能、不新增探针或脚本、不改 `src/`、不进入实施。
> 落盘口径：按闸门硬编码路径落 `docs/requirements/REQ-260922204751-cb0f/design/`；需求正文另以逐字一致副本落盘（见 requirement.md 顶部补记）。
> 文件名沿用 `validation-protocol.md`：台账已自动登记该路径的 kind=design 产物，改名会让该条目悬空（R-020）。

## D-VALID-0 决策：本需求不需要开发（serves: SP-1, SP-2, SP-3, SP-4, SP-5, SP-6）

- **依据**：G2 确认弹框中的人工意见「我们不需要开发」（2026-09-22，本窗口 w-bbfc9a7a）。
- **含义**：可行性结论保留，但**不做实现**——pmboard 不新增 diff 展示功能，本需求不再投入开发工作量，也不落任何实现类任务卡。
- **本设计的全部内容**：把**已经实测过**的证据与结论固化在案，日后若改变决定可直接复用（须另立 feature 需求，见 D-VALID-5）。

## D-VALID-1 要回答的问题与答案（serves: SP-1, SP-2, SP-3, SP-4, SP-5, SP-6）

**问题（一句话）**：在不新增第三方依赖、不放宽文件访问白名单的前提下，pmboard 能否在任务实施过程中给出「工作区当前状态 vs 开工基线」的真实 unified diff，且路径口径与台账 `filesChanged` 一致？

**答案：能做（已实测，证据见 D-VALID-2）；但本需求决定不做。**

## D-VALID-2 已完成的验证：一次性命令实测（2026-09-22）（serves: SP-1, SP-2, SP-4, SP-5）

工作区根 `…/agent-dh`（实测 pmboard state 接口 `workspaceRoot` 字段），git 2.39.5，当时 HEAD `42159f56`。以下均为**已执行**，不是待办：

| 探针 | 验证什么 | 命令（已跑） | 实测结果 | 结论 |
|---|---|---|---|---|
| P1 | 基线 diff 同时覆盖已提交与未提交改动 | `git -C …/agent-dh diff --relative --numstat b24fb9ed -- packages/solve-kit/src/host.ts`；基线换 `HEAD~3` 对照 | 基线 `b24fb9ed` → 三列 `0`、`301`、`packages/solve-kit/src/host.ts`；`HEAD~3` → 空 | 成立：基线必须早于改动（开工记 HEAD） |
| P2 | 路径口径与台账 `filesChanged` 一致 | 台账 `lastReport.filesChanged` vs `--relative --numstat` 的路径列 | 两侧均为工作区相对路径、无前导 `./`（台账样例 `packages/pages/dsh-pmboard/src/domain/errors.ts`） | 成立 |
| P4 | 基线失效可被机械探测 | `git cat-file -e b24fb9ed` 与 `-e deadbeef` | 退出码 `0` / `128` | 成立：可据此返回 `baseline_unavailable` |
| P3 | 共享工作区污染规模与可标注性 | `git status --porcelain` 计数 | 71 个脏文件（快照，2026-09-22；报告初稿实测 59） | 只能如实标注，无法从 git 侧区分同一文件内的他方改动 |
| P5 | diff 体量可控、截断阈值可校准 | `--numstat` 与字节数统计 | 可取得单文件量级样本 | 阈值（2000 行 / 512KB）需在真实施时校准——本次不实施 |
| P6 | 服务端取 git 的进程前提 | 静态核实：同仓先例 `packages/tools/lifecycle/src/git.ts`、工作区 git 2.39.5 可用 | **未在插件进程内实跑** | **未验证**（如实标注，不冒充通过） |

## D-VALID-3 判定口径与时限（serves: SP-3, SP-4）

- 三态口径：**是（可行）**＝P1 / P2 / P4 全过；**何种条件**＝仅 P3 / P5 / P6 不过；**否**＝P1 / P2 / P4 任一不过。本次落点 = **是（能做）**。
- **时限：0（不再投入）**——验证已于 2026-09-22 一次性完成，本需求不设新的时间盒，也不再派发探针任务。
- 降级纪律（留给将来实施）：基线失效须**响亮**降级（`degraded: baseline_unavailable` + 原因），禁止用空 diff 冒充「无改动」。

## D-VALID-4 边界：本设计不做什么（serves: SP-6）

- 不实现功能、不新增探针或脚本、不改 `src/` 任何文件、不新增第三方依赖。
- 不放宽 `src/http/routers/artifacts.ts` 的文件白名单 `classify()`（将来若实施，这是硬约束）。
- 不修 SP-6 的流水线断点（spike 的流程档案声明跳过 design/decomposing，但 `reqboard_capture` 无条件进 brainstorming、状态机无 `draft→implementing`）：属独立缺陷，另立需求。
- 不出统计结论：样本 = 1 仓库 / 1 需求，只判「能不能做、坑在哪、代价多少」，不判上线收益（R-016 精神）。

## D-VALID-5 若将来重启该功能（serves: SP-1, SP-2, SP-3, SP-4, SP-5, SP-6）

推荐方案（git 基线 diff）、代价估算与「实施候选验收清单」原样保留在需求 §结论 与 §附录；重启须**另立 feature 需求**并重走设计 → 拆分，不在本需求内二次创作。

## D-VALID-6 本设计的验收口径（serves: SP-1, SP-2, SP-3, SP-4, SP-5, SP-6）

- [ ] 本文件存在于 `docs/requirements/REQ-260922204751-cb0f/design/`，且每个二级章节带 `serves:`（本窗口已用线上闸门代码预检：`design_orphan`、`dangling_reference`、`design_contains_decomposition` 均通过）。
- [ ] 需求正文可打开（看板「文档记录」）：`docs/rfcs/REQ-260922204751-cb0f/requirement.md` 与 `docs/requirements/REQ-260922204751-cb0f/requirement.md` 的 sha256 一致（实测均为 `0805ecaa…`）。
- [ ] 结论口径可核验：**本需求无开发任务**，后续阶段不应落任何实现类任务卡。

## D-VALID-7 修订记录（serves: SP-1, SP-2, SP-3, SP-4, SP-5, SP-6）

| 日期 | 修订 | 依据 |
|---|---|---|
| 2026-09-22 | 初稿：spike 验证协议（探针 P1–P6 + 三态判定 + 1 工作日时限） | 需求 §结论 |
| 2026-09-22 | 按 G2 意见「我们不需要开发」改为**结论文档**：探针由「待执行」改为「已完成证据」，时限归零，明确不进入实施、不落实现类任务卡 | G2 确认弹框人工意见 |
