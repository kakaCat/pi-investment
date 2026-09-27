# t-a1ecaa 同步文档：流程图 / 白名单 / 手册

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
同步文档：流程图 / 白名单 / 手册

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：doc
- 端侧：doc

## 得到什么结果
python3 agent-dh/scripts/wiki_probe.py 无新增死链/孤儿；流程图文档的缺陷落点索引覆盖 D1–D13。

## 实施方案（implementation）
更新 docs/architecture/reqboard-pipeline-flow.md（缺陷落点补齐）、reqboard-dive-mode.md（投递白名单）与项目说明书相关章节；跑 scripts/wiki_probe.py 自检。

## 上游产出摘要（dependsSummary）
- Dive 采集半停止直投 + 投递白名单
- RTM 窗口绑定投影可更新且有消费者

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-27T03:46:00.725Z，窗口 session-52f725ef-eeda-4458-8c6d-cb15b10ad5b8）

把这一轮"拆分→实施要么真落库、要么响亮失败"的结论落进人读的文档：节点流程图补上每个缺陷的修复状态，项目说明书新增一条更新点，Dive 契约写明投递白名单；wiki 索引重生、无新增死链/孤儿。

### 完成项

- reqboard-pipeline-flow.md：缺陷落点索引 D1–D13 增加"对应 FR + 修复状态"列（✅ 已修 / — 未纳入），front-matter 摘要同步
- docs/architecture/project-manual.md：新增 2026-09-27 更新点（本需求交付的完整变化面）
- reqboard-dive-mode.md：投递白名单一节与实现对齐；缺陷索引引用同步为 D1–D13
- docs_index.py 重生索引（INDEX.md / README.md 自动区）→ --check 报"索引与文档一致"
- wiki_probe 复核：现行页死链 30 条全部为既有（README 指向 packages/*/README.md、work-logs 索引等），本次新增/修改页零新增死链/孤儿

### 改动文件

- `docs/architecture/project-manual.md`
- `agent-dh/docs/architecture/reqboard-pipeline-flow.md`
- `agent-dh/docs/architecture/reqboard-dive-mode.md`
- `agent-dh/docs/INDEX.md`
- `agent-dh/docs/README.md`

---
