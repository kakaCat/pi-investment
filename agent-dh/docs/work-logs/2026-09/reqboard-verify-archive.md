# 需求看板：验收人工审核 + 归档文档合并规范

- **日期**：2026-09-13
- **窗口**：w-1cee2467
- **分支**：feat/reqboard-verify → main
- **用户要求（原文）**：「验收 有人工审核 / 归档 要有项目文档设计，文档如何合并，不同问题如何记录文档」

## 一、验收：人工审核 + 证据闸

- **闸门收回**：`accepting>done` 重新成为**人工闸门**（agent 调用返回 human_gate）——
  agent 可以把需求推到验收、可以交材料，但「过」必须人点。此前为了让流程不静止把这道闸也放开了，
  代价是"没有人工审核"；现在闸门只在这一处收紧，其余在途推进仍全自动（回到 2026-09-11 的裁定边界）。
- **证据闸**：新工具 `reqboard_verify_submit({ summary, evidence[] })` 提交验收材料
  （一句话交付结论 + 可复核的证据：命令与输出摘要 / 报告路径 / 截图路径）；空 summary、空证据一律拒绝。
  **没有验收材料时人也不能点通过**（`POST /req/verify/pass` 返回 400 并说明缺什么）。
- **人工裁决**：`POST /req/verify/pass` → done；`/req/verify/rework`（**必须写意见**）→ implementing 返工；
  审核结论（pass/rework + 意见 + 审核人 + 时间）写进 `verification`，同时进评论与时间线。
- 看板：卡面 `待人工审核 / 待验收材料` chip；详情页「验收（人工审核）」区展示证据清单与两个按钮。

## 二、归档：项目文档设计（文档如何合并 / 不同问题如何记录）

**设计文档**：`agent-dh/docs/architecture/requirement-archive.md`（与代码同源，改规则要同时改）
**模板**：`agent-dh/docs/requirements/_template/{requirement,plan,verification,retro,known-issue,research}.md`

核心定义：**归档 = 存底 + 合并**——需求目录留全套原始材料（过程与证据），同时把"别人以后要读的结论"
并进项目文档并写索引条目。一句话判据：需求目录是档案，项目文档是活的知识。

**合并矩阵（代码级 `ARCHIVE_DOC_RULES`，缺项/去错地方直接拒绝）**：

| 类型 | 需求目录必填 | 合法合并去向 |
|---|---|---|
| feature | requirement, plan, verification | agent-dh/docs/architecture|guides（或 docs/ 同名） |
| bug | requirement, verification, **retro** | agent-dh/docs/known-issues/ |
| doc | requirement, verification | agent-dh/docs/ |
| refactor | requirement, plan, verification, **retro** | agent-dh/docs/architecture|work-logs |
| spike | requirement, **retro** | agent-dh/docs/research/ |
| chore | requirement, verification | agent-dh/docs/work-logs/ |

**三种合并方式**：追加小节（既有架构/指南里加节 + 标 REQ id）/ 新建独立文档（known-issues、research）/
更新索引一行（`agent-dh/docs/requirements/INDEX.md`）。

**流程**：agent `reqboard_archive_submit({ dir, docs[], merged_into[], index_entry })`（落库前逐条校验）
→ 人点「归档」（`POST /req/archive`，同样再校验一次）→ 需求进 archived + 写 `archivePath` 与时间线。

新增目录与索引：`agent-dh/docs/known-issues/README.md`、`agent-dh/docs/research/README.md`、
`agent-dh/docs/requirements/INDEX.md`（归档索引）、`agent-dh/docs/requirements/_template/`。

## 验证

- **单测 184 passed / 14 files**：新增 `acceptance-archive.test.ts` 11 例（agent 点不动验收通过、
  无材料不能过、提交→通过→done 与时间线、退回返工必须写意见且回 implementing、空材料拒绝、
  归档矩阵正反例、未备材料不能归档、未完成不能备材料）+ client-view 新增 6 例（验收/归档区渲染与 chip）。
- 类型检查：与 main 基线逐条比对，无新错误种类（仅既有 `Cannot find name 'window'` 一类）。
- client 产物重建：`lib/client.js` 65631 bytes。

## 生效方式

- client 半（验收区/归档区/chip）→ 刷新页面。
- host 半（新工具、两个闸门、归档校验）→ 重启 13080。

## 补记（同日）：归档规范对齐项目文档规范（用户追问「归档要有规范，你设计了吗」）

**认账**：第一版只设计了"需求归档时的合并规则"，**没有设计项目归档规范**，而且**擅自新增了
`known-issues/` 与 `research/` 两个目录**——它们不在项目既有的《文档管理规范》
（`docs/DOCUMENT-MANAGEMENT-PLAN.md`）里。这正是"自创平行体系"，是归档最容易犯的错。

**改正**：

1. 合并去向**收敛到既有规范目录**（`adr / architecture / guides / rfcs / work-logs / strategy-research`
   及其 agent-dh 对应目录），删掉自建的 `known-issues/`、`research/`；
   缺陷类改去 `guides/`（故障排查手册）或 `architecture/`（机制性根因），调研类改去
   `rfcs/`（成提案）/ `architecture/`（成认知）/ `strategy-research/`（策略类）；
2. 项目级规范 `docs/DOCUMENT-MANAGEMENT-PLAN.md` 增加「需求归档（reqboard）」一章（档案库 + 合并矩阵 +
   索引 + 铁律），`docs/README.md` 增加「需求归档」入口；
3. 执行细则重写：`agent-dh/docs/architecture/requirement-archive.md`（明确上位规范、版本控制提醒：
   `work-logs/` 不入库 → 耐久结论不许只落在那里）；
4. 模板改名并改口径：`known-issue.md` → `troubleshooting-entry.md`（落 `guides/` 的一条条目）；
5. **代码级守卫**：单测断言 `ARCHIVE_DOC_RULES` 的每个合并去向都必须落在
   `(agent-dh/)docs/` 下的既有规范子目录内——自创目录会被测试与运行时双重拦住。

**教训（值得记）**：规范类需求要先读既有规范再设计。我上一轮只看了代码与需求，没读
`docs/DOCUMENT-MANAGEMENT-PLAN.md`，结果设计出与项目标准冲突的目录——**"看起来更专业的新目录"
往往就是规范破坏的第一粒沙**。
