# t-cf63f0 新增产物路径归一层（domain 纯函数）+ 单测

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 目标
新增产物路径归一层（domain 纯函数）+ 单测

## 背景摘要（context）
（待补充）

## 范围
- 阶段：implement
- 端侧：backend

## 验收标准
npx vitest run tests/domain/artifact-path.test.ts 全绿；用例覆盖 4 形态（agent-dh/ 前缀、绝对路径、quantsys-v2/ 跨仓、{a,b} 伪路径）与合规路径原样不变；npx vitest run tests/layer-boundary.test.ts 仍绿。

## 实施方案（implementation）
改 packages/pages/dsh-pmboard/src/domain/artifact/ArtifactPath.ts（新建）+ tests/domain/artifact-path.test.ts（新建）。纯函数、无 I/O、无 Date/random。验证：npx vitest run tests/domain/artifact-path.test.ts tests/layer-boundary.test.ts。

## 上游产出摘要（dependsSummary）
- （无依赖）

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-18T15:41:01.236Z，窗口 session-e7129862-11b3-4e7d-ab11-53f6a6db9923）

t1：新增产物路径归一层 domain 纯函数 + 16 例单测

### 完成项

- src/domain/artifact/ArtifactPath.ts：normalizeArtifactPath(raw, workspaceRoot) → {path, form: workspace|outside|pseudo}；规则=反斜杠→/、剥绝对前缀（工作区根/仓库根）、剥重复工作区名前缀、含 {}/* 判 pseudo、任意 .. 段判 outside；零 I/O、无 Date/random（层边界 INV-2）
- tests/domain/artifact-path.test.ts：16 例——四种实测形态（A agent-dh/ 前缀、B 绝对路径含工作区内/外、C 跨仓相对、D brace/通配伪路径）+ 5 条合规路径原样不变 + ./ 与反斜杠清洗 + ../ 逃逸判定
- 实测：npx vitest run tests/domain/artifact-path.test.ts tests/layer-boundary.test.ts → 25 passed（含层边界 9 例仍绿）

### 改动文件

- `packages/pages/dsh-pmboard/src/domain/artifact/ArtifactPath.ts`
- `packages/pages/dsh-pmboard/tests/domain/artifact-path.test.ts`

### 下一步

t2/t3 接入归一层

---
