# t-9d70fe 发版部署与实证回归（FR-5）

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
发版部署与实证回归（FR-5）

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：test
- 端侧：fullstack

## 得到什么结果
dist 校验 grep 命中新逻辑符号；实证三步骤全过：①strategy_execute(mode=backtest, strategy_id=202, symbol=002007, 2025-09-20~2026-09-20) 返回 total_trades≥1 且含 forced_closes/open_position_at_end；②evolution_run(202, 002007, propose) 返回 success（qv2_real 或 degraded），degraded 时 degraded_reason 非空无 schema 硬错误；③evolution_leaderboard(202) 与 evolution_run 表述一致

## 实施方案（implementation）
quantsys-v2 侧重启服务使 t1 生效；agent-dh 侧走 agent-dh/scripts/restart-with-build.sh 发版 evolution 包（dist 加载，构建后必须 grep dist 产物确认新符号存在，失败按未生效处理并报告，lessons 纪律）。然后实调三个验收锚点（FR-5）：strategy_execute(backtest,202,002007,一年窗)、evolution_run(202,002007,propose)、evolution_leaderboard(202)。实调结果记录到验收证据（命令+输出摘要）。

## 上游产出摘要（dependsSummary）
- 回测窗口末强制平仓计账与口径字段
- evolution_run 降级 null 键剔除与契约用例

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
