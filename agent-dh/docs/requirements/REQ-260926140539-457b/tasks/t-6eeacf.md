# t-6eeacf 任务状态变更时更新 rtm-implementing.yml

> 需求：REQ-260926140539-457b RTM YAML 追溯基础设施 - Dive 模式自动化的数据底座

## 在做什么
任务状态变更时更新 rtm-implementing.yml

## 解决什么问题
修改 src/tools/reqboard-task-move.ts，任务状态变更后调用 updateTaskDetail(reqId, taskId, {status, started_at/completed_at}) 并重新统计汇总文件。

## 得到什么结果
运行集成测试 `pnpm test reqboard-task-move-integration.test.ts` 通过；t-001 开工后 `yq .task.status rtm-implementing/t-001.yml` 返回 "in_progress" 且 started_at 非空；汇总文件 tasks_in_progress=1、tasks_todo=4；完成后 tasks_done=1

---
## 汇报 1（2026-09-26T10:32:49.378Z，窗口 session-c5ea210f-afc3-4735-a4d1-f9058b378363）

这一步做完，任务一开工/一完成，追溯快照里的任务状态和统计就跟着变，且永远以台账为准（RTM 不反向写台账）。

### 完成项

- 任务开工/完成 → 任务详情 + 汇总同步
- 首次进入执行态点亮第一个子阶段（幂等，不重复推进）
- HTTP 任务状态路由接线

### 改动文件

- `packages/tools/reqboard/src/rtm/implementing-generator.ts`
- `packages/web/dsh-pmboard/src/http/routers/tasks.ts`

---
