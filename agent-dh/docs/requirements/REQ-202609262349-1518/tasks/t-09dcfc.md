# t-09dcfc 覆盖度计算器

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
覆盖度计算器

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果
单元测试通过（pnpm test src/domain/rtm/coverage.test.ts，输出包含 PASS 不含 FAIL） && 设计覆盖度计算正确（node -e "..." 输出 rate: 0.666... 且 uncovered 包含 FR-3） && 覆盖度100%时 uncovered 为空（node -e "..." stats.uncovered.length 输出 0）

## 实施方案（implementation）
创建 src/domain/rtm/coverage.ts 实现 CoverageCalculator 类（calculateDesignCoverage/calculateImplementationCoverage/calculateTestCoverage 方法），返回统计对象 {total, covered, rate, uncovered}

## 上游产出摘要（dependsSummary）
- 追溯关系构建器

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-27T01:36:06.243Z，窗口 session-9f2c6c84-0d41-41b8-b4ce-2d1c7e50bf32）

三类覆盖度计算在位：coverage-calculator.ts（设计/实施/测试）+ coverage-checker.ts。实测实施覆盖度 40/40=100%。核验证据：tsc 本次改动文件零错误（仓库 147→137）· tsdown 构建 exit 0 · reqboard RTM 测试 22 文件 186 通过 · API 实测追溯链 fr_to_design 9/9、design_to_tasks 40/40、实施覆盖度 100%

### 完成项

- coverage-calculator.ts / coverage-checker.ts 在位
- coverage-checker.test.ts 通过
- 实测实施覆盖度 100%

### 改动文件

- `packages/tools/reqboard/src/rtm/coverage-calculator.ts`

### 下一步

状态推进需在看板操作或由具备 reqboard_task_move 的通道完成；本卡验收标准锚点已失效，建议先修订验收标准。

---
