# t-c4fa59 实现实施节点 RTM 生成（汇总 + 任务详情目录）

> 需求：REQ-260926140539-457b RTM YAML 追溯基础设施 - Dive 模式自动化的数据底座

## 在做什么
实现实施节点 RTM 生成（汇总 + 任务详情目录）

## 解决什么问题
创建 src/rtm/implementing-generator.ts，实现 generateImplementingRTM(reqId)（汇总 + 任务详情目录）与 updateTaskDetail(reqId, taskId, updates)（只写变化的任务文件），workflow 依 phase 决定子阶段。

## 得到什么结果
运行 `pnpm test implementing-generator.test.ts` 通过；5 个任务生成后 `yq .status.tasks_total` 返回 5；`ls rtm-implementing/*.yml | wc -l` 返回 5；backend 任务 workflow 不含 ui 阶段；updateTaskDetail 后 `git diff` 仅该任务文件变化

---
## 汇报 1（2026-09-26T10:32:48.996Z，窗口 session-c5ea210f-afc3-4735-a4d1-f9058b378363）

这一步做完，实施阶段有了「快照 + 明细」两级文件：看板只读一个轻量汇总就能知道进度，要看细节再读单个任务文件——更新也只写变化的那一份。

### 完成项

- rtm-implementing.yml 汇总（tasks_total/done/in_progress/todo）
- 每任务一个 rtm-implementing/t-xxx.yml，含按 phase 生成的 workflow 子阶段
- updateTaskDetail 增量更新 + 汇总刷新（以台账为事实源）
- backend 任务自动跳过 ui 阶段

### 改动文件

- `packages/tools/reqboard/src/rtm/implementing-generator.ts`

---
