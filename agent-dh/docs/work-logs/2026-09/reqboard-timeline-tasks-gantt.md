---
id: wl-2026-09-reqboard-timeline-tasks-gantt
title: 项目看板：状态时间线 + 真拆分 + 任务页/甘特图
type: worklog
status: archived
updated: 2026-09-13
owners: [w-1cee2467]
tags: [worklog, 2026-09]
---

# 项目看板：状态时间线 + 真拆分 + 任务页/甘特图

- **日期**：2026-09-13
- **窗口**：w-1cee2467（session-1cee2467-95f9-46ec-9cd8-8577932e7060）
- **分支**：feat/reqboard-time → main
- **背景**：用户第二轮反馈三个「看起来有了、其实没有」的缺口（原文）：
  1. 「项目看板的需求没有对应的时间，创建时间，评审时间，拆分时间，实施时间，验收时间，归档时间」
  2. 「拆分是真拆分吗」
  3. 「拆分会拆分任务，有任务页面，任务有甘特图吗」

## 事实核对（改代码前先查账）

用真实台账（`agent-dh/.dsh-home/dsh-reqboard.json`，阅读时点 2026-09-13 16:18，revision 307）核对：

| 用户质疑 | 台账事实 | 结论 |
|---|---|---|
| 没有时间 | 需求记录只有 `createdAt/updatedAt`，没有任何按状态的进入时间 | **确认缺**——评审判定、停留时长、流程瓶颈都无法计算 |
| 拆分是真拆吗 | `tasks` 数组 **0 条**；除 HTTP `task/create` 外没有任何把需求变成任务的工具/代码路径 | **不是**——`decomposing` 只是个状态名 |
| 有任务页/甘特图吗 | client 只有「需求详情页内的任务列」，无跨需求任务页，无甘特图 | **没有** |

## 实现

### 1. 状态事件时间线（schemaVersion 2 → 3）
- `shared/protocol.ts`：新增 `StatusEvent {status, at, by, reason, inferred?}`、`recordStatus()`、`milestoneAt()`；
  `RequirementRecord.statusHistory` / `TaskRecord.statusHistory`。
- 写入点全覆盖：需求建卡/转移（routes）、任务建卡/转移（routes）、rollup 自动推进、`reqboard_move`、
  `reqboard_decompose`、`reqboard_task_move`。
- **历史回填**：`backfillRequirementHistory/backfillTaskHistory` 从 `createdAt` + 评论留痕
  （`[自动推进] a → b` / `[窗口推进] a → b` / `[状态] x ←` / `[状态] → x`）逐条反推，
  末态用 `updatedAt` 兜底；全部标 `inferred=true`，UI 显式渲染「回填」角标——
  推导值不得伪装成原始记录（R-013 口径）。
- `host/store.ts` 加载即迁移（内存补字段，下一次写盘持久化），不阻塞启动。

### 2. 真拆分 `reqboard_decompose`
- 参数：`requirement_id?` + `tasks[]`（`key/title/phase/side/depends_on/acceptance/context/skip_integration`）。
- 一次调用落库整批任务：批次内 `key` → 真实任务 id 映射；依赖只能是同批 key 或本需求已有任务；
  落库前过 `assertDagAcyclic`（无环/无悬空/无自依赖）——失败整笔回滚（不写库、revision 不 bump）。
- 只允许拆**本窗口绑定**的需求，状态须为评审/拆分/实施态（立项态先走评审）。
- 落库后 rollup 自动 `reviewing → decomposing`；任务开工 → `implementing`；全部完成 → `accepting`。

### 3. 任务推进 + 任务闸门同口径
- 新增 `reqboard_task_move`（本窗口需求下的任务；开工自动记一段执行段，离开 `in_progress` 自动结算
  `endedAt` + outcome，供甘特图/耗时统计）。
- `HUMAN_ONLY_TASK_TRANSITIONS` 收缩为**仅破坏性动作**（`*→canceled`、`canceled→todo`）：
  原 `in_review>done` 仅人可点 → 任务卡停在验收 → 需求永远进不了验收，看板再次静止。
- routes `task/move` 同步补执行段结算。

### 4. Client：时间线 + 任务页 + 甘特图
- 泳道卡面新增时间行（创建时间 / 当前态进入时间 / 已停留时长）。
- 需求详情：新增「时间线」（7 里程碑 + 停留时长 + 操作者 + 回填标注 + 总计）、「甘特图」，
  任务区块加「+ 任务」人工建卡入口。
- 任务详情：新增任务时间线。
- 新增**任务页**（页头「任务」入口）：按需求分组 → 里程碑条 + 甘特图 + 任务清单表
  （id/标题/状态/阶段/端侧/依赖/创建/耗时），行可点开任务详情。
- 甘特图零依赖 SVG：横轴时间、每行一任务、条形按状态分段着色（数据源 = `statusHistory`）、
  叠加需求里程碑竖线 + 「现在」线，`<title>` 悬停显示每段起止与时长。

## 验证

- **单测 153 passed / 12 files**（新增 `tests/timeline.test.ts` 5 例、`tests/decompose-tools.test.ts` 5 例、
  `client-view.test.ts` 新增时间线/甘特图/任务页/转义 9 例；改写任务闸门与工具清单契约 2 例）。
- 端到端（真实 Store + 临时台账文件）：拆分 2 任务（含依赖）→ 需求自动进拆分态 → 任务开工 → 自动进实施 →
  全部完成 → 自动进验收；越权/状态非法/悬空依赖/人工闸门逐条拒绝。
- 类型检查：与 main 基线逐条比对，唯一差异是 `board-mount.ts` 新增 2 处 `Cannot find name 'window'`
  （与既有 11 处同类，DOM lib 未纳入 root tsconfig 的既有噪声），无新错误种类。
- client 产物重建并校验符号：`lib/client.js` 55013 bytes，含 `dsh-pm-gantt`(28) / `dsh-pm-timeline`(2) /
  `dsh-pm-ttable`(4) / `open-tasks`(2)。

## 生效方式

- client 半（时间线/任务页/甘特图）→ 重建 `lib/` 后刷新页面即生效。
- host 半（新工具、时间线写入、加载迁移、闸门口径）→ 需重启 13080（`launchctl kickstart -k`）。

## 遗留

- 现有台账 15 条需求均为历史记录，时间线为回填（`inferred=true`，UI 标「回填」）；真实事件从本轮起累积。
- 任务页当前为空（历史 0 任务）——首条真实任务由窗口 agent 调 `reqboard_decompose` 产生。
