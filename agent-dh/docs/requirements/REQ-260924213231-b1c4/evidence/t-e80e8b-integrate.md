# t-e80e8b 联调记录（父卡 t-216224 / T-8「设计提示词写明登记命令」· 阶段 integrate）

- 联调时间：2026-09-25T≈00:56+0800
- 联调环境：node v22.23.2 · vitest 2.1.9（darwin-arm64）· HEAD `9e5ebf60`（branch `main`）· 测试工作目录 `packages/web/dsh-pmboard`
- 联调对象（接口）：**FR-5 提示词文本面 ↔ I-1 `reqboard_submit(kind=design)` 工具契约面**
  - 文本面：`packages/web/dsh-pmboard/src/domain/prompt/fragments/design/{light,heavy}/overrides.md`
    → 生成器 `scripts/inline-prompt-fragments.mjs` → 产物 `packages/web/dsh-pmboard/src/domain/prompt/generated/fragments.ts`
    → 解析 `resolveStagePrompt({stage:'design', difficulty, category})` 的注入文本
  - 工具面：`packages/web/dsh-pmboard/src/tools/SubmitTool/SubmitTool.ts`（`kind` 枚举 / 输出 schema）
    → 用例 `packages/web/dsh-pmboard/src/application/use-cases/SubmitDesignArtifacts.ts`（FR-1 / I-1，T-3 交付）
  - 契约见 `docs/requirements/REQ-260924213231-b1c4/design/interfaces.md` §I-1
- 结论：**接口联调通过** —— 请求样例（提示词写明的命令）、期望响应、实际返回**三者一致**（12/12 例 MATCH）；
  目标测试 2 文件 25/25 绿；生成器同步门禁退出 0。

---

## 1. 接口三方对照（核心验收）

联调方式：在本轮内运行**临时探针** `tests/__probe-te80e8b.test.ts`（跑完即删，不入库），
从真实生成产物解析出 agent 实际读到的提示词文本，抽出登记命令，再以真实工具
`defineSubmitTool(deps)` 的 `parameters` / `execute` 对齐比对。
探针夹具：临时工作区 + 需求 `REQ-te80e8b`（status=design、category=feature，绑定窗口 `session-te80e8b-001`），
落盘 feature 五份设计文档。判定式 `JSON.stringify(expected) === JSON.stringify(actual)`。

### C1 — 提示词产出的命令名/ kind = 工具真实接受的枚举（文本面 ∩ 工具面）

| 项 | 内容 |
|---|---|
| 请求样例 | 对 `difficulty ∈ {light,heavy} × category ∈ {feature,bug,doc,refactor,spike,chore}` 共 12 档调 `resolveStagePrompt({stage:'design',difficulty,category}).text`，正则 `/reqboard_submit\(kind=([a-z_]+)\)/` 抽命令 |
| 期望响应 | 12 档均能抽出命令、kind 均为 `design`；`defineSubmitTool(deps).name='reqboard_submit'`；`parameters.properties.kind.enum` 含 `design` 且与 `SUBMIT_KINDS` 一致 |
| 实际返回 | `{"light/feature":"design",...,"heavy/chore":"design"}`（12/12 = design）；name=`reqboard_submit`；enum=`["requirement","plan","verification","archive","design"]`；`SUBMIT_KINDS` 同值 |
| 判定 | **一致（MATCH × 4）** |

意义：提示词写明的命令**恰好命中**工具枚举内的 `design`，agent 照提示词执行不会被枚举挡下；
12 档（含六种类型档路由壳）全部覆盖，不是只在缺省档生效。

### C2 — 真实执行：`{kind:'design'}` 首登 5 份

| 项 | 内容 |
|---|---|
| 请求样例 | `execute({kind:'design'}, {agent:{id:'session-te80e8b-001'}})`（design/ 在盘 5 份必交） |
| 期望响应 | `{success:true, requirement_id:'REQ-te80e8b', registered_count:5, design_docs:5×{on_disk:true,registered:true,confirmed:false}}`，台账新增 5 条 `kind=design` |
| 实际返回 | 与期望逐字段相同（design_docs 5 行按 name 序：architecture/data-model/interfaces/test-cases/use-cases） |
| 判定 | **一致（MATCH × 2）** |
| 实际 note | 「已登记 5 份设计文档（kind=design）。下一步：调 reqboard_ask_confirm（target=artifact, kind=design）弹框请人确认设计——一次确认 = 全部设计文档成组落章，确认后进入拆分」 |

### C3 — 幂等（提示词声称「幂等，重复调不重计」）

| 项 | 内容 |
|---|---|
| 请求样例 | 同一窗口再次 `execute({kind:'design'})` |
| 期望响应 | `{success:true, registered_count:0}`；台账仍 5 条 |
| 实际返回 | `success=true, registered_count=0`；台账 5 条 |
| 判定 | **一致（MATCH × 3）** |

### C4 —「不要猜 kind」边界：猜错被枚举挡下（提示词断言为真）

| 项 | 内容 |
|---|---|
| 请求样例 | ① `execute({kind:'designs'})`（猜错种类）；② `execute({kind:'design', path:'docs/../etc/passwd'})`（伪路径） |
| 期望响应 | ① 被拒且提示合法枚举；② 被可打开性校验拒（REQBOARD_ARTIFACT_NOT_OPENABLE） |
| 实际返回 | ① `invalid arguments: "kind" must be one of ["requirement","plan","verification","archive","design"]`（绑定层枚举挡下，含 design、不含 designs）；② 命中 REQBOARD_ARTIFACT_NOT_OPENABLE |
| 判定 | **一致（MATCH × 2）** |

意义：提示词「不要猜 kind：只认 design，传错必被拒」不是空话——猜错在绑定层即被挡下；
同时单份登记仍走可打开性校验（FR-1 边界未被本次文本改动放松）。

探针执行结果（12/12 MATCH，脚本退出码 0）：

```
PROBE-TE80E8B VERDICTS:
[MATCH] C1.tool.name
[MATCH] C1.enum 含 design 且与 SUBMIT_KINDS 一致
[MATCH] C1.命令解析出 12 键（2 难度 × 6 类型）
[MATCH] C1.全部命令 kind = design
[MATCH] C1.命令 kind 均在工具 enum 内（提示词不会让 agent 发出被枚举挡下的调用）
[MATCH] C2.execute({kind:design})
[MATCH] C2.台账新增 5 条 kind=design
[MATCH] C3.second.registered_count
[MATCH] C3.second.success
[MATCH] C3.台账条目数不变
[MATCH] C4.kind=designs 被枚举挡下（must be one of + 枚举含 design 不含 designs）
[MATCH] C4.伪路径仍被可打开性校验拒
PROBE-TE80E8B SUMMARY: 12 checks, 0 MISMATCH

 Test Files  1 passed (1)
      Tests  5 passed (5)
EXIT=0
```

> 探针标定说明：首跑 C1 / C4 两处 MISMATCH 均系**探针侧写法不准**（C1：`defineTool` 把参数 DSL 归一为
> `{type:'object',properties:{...}}`，枚举在 `parameters.properties.kind.enum` 而非 `parameters.kind.enum`；
> C4：猜错 kind 在**绑定层**即被 `ToolArgsError` 挡下，错误语为 `must be one of [...]` 而非处理器内
> 的 REQBOARD_INVALID_INPUT）。修正探针后 12/12 MATCH。**非实现缺陷，未改动任何实现源码。**

## 2. 目标命令与输出摘要

### 2.1 生成器同步门禁（命令 1）

```bash
cd agent-dh
node packages/web/dsh-pmboard/scripts/check-prompt-fragments.mjs
```

实际输出（退出码 0）：

```
[check-prompt-fragments] OK: src/domain/prompt/generated/fragments.ts 与 fragments/**.md 一致；heavy.md ↔ vendor 原文逐字节一致
```

- 期望：退出 0（源 `overrides.md` 与产物 `generated/fragments.ts` 逐字节一致）
- 实际：OK，退出码 0 —— 与期望一致（父卡「重跑生成器」已落地，无源/产物漂移）

### 2.2 父卡验收目标测试（命令 2）

```bash
cd packages/web/dsh-pmboard
npx vitest run tests/design-prompt-registration.test.ts tests/prompt-baseline.test.ts
```

实际输出：

```
 ✓ tests/prompt-baseline.test.ts (15 tests) 5ms
 ✓ tests/design-prompt-registration.test.ts (10 tests) 6ms

 Test Files  2 passed (2)
      Tests  25 passed (25)
EXIT=0
```

- 期望：全绿（父卡验收命令）
- 实际：2/2 文件、25/25 通过，退出码 0 —— 与期望一致

### 2.3 本卡改动文件

本卡为 integrate 阶段，只执行上述探针与目标命令并落本记录；**未修改任何实现、生成器或测试源码**。
本轮新增产物仅本文件；临时探针 `tests/__probe-te80e8b.test.ts` 已在本轮内删除（`rm -f`，复核不存在）。

## 3. 结论

1. 设计阶段提示词写明的登记命令 `reqboard_submit(kind=design)`（light/heavy × 6 类型档共 12 档）
   与真实工具契约的 `kind` 枚举**逐档对齐**，请求样例、期望响应、实际返回三者一致（12/12 MATCH）。
2. 工具真实执行验证：首登 5 份 `registered_count=5`、二次幂等 `=0`、逐份登记态
   `{on_disk:true,registered:true,confirmed:false}` 与磁盘 + 台账一致；返回 note 给出下一步
   `reqboard_ask_confirm(target=artifact, kind=design)`，与提示词覆盖条目 1 的引导闭环。
3. 「不要猜 kind」在绑定层可证伪：`kind=designs` 被枚举挡下，伪路径被可打开性校验拒——
   提示词的强约束句有真实工具行为背书，而非措辞。
4. 生成器同步门禁退出 0、父卡验收 2 文件 25/25 全绿，无本卡引入的回归；
   FR-5「提示词含登记说明」达成，并锁死 FR-1 的 I-1 接口面。
