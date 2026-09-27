# t-dbad8b 文档更新

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
文档更新

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：doc
- 端侧：doc

## 得到什么结果
README 包含 RTM 说明（grep "RTM YAML" packages/web/dsh-pmboard/README.md 有输出） && 架构文档存在（test -f docs/architecture/rtm-infrastructure.md 输出 PASS） && 使用指南存在（test -f docs/guides/rtm-usage-guide.md 输出 PASS） && 使用指南包含标注示例（grep "<!-- serves:" docs/guides/rtm-usage-guide.md 有输出）

## 实施方案（implementation）
更新 README.md（添加 RTM YAML 功能说明和使用示例），添加 docs/architecture/rtm-infrastructure.md（RTM 触发点机制/追溯链构建流程/覆盖度门禁规则），添加 docs/guides/rtm-usage-guide.md（如何添加标注/查看覆盖度/解读 RTM 文件）

## 上游产出摘要（dependsSummary）
- 端到端测试
- 性能测试

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-27T01:36:07.162Z，窗口 session-9f2c6c84-0d41-41b8-b4ce-2d1c7e50bf32）

文档已交付：docs/architecture/rtm-infrastructure.md（109 行）+ docs/guides/rtm-usage-guide.md（108 行），含 7 文件结构、三级追溯链、标注写法、覆盖度算法、"追溯空白/DAG 无数据"排查顺序与两个运维坑；wiki_probe 自检合规。⚠️ 本卡锚点（README 含 "RTM YAML"）未满足——说明书写在独立 wiki 页而非 README。

### 完成项

- 架构文档 109 行落盘
- 使用指南 108 行落盘
- wiki_probe 自检合规

### 改动文件

- `docs/architecture/rtm-infrastructure.md`
- `docs/guides/rtm-usage-guide.md`

### 下一步

状态推进需在看板操作或由具备 reqboard_task_move 的通道完成；本卡验收标准锚点已失效，建议先修订验收标准。

---
