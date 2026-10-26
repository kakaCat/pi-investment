# 用例 · REQ-261019224003-0041

> serves: FR-5, FR-6, FR-7, FR-8

## UC-1 起链与驱动接管（serves: FR-6）

1. 人或 agent 调 `reqboard_task_run`（起链入口，`autoRun=true`）；
2. workprocess 驱动器每拍：投影器重建 WorkProcess 快照 → decide 纯函数出决策 → 写回经 pm 用例 / 投递经 pm 投递器；
3. 子卡全部完成 → `closedAt` 落 workprocess 存储域；需求进 accepting 仍由 pm 现状逻辑推进。
- 验收：真机两阶段全 auto 流程，阶段自动开工/收口、`closedAt` 落账。

## UC-2 子卡 blocked 与预算追加（serves: FR-5, FR-7）

1. 子卡连续 blocked 达 `blockedAfterRounds`（=3，驱动器与工具面同值）→ 任务挂 blocked，`blockedReason` 写 pm 卡面并显示；
2. 人处置后 resume → workprocess 回合账 `grants` +1 份（预算追加），驱动器续跑。
- 验收：构造 blocked 场景，卡面出现 `blockedReason`；resume 后 `rounds.tasks[id].grants` 加一。

## UC-3 DAG 顺序与投影（serves: FR-5）

1. 父卡下多子卡带 `depends_on`；pm ready 集合决定下一张可执行卡；
2. 投影器把 `nextReady` 折进阶段事实，驱动器只驱动"当前 ready 那张"的回合。
- 验收：投影器单测——给定 tasks/runs 夹具，输出快照中可执行任务与 pm `nextReady` 一致。

## UC-4 需求级人工门不受影响（serves: FR-6）

- `reqboard_move` / `reqboard_ask_confirm` / 验收单 / 归档全程不经过 workprocess；workprocess 的 `closedAt` ≠ 需求归档。
- 验收：回归——走一遍 brainstorming→design 人工门，确认无 workprocess 参与痕迹。

## UC-5 goal/pm-workflow 退役后旧引用收编（serves: FR-8）

- 17 个 `import pm-goal*` 文件逐一改接 `ctx.workprocess` 服务面或摘除；`round-state.ts` 回合契约归属改指 workprocess。
- 验收：`grep -rlE "from '(pm-goal|tool-pm-goal)"` = 0 且 `pnpm typecheck` 退出码 0。

## UC-6 装载形态切换（serves: FR-2）

- desktop profile 摘除四条 workprocess bundle 行（改由 `pm/cordis.patch.yml` 5 行提供），重启后六个工具在、客户端半进浏览器、`workprocess.json` 继续被写。
- 验收：`composeEntries` 复现 5 条 entry、`skippedBundles` 为空；重启实测工具面在。
