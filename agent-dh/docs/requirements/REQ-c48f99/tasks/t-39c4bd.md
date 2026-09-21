# t-39c4bd 端到端实测验收（E1-E4）+ 留证

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
端到端实测验收（E1-E4）+ 留证

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：review
- 端侧：fullstack

## 得到什么结果
E1 三连不同 to 的 task_move 折叠行两两不同含中文动作；E2 reqboard_status 展开首行中文；E3 bash/read/edit 零回归；E4 畸形 block 显示兜底行不白屏——四项逐条记录进验收材料

## 实施方案（implementation）
restart-with-build.sh 重启后新窗口会话实操；对照审计报告改前状态描述

## 上游产出摘要（dependsSummary）
- 其余 8 张业务卡片（submit/ask_confirm/status/capture/memory_write/decision_audit/portfolio_trade/watch_manage）
- renderSmart 人话首行：13 个 pmboard 工具逐配 summarize
- 迁移与兼容验证：renderJson 保留 + 旧会话重渲染 + 未注册工具零回归

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
