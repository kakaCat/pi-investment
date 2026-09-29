# t-f42b5a 一眼看清父子：新增「父卡→子卡」结构查询·复核

> 需求：REQ-260927144541-0481 对齐父卡/子卡工具面：链入口收口 + 父子结构可查 + 契约与门禁对齐

## 在做什么
一眼看清父子：新增「父卡→子卡」结构查询·复核

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果
对设计与实现的偏离逐条给出结论；无偏离时显式写明「无偏离」及依据

---
## 汇报 1（2026-09-27T10:27:29.124Z，窗口 session-b71bb246-6f5c-417b-89d6-e48e4b697dcf）

复核：实现与 design/interfaces I-3、design/data-model 视图模型逐条比对——参数 parent_id?/requirement_id?、返回体 success/requirement_id/parents[]/error?、三枚错误码、无子卡 note 文案、10 个节点字段全部一致，无偏离；两条实现说明（reportSummary 由 completed[] 派生、未展开顶层卡 role=legacy）为口径注记，非行为偏离。

### 完成项

- I-3 参数与返回体逐条核对：parent_id?/requirement_id?、success/requirement_id/parents[]/error? 无偏离
- 错误码核对：REQBOARD_NO_BOUND_REQ、REQBOARD_NOT_BOUND_TO_WINDOW、REQBOARD_TASK_NOT_FOUND 均在用例覆盖
- 无子卡分支：subtasks=[] 且 note 与设计文案逐字一致「该父卡尚未开工展开子卡链」
- 只读性核对：TaskTree.ts 无 mutate 调用，读取仅经 deps.repo.snapshot（不改台账）
- 链序核对：按 dependsOn 拓扑排序；成环/悬空回退插入序且不抛（有注释说明）
- 口径注记（非偏离）：reportSummary 由 lastReport.completed 派生（台账无 summary 字段，守「不新增字段」）；未展开顶层卡 role=legacy 来自共享 taskRoleIn
- 证据复核：vitest run tests/task-tree.test.ts → 6 passed；线上实调 reqboard_task_tree 多次成功返回 8 条父卡链结构

### 下一步

测试卡：跑全量契约与门禁命令并附输出摘要

---
