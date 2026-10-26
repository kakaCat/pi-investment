# t-e7ef23 单测补全 + 全量回归

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
单测补全 + 全量回归

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：test
- 端侧：backend

## 得到什么结果
pytest tests/v2 -q 退出码 0；pytest tests/ -k watch -q 无新增失败

## 实施方案（implementation）
补 tests/v2 遗漏用例；pytest tests/v2 -q；pytest tests/ -k watch 全量。验证：退出码 0 无新增失败。

## 上游产出摘要（dependsSummary）
- 宿主接入：bootstrap 分支 + registry 任务

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
