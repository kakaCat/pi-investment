# t-788302 联调记录（父卡 t-7e9633 / T-4「投影逐份登记态到 reqboard_status」· 阶段 integrate）

- 联调时间：2026-09-24T≈24:04+0800
- 联调环境：node v22.23.2 · vitest 2.1.9（darwin-arm64）· HEAD 9e5ebf60 · 测试工作目录 `packages/web/dsh-pmboard`
- 联调对象（接口）：**I-2** `reqboard_status()` 的 `design_docs[]` 投影（磁盘 / 产物簿 / 确认章三源合成）
  - 工具壳 `packages/web/dsh-pmboard/src/tools/StatusTool/StatusTool.ts`（零参入参 + 输出 schema 增 `design_docs[]`）
  - → 用例 `packages/web/dsh-pmboard/src/application/query/QueryState.ts`（`queryState` 调 `designDocRegistrationOf`）
  - → 投影纯函数 `packages/web/dsh-pmboard/src/application/internal/design-docs.ts`（`designDocRegistration` / `designDocRegistrationOf`）
  - 契约见 `docs/requirements/REQ-260924213231-b1c4/design/interfaces.md` §I-2
- 结论：**接口联调通过** —— 请求样例、期望响应、实际返回**三者一致**（8/8 例 MATCH）；
  目标测试 3 文件 35/35 绿；无本卡引入的回归。

---

## 1. 接口三方对照（核心验收）

联调方式：在本轮内运行**临时探针** `tests/__probe-t788302.test.ts`（跑完即删，不入库），
以真实适配器（`JsonLedgerRepository` + `FileDocRepository`）构造 `defineStatusTool(deps)` 并 `execute`，
逐用例打印「请求样例 / 期望响应 / 实际返回」，由探针逐条比对
（`verdict` 由 `JSON.stringify(expected) === JSON.stringify(actual)` 得出）。
测试夹具：独立临时工作区 + 需求 `REQ-e78803`（status=design，绑定窗口 `session-t788302-001`）。

### C1 — 工具入口契约：零参 parameters + 输出 schema

| 项 | 内容 |
|---|---|
| 请求样例 | `defineStatusTool(deps).parameters`；`output.schema.properties.design_docs` |
| 期望响应 | `parameters={type:'object',properties:{}}`（零参可调）；`design_docs` 为 array，items 键 = name/path/on_disk/registered/confirmed/exempted/conditional，`additionalProperties:false` |
| 实际返回 | 与期望逐字符相同 |
| 判定 | **一致（MATCH）** |

### C2 — 三源四态：未登记 / 待确认 / 已落章 / 缺失

| 项 | 内容 |
|---|---|
| 请求样例 | `execute({}, {agent:{id:'session-t788302-001'}})`；design/ 在盘 3 份（architecture/data-model/interfaces），产物簿 2 条（data-model 未落章、interfaces 已落章 confirmedAt=2） |
| 期望响应 | 5 行（feature 必交集顺序）：architecture {on_disk:true,registered:false,confirmed:false}（未登记）/ data-model {true,true,false}（待确认）/ interfaces {true,true,true}（已落章）/ test-cases 与 use-cases {false,false,false}（缺失仍逐份列出） |
| 实际返回 | 与期望逐字符相同（path 均为 `docs/requirements/REQ-e78803/design/<name>`） |
| 判定 | **一致（MATCH）** |

```
[MATCH] C2.design_docs
  expected: [{"name":"architecture.md","path":"docs/requirements/REQ-e78803/design/architecture.md","on_disk":true,"registered":false,"confirmed":false},
             {"name":"data-model.md",...,"on_disk":true,"registered":true,"confirmed":false},
             {"name":"interfaces.md",...,"on_disk":true,"registered":true,"confirmed":true},
             {"name":"test-cases.md",...,"on_disk":false,"registered":false,"confirmed":false},
             {"name":"use-cases.md",...,"on_disk":false,"registered":false,"confirmed":false}]
  actual  : <与 expected 逐字符相同>
```

附带 `C2.bound`：`{bound:true, open_count:1, ids:['REQ-e78803']}` —— MATCH。

### C3 — 未绑定窗口

| 项 | 内容 |
|---|---|
| 请求样例 | `execute({}, {agent:{id:'session-t788302-001'}})`（需求绑定在别的窗口 `session-t788302-999`） |
| 期望响应 | `{bound:false, design_docs:[]}` |
| 实际返回 | `{bound:false, design_docs:[]}` |
| 判定 | **一致（MATCH）** |

### C4 — front-matter 策略（sides / design_exempt）

| 项 | 内容 |
|---|---|
| 请求样例 | requirement.md `sides: frontend` + `design_exempt: test-cases.md=本需求无测试点（已评审）` → `execute({})` |
| 期望响应 | frontend.md 行 {on_disk:false,registered:false,confirmed:false,conditional:'frontend'}；无 backend.md 行；test-cases.md 行 `exempted='本需求无测试点（已评审）'` |
| 实际返回 | 与期望逐字段相同 |
| 判定 | **一致（MATCH）** |

### C5 — 未知/缺 category

| 项 | 内容 |
|---|---|
| 请求样例 | 需求 category 缺省；design/ 仅 `extra.md` → `execute({})` |
| 期望响应 | 行集 = `['extra.md']`（只报磁盘额外件，不瞎报必交清单） |
| 实际返回 | `['extra.md']` |
| 判定 | **一致（MATCH）** |

### C6 — I-1 × I-2 联动（登记 → 落章逐份同步）

| 项 | 内容 |
|---|---|
| 请求样例 | 落盘 feature 必交 5 份 → `submit({kind:'design'})` → `status({})`；再在台账给 architecture.md 落章 confirmedAt=7 → `status({})` |
| 期望响应 | 登记后 `registered_count=5` 且 5 行 {on_disk:true,registered:true,confirmed:false}；落章后 architecture {true,true,true}、其余 {true,true,false} |
| 实际返回 | 与期望逐字段相同 |
| 判定 | **一致（MATCH）** |

C6 证明 `reqboard_submit(kind=design)`（I-1）与 `reqboard_status`（I-2）**共用同一份三源合成规则**——
登记入口写入产物簿后，status 的 `registered` 逐份同步；确认章写入后 `confirmed` 逐份同步，两条工具面不存在「两套真相」。

探针执行结果（8/8 MATCH，脚本退出码 0）：

```
 ✓ tests/__probe-t788302.test.ts (7 tests) 47ms
 Test Files  1 passed (1)
      Tests  7 passed (7)
PROBE-T788302 SUMMARY: 8/8 MATCH
```

> 探针标定说明：首跑 C1/C5 两处 MISMATCH 均系**探针侧期望写错**（C1：`defineTool` 把零参入参 DSL 归一为
> `{type:'object',properties:{}}`，并非字面 `{}`；C5：探针 `seed()` 用 `?? 'feature'` 吞掉了显式 `undefined` category），
> 修正后 8/8 MATCH。**非实现缺陷**，未改动任何实现源码。

## 2. 目标命令与输出摘要

### 2.1 本卡接口联调探针（命令 1）

```bash
cd packages/web/dsh-pmboard
npx vitest run tests/__probe-t788302.test.ts        # 临时文件，跑完已删
```

实际输出摘要：`Test Files 1 passed (1)` / `Tests 7 passed (7)`，8/8 `verdict=MATCH`，退出码 0。

### 2.2 父卡验收目标测试（命令 2）

```bash
cd packages/web/dsh-pmboard
npx vitest run tests/tools-status.test.ts tests/design-registration.test.ts tests/output-contract.test.ts
```

实际输出：

```
 ✓ tests/tools-status.test.ts (7 tests) 26ms
 ✓ tests/design-registration.test.ts (9 tests) 125ms
 ✓ tests/output-contract.test.ts (19 tests) 125ms

 Test Files  3 passed (3)
      Tests  35 passed (35)
```

- 期望：全绿（父卡验收命令）
- 实际：3/3 文件、35/35 通过，退出码 0 —— 与期望一致

### 2.3 本卡改动文件

本卡为 integrate 阶段，只执行上述探针与目标命令并落本记录；**未修改任何实现或测试源码**。
本轮新增产物仅本文件；临时探针 `tests/__probe-t788302.test.ts` 已在本轮内删除（`rm -f`，复核不存在）。

## 3. 结论

1. I-2 `reqboard_status()` 的**输入契约**（零参可调，`parameters={type:'object',properties:{}}`）与
   **输出契约**（`design_docs[]` 逐份三态 name/path/on_disk/registered/confirmed + 可选 exempted/conditional）
   经真实工具 `execute` 调用验证，请求样例、期望响应、实际返回**三者一致**（8/8 MATCH）。
2. 三源四态（未登记 / 待确认 / 已落章 / 缺失）逐份与磁盘 + 台账一致；未绑定窗口返回空数组不瞎报；
   front-matter 策略（sides / design_exempt）与未知 category 边界均按契约落地。
3. I-1（`submit(kind=design)`）与 I-2（`status`）共用同一份 `designDocRegistrationOf` 合成规则，
   登记 / 落章在两个工具面逐份同步，达成 FR-1「agent 不打开看板也能读出设计文档逐份登记态」。
4. 父卡验收命令 3/3 文件、35/35 用例全绿，无本卡引入的回归。
