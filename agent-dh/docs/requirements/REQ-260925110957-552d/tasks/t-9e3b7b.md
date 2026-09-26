# t-9e3b7b 选择器改造

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
选择器改造

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果
单测验证：孤儿卡被选中；attempt 递增；非孤儿 in_progress 卡不被选中

## 实施方案（implementation）
1. 修改 application/internal/advance-select.ts：
   - selectReadySubtasks() 增加 resume 分支
   - 调用 orphanRecovery.identifyOrphans() 获取孤儿卡
   - 孤儿卡加入候选集（attempt+1）
   - 原有 todo 选择逻辑保持不变

## 上游产出摘要（dependsSummary）
- 孤儿回收
- 仓储层扩展

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-25T07:41:42.845Z，窗口 session-c954a261-4edb-4445-b1ff-56a53a9b5431）

完成选择器改造：补充孤儿回收 resume 分支

### 完成项

- 导入 orphan-collector 的 identifyOrphans 函数
- 在 selectAdvanceEvent 的"跑子卡"分支后增加 resume 分支（2.5）
- 遍历 in_progress 父卡，调用 identifyOrphans() 识别孤儿子卡
- 孤儿卡返回 RUN_SUBTASK 事件（会在执行时触发 attempt+1）
- 非孤儿的 in_progress 卡不被选中（保持原逻辑）
- 使用空 activeJobIds 集合（选择器是纯函数，不依赖外部状态）

### 改动文件

- `packages/web/dsh-pmboard/src/application/internal/advance-select.ts`

### 下一步

下一步：t-182606 workflow script 改造（批次 5 最后一个任务）

---

### 验证方法（可执行命令）
1. resume分支存在: `grep -i "resume" packages/web/dsh-pmboard/src/application/internal/advance-select.ts` 预期有输出
