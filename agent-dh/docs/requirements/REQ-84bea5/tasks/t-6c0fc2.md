# t-6c0fc2 失败响亮化：评论+告警+标记

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
失败响亮化：评论+告警+标记

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果
grep -n "pausedReason" src/application/use-cases/AskConfirm.ts 命中；grep -n "commentRepo.create" 命中；grep -n "deps.alert" 命中；npx tsc --noEmit 编译通过

## 实施方案（implementation）
1. 打开 src/application/use-cases/AskConfirm.ts
2. 定位 catch 路径（约 L295-299）
3. 新增写系统评论（失败原因+恢复路径）
4. 新增调用 deps.alert（level=high）
5. 新增标记 advance.pausedReason
6. 保留原 note 返回

## 上游产出摘要（dependsSummary）
- 数据契约：RequirementRecord 扩展 pausedReason

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-21T06:34:38.276Z，窗口 session-8375f8a6-ef99-4656-83b1-6bb110a18f73）

AskConfirm catch 路径已实现失败响亮化：评论+告警+标记

### 完成项

- ✅ 在 catch 块中添加写系统评论（第 307-314 行）
- ✅ 评论内容包含失败原因和恢复指引（reqboard_decompose）
- ✅ 标记 advance.pausedReason（第 317-319 行）
- ✅ 调用 deps.alert?.alert() 发高优告警（第 326-330 行）
- ✅ 保留原 autoNote 返回逻辑
- ✅ npx tsc --noEmit 编译通过

### 改动文件

- `src/application/use-cases/AskConfirm.ts`

### 下一步

推进到 done，继续下一个任务

---
