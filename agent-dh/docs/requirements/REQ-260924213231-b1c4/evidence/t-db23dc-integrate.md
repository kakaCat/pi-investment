# t-db23dc 联调记录（父卡 t-6cfab3 / T-7「打零参绑定 patch」· 阶段 integrate）

- 联调时间：2026-09-24T23:26+0800
- 联调环境：node v22.23.2 · vitest 2.1.9（darwin-arm64，运行 banner 为准）· 工作目录 `agent-dh`，测试工作目录 `packages/web/dsh-pmboard`
- 联调对象（接口 **I-5 工具绑定层**，FR-4）：`@deepseek-ai/dsh-ptc-runtime-node@0.1.6-alpha.2` 的绑定工厂，由
  `patches/@deepseek-ai__dsh-ptc-runtime-node@0.1.6-alpha.2.patch`（`lib/process.js` 单行 `value: (args) => {` → `value: (args = {}) => {`）
  + 根 `package.json` 的 `pnpm.patchedDependencies` 登记 + `packages/web/dsh-pmboard/tests/zero-arg-binding.test.ts` 四层守护构成
- 结论：**接口联调通过** —— 请求样例、期望响应、实际返回三者一致；零参调用与显式 `{}` 等价，且不再产生 `binding arguments must be lossless JSON`。

---

## 1. 接口 I-5 三方对照（核心验收）

联调方式：在本窗口 `run_code` 内对**同一工具**发两次调用 —— A 零参、B 显式空对象 —— 逐字节比较两者返回值，并检查是否出现绑定层拒绝错误。

| 项 | 内容 |
|---|---|
| 请求样例 A（零参） | `await tools.reqboard_status()`（省略 args；wire 帧 args 预序编码为 `[{kind:'object',keys:[]}]`，见第 2 节第 4 例） |
| 请求样例 B（对照） | `await tools.reqboard_status({})`（显式空对象，补丁前的合法写法） |
| 期望响应 | A 与 B **完全一致**；不抛错；输出不含 `binding arguments must be lossless JSON`；键集合为 `board_link,bound,clause_receive_status,next_actions,note,open_count,open_requirements,unreceived_clauses,window_key` |
| 实际返回 A | `{"window_key":"80f4a392-1c60-4534-985d-0befcfd5b7a9","bound":false,"open_count":0,"open_requirements":[],"next_actions":[],"clause_receive_status":[],"unreceived_clauses":[],"note":"本窗口未绑定需求：识别到值得立项的新工作 → 调 reqboard_capture 弹「立项三问」（需求名称 / 需求类型 / 提示词难度），用户作答即在同一次调用内创建并绑定本窗口（创建即立项）","board_link":"/dashboard#pmboard"}` |
| 实际返回 B | 与 A 逐字符相同（见下方判定） |
| 判定 | **一致**：`JSON.stringify(A) === JSON.stringify(B)` → `true`；`A.includes('binding arguments must be lossless JSON')` → `false` |

实测输出（节选）：

```
zero-arg  : {"window_key":"80f4a392-1c60-4534-985d-0befcfd5b7a9","bound":false,"open_count":0,...,"board_link":"/dashboard#pmboard"}
explicit{}: {"window_key":"80f4a392-1c60-4534-985d-0befcfd5b7a9","bound":false,"open_count":0,...,"board_link":"/dashboard#pmboard"}
deep-equal: true
keys      : board_link,bound,clause_receive_status,next_actions,note,open_count,open_requirements,unreceived_clauses,window_key
no-binding-error: true
```

- 说明：本卡为 subagent 窗口，`reqboard_status()` 如实返回 `bound=false / open_count=0`（未绑定需求），两次调用读到的 `window_key` 均为本窗口标识，故返回值稳定可比。
- 对照意义：补丁前零参在 `snapshotPtcJsonValue(undefined)` 处即被 reject，宿主收不到 call 帧，表现为「静默失败」；补丁后零参走缺省 `{}`，回落为与显式空对象**同一路径**。

## 2. 目标命令：绑定守护测试（命令与输出摘要）

```bash
cd packages/web/dsh-pmboard
npx vitest run tests/zero-arg-binding.test.ts
```

实际输出：

```
 RUN  v2.1.9 /Users/yunpeng/pi-investment/agent-dh/packages/web/dsh-pmboard

 ✓ tests/zero-arg-binding.test.ts (4 tests) 38ms

 Test Files  1 passed (1)
      Tests  4 passed (4)
```

- 退出码：**0**（全绿）
- 期望：`npx vitest run tests/zero-arg-binding.test.ts` 全绿且断言补丁后 `lib/process.js` 绑定工厂为 `(args = {})`
- 实际：4 例全通过 —— 与期望一致。四例分别守护：① 根 `package.json` 仍登记 `patchedDependencies`；② patch 文件仍含 `(args = {})`；③ **已安装产物** `lib/process.js` 真带默认参数；④ **跨进程行为**：零参调用 call 帧 `args` 恰为 `[{kind:'object',keys:[]}]` 且能收到宿主 `done` 回包。

## 3. 补丁链路落地核验（贴片登记 → 文件 → 已安装产物）

| 环节 | 命令 | 实际结果 |
|---|---|---|
| ① 登记 | `grep -n -A6 patchedDependencies package.json` | `"@deepseek-ai/dsh-ptc-runtime-node@0.1.6-alpha.2": "patches/@deepseek-ai__dsh-ptc-runtime-node@0.1.6-alpha.2.patch"` |
| ② 补丁文件 | `ls -la patches/@deepseek-ai__dsh-ptc-runtime-node@0.1.6-alpha.2.patch` | 存在，544 字节，唯一改动为 `lib/process.js` 第 952 块 `value: (args = {}) => {` |
| ③ 已安装产物 | `grep -n "value: (args = {}) => {" node_modules/.pnpm/node_modules/@deepseek-ai/dsh-ptc-runtime-node/lib/process.js` | 命中 `955:			value: (args = {}) => {`（提升层与虚拟店副本两处均为补丁后） |
| ④ 运行时（本窗口） | `run_code` 内零参 `tools.reqboard_status()` | 正常返回（见第 1 节），无绑定层拒绝 |

## 4. 联调结论

1. 接口 I-5 的**请求样例（零参）→ 期望响应（等同显式 `{}`、无绑定拒绝）→ 实际返回（逐字符相同）** 三方一致，FR-4「零参数工具可直接调用」在本窗口运行时成立。
2. 补丁链路四层（登记 / patch 文件 / 已安装产物 / 跨进程 wire 帧）均实测通过，`zero-arg-binding.test.ts` 4/4 绿、exit 0。
3. 本卡为 integrate 阶段，只执行上述命令与探针并落本记录；**未修改任何实现、补丁或测试源码**，本轮新增产物仅本文件。
4. 工作区状态：`package.json`、`pnpm-lock.yaml`、patch 文件、`zero-arg-binding.test.ts` 为父卡 T-7 的待提交改动（本卡未触碰），HEAD = `9e5ebf60`（branch `main`）。
