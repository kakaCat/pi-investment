# t-acd60f 一眼看清父子：新增「父卡→子卡」结构查询

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
一眼看清父子：新增「父卡→子卡」结构查询

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果
新增 tests/task-tree.test.ts 全绿：含 4 子卡的父卡返回 subtasks.length=4 且链序；无子卡返回 [] + note；跨窗口 → REQBOARD_NOT_BOUND_TO_WINDOW。

## 实施方案（implementation）
新增 TaskTree.ts 用例 + TaskTreeTool（只读，经 deps.repo），在 src/index.ts 注册；返回父卡 + 子卡链（按链序）。

## 上游产出摘要（dependsSummary）
- 先定契约：任务/链工具的入参与返回长什么样

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
