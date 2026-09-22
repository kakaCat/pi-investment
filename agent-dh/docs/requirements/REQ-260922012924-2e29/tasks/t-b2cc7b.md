# t-b2cc7b [FR-3] cordis.yml 开启 nodeIsolation 并重启验证

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
[FR-3] cordis.yml 开启 nodeIsolation 并重启验证

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果
grep -A2 "id: dsh-pmboard" config/cordis.yml 见 nodeIsolation: true；重启后 grep "压缩开关" .dsh-data/state/launchd.out.log | tail -1 见 NODE_ISOLATION=true；isolation-trace 有 G0 门 skip(doc_not_ready) 或后续压缩留痕。

## 实施方案（implementation）
编辑 agent-dh/config/cordis.yml 第 127-129 行；cd agent-dh && ./scripts/start.sh（托管自动 kickstart）；grep 启动日志与 state/node-isolation-log.json。

## 上游产出摘要（dependsSummary）
- （无依赖）

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
