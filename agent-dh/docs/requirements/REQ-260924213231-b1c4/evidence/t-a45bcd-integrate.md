# t-a45bcd 联调记录（父卡 t-800d53 / T-12「组合根瘦身使尺寸门禁转绿」· 阶段 integrate）

- 联调时间：2026-09-25T01:58+0800
- 联调环境：node v22.23.2 · vitest 2.1.9（darwin-arm64）· 工作目录 `packages/web/dsh-pmboard`
- 联调对象（T-12 抽出/再导出的接口面）：
  - **I-A** `dshHomePath(config, file): string` / `nodeIsolationEnabled(config?, env?): boolean` ——
    `packages/web/dsh-pmboard/src/plugin-config.ts`（新抽出的配置/路径纯函数）
  - **I-B** `export { dshHomePath, nodeIsolationEnabled }` ——
    `packages/web/dsh-pmboard/src/index.ts`（兼容再导出，指针必须与 I-A 同一函数）
  - **I-C** `createCaptureRuntime({plugin, getAgents})` / `assembleCaptureHook(deps)` ——
    `packages/web/dsh-pmboard/src/wiring/pm-capture-root.ts`（新抽出的捕获根装配）
  - **I-D** `apply(ctx, config)` —— `packages/web/dsh-pmboard/src/index.ts`（抽取后组合根装配顺序仍成立）
- 结论：**接口联调通过** —— 请求样例、期望响应、实际返回三者一致（C1–C6 全 MATCH，7/7 探针用例绿）；
  `index.ts` 357 行 ≤ 400 尺寸门禁；父卡目标测试 3 文件 60/60 绿。

---

## 1. 接口三方对照（核心验收）

联调方式：在本轮内运行**临时探针** `packages/web/dsh-pmboard/tests/__probe-ta45bcd.test.ts`
（7 个用例，跑完即删、未入库），对 I-A/I-B/I-C/I-D 各发真实调用，逐字段打印并比较
「请求样例 / 期望响应 / 实际返回」。

### C1 — I-B 再导出同一性（index.ts 的兼容面必须指向 I-A）

| 项 | 内容 |
|---|---|
| 请求样例 | `import * as idx from './index.js'; import * as cfg from './plugin-config.js'` |
| 期望响应 | `{sameDshHomePath:true, sameNodeIsolationEnabled:true}` |
| 实际返回 | `{"sameDshHomePath":true,"sameNodeIsolationEnabled":true}` |
| 判定 | **一致（MATCH）**：`idx.dshHomePath === cfg.dshHomePath`、`idx.nodeIsolationEnabled === cfg.nodeIsolationEnabled`（同一函数对象，非转发包装） |

### C2 — I-A `dshHomePath` 三方对照（三级优先，行为与抽取前逐字一致）

| # | 请求样例 | 期望响应 | 实际返回 | 判定 |
|---|---|---|---|---|
| D1 | `{config:{dshHome:'/tmp/dsh-home-A'}, file:'dsh-reqboard.json', env:{DSH_HOME:'/tmp/env-B'}}` | `/tmp/dsh-home-A/dsh-reqboard.json` | `/tmp/dsh-home-A/dsh-reqboard.json` | **一致** |
| D2 | `{config:{}, file:'state/node-isolation-log.json', env:{DSH_HOME:'/tmp/env-B'}}` | `/tmp/env-B/state/node-isolation-log.json` | `/tmp/env-B/state/node-isolation-log.json` | **一致** |
| D3 | `{config:undefined, file:'dsh-reqboard.json', env:{}}` | `~/.dsh/dsh-reqboard.json`（`os.homedir()`） | `/Users/yunpeng/.dsh/dsh-reqboard.json` | **一致** |

### C3 — I-A `nodeIsolationEnabled` 三方对照（真值表：显式 config > env > 默认 false）

| # | 请求样例 | 期望响应 | 实际返回 | 判定 |
|---|---|---|---|---|
| E1 | `{config:{nodeIsolation:true}, env:{}}` | `true` | `true` | **一致** |
| E2 | `{config:{nodeIsolation:false}, env:{NODE_ISOLATION:'1'}}` | `false`（显式压过 env） | `false` | **一致** |
| E3 | `{config:undefined, env:{NODE_ISOLATION:'1'}}` | `true` | `true` | **一致** |
| E4 | `{config:undefined, env:{NODE_ISOLATION:'true'}}` | `true` | `true` | **一致** |
| E5 | `{config:undefined, env:{NODE_ISOLATION:'on'}}` | `true` | `true` | **一致** |
| E6 | `{config:undefined, env:{NODE_ISOLATION:'  YES '}}` | `true`（trim+小写容错） | `true` | **一致** |
| E7 | `{config:undefined, env:{NODE_ISOLATION:'0'}}` | `false` | `false` | **一致** |
| E8 | `{config:undefined, env:{}}` | `false`（默认关） | `false` | **一致** |
| E9 | `{config:undefined, env:{NODE_ISOLATION:'maybe'}}` | `false`（未知值不猜） | `false` | **一致** |

### C4 — I-C `createCaptureRuntime` 形状与投递行为

| # | 项 | 期望响应 | 实际返回 | 判定 |
|---|---|---|---|---|
| C4a | `createCaptureRuntime({plugin:'dsh-pmboard', getAgents:()=>undefined})` | 三张空 Map（`pendingCapture`/`toolTrace`/`recentUserMsgs`，size 0）+ `deliverer` 为 `AgentDeliverer` 实例 | `{"pendingCaptureIsMap":true,"toolTraceIsMap":true,"recentUserMsgsIsMap":true,"delivererClass":"AgentDeliverer",...}` | **一致** |
| C4b | `deliverer.deliver('session-unbound-x',{text:'hi'})`（agents 不可得） | `{delivered:false, reason:'agents 服务不可得（未装配 ctx.agents）'}`（永不抛） | 同期望 | **一致** |
| C4c | `deliverer.deliver('session-bound-1',{text:'阶段提示'})`（agents 就绪、agent 有 followup） | `{delivered:true}` + followup 载荷 `content[0].text='阶段提示'`、`source={kind:'plugin',plugin:'dsh-pmboard'}` | 同期望 | **一致** |

### C5 — I-C `assembleCaptureHook` 装配、订阅与解除

| # | 项 | 期望响应 | 实际返回 | 判定 |
|---|---|---|---|---|
| C5a | `assembleCaptureHook({ctx:{on}, store:空台账, runtime, ...})` | 订阅事件 = `['session/event']`；返回 `() => void` 解除订阅；handler 为函数 | `{"subscribedEvents":["session/event"],"returnsDisposer":true,"handlerIsFn":true}` | **一致** |
| C5b | handler(`{id:'session-unbound-x'}`, `user/message` 直接人类消息「组合根瘦身：把 index.ts 拆小」) | `pendingCapture` 命中：`{windowKey:'session-unbound-x', text:'组合根瘦身：把 index.ts 拆小', capturedAt:1000}`（完整判定链直连共享 Map） | `{"windowKey":"session-unbound-x","text":"组合根瘦身：把 index.ts 拆小","capturedAt":1000}` | **一致** |
| C5c | 调 C5a 返回的解除订阅函数 | 订阅被解除（`unsubscribed=true`，不抛） | `unsubscribed = true` | **一致** |

### C6 — I-D `apply()` 组合根装配（抽取后装配顺序仍成立）

| 项 | 内容 |
|---|---|
| 请求样例 | `apply(stubCtx(注入 systemPrompt/tools/webServer/agents/sessionProjections), {dshHome:<tmpdir>})` |
| 期望响应 | 注册 15 个 agent 工具；capture section `reqboard:capture` order=60；路由 `/dashboard/api/reqboard` |
| 实际返回 | `toolCount=15`（`reqboard_accept_sheet/ask_confirm/capture/confirm_receipt/create/decompose/move/note_interruption/status/submit/task_execute/task_move/task_report/task_run/task_status`）、`captureSectionOrder=60`、`route=/dashboard/api/reqboard` |
| 判定 | **一致（MATCH）**：抽取未打断组合根 `inject → effect → section/tools/route` 装配链 |

---

## 2. 目标门禁与尺寸（父卡验收命令复跑）

```
$ cd packages/web/dsh-pmboard && npx vitest run tests/size-budget.test.ts tests/isolate-node-context.test.ts tests/capture-hook.test.ts
 ✓ tests/isolate-node-context.test.ts (29 tests)
 Test Files  3 passed (3)
      Tests  60 passed (60)

$ wc -l packages/web/dsh-pmboard/src/index.ts packages/web/dsh-pmboard/src/plugin-config.ts packages/web/dsh-pmboard/src/wiring/pm-capture-root.ts
     357 packages/web/dsh-pmboard/src/index.ts
      42 packages/web/dsh-pmboard/src/plugin-config.ts
     161 packages/web/dsh-pmboard/src/wiring/pm-capture-root.ts
```

- `size-budget` 转绿：`index.ts` **357 行 ≤ 400**（抽取前 434 行，已回落）。
- `isolate-node-context` / `capture-hook` 全绿：捕获根装配搬文件后行为零变更（hook 订阅/判定链/隔离信号语义不变）。
- 探针 `__probe-ta45bcd.test.ts` 7/7 绿，跑完即删（`ls tests/ | grep __probe` 无残留）。

---

## 3. 结论与遗留

- **接口联调通过**：I-A（纯函数语义）/ I-B（同一性再导出）/ I-C（运行时装配 + 订阅回执）/ I-D（组合根装配）
  四类接口的「请求样例 / 期望响应 / 实际返回」逐项一致，无偏差。
- 兼容性：既有 `import { dshHomePath | nodeIsolationEnabled } from './index.js'` 的调用方无需改动；
  两者为**同一函数对象**（非转发 wrapper），行为与抽取前一致（C2/C3）。
- 遗留（不属本卡）：`index.ts` 仍 357 行、后续 FR 接线若再加行需继续盯门禁；本卡仅联调，不改行为。
