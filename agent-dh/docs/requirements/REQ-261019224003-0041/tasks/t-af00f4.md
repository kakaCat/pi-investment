# t-af00f4 goal/pm-workflow 旧名收尾

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
goal/pm-workflow 旧名收尾

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果
grep -rlE "from '(pm-goal|tool-pm-goal)" --include='*.ts' . | grep -v node_modules | wc -l = 0；pnpm typecheck 退出码 0；git status 确认 goal/ 与 pm-workflow/ 维持删除状态

## 实施方案（implementation）
17 个仍 import pm-goal* 的文件（pm/src 3、pm-core src 5、pm-core tests 5、tests 3、tool-pm tests 1，清单见 01-facts §3.2）逐一改接 ctx.workprocess 服务面或摘除；tsconfig.json/vitest 两处 goal 旧名三组映射摘除；scripts/package-boundary-check.mts 的 pm-goal 行摘除；goal/* 与 pm-workflow/ 保持删除不复活。

## 上游产出摘要（dependsSummary）
- 投影器 + 写回适配 + 驱动接管起链

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
