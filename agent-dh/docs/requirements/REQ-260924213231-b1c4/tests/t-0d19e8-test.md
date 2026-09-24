# t-0d19e8 测试记录（父卡 T-7「打零参绑定 patch」· 阶段 test）

- 测试时间：2026-09-24T23:29+0800
- 测试环境：node v22.23.2 · vitest 2.1.9（darwin-arm64，运行 banner 为准）· 仓库工作目录 `agent-dh`，测试工作目录 `packages/web/dsh-pmboard`；HEAD = `9e5ebf60`（branch `main`）
- 被测对象（接口 **I-5 工具绑定层**，FR-4）：
  - `patches/@deepseek-ai__dsh-ptc-runtime-node@0.1.6-alpha.2.patch`（544 字节，唯一改动 `lib/process.js` 的绑定工厂 `value: (args) => {` → `value: (args = {}) => {`）
  - 根 `package.json` 的 `pnpm.patchedDependencies` 登记项
  - `packages/web/dsh-pmboard/tests/zero-arg-binding.test.ts`（四层守护：登记 / patch 文件 / 已安装产物 / 跨进程 wire 帧）
- 测试结论：**目标命令全绿** —— `npx vitest run tests/zero-arg-binding.test.ts` → 1 file / 4 tests 通过，**exit 0**；另在本窗口复跑零参运行时探针，零参与显式 `{}` 逐字符相同且无绑定层拒绝。验收标准「目标命令输出全绿」达成。

---

## 1. 目标命令：绑定守护测试

```bash
cd packages/web/dsh-pmboard
npx vitest run tests/zero-arg-binding.test.ts
```

实际输出（逐字）：

```
 RUN  v2.1.9 /Users/yunpeng/pi-investment/agent-dh/packages/web/dsh-pmboard

 ✓ tests/zero-arg-binding.test.ts (4 tests) 31ms

 Test Files  1 passed (1)
      Tests  4 passed (4)
   Start at  23:28:49
   Duration  233ms (transform 17ms, setup 0ms, collect 17ms, tests 31ms, environment 0ms, prepare 28ms)
```

- 退出码：**0**（全绿）
- 判定：与验收「`npx vitest run tests/zero-arg-binding.test.ts` 全绿」一致。

### 1.1 逐例结果（`--reporter=verbose`，4/4 通过）

```
 ✓ tests/zero-arg-binding.test.ts > 零参绑定守护：dsh-ptc-runtime-node 补丁 > 根 package.json 仍登记该包的 patchedDependencies
 ✓ tests/zero-arg-binding.test.ts > 零参绑定守护：dsh-ptc-runtime-node 补丁 > patch 文件仍把绑定工厂改成 (args = {})
 ✓ tests/zero-arg-binding.test.ts > 零参绑定守护：dsh-ptc-runtime-node 补丁 > 已安装产物 lib/process.js 带上了默认参数（patch 未生效即红）
 ✓ tests/zero-arg-binding.test.ts > 零参绑定守护：dsh-ptc-runtime-node 补丁 > 零参调用跨进程生效：call 帧 args 编码为 {} 且能拿到回包

 Test Files  1 passed (1)
      Tests  4 passed (4)
```

四例分别守护（任一层被回退即红）：

| 层 | 守护内容 | 结果 |
|---|---|---|
| ① 登记 | 根 `package.json` 仍登记 `@deepseek-ai/dsh-ptc-runtime-node@0.1.6-alpha.2` 的 `patchedDependencies` 且 patch 文件存在 | ✅ |
| ② 补丁文本 | patch 文件同时含原文 `value: (args) => {` 与改后 `value: (args = {}) => {` | ✅ |
| ③ 已安装产物 | pnpm 实际安装的 `lib/process.js` 真带默认参数（patch 没生效即红） | ✅ |
| ④ 跨进程行为 | 子进程零参调用 `tools.ping()` → call 帧 `args` 恰为 `[{kind:'object',keys:[]}]`，回包 `done` 且 `value=[{kind:'object',keys:['got']},'pong']` | ✅ |

## 2. 补丁链路独立核验（贴片登记 → 文件 → 已安装产物）

| 环节 | 命令 | 实际结果 |
|---|---|---|
| ① 登记 | `grep -n -A7 '"patchedDependencies"' package.json` | 第 338 行命中 `"@deepseek-ai/dsh-ptc-runtime-node@0.1.6-alpha.2": "patches/@deepseek-ai__dsh-ptc-runtime-node@0.1.6-alpha.2.patch"` |
| ② 补丁文件 | `ls -la patches/@deepseek-ai__dsh-ptc-runtime-node@0.1.6-alpha.2.patch` | 存在，544 字节；唯一改动为 `lib/process.js` 的 `value: (args) => {` → `value: (args = {}) => {` |
| ③ 已安装产物（提升层） | `grep -n "value: (args = {}) => {" node_modules/.pnpm/node_modules/@deepseek-ai/dsh-ptc-runtime-node/lib/process.js` | 命中 `955:			value: (args = {}) => {` |
| ④ 已安装产物（虚拟店） | `grep -n … node_modules/.pnpm/@deepseek-ai+dsh-ptc-runtime-node@0.1.6-alpha.2_…/node_modules/@deepseek-ai/dsh-ptc-runtime-node/lib/process.js` | 命中 `955:			value: (args = {}) => {`（两处副本均为补丁后，无静默停旧版） |

## 3. 运行时探针：本窗口零参调用（跨进程 wire 帧行为）

`run_code` 内对**同一工具**发两次调用 —— A 零参 `tools.reqboard_status()`、B 显式空对象 `tools.reqboard_status({})`：

```
zero-arg  : {"window_key":"72144a62-30bb-460d-82e0-c2f65aa4a3c0","bound":false,"open_count":0,...,"board_link":"/dashboard#pmboard"}
explicit{}: {"window_key":"72144a62-30bb-460d-82e0-c2f65aa4a3c0","bound":false,"open_count":0,...,"board_link":"/dashboard#pmboard"}
deep-equal: true
keys      : board_link,bound,clause_receive_status,next_actions,note,open_count,open_requirements,unreceived_clauses,window_key
no-binding-error: true
```

- `JSON.stringify(A) === JSON.stringify(B)` → `true`；输出不含 `binding arguments must be lossless JSON`。
- 意义：补丁前零参在 `snapshotPtcJsonValue(undefined)` 处即被 reject，宿主收不到 call 帧（表现为「静默失败」）；补丁后零参走缺省 `{}`，与显式空对象同路径。
- 说明：本卡为 subagent 窗口，`reqboard_status()` 如实返回 `bound=false / open_count=0`，两次读到同一 `window_key`（本窗口标识），故返回值稳定可比。

## 4. 测试结论

1. 目标命令 `npx vitest run tests/zero-arg-binding.test.ts`：**1 file / 4 tests 全绿，exit 0** —— 验收标准「目标命令输出全绿」达成。
2. 补丁链路四层（登记 / patch 文件 / 已安装产物两处副本 / 跨进程 wire 帧）独立复验均通过。
3. 本卡为 test 阶段，只执行目标命令与探针并落本记录；**未修改任何实现、补丁或测试源码**，本轮新增产物仅本文件。
4. 工作区状态：`package.json`、`pnpm-lock.yaml`、patch 文件、`zero-arg-binding.test.ts` 为父卡 T-7 的待提交改动（本卡未触碰），HEAD = `9e5ebf60`。
