# t-ac97a2 推错状态要说清：报错带上角色与合法边，验收标准能当场改

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
推错状态要说清：报错带上角色与合法边，验收标准能当场改

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果
新增 tests/task-move-role.test.ts 全绿：legacy 边推父卡报错含「父卡」与合法边；task_move(acceptance=…) 后台账 task.acceptance 已更新（不接线必红）。

## 实施方案（implementation）
TaskStatus.ts 暴露「角色 → 合法边」文本；MoveTask 非法转移报错含角色与合法边；TaskMoveTool 加 acceptance 参数并接线 amendTaskAcceptanceIfRequested（无 to 时仅修订）。

## 上游产出摘要（dependsSummary）
- 先定契约：任务/链工具的入参与返回长什么样

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
