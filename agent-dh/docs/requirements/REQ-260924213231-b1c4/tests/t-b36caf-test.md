# t-b36caf 测试记录（父卡 t-800d53 / T-12「组合根瘦身使尺寸门禁转绿」· 阶段 test）

- 测试时间：2026-09-25T02:02+0800（本轮执行内现场复跑）
- 测试环境：node v22.23.2 · vitest 2.1.9（darwin-arm64）· 工作目录 `agent-dh`，测试工作目录 `packages/web/dsh-pmboard`；HEAD = `9e5ebf60`（branch `main`）
- 被测对象（T-12 组合根瘦身；实现改动为工作区未提交状态，本卡只跑不改）：
  - **组合根** `packages/web/dsh-pmboard/src/index.ts`（工作区修改 `35 insertions(+), 111 deletions(-)`）：**357 行**（≤400），配置/路径纯函数与捕获根装配已移出，只留装配顺序
  - **新增配置纯函数** `packages/web/dsh-pmboard/src/plugin-config.ts`（untracked，42 行）：`PluginConfig` / `dshHomePath` / `nodeIsolationEnabled`
  - **新增捕获根装配** `packages/web/dsh-pmboard/src/wiring/pm-capture-root.ts`（untracked，161 行）：`createCaptureRuntime` / `assembleCaptureHook`（+`PendingCaptureMessage`/`CaptureRuntimeDeps`/`CaptureRuntime`/`CaptureHookAssemblyDeps` 类型）
  - **兼容再导出**：`src/index.ts:21` 从 `./plugin-config.js` 引入，`src/index.ts:73` `export { dshHomePath, nodeIsolationEnabled };`（原 import 站点 `src/index.ts:98,102,108,181,190,195,235` 全部走同一实现）
- 测试结论：**目标命令全绿** —— `npx vitest run tests/size-budget.test.ts tests/isolate-node-context.test.ts tests/capture-hook.test.ts` → **3 files / 60 tests 通过，exit 0**；`wc -l src/index.ts` = **357 ≤ 400**；`nodeIsolationEnabled` 仍可从 `src/index.js` import（`tests/isolate-node-context.test.ts:38` 实测）且优先级行为逐例不变（L523-531）。验收标准「目标命令输出全绿」达成。

---

## 1. 目标命令（父卡 t-800d53「得到什么结果」验收命令）

```bash
cd packages/web/dsh-pmboard
npx vitest run tests/size-budget.test.ts tests/isolate-node-context.test.ts tests/capture-hook.test.ts --reporter=basic
```

实际输出：

```
 RUN  v2.1.9 /Users/yunpeng/pi-investment/agent-dh/packages/web/dsh-pmboard
 ✓ tests/size-budget.test.ts (5 tests) 12ms
 ✓ tests/capture-hook.test.ts (26 tests) 7ms
 ✓ tests/isolate-node-context.test.ts (29 tests) 21ms
 Test Files  3 passed (3)
      Tests  60 passed (60)
   Start at  02:02:35
   Duration  653ms
```

- 退出码：**0**（全绿）
- 判定：与父卡验收命令逐字一致。

## 2. 尺寸门禁：`src/index.ts` ≤ 400

```bash
cd packages/web/dsh-pmboard && wc -l src/index.ts src/plugin-config.ts src/wiring/pm-capture-root.ts
```

```
     357 src/index.ts
      42 src/plugin-config.ts
     161 src/wiring/pm-capture-root.ts
     560 total
```

- `357 ≤ 400` ✅（抽走前为 434 行，见拆分计划 D-2）。
- `tests/size-budget.test.ts` 用**与 `wc -l` 同口径**的 `lineCount()` 递归扫描 `src/**/*.ts` 全量文件，断言「所有 .ts 单文件 ≤ 400 行（白名单逐条带理由且须仍超限）」——该门禁绿，说明不只是 index.ts、整个 `src/` 无新增超标文件；扫描器自检（≥20 个 .ts）与 `src/host/` 收口项一并通过。

## 3. 兼容再导出与行为不变（`nodeIsolationEnabled`）

- 消费面未变：`tests/isolate-node-context.test.ts:38` 仍 `import { nodeIsolationEnabled } from '../src/index.js'`（走 index 再导出，而非新模块路径）→ 实测可用。
- 行为逐例锁定（`tests/isolate-node-context.test.ts:523-531`，全通过）：
  - 默认关：`undefined` / `{}` → `false`；`NODE_ISOLATION=off|0` → `false`
  - 环境变量开：`NODE_ISOLATION=1|true|ON`（大小写不敏感、trim）→ `true`
  - 显式配置优先：`{ nodeIsolation: false }` + `NODE_ISOLATION=1` → `false`；`{ nodeIsolation: true }` + 空 env → `true`
- `dshHomePath` 同为再导出，index.ts 内 6 处路径拼装改用同一实现（`CAPTURE_DIAG_REL`/`LEDGER_FILE`/`INJECTION_LOG_REL`/`ISOLATION_TRACE_REL`/`CAPTURE_REJECTION_REL`），`tests/capture-hook.test.ts`（26 例）与 `tests/isolate-node-context.test.ts`（29 例）覆盖其装配路径，全绿。

## 4. 结论

| 父卡验收口径 | 证据 | 结果 |
|---|---|---|
| 目标命令全绿 | §1：3 files / 60 tests passed，exit 0 | ✅ |
| `wc -l src/index.ts` ≤ 400 | §2：357 行；size-budget 门禁全量扫描亦绿 | ✅ |
| `nodeIsolationEnabled` 仍可从 `src/index.ts` import 且行为不变 | §3：index 再导出被测试直接 import；优先级 9 例断言全通过 | ✅ |

- 全绿，无失败、无跳过、无新增红例。
- 本卡为 T-12 的 test 阶段：只复跑目标命令并落本记录，未改动任何源码/测试文件。

修订记录：v1 · 2026-09-25 · 本窗口 · 初稿
