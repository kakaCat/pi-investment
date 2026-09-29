# t-be396c 测试记录（REQ-260927121324-abde · 父卡 t-f6ee83「需求迁移写路径统一经收敛点并带写时快照」· 阶段 test）

> 验收标准：目标命令输出全绿（贴命令与结果摘要）。
> 结论：**通过**——父卡口径命令全绿（3 files / 15 tests，exit 0）；静态复验确认 src/application 与 src/http
> 内需求状态再无直接赋值（唯一写入口收敛于 token-usage.ts:291）。

- 测试时间：2026-09-27（本轮执行内）
- 环境：node v22.23.2 · vitest 2.1.9（darwin-arm64）· HEAD `daa4169e`（branch `main`）· 工作目录 `packages/web/dsh-pmboard`
- 被测交付面：`src/application/internal/confirm-settle.ts`（批准计划两分支补 snap）、
  `src/http/routers/requirements.ts`（板级推进五连写改经收敛点 + 看板确认即推进带 snap）、
  `src/http/routers/verdicts.ts`（验收五连写 + applyVerdicts 第 8 实参 snap）、
  `src/application/use-cases/HandleFailure.ts`（上游/取消两分支改经收敛点）

---

## 1. 目标命令 A —— 父卡「得到什么结果」命令（vitest 口径）

```
$ cd /Users/yunpeng/pi-investment/agent-dh/packages/web/dsh-pmboard
$ npx vitest run tests/token-transition-helper.test.ts tests/verdicts-and-rework.test.ts tests/confirm-settle-plan-persist.test.ts

 RUN  v2.1.9 /Users/yunpeng/pi-investment/agent-dh/packages/web/dsh-pmboard

 ✓ tests/token-transition-helper.test.ts (3 tests) 2ms
 ✓ tests/confirm-settle-plan-persist.test.ts (2 tests) 23ms
 ✓ tests/verdicts-and-rework.test.ts (10 tests) 129ms

 Test Files  3 passed (3)
      Tests  15 passed (15)
   Duration  581ms
```

- 期望：收敛点带快照迁移 + 验收/返工/计划落库推进三组行为全绿；实际 **15/15 passed，exit 0**。

## 2. 目标命令 B —— 父卡「得到什么结果」命令（grep 口径，唯一写入口）

```
$ grep -rn "req.status = \|r.status = " src/application src/http
src/application/internal/token-usage.ts:278:  //    都记得校验。此前本函数直接 `req.status = to` 无任何校验，于是：
src/application/internal/token-usage.ts:291:  req.status = to
```

- 期望：除收敛点 `token-usage.ts` 内部外，路径内无直接状态赋值；实际**只剩收敛点一处真实赋值**（:291），
  :278 为注释文本，对照父卡口径「只剩 token-usage.ts 一处」成立。

## 3. 扩展回归（独立复跑，防迁移引入回归）

```
$ npx vitest run tests/token-transition-helper.test.ts tests/verdicts-and-rework.test.ts \
    tests/confirm-settle-plan-persist.test.ts tests/token-usage.test.ts \
    tests/token-fallback.test.ts tests/token-endpoint.test.ts tests/ledger-v6-token.test.ts

 ✓ tests/token-transition-helper.test.ts (3 tests)
 ✓ tests/token-usage.test.ts (11 tests)
 ✓ tests/token-fallback.test.ts (3 tests)
 ✓ tests/confirm-settle-plan-persist.test.ts (2 tests)
 ✓ tests/ledger-v6-token.test.ts (8 tests)
 ✓ tests/token-endpoint.test.ts (6 tests)
 ✓ tests/verdicts-and-rework.test.ts (10 tests)

 Test Files  7 passed (7)
      Tests  43 passed (43)
EXIT=0
```

## 4. 接线点静态复验（不采信上游自述）

```
$ grep -n "snap: captureSnapshot" src/application/internal/confirm-settle.ts
180:          snap: captureSnapshot(deps, d.windowKey),
293:          snap: captureSnapshot(deps, d.windowKey),
320:              snap: captureSnapshot(deps, d.windowKey),

$ grep -n "transitionRequirement" src/http/routers/requirements.ts src/http/routers/verdicts.ts src/application/use-cases/HandleFailure.ts
src/http/routers/requirements.ts:117:      transitionRequirement(req, to, {
src/http/routers/requirements.ts:279:        transitionRequirement(r, gate.to, {
src/http/routers/verdicts.ts:110:      transitionRequirement(r, to, {
src/application/use-cases/HandleFailure.ts:89:      transitionRequirement(req, 'design', {
src/application/use-cases/HandleFailure.ts:113:    transitionRequirement(req, 'canceled', {

$ grep -n "snapshotForWindow" src/application/use-cases/HandleFailure.ts
88:      const snap = snapshotForWindow(deps, req.sourceSessionId)
112:    const snap = snapshotForWindow(deps, req.sourceSessionId)
```

- 批准计划两分支（:293 正常路径 / :320 收尾报错路径）均带 `snap`；:180 为既有确认路径。
- 板级推进、看板确认即推进、验收裁决、失败处置四路均改经 `transitionRequirement`；
  会话码取不到时经 `...(snap !== undefined ? { snap } : {})` 诚实不传（不伪造写时快照）。

---

**裁决：通过（目标命令全绿，0 failed）。**
