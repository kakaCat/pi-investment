# t-be76e7 文档校验骨架：把标准变成能判的代码

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 目标
文档校验骨架：把标准变成能判的代码

## 背景摘要（context）
（待补充）

## 范围
- 阶段：implement
- 端侧：backend

## 验收标准
npx vitest run /Users/yunpeng/pi-investment/agent-dh/packages/pages/dsh-pmboard/tests/content-gates.test.ts 通过；空文档/缺节/正常三种输入各返回结构化清单

## 实施方案（implementation）
新增 application/internal/content-gates.ts：parseDocument + 各 check* 纯函数，零 IO，无副作用

## 上游产出摘要（dependsSummary）
- 定稿文档标准：六类文档各写什么

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-18T13:39:02.973Z，窗口 session-e1fc9bb5-906c-4d20-92fc-cbd5f3e2a512）

文档校验骨架：新增纯函数模块 content-gates.ts（零 IO、零 import、196→238 行），把标准变成能判的代码——解析器（front-matter/标题/表格，且必须跳过代码围栏）+ 四个判定（条款覆盖/编号串联/验收四件套/E2E 覆盖），配 22 条单测全绿。

### 完成项

- parseDocument：解析 front-matter / 标题 / 表格，**跳过代码围栏块**（文档里贴代码不会误判结构）
- checkClauseCoverage（TC-001/002）：条款无落点 → gaps 列出缺失编号；显式标"本轮不做" → 不算缺口
- checkNumberChain（TC-003/004）：serves 指向不存在 → dangling；根编号无人指向 → orphans
- checkAcceptanceKit（TC-005）：四件套（验什么/对应编号/怎么验/预期）缺任一 → missing 并指出行键
- checkE2ECoverage（TC-006）：测试策略表无 E2E 行 → hasE2E=false（不假装有）
- extractServesFrom：汇总三来源（标题 serves / 表格 serves 列 / front-matter requirement_refs）
- 单测 22 条全绿；tsc 本模块 0 错误；**变异测试实测有效**（弄坏代码围栏跳过 → 陷阱用例精确变红）

### 改动文件

- `packages/pages/dsh-pmboard/src/application/internal/content-gates.ts`
- `packages/pages/dsh-pmboard/tests/content-gates.test.ts`

### 下一步

T-3（拆分门禁接线）依赖本模块；接线的调用点 MoveRequirement.ts 正被另一窗口修改，等其落地。

---
