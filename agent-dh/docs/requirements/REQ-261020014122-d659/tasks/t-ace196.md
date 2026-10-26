# t-ace196 total_trades 口径变更声明落 changelog

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
total_trades 口径变更声明落 changelog

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：doc
- 端侧：doc

## 得到什么结果
quantsys-v2 变更记录中出现本次口径变更条目：含字段名（total_trades/open_position_at_end/forced_closes）、新旧口径定义、生效时点（验收上线日）、新旧报告不可直接比较的提示

## 实施方案（implementation）
按 design/data-model.md §口径变更声明 的文案落 quantsys-v2 变更记录：total_trades 新口径=发生过的往返交易数（含窗口末强制平仓），旧口径=恰好平仓的交易数；变更方向只增不减；生效时点=本需求验收上线日；新旧报告不可直接比较。声明须与 t1 实际实现口径一致（先读 t1 代码再写）。

## 上游产出摘要（dependsSummary）
- 回测窗口末强制平仓计账与口径字段

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
