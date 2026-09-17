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
