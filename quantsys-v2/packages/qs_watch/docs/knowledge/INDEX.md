# 项目知识索引

> （待写：一句话项目摘要——这个项目是什么、分几层、给谁用）

## 架构

- kb-architecture-layers · architecture · 四层职责与依赖方向 · → architecture.md#layers
- kb-guide-exec-loop · architecture · 盯盘执行闭环三接缝（成交回写/消息投递/待办闭环） · → [watch-exec-loop.md](../guides/watch-exec-loop.md#exec-loop)

## 规范

- kb-conventions-c01 · standard · 层边界只许向内 · → conventions.md#c-01

## 前端令牌

<!-- kb:generated:begin -->
- kb-tokens-colors · tokens · 颜色表与变量入口 · → design-tokens.md#colors
<!-- kb:generated:end -->

## 决策

（暂无）
- kb-0002 · decision · 交易计划（qs_plan）落地：计划编译成带 plan_id 的 watch_rules 由 WatchEngine 执行，成交回执推进计划状态，盘后定时反思四输入五问并驱动计划修改；进化层只沉淀知识不碰在跑计划；agent 经 trading_plan 工具双端调用。 · → entries/kb-0002.md
- kb-0003 · decision · 交易闭环三处接线补齐：盘后反思经既有 notify_agent /wake 真正唤醒 agent；减仓部分成交按累计比例逐批退役规则并写 fill 事件（幂等+降级）；消息 离场核实为既有 69b8 实现并补回归；metrics 增两个当日读数（缺数 null）。 · → entries/kb-0003.md

## 坑

（暂无）
- kb-0001 · pitfall · 盯盘执行闭环三接缝落地：成交回写收敛待办、critical 消息建 P1 待办、关闭接规则联动；agent 下单终判不变。 · → entries/kb-0001.md

## 契约

（暂无）

## 术语

- kb-glossary-terms · glossary · 术语表 · → glossary.md#terms

## 代码地图

<!-- kb:generated:begin -->
- kb-code-map-modules · map · 模块级地图与符号检索入口 · → code-map.md#modules
<!-- kb:generated:end -->

## 待写

- 《需求流水线》：六阶段状态机与五道人工门
