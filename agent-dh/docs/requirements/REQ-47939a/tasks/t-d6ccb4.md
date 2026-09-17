# t-d6ccb4 文档演进与死代码清理 + 归档材料

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 目标
文档演进与死代码清理 + 归档材料

## 背景摘要（context）
（待补充）

## 范围
- 阶段：doc
- 端侧：doc

## 验收标准
python3 agent-dh/scripts/wiki_probe.py 通过（无死链/孤儿页）；docs/architecture/workflow-stages.md 与 docs/rfcs/014-requirement-board.md 内出现 9 个收敛后工具名且不再把 confirm_artifact 列为独立入口。

## 实施方案（implementation）
更新 docs/architecture/workflow-stages.md 阶段职责中的工具名（13→9）；docs/rfcs/014-requirement-board.md 增补分层落地记录小节；docs/architecture/TOOLS_INVENTORY.md 与 glossary.md 同步；清理确认无引用的死代码并在任务汇报列出；跑 python3 agent-dh/scripts/wiki_probe.py 自检死链/孤儿页。验证：wiki_probe.py 与文档 diff。

## 上游产出摘要（dependsSummary）
- 账本 v4→v5 无损迁移（脚本 + 报告 + 测试）
- 客户端 styles.ts 分层 + 构建门

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-17T12:53:12.099Z，窗口 session-41e7e4cd-4038-476c-9307-d93622a411e2）

t13 完成：文档演进（workflow-stages 新增「工具面 13→9」章节、RFC 014 新增 §15 分层+收敛+四条经验、glossary 新增 4 条术语）+ 死代码全仓复扫无死文件 + wiki 探针现行页零死链零孤儿。

### 完成项

- workflow-stages.md：新增「工具面（2026-09-17 收敛后：13 → 9）」章节并同步两处现行引用（verify/archive submit → reqboard_submit(kind=…)）
- rfcs/014-requirement-board.md：新增 §15「分层重构与工具收敛」，含四层目录图、四条来自实测的经验（门禁必须能证明自己扫到了东西 / "换个花样的绕过"更危险 / 续版语义要问"没被处理的去哪了" / 卡面"复用 X 实现"与"不依赖 X 环境"可能不可兼得）、产物索引
- glossary.md：新增 4 条术语（四层分层 / 端口·用例 / 机械门禁 / 续版验收）
- 死代码复扫：同时认 .ts 与 .js 后缀并含 scripts/tests 引用方 → 无死文件；13 个假阳性（client 用 .ts 后缀 import、脚本引用 domain/legacy/LegacyStatus.ts）已查清
- TOOLS_INVENTORY.md 经查无需更新（本无 reqboard 条目）——显式记录避免"漏做"误判
- 卡面验收命令实测：从仓库根跑 wiki 探针 → 现行页死链 0 / 孤儿 0；9 个收敛后工具名齐备；confirm_artifact 独立入口 0 次
- 边界原则遵守：work-logs 与 RFC 历史叙述不改写（history 只增不改），只在 living 文档更新现行表述、RFC 用新增一节记录收敛
- 文档索引：docs_index.py --check = OK（须从仓库根跑且连跑两次——该陷阱已写进 docs/standards/testing.md）

### 改动文件

- `docs/requirements/REQ-47939a/verification.md`
- `docs/architecture/workflow-stages.md`
- `docs/rfcs/014-requirement-board.md`
- `docs/architecture/glossary.md`
- `docs/standards/testing.md`

### 下一步

全部 13 张卡完成后：需求自动进验收；随后由发起窗口执行真实台账 v4→v5 迁移 + 重启加载 v5，再提交验收材料并逐项弹框验收。

---
