# 项目知识索引

> （待写：一句话项目摘要——这个项目是什么、分几层、给谁用）

## 架构

- kb-architecture-layers · architecture · 四层职责与依赖方向 · → architecture.md#layers

## 规范

- kb-conventions-c01 · standard · 层边界只许向内 · → conventions.md#c-01

## 前端令牌

<!-- kb:generated:begin -->
- kb-tokens-colors · tokens · 颜色表与变量入口 · → design-tokens.md#colors
<!-- kb:generated:end -->

## 决策

（暂无）
- kb-0011 · decision · 盯盘通知四条硬契约落地：非交易日零事件（tick 与 run_forever 同口径 + 跳过留痕）、名称缺失不回落成代码、级别与闭环承诺解耦、外发可归因（quant.notification_audit 一通知一行 + 卡面 v2-watch@host#pid 尾注）。认知并进 · → entries/kb-0011.md
- kb-0002 · decision · DailyJobs 宿主加任务级交易日门：休市日不再空跑与发通知，跳过留痕为 skipped，门 fail-open、复市首日不跳过。 · → entries/kb-0002.md
- kb-0003 · decision · 对 a7cd 那套「V13 链路可信性设计」做了一次只读独立审计：26 个落点判定为「已实现但语义偏离」（一致 12/偏离 8/未实现 5/无法判定 1），并给出三条必须先处理项——跳过在调度路径仍被记 success（休市日实测）、回滚与判据载体均不在版本控制内、设计未管住的风 · → entries/kb-0003.md
- kb-0004 · decision · 给 v2 库表调度（APScheduler）补上与 DailyJobs 同一道交易日门：8 条吃当日行情的任务休市日只留 status=skipped（判据统一到 application/services/trading_day_gate.py，三值策略、门在执行期免 reloa · → entries/kb-0004.md
- kb-0006 · decision · 异常值检测三态化并修复 polars 迭代错对象：报错 7995 条归零、质量分由 95.01 降至 86.28、问题股 748 升至 4623。L2 页 data-quality-anomaly-semantics.md · → entries/kb-0006.md
- kb-0007 · decision · 编排 tick 与盘中监控接入唯一交易日门：休市日零调用、不读写持仓，留痕可循；10-07/10-08 窗口未取到，按人裁定以 10-06 同性质休市日收口 · → entries/kb-0007.md
- kb-0008 · decision · 数据质量告警去伪：D级改为按 distinct 标的计数、三项指标只在可交易域内判定，旧的两条误报（D级 806 只 / 评分 86.28）消失；新增「本期掉出可交易域」哨兵防采集漏批被静默豁免。 · → entries/kb-0008.md
- kb-0010 · decision · 净值序列统一交易日口径（写入闸门 / 读取过滤 / 缺口判断 / 存量清理四层落地）：非交易日的行写不进、读不到、不算缺口；缺口判断从 agent-dh 搬到 v2；并纠正「日历是白名单而非黑名单」这一被设计初稿搞错的前提（D-6）。 · → entries/kb-0010.md

## 坑

（暂无）
- kb-0001 · pitfall · quantsys-v2 记忆子系统下线：15 个 /api/memory* 端点与领域/仓储/测试/端口全删，记忆改由 agent-os（:8080）承载；表先备份后 DROP，四处外部消费方同步迁移（ADR-003 定归属）。 · → entries/kb-0001.md
- kb-0009 · pitfall · 每日任务通知改为「有事才说」：无事（no_output is True 或 status∈{no_event,no_op}）时开始与完成两条飞书都不发（台账仍 success），开始消息改为超阈值「⏳ 仍在运行」提示，失败与人工触发不受影响，两个 env 可一键回滚。 · → entries/kb-0009.md

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
