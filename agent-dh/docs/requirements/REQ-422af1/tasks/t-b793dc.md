# t-b793dc 实现注入留痕（ring buffer + 只读查询）

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 目标
实现注入留痕（ring buffer + 只读查询）

## 背景摘要（context）
（待补充）

## 范围
- 阶段：implement
- 端侧：backend

## 验收标准
tests/prompt-injection-log.test.ts 全绿：每条记录包含 at/windowKey/stage/difficulty/category/routeKey/hitLevel/fragmentIds/charCount/trimmed 十项且值与写入一致；连续写入 N+100 条后文件条数等于 N（有界）；文件不存在时读取返回空数组且不抛错；删除 prompt-injection-log.json 后功能仍正常（无硬依赖）。验证命令：npx vitest run tests/prompt-injection-log.test.ts（在 packages/pages/dsh-pmboard 下）；不通过则本卡不完成。

## 实施方案（implementation）
新增 src/application/internal/injection-log.ts（读写 state 目录下 prompt-injection-log.json，ring buffer 保留最近 N=500 条，原子写沿用本仓既有 writeFileAtomic 模式，字段与 design/architecture.md §2 一致）；在 capture-section 与 CaptureHook 注入后调用记录；暴露只读查询函数供看板读取。

## 上游产出摘要（dependsSummary）
- 实现 resolveStagePrompt 路由解析与预算

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-17T14:37:57.575Z，窗口 session-41e7e4cd-4038-476c-9307-d93622a411e2）

注入留痕落地：ring buffer 500 条 + 原子写 + 只读查询，两处注入点均已接线。

### 完成项

- 十字段记录且与写入一致
- 写 600 条后文件条数=500（有界）
- 缺文件返回空且不抛、删文件后功能正常
- 无 .tmp 残留

### 改动文件

- `packages/pages/dsh-pmboard/src/application/internal/injection-log.ts`
- `packages/pages/dsh-pmboard/src/adapters/InjectionLogFile.ts`
- `packages/pages/dsh-pmboard/tests/prompt-injection-log.test.ts`
- `packages/pages/dsh-pmboard/src/index.ts`

### 下一步

P3 看板读取该留痕做可见块

---
