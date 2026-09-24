# t-0f05c1 联调记录（父卡 t-41f158 / T-1「定义新契约类型与端口」· 阶段 integrate）

- 联调时间：2026-09-24T23:14:41+0800
- 联调对象：`packages/web/dsh-pmboard/src/shared/protocol.ts`（`InterruptionRecord` / `DesignDocRegistration` / `PendingConfirmation` / `PendingConfirmationOutcome` / `PENDING_CONFIRM_TICKET_PREFIX` / `RequirementRecord.interruption?`）与 `packages/web/dsh-pmboard/src/application/ports.ts`（`PendingConfirmPort` / `UseCaseDeps.pendingConfirms?`）
- 结论：**接口联调通过** —— 请求样例、期望响应、实际返回三者一致；契约测试与该包基线类型错误数均无新增。

---

## 1. 契约门禁测试（命令与输出摘要）

```bash
cd packages/web/dsh-pmboard
npx vitest run tests/contract-shapes.test.ts tests/output-contract.test.ts
```

实际输出（节选）：

```
 ✓ tests/contract-shapes.test.ts (8 tests) 2ms
 ✓ tests/output-contract.test.ts (19 tests) 86ms

 Test Files  2 passed (2)
      Tests  27 passed (27)
```

- 退出码：0
- 期望：契约形状测试 8 例 + 输出契约回归 19 例全绿
- 实际：2 files / 27 tests 全绿 —— 与期望一致

## 2. 类型基线（命令与输出摘要）

```bash
cd packages/web/dsh-pmboard
npx tsc --noEmit -p tsconfig.json
```

实际输出（摘要）：

```
exit=2
error TS 计数 = 23        # = 本卡基线 23（见拆分计划 D-1）
changed/new 文件命中 = 0  # contract-shapes.test.ts / shared/protocol.ts / application/ports.ts 无报错
报错文件（8 个，均为基线存量）：
  src/adapters/CaptureHook.ts
  src/application/gate/handlers/h3-inject.ts
  src/application/internal/node-input-package.ts
  src/domain/template/render.ts
  src/domain/template/resolve.ts
  src/gate-wiring.ts
  tests/gate-aware-questions.test.ts
  tests/template-address-injection.test.ts
```

- 期望：错误数 ≤ 基线 23，且本卡新增/改动文件 0 报错
- 实际：总数 23（恰为基线），本卡 3 个文件 0 报错 —— 与期望一致

## 3. 接口联调（运行时三方对照）

联调方式：用一份**临时**探针测试为 `PendingConfirmPort` 接最小内存实现（真实实现 `adapters/PendingConfirmRegistry.ts` 属 T-6，本卡不写行为），
实际调用 `register → get → settle → get` 并打印每次「请求 / 期望 / 实际返回」，同时做 `InterruptionRecord` 的 JSON 往返。

```bash
cd packages/web/dsh-pmboard
npx vitest run tests/__probe-t0f05c1.test.ts   # 探针为本轮临时文件，跑完已删除
```

### 3.1 `PendingConfirmPort.register`（I-4）

| 项 | 内容 |
|---|---|
| 请求样例 | `{"windowKey":"session-abc123","requirementId":"REQ-abc123","target":"artifact","kind":"design"}` |
| 期望响应 | ticket 前缀 `pc-`；回显 windowKey / requirementId / target / kind；`createdAt` 为 number；键集合恰为 `createdAt,kind,requirementId,target,ticket,windowKey` |
| 实际返回 | `{"ticket":"pc-000001","windowKey":"session-abc123","requirementId":"REQ-abc123","target":"artifact","kind":"design","createdAt":1790262000001}` |
| 判定 | 一致（`startsWith('pc-')=true`、`toMatchObject(请求)=true`、键集合断言通过） |

### 3.2 `PendingConfirmPort.get`（窗口绑定）

| 项 | 内容 |
|---|---|
| 请求样例 | `{"ticket":"pc-000001","windowKey":"session-abc123"}` |
| 期望响应 | 同窗口 → 返回该 `PendingConfirmation`；异窗口 → `undefined`（不抛） |
| 实际返回 | 同窗口：`{"ticket":"pc-000001","windowKey":"session-abc123","requirementId":"REQ-abc123","target":"artifact","kind":"design","createdAt":1790262000001}`；异窗口（`session-other`）：`undefined` |
| 判定 | 一致 |

### 3.3 `PendingConfirmPort.settle`（回填 + 幂等 + 未知 ticket）

| 项 | 内容 |
|---|---|
| 请求样例 | `{"ticket":"pc-000001","outcome":{"confirmed":true,"advanced":true}}` |
| 期望响应 | 返回带 `outcome` 的记录；settle 后 `get` 能读回 outcome；未知 ticket → `undefined`（不抛） |
| 实际返回 | settle：`{"ticket":"pc-000001",...,"outcome":{"confirmed":true,"advanced":true}}`；settle 后 get：同上（outcome 已回填）；`settle("pc-ffffff")` → `undefined` |
| 判定 | 一致 |

### 3.4 `UseCaseDeps.pendingConfirms?`（缺省语义）

| 项 | 内容 |
|---|---|
| 请求样例 | `const deps = {}`（不传端口） |
| 期望响应 | `deps.pendingConfirms === undefined`（= 未装配非阻塞能力 → 保持旧阻塞语义） |
| 实际返回 | `undefined` |
| 判定 | 一致（装入端口时 `depsWith.pendingConfirms === port` 亦成立） |

### 3.5 `InterruptionRecord` 挂载 + JSON 往返（I-8）

| 项 | 内容 |
|---|---|
| 请求样例 | `{"at":1790262000000,"reason":"checkpoint","stage":"design","pendingAction":"reqboard_ask_confirm(target=artifact, kind=design)","tool":"reqboard_submit"}` |
| 期望响应 | 作为 `RequirementRecord.interruption?` 写入后 JSON round-trip 逐字段一致；存量记录（无该键）读出为 `undefined`（不是空对象） |
| 实际返回 | round-trip：`{"id":"REQ-abc123","interruption":{...与请求逐字段相同...}}`；存量记录：`{"interruption":undefined}` |
| 判定 | 一致 |

探针执行结果：

```
 ✓ tests/__probe-t0f05c1.test.ts (2 tests) 2ms
 Test Files  1 passed (1)
      Tests  2 passed (2)
```

## 4. 联调结论

1. `PendingConfirmPort` 三方法（register / get / settle）的请求样例、期望响应、实际返回三方一致，且「不抛」语义（异窗口 / 未知 ticket → `undefined`）成立。
2. `InterruptionRecord` 作为 `RequirementRecord.interruption?` 的可选字段可无损 JSON 往返；缺省即「无断点」。
3. `contract-shapes.test.ts` 的运行时键集合 + `expectTypeOf` 精确类型双断言锁住了 `InterruptionRecord` / `DesignDocRegistration` / `PendingConfirmation` / `PendingConfirmationOutcome` / `PendingConfirmPort` 的字段表。
4. 本卡为纯契约（无运行时行为），端到端行为验收在 T-13。
5. 未新增任何测试失败：契约+输出契约 27/27 绿；`tsc` 23 条 = 基线且本卡文件 0 报错。

> 联调探针 `tests/__probe-t0f05c1.test.ts` 为本轮临时文件，已在本轮内删除（`rm -f`，复核不存在）；工作区未遗留临时产物。
