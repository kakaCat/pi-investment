# t-eab3f3 定义北极星 KPI 并改造进化周报模板·复核

> 子卡（父卡 t-954eb4 · 阶段 review）——由自动实施链展开；本卡文档在验收前按 queue.json 台账回填（2026-10-19，w-503df447）。

## 在做什么
定义北极星 KPI 并改造进化周报模板·复核

## 状态
done（lastRun.ok=True）

## 完工记录（台账回填，原文）

- 对父卡 t-954eb4「定义北极星 KPI 并改造进化周报模板」实施方案三条逐条复核，结论：无偏离。①数据源工具与口径：w2-northstar-kpi.md §1-§3 与设计文档 design.md §2 W2 完全一致——KPI-1 信号胜率=signal_track report 按周（主指标 A+B 级 10 日胜率）、KPI-2 决策超额=decision_scores 逐条核对 context.account 过滤本实例账户、KPI-3 机制健康度=进化任务成功率(scheduler_manage list)+经验库有结局占比(experience_stats)+策略库 measured 占比(strategy_list)，且各项均附 2026-10-19 实调基线。②scheduler_manage update 改写周报 payload：经后端 API（GET /api/v1/scheduler/tasks/afe560bc-dc9b-4692-982f-1cd1a10e85d6）复核线上实况，weekly-report-m6 的 payload 已含【北极星 KPI 强制段】（三 KPI 逐项取数指令+工具名+时点）与【降频判定与执行】段（连续 4 周无改善→暂停 evolution-weekly-variant/meta-learning-weekly、evolution-distill-daily cron 改 0 0 23 * * 1、保留 weekly-report-m6 与 evolution-gate-adjudicate、飞书 high 告警、n/4 计数、恢复条件），与文档 §4/§5 逐条对应；原【技能指引】【M6 周报】【汇报要求】【账户事实源】段完整保留；全文不含 agent_brain 硬编码（用 <agent:identity 段账户名> 占位符，符合 R-019）。③KPI 定义文档已落盘 docs/requirements/REQ-261019144524-ec50/w2-northstar-kpi.md，含口径表、实测基线、降频规则（连续 4 周，与 decomposition.md 批准值一致）与恢复条件。一处有意适配（非偏离）：父卡描述写「decision_scores 按 agent_brain 过滤」，实现按 R-019 改为占位符引用本实例账户，语义等价且为规则强制。本卡边界遵守：未改代码、未跑父卡终态验收命令（signal_track/decision_scores 实调取数属测试段）。
