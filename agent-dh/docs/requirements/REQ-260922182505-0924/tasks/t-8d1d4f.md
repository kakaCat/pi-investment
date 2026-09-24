# t-8d1d4f 删除 triage 兼容路径与 .bak 文件

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
删除 triage 兼容路径与 .bak 文件

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：fullstack

## 得到什么结果
① npx tsc --noEmit（或等价构建）通过；② grep -rn "triage" src/ 仅剩 protocol.ts 冻结契约、JsonLedgerRepository 管道、rollup 读取与历史注释；③ ls src/application/internal/*.bak* 为空；④ vitest run 失败集与 t1 基线差集为空。

## 实施方案（implementation）
按 design/architecture.md 的顺序：先摘调用方（capture/create/QueryState/前端）→ 再删定义（window/support/Predicates）→ 最后删路由与文件，每步保持可编译；测试文件随删随改。

## 上游产出摘要（dependsSummary）
- 复现死代码现状并建立回归基线

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-22T12:26:39.191Z，窗口 session-9faaac35-2641-473c-a5dc-ea6e6d11efbf）

旧立项流程（triage）的前后台残留代码已全部删除：路由/前端面板/立项前置检查不复存在，看板不再有"待归类"入口；3 个 .bak 备份文件已清除。台账里的 2 条历史记录与读取管道原样保留（只读兼容）。四项验收全过：tsc 编译干净、grep 只剩冻结契约与历史注释、.bak 为空、全量测试失败集与基线完全一致（86=86，差集为空）。

### 完成项

- 删文件：routers/triage.ts + support.ts.bak2/.bak3/.bak4
- 摘调用方：CaptureRequirement 前置检查、capture-section pending 分支、QueryState has_pending/pending_triage_id、StatusTool schema+prompt
- 删定义：window.ts hasPendingSuggestion/pendingSuggestionFor、support.ts findPending、Predicates isPendingTriage/isResolvedTriage
- 摘路由：routes.ts 4 挂载点+import、index.ts 注册日志、CaptureHook 日志文案
- 摘前端：api.ts 4 接口、types.ts TriageRecord/TriageList、views/board.ts buildTriage、board-mount.ts 视图状态机+action 处理器、styles/base.ts triage CSS、view.ts 导出
- 冻结保留：protocol.ts TriageRecord/台账 triages 字段、JsonLedgerRepository 管道、RollupSpec/rollup 读取（注释更新为只读兼容口径）
- 测试同步：api-client/capture/capture-hook/client-view/reqboard 五个测试文件的 triage 用例删除或改写
- 验收：tsc clean；grep 只剩冻结契约与历史注释；.bak 为空；vitest 失败集 86=86 与基线差集为空

### 改动文件

- `src/http/routers/triage.ts（删除）`
- `src/application/internal/support.ts.bak2/.bak3/.bak4（删除）`
- `src/http/routes.ts`
- `src/index.ts`
- `src/gate-wiring.ts`
- `src/adapters/CaptureHook.ts`
- `src/application/internal/window.ts`
- `src/application/internal/support.ts`
- `src/application/internal/capture-section.ts`
- `src/application/use-cases/CaptureRequirement.ts`
- `src/application/query/QueryState.ts`
- `src/tools/StatusTool/StatusTool.ts`
- `src/tools/StatusTool/prompt.ts`
- `src/domain/status/Predicates.ts`
- `src/shared/protocol.ts（仅注释口径更新，契约未动）`
- `src/client/api.ts`
- `src/client/types.ts`
- `src/client/view.ts`
- `src/client/views/board.ts`
- `src/client/board-mount.ts`
- `src/client/styles/base.ts`
- `tests/api-client.test.ts`
- `tests/capture.test.ts`
- `tests/capture-hook.test.ts`
- `tests/client-view.test.ts`
- `tests/reqboard.test.ts`
- `docs/requirements/REQ-260922182505-0924/after-test-failures.txt`
- `docs/requirements/REQ-260922182505-0924/after-grep.txt`

### 下一步

t3（t-9311e7）：独立回归复核 + 部署后验证 triage 路由 404 与看板正常渲染

---
