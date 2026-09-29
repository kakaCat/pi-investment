---
id: workflow-switch-plan
title: 实施链执行方式切换为 workflow 兜底路径（用户裁定 2026-09-27）
type: notes
requirement: REQ-260927202051-f6df
generated: 2026-09-27
---

# 实施链切换到 workflow 执行（断点备忘）

## 用户裁定
「接下来用 workflow 执行」——**关闭 Agent Teams，实施链子卡执行走 workflow 兜底路径**。
config/cordis.yml（与活动 patch）已于 **23:19:44** 写入：

```
- id: agent-team         disabled: true   # TeamService 本体
- id: tool-agent-team    disabled: true   # 模型侧 spawn/send/team_task_* 工具
- id: ui-agent-team      disabled: true   # 看板团队面板
- id: workflow-ptc       disabled: false  # 引擎真身（reqboard 兜底路径用）
```

**但 config 写入时刻（23:19:44）晚于本进程启动时刻（22:56:12）⇒ 未生效**，需重启。
运行期证据：本进程在 23:12 仍 spawn 出 `reqboard-t-e77b06`（说明 TeamService 仍可用）。

## 断点状态（重启前）
- t-0e7fac「实现 DAG 拓扑分层与派生视图」：**done（100%）**，子卡 t-5be8c6/t-315ea1/t-1e2054/t-a21eb3 全 done。
  交付：`src/domain/queue/topology.ts` + `tests/queue/topology.test.ts`(17) + `tests/queue/topology-integration.test.ts`(3)。
  验收证据：2 files / 20 passed；tests/queue/ 123 passed；`grep -c node:fs` = 0。
- t-e77b06「看板实测回归」：**in_progress**，子卡 t-c130ca/t-6df9a0/t-f4c9f5/t-10122a 全 todo，
  teamTaskId=task-22..25（Teams 关闭后不再使用）。重启会杀掉在跑的 `reqboard-t-e77b06` worker。
  该 worker 已产出真实浏览器证据（重启前）：`notes/board-live/cdp-board-check.mjs` +
  `shots-before-restart/{01-board-lanes,02-board-list,03-tasks-gantt}.png`。

## 重启后要做（续跑清单）
1. `scheduler_manage`/`agent_os_status` 确认进程已起、:13080 健康。
2. 确认 Teams 已关：`list_agents` 不再能 spawn；或看启动日志无 agent-team 服务。
3. `reqboard_task_run(task_id='t-e77b06')` → 子卡经 **workflow 引擎**执行（ExecuteTask 的 `deps.workflow.start` 分支），
   不再 spawn 持久 Worker、无 `team_report_missing`。
4. 链收口后：
   - 核对 queue.json 中 t-e77b06 及其 4 子卡 done、需求侧状态；
   - **执行已裁定待办**：修 `src/application/use-cases/queue-access.ts:37 readyTasksOf` 的口径漂移
     （放宽 `computeReady` 形参为结构子集 + 该函数委托同一实现），跑测试后 `pnpm build`（dsh-pmboard 从 dist 加载）。
5. 全部父卡收口 → 需求进 accepting → `reqboard_submit(kind=verification)` 交棒（材料=verification-evidence.md，
   其中 #5「看板渲染」待补 board-live 截图证据）。

## 注意
- **dsh-pmboard 运行时加载 dist/index.mjs**（package.json main）⇒ 改源码必须 `pnpm build` 才生效。
- 本需求迁移**已完成**（活台账 schemaVersion=9、tasks 已移除、51 份 queue.json 落盘、进程 22:56 重启后加载 v9）。
  早期 verification-evidence §7 的「脆弱窗口」已解除。
