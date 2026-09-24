# t-c1cb5c 修复六份 brainstorming 模板消除门禁矛盾

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
修复六份 brainstorming 模板消除门禁矛盾

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：fullstack

## 得到什么结果
pnpm vitest run tests/template-clause-gate.test.ts 全绿；bug 模板目标表无 G1/G2 编号；本需求自身 requirement.md 过 missingCategoryDocs（G2 已实测通过）。

## 实施方案（implementation）
逐份编辑 6 个模板；新增 tests/template-clause-gate.test.ts（示范定义行可解析 + 前缀正确 + feature 模板章节覆盖 requiredRootSectionsFor）。验证：pnpm vitest run tests/template-clause-gate.test.ts。

## 上游产出摘要（dependsSummary）
- （无依赖）

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-23T07:22:05.818Z，窗口 session-f3978f17-ddb9-4fbc-81b6-7948a6999f4d）

修复 6 份 brainstorming 模板的门禁矛盾（FR-10）：每份追加「条款定义行（G2 门禁可解析）」段——按类型给出前缀（feature=FR/bug=BUG/refactor=RF/spike=SP/doc=DOC/chore=CH）、独立成行的示范定义行（- **PREFIX-1: 一句话…**）、requiredRootSectionsFor 对应的必填根节清单；编号纪律改用 PREFIX-N、禁用与闸门撞名的 G 系列。重新生成 generated/fragments.ts（128 片一致）。新增 tests/template-clause-gate.test.ts 5 用例全绿（示范行可解析+前缀正确+feature 覆盖必填节+bug 无 G 撞名编号+ROOT_PREFIXES 覆盖）。本需求 requirement.md 含 产品定义/用户与角色/功能点/边界，过 missingCategoryDocs。

### 完成项

- 6 份 brainstorming 模板追加条款定义行段（前缀/示范行/必填节）
- inline-prompt-fragments 重新生成 + check 一致
- tests/template-clause-gate.test.ts 5 用例全绿
- requirement.md 必填节齐（G2 过）

### 改动文件

- `src/domain/prompt/fragments/brainstorming/feature.md`
- `src/domain/prompt/fragments/brainstorming/bug.md`
- `src/domain/prompt/fragments/brainstorming/refactor.md`
- `src/domain/prompt/fragments/brainstorming/spike.md`
- `src/domain/prompt/fragments/brainstorming/doc.md`
- `src/domain/prompt/fragments/brainstorming/chore.md`
- `src/domain/prompt/generated/fragments.ts`
- `tests/template-clause-gate.test.ts`

### 下一步

t8 全量构建 + 重启 + 浏览器验收 UC-1/4/5

---
