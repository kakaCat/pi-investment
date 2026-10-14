# t-9adb94 设计未覆盖缺口审计

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
设计未覆盖缺口审计

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：analysis
- 端侧：doc

## 得到什么结果
evidence/a4-gaps.md 存在且缺口 ≥4 条，每条带 [L1]-[L3] 级证据与风险等级（取值只能是 高/中/低）；其中 ≥2 条属「设计未覆盖」（明确标注与 requirement.md 已列 E-* 的区别）；对 E-2 给出面 E 证据（新件 git status 显示未跟踪 + git ls-files 报 pathspec 不匹配），对 E-3 给出文件不存在证据，对 E-4 给出 git check-ignore -v 输出。

## 实施方案（implementation）
复核 requirement.md 已实测的 E-2（实现从未提交）E-3（验收工具缺失）E-4（判据被 gitignore 排除）E-6（归档需求覆盖度自相矛盾），并主动找「该设计未覆盖但仍在风险中」的链路：a7cd 的 E15（risk_check / verification / weekly_report 三条链路坏且未排班）、E16（盘中无 V13 止损，intraday_monitor 账户写死 rotation_main 且 rule_guard 拒绝策略账户）、休市日非日检写入路径、无提交导致的回滚失效、pytest.ini 假绿灯门禁是否真落地。每条给证据（L1-L3）+ 影响面 + 风险等级（高/中/低）。产出 docs/requirements/REQ-261006010812-cd19/evidence/a4-gaps.md。

## 上游产出摘要（dependsSummary）
- 实现一致性矩阵（面 B，逐条落点）
- 只读库表事实 + 验收命令复跑

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-10-06T01:32:40.892Z，窗口 session-6a58ec8c-8f25-44a6-9be1-a02c4a16d94f）

t4 完工：8 条缺口定级落盘（高 4 / 中 3 / 低 1），其中 4 条属「设计未覆盖」；三张子卡（取数/分析/复核）均已走完。

### 完成项

- 产出 evidence/a4-gaps.md：8 条缺口，每行带 [L] 证据 + 影响面 + 风险等级
- 高风险 4 条：G-1 风险检查链路坏且未排班、G-2 验证链路坏且未排班、G-3 盘中无止损、G-4 回滚与判据载体不在版本控制
- 中风险 3 条：G-5 盘点器未接日历、G-6 missed 零实证、G-7 v13 之外声明失真；低 1 条：G-8 假绿灯结构门禁
- 设计未覆盖 4 条（G-1/G-2/G-3/G-5），并以 design/ 全文 4 符号 0 命中作反证
- 含 E-2/E-3/E-4 的点名证据（pathspec 不匹配 / 文件不存在 / check-ignore 输出）

### 改动文件

- `docs/requirements/REQ-261006010812-cd19/evidence/a4-gaps.md`

### 下一步

t5：汇总 audit-report.md + 三道自检 + 抽查复现。

---
