# t-dea770 会话 Token 读取端口与降级

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 目标
会话 Token 读取端口与降级

## 背景摘要（context）
（待补充）

## 范围
- 阶段：implement
- 端侧：backend

## 验收标准
单测：假 projections→source=projection 四桶一致；服务 undefined→source=unavailable、全 0、不抛。

## 实施方案（implementation）
改 src/application/ports.ts、src/adapters/SessionProbeAdapter.ts；测试 tests/session-probe-token.test.ts。验证：pnpm test。

## 上游产出摘要（dependsSummary）
- 立 Token 契约与纯函数

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-17T21:48:06.684Z，窗口 session-b11b0a40-5c65-4c8d-88c7-23988b4979b0）

会话 Token 读取端口与降级：ports.ts SessionProbe 增 tokenTotals(windowKey): TokenSnapshot；SessionProbeAdapter 读 sessionProjections.stateOf(session,'tokenUsage') 组装快照（sessionId/seq/totals），任一环节不可得 → source=unavailable 空桶且不抛错；导出 readTokenTotals 兼容 {totals} 与裸四桶两种形状；FakeSession 补齐端口方法；新增 6 条单测。

### 完成项

- ports.ts 增 tokenTotals 端口方法（TokenSnapshot，不返回 undefined：可用性由 source 字段表达）
- SessionProbeAdapter.tokenTotals 实现 + readTokenTotals/readSessionId/readSessionSeq 解析（形状不符不猜 0）
- tests/application/harness.ts FakeSession 补端口方法（默认 unavailable，可注入）
- 新增 tests/session-probe-token.test.ts 6 条用例全绿；typecheck 通过；全量测试无新增失败

### 改动文件

- `agent-dh/packages/pages/dsh-pmboard/src/application/ports.ts`
- `agent-dh/packages/pages/dsh-pmboard/src/adapters/SessionProbeAdapter.ts`
- `agent-dh/packages/pages/dsh-pmboard/tests/application/harness.ts`
- `agent-dh/packages/pages/dsh-pmboard/tests/session-probe-token.test.ts`

### 下一步

t3：台账 schema v6 + 写路径快照 + 迁移。

---
