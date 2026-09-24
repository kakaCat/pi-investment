# t-8da5ac 新增 isolation-log 只读端点并接线

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
新增 isolation-log 只读端点并接线

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果
pnpm vitest run tests/isolation-router.test.ts 全绿（k 非法→400 / 端口缺省→available=false 空清单 / window 过滤生效 / 留痕文件损坏→降级不红）。

## 实施方案（implementation）
新建 isolation.ts；routes.ts 增加分支与 deps 传递；index.ts 接线。新增 tests/isolation-router.test.ts。验证：pnpm vitest run tests/isolation-router.test.ts。

## 上游产出摘要（dependsSummary）
- （无依赖）

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-23T06:55:50.849Z，窗口 session-f3978f17-ddb9-4fbc-81b6-7948a6999f4d）

新增 isolation-log 只读端点：isolation-trace.ts 补 IsolationLogReadPort + queryIsolationTrace；新建 routers/isolation.ts（照抄 injection.ts：k 1..200 校验、端口缺省 available=false、window 过滤、readAll 损坏降级不红）；routes.ts 注册 + deps 透传；index.ts 把既有 isolationTrace 只读接入。6 用例全绿。

### 完成项

- isolation-trace.ts +IsolationLogReadPort/queryIsolationTrace
- 新建 src/http/routers/isolation.ts
- routes.ts 注册 GET isolation-log + ReqboardRouteDeps/RouterCtx deps 透传
- index.ts isolationLog: isolationTrace 只读接线
- tests/isolation-router.test.ts 6 用例全绿（k 400/缺省 false/窗口过滤/损坏降级/顺序/k 上限）

### 改动文件

- `src/application/internal/isolation-trace.ts`
- `src/http/routers/isolation.ts`
- `src/http/routers/shared.ts`
- `src/http/routes.ts`
- `src/index.ts`
- `tests/isolation-router.test.ts`

### 下一步

t3 progress 透出 promptDifficulty

---
