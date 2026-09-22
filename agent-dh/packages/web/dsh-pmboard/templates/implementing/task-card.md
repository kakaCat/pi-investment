# {{TASK_ID}} {{TASK_TITLE}}

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件。
> 「在做什么 / 解决什么问题 / 得到什么结果」三节是契约不是排版——缺任一会被门禁拦。

## 在做什么

（一句话 + 改哪些文件）

## 解决什么问题

（业务问题——开工前必填，不许留"未填写"）

## 范围

- 阶段：doc / ui / analysis / implement / test / review / merge
- 端侧：frontend / backend / fullstack / doc
- 需求条款：FR-x（requirement_refs）
- 设计落点：（I-x / S-x / P-x / C-x / T-x / UC-x / M-x——继承拆分任务表的「落点」列：本卡改哪个编号对象、在哪个文件）
- 覆盖用例：（TC-x——本卡由哪几条用例验证；完成后测试证据回填这些用例的执行结果）

## 得到什么结果

（验收标准：可证伪——跑什么、看到什么算过）

## 风险与回退

| 风险 | 回退动作 |
|---|---|
| （做砸了会怎样） | （怎么回到改前：git revert 本卡 commit / 关开关 / 恢复备份——写死，失败时不用现场想） |

## 依赖

（前置任务 id 与标题）

---
<!-- 以下由 reqboard_task_report 追加：完成项 / 改动文件 / 下一步 -->
