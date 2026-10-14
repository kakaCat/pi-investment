# t-9f0fbe 设计文档自洽性 + 版本面取证

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
设计文档自洽性 + 版本面取证

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：analysis
- 端侧：doc

## 得到什么结果
evidence/a1-design-selfconsistency.md 存在；自洽性条目 ≥10 条且每条带两侧「文档:行」指针；面 E 表中设计点名的每个路径都有「是否在版本控制内 + 最近一次提交」两列；文件内每条证据以 [L1]-[L4] 前缀标注（grep -c '^\[L' 命中数 ≥ 条目数）；grep -cE '基本一致|大致符合|疑似|应该没问题' 命中 0。

## 实施方案（implementation）
读 a7cd 设计目录下的 6 份文档与 requirement.md，建「设计条目清单」（每条：文档:行 / 声明内容 / serves 哪条 FR）。做四类自洽性检查：① 同一事实跨文档取值（design.md §12 验收命令 vs test-cases.md §6；§2 的 reason 枚举 vs interfaces.md §1）；② 文档间引用有效性（互链、被点名的文件与工具是否存在）；③ §13 四个未定决策是否闭环（对照 requirement.md 与 verification.md）；④ 数值口径（持仓数 / 止损线 / factors_count / cron 时刻在设计与需求间是否一致）。再跑面 E：对设计点名的每个文件与工具执行 git check-ignore -v、git ls-files --error-unmatch、git log -1 -- <path>、git status --porcelain。产出 docs/requirements/REQ-261006010812-cd19/evidence/a1-design-selfconsistency.md。

## 上游产出摘要（dependsSummary）
- （无依赖）

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-10-06T01:25:17.655Z，窗口 session-6a58ec8c-8f25-44a6-9be1-a02c4a16d94f）

t1 完工：建 16 条设计条目清单，做四类自洽性检查（15 条 A1-*）+ 面 E 全量取证（57 个被点名路径逐个查存在性/版本内/ignore 规则/最近提交），共抓到 19 条问题，其中 3 条高风险。

### 完成项

- 产出 evidence/a1-design-selfconsistency.md（38 条 [L 标注证据行）
- 自洽性：A1-1 reason 枚举两处不等（design.md:70 有 no_cash，interfaces.md:27-32 无）
- 自洽性：A1-2 同一判据两个载体——design.md:308 要 CLI 工具，test-cases.md:35-43 用内联 python
- 引用失效：A1-6 tools/check_trading_day_judgment.py 不存在，FR-3 判据载体缺失
- 留档失效：A1-7 三个 tools/check_*.py 被 .gitignore:85 吃掉，判据不在版本控制内
- 留档失效：A1-16 整个 a7cd 需求目录未跟踪（6 份设计文档 + 67 张任务卡）
- 回滚不成立：A1-17 design.md:289 押 git revert，但 20 文件 M、5 新模块 ??
- patch 不自足：A1-18 patch 只含已跟踪文件改动，新模块只在 tar 快照里
- 数值口径：A1-14 v14 factors_count 仍写 75 而真实 78（设计自己列的待修项未落地）
- 数值口径：A1-15 config_simulation.yaml 注释仍称 v13 生効 8 只，v13.yaml 已改 5
- 含 5 条通过项：cron 口径一致、health-probe.plist 可解析、§13 四条裁定均闭环、v13 因子数 75 已修、持仓 5 已收口

### 改动文件

- `docs/requirements/REQ-261006010812-cd19/evidence/a1-design-selfconsistency.md`

### 下一步

t2（实现一致性矩阵）与 t3（库表事实 + 验收命令复跑）可并行开工，输入为本卡的 16 条条目清单。

---
