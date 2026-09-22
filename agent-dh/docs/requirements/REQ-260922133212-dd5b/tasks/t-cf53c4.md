# t-cf53c4 [BUG-1] 归档目录校验兼容新旧两种需求 id 格式

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
[BUG-1] 归档目录校验兼容新旧两种需求 id 格式

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果
cd agent-dh && npx vitest run packages/web/dsh-pmboard/tests/requirement-dir-pattern.test.ts → passed（5 用例：旧格式过/新格式过/非法 id 拒/层级错误拒/尾部多段拒）；连带 migration+acceptance-archive 套件无新失败。

## 实施方案（implementation）
改 packages/web/dsh-pmboard/src/shared/protocol.ts 的 REQUIREMENT_DIR_PATTERN 为 /(?:^|\/)docs\/requirements\/REQ-(?:[0-9a-f]{6}|\d{12}-[0-9a-f]{4})$/（按 RandomIdFactory 真身 YYMMDDHHmmss-xxxx 校准）；新建 tests/requirement-dir-pattern.test.ts（// serves: BUG-1）。

## 上游产出摘要（dependsSummary）
- （无依赖）

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-22T06:32:40.107Z，窗口 session-9faaac35-2641-473c-a5dc-ea6e6d11efbf）

归档目录校验现在同时认新旧两种需求 id：老需求（REQ-f6307c）和新时间戳需求（REQ-260922012924-2e29）的归档材料都能通过门禁，非法 id 和错误目录仍然拒——新格式需求"归档手续办不了"的问题消除

### 完成项

- REQUIREMENT_DIR_PATTERN 改为 /REQ-(?:[0-9a-f]{6}|\d{12}-[0-9a-f]{4})$/（按 RandomIdFactory 真身 YYMMDDHHmmss-xxxx 校准）
- 新增 tests/requirement-dir-pattern.test.ts 5 用例（旧过/新过/非法拒/层级拒/尾段拒）
- 连带 migration+acceptance-archive 套件 25/25 全绿
- 暂存构建 20/20 通过，新正则已进 dist

### 改动文件

- `packages/web/dsh-pmboard/src/shared/protocol.ts`
- `packages/web/dsh-pmboard/tests/requirement-dir-pattern.test.ts`

### 下一步

t2 部署重启并补交 REQ-260922012924-2e29 归档材料

---
