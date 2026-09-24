# t-d76da9 复核记录（父卡 t-6eca2a / T-3「新增 kind=design 登记用例与工具入口」· 阶段 review）

- 复核时间：2026-09-24T23:53+0800
- 复核环境：node v22.23.2 · vitest 2.1.9（darwin-arm64）· HEAD 9e5ebf60 · 测试工作目录 `packages/web/dsh-pmboard`
- 复核对象（实现）：
  - 新增 `packages/web/dsh-pmboard/src/application/use-cases/SubmitDesignArtifacts.ts`（133 行）
  - 改 `packages/web/dsh-pmboard/src/tools/SubmitTool/SubmitTool.ts`（+27/-6：SUBMIT_KINDS 增 design、分派表、kind/path 描述、输出 schema 增 design_docs/registered_count）
  - 改 `packages/web/dsh-pmboard/src/tools/SubmitTool/prompt.ts`（+6/-3：「四类」→「五类」+ design 段）
  - 改 `packages/web/dsh-pmboard/src/shared/protocol.ts`（+7/-0：`SubmitKind`/`SUBMIT_KINDS` 权威定义迁入 shared）
  - 新增 `packages/web/dsh-pmboard/tests/design-registration.test.ts`（170 行 / 9 例）
  - 改 `packages/web/dsh-pmboard/tests/output-contract.test.ts`（+2/-0：RESPONSE_SOURCES 补 SubmitDesignArtifacts 映射）
- 复核基准（设计）：`requirement.md` §6 FR-1 / §7 接口契约 / §8 迁移兼容 · `design/interfaces.md` I-1 及「I-1 字段明细」「错误语义 E-1/E-2」· `design/data-model.md` T-2/T-3 · `design/use-cases.md` UC-1 · `design/test-cases.md` TC-1/TC-19（前半）· `decomposition.md` T-3 行 + 测试文件落点 · 任务卡 `tasks/t-6eca2a.md`
- 复核方式：**只读复核**（不修改任何实现/测试源码），独立复现验收命令；另用临时探针（跑完即删）验证「投影 on_disk ↔ 发现核心」的边界一致性。
- 总裁决：**实现与设计逐条一致，无实现偏离**（§1 表 17/17）；发现 2 处**轻微口径差**（M-1 输出 schema 宽于设计联合类型、M-2 投影与发现核心对隐藏/嵌套件的口径不一致）与 1 处**文档级 nit**（M-3 分派测试注释与覆盖未随 5 类更新），**均无闸门/功能影响、不阻断父卡收尾**。

---

## 0. 设计基线（判定依据）

| 依据 | 位置 | 关键约定 |
|---|---|---|
| 需求 FR-1 | `requirement.md` §6 / §7 | 给 agent 可调用的设计产物登记入口；`reqboard_submit` 增补 `kind=design`（纯新增，既有 4 值语义不变）；新增登记能力**必须幂等**（同 path 已登记 → 跳过），与 ArtifactSync 语义一致 |
| 接口契约 I-1 | `design/interfaces.md` I-1 + 字段明细 | 入参 `kind=design`/`requirement_id?`/`path?`（缺省=扫 `design/*.md`）；出参 `success`/`requirement_id`/`design_docs[]`/`registered_count`/`note`；`registered_count`=本次**新登记**条数 |
| 错误语义 | 同 E-1/E-2 | `path` 伪路径/越界 → `REQBOARD_ARTIFACT_NOT_OPENABLE`；文件不存在 → `REQBOARD_FILE_MISSING` |
| 数据投影 T-3 | `design/data-model.md` T-3 | `DesignDocRegistration` = name/path/on_disk/registered/confirmed（+exempted?/conditional?），派生投影不落盘，三源合成 |
| 场景 UC-1 | `design/use-cases.md` | agent 只调工具（不打开看板）即可登记 5 份设计文档，全程无 `REQBOARD_MISSING_ARTIFACT` |
| 测试用例 TC-1/TC-19 | `design/test-cases.md` + 落点表 | 首次 `registered_count=5`、二次 `=0`；空目录 → `registered_count=0` 且不谎报 |
| 拆分计划 T-3 | `decomposition.md` 任务表/落点表 | 落点 4 文件（用例 + 工具壳 + 提示词 + 测试）；验收命令 `vitest run tests/design-registration.test.ts tests/tools-schema.test.ts tests/output-contract.test.ts` |
| 任务卡 | `tasks/t-6eca2a.md`「得到什么结果」 | 同上三条验收 + 「空目录返回 0 且不谎报成功」 |

---

## 1. 逐条对照（设计 → 实现 → 结论）

| # | 设计条目 | 实测实现 | 结论 |
|---|---|---|---|
| 1 | 入口 = `reqboard_submit(kind=design)`，`SUBMIT_KINDS` 增 `design`，既有 4 值语义不变 | `shared/protocol.ts:244-245` `SubmitKind = 'requirement'\|'plan'\|'verification'\|'archive'\|'design'`；既有 4 值原样保留、仅追加 | **无偏离**（依据：`git diff protocol.ts` = +7/-0 纯新增） |
| 2 | 工具 schema `kind.enum` 含 design | `SubmitTool.ts:45` `enum: [...SUBMIT_KINDS]`，实测 `["requirement","plan","verification","archive","design"]` | **无偏离**（依据：联调 `t-52d7fe-integrate.md` C1；`tools-schema.test.ts` 绿） |
| 3 | 表驱动分派，分支体仅一行用例调用（禁大 if） | `SUBMIT_DISPATCH` 增 `design: submitDesignArtifacts`；execute 仍「取表 + 一行 `return run`」 | **无偏离**（依据：`tools-dispatch.test.ts` 绿；§2.1） |
| 4 | 新用例落点/命名 `application/use-cases/SubmitDesignArtifacts.ts` | 文件存在（133 行），导出 `submitDesignArtifacts(deps,args,exec)` | **无偏离**（依据：§2.4 范围核验） |
| 5 | `requirement_id` 缺省 = 本窗口绑定需求；非本窗口绑定 → 拒 | 复用 `openRequirementsFor`：空 → `REQBOARD_NO_BOUND_REQ`，指定但越界 → `REQBOARD_NOT_BOUND_TO_WINDOW` | **无偏离**（与既有 `SubmitArtifact` 同口径，I-1「必须属于本窗口」；测试「归属校验」例绿） |
| 6 | `path` 缺省 → 扫 `design/*.md`；给了 → 只登记该份且走可打开性校验 | 缺省走 `discoverArtifactsFrom`（整个需求目录）后 `kind==='design'` 过滤；给了走 `assertArtifactOpenable` 单份 | **无偏离**（口径差见 M-2/O-3：`kindForRelPath` 只把 `design/**/*.md` 归 design，故登记集合 ≡ `design/` 下的设计件） |
| 7 | 幂等：同 path 已登记 → 跳过；`registered_count` 只数本次新增 | 候选先按 `priorDesignPaths` 排除，`registerArtifact` 再判 `stage+kind+path` 去重；`registered_count = added.length` | **无偏离**（TC-1 首次 5 / 二次 0 / 部分新增 1，测试绿） |
| 8 | `design_docs[]` = name/path/on_disk/registered/confirmed（+exempted?/conditional?） | `designDocRegistration(req, category, policy, onDisk)` 三源合成，7 字段齐 | **无偏离**（依据：`design-docs.ts:76-105`；测试逐份断言） |
| 9 | `conditional` 类型 = `"frontend"\|"backend"` | TS 接口匹配（`protocol.ts:455`），但**工具输出 schema 声明为 `type:'string'`（无 enum）** | **轻微偏离 → M-1**（实现宽于设计，无功能影响） |
| 10 | 空目录 / 无 .md → `registered_count=0` 且**不谎报成功** | `success=false` + note「未发现可登记的设计文档…不谎报成功」；`design_docs` 仍逐份回报 `on_disk=false` | **无偏离**（I-1 未规定空目录 `success` 取值，任务卡明确「不谎报成功」；TC-19 断言绿） |
| 11 | E-1 伪路径/越界 → `REQBOARD_ARTIFACT_NOT_OPENABLE`；E-2 文件不存在 → `REQBOARD_FILE_MISSING` | `assertArtifactOpenable` 当场抛，两错误码测试覆盖 | **无偏离**（依据：测试「I-1 path 语义」2 例绿） |
| 12 | 登记入口必须被 G2 闸门读到（不再 missing） | 登记后 `assertArtifactGates` 返回 `artifact_not_confirmed`（非 `missing_artifact`） | **无偏离**（测试「登记后 G2 读得到」绿；联调 C5） |
| 13 | 提示词写明 design 登记路径（扫目录/单份/幂等/先登记） | `prompt.ts`「四类→五类」+ design 段（含「未登记时 design→decomposing 会被代码级拒绝，先调本入口」） | **无偏离**（依据：`git diff prompt.ts`） |
| 14 | 与既有登记共用**唯一发现核心**，不在用例另立扫描真相 | 登记路径调 `discoverArtifactsFrom`（T-2 唯一核心）；`on_disk` 投影另用扁平 `designDocNames` 列目录 | **登记路径无偏离**；投影侧口径差见 M-2 |
| 15 | 不新增工具、不改既有 kind 契约、不动宿主 DSH 包 | 无新增工具注册；既有 4 kind 分支未改；无 `@deepseek-ai/dsh-*` 改动 | **无偏离**（依据：§2.4） |
| 16 | 无阶段门（历史需求可补齐登记） | 用例只校验窗口绑定，不校验 `status`（区别于 `SubmitArtifact` 的 brainstorming 门） | **无偏离**（依据：`data-model.md` §迁移「历史需求修复后可直接 `reqboard_submit(kind=design)` 补齐」；I-1 无阶段约束） |
| 17 | 验收命令全绿；类型面不新增错误 | 4 文件 35/35 绿；`tsc` 错误数 = 23 = 基线，T-3 文件命中 0 | **无偏离**（依据：§2.1/§2.2） |

> 结论：17 项设计/卡面约定**逐条无实现偏离**；M-1/M-2/M-3 为口径差与文档 nit，不构成契约破坏。

---

## 2. 独立复现（命令与输出摘要）

### 2.1 目标命令（卡面验收）

```bash
cd packages/web/dsh-pmboard
npx vitest run tests/design-registration.test.ts tests/tools-schema.test.ts tests/output-contract.test.ts tests/tools-dispatch.test.ts
```

```
 ✓ tests/output-contract.test.ts (19 tests) 122ms
 ✓ tests/design-registration.test.ts (9 tests) 124ms
 Test Files  4 passed (4)
      Tests  35 passed (35)
```

退出码 0 —— 与卡验收一致：TC-1 首次 `registered_count=5`、二次 `=0`；空目录 `registered_count=0, success=false`。

### 2.2 类型门禁（旁证）

```bash
npx tsc --noEmit -p tsconfig.json
```

```
error TS 行数 = 23（= decomposition.md D-1 记录的基线 23）
SubmitDesignArtifacts / SubmitTool / prompt 命中 0 条
```

### 2.3 独立探针：投影 ↔ 发现核心的边界一致性（跑完即删）

临时探针 `tests/__probe-t-d76da9.test.ts` 构造 `design/architecture.md` + `design/.hidden.md`（点文件）
+ `design/sub/deep.md`（嵌套）+ 需求根 `requirement.md`/`decomposition.md`，调 `{kind:'design'}`：

```
registered_count = 2                 # architecture.md + design/sub/deep.md
design_docs[.hidden.md] = {on_disk:true, registered:false}
design_docs 中存在 sub/deep.md ? = ABSENT
```

- **登记侧**：递归整个需求目录 + 跳点文件 + 只留 `kind=design` → 根目录 `requirement.md`/`decomposition.md` 不登记、`.hidden.md` 不登记、嵌套 `design/sub/deep.md` 登记 —— 与真实落盘 `registered_count` 一致。
- **投影侧**：`designDocNames` 用扁平 `docs.list(design/)` + 不跳点文件 → `.hidden.md` 显示 `on_disk=true/registered=false`（扫描永不登记它），嵌套件被登记却不出现在 `design_docs[]`。
- 探针已在本轮内 `rm -f` 删除：`ls tests/__probe-t-d76da9.test.ts` → `No such file or directory`。

### 2.4 范围与改动面核验

```bash
cd /Users/yunpeng/pi-investment
git diff --numstat -- .../shared/protocol.ts .../SubmitTool/SubmitTool.ts .../SubmitTool/prompt.ts .../tests/output-contract.test.ts
```

```
7   0   src/shared/protocol.ts
27  6   src/tools/SubmitTool/SubmitTool.ts
6   3   src/tools/SubmitTool/prompt.ts
2   0   tests/output-contract.test.ts
```

新增文件：`SubmitDesignArtifacts.ts` 133 行、`design-registration.test.ts` 170 行。
T-3 落点外多出 `tests/output-contract.test.ts`（+2 行：RESPONSE_SOURCES 登记新用例，使卡面验收含该文件时仍绿）——
属验收必需接线，不改任何断言语义（见 M-3 邻域说明）。

---

## 3. 偏离清单

### 3.1 无实现偏离

T-3 / FR-1 / I-1 / T-3 实体 / 任务卡的全部约定与实现逐条一致（§1 表 17/17）。以下 3 项**均不构成设计契约破坏、不阻断父卡收尾**。

| # | 性质 | 位置 | 实测 vs 设计 | 判定 |
|---|---|---|---|---|
| M-1 | 输出 schema 宽于设计（轻微） | `SubmitTool.ts:157` vs `interfaces.md` I-1 字段明细 | 设计 `conditional` = `"frontend"\|"backend"`；实现输出 schema 写 `type:'string'`（未用 enum，而 DSL 支持 enum——同文件 kind/phase/side 均用了）。TS 接口 `protocol.ts:455` 与设计一致，仅 wire 声明更宽 | 无功能影响（binding 不会拒合法值，也不会拦非法值）。**建议**（非阻断）补 `enum:['frontend','backend']` |
| M-2 | 投影 on_disk 与发现核心口径不一致（边界） | `SubmitDesignArtifacts.ts:33-38` 的 `designDocNames` vs `artifact-discovery.ts` | 登记走递归 + 跳点文件的唯一核心；`on_disk` 走扁平列目录 + 不跳点文件 → ①`.hidden.md` 报 `on_disk=true/registered=false` 而扫描永不登记它；②嵌套 `design/sub/*.md` 被登记却在 `design_docs[]` 不可见（§2.3 探针实证） | 边界、无闸门影响（G2 读的是必交清单，不读该投影）。**建议**（非阻断）让投影也复用发现核心或至少同口径过滤点文件 |
| M-3 | 测试注释/覆盖未随 5 类更新（文档级） | `tools-dispatch.test.ts:38` | 注释仍写「四类 kind 各有独立用例」；断言只列 `requirement/plan/verification/archive`，**未把 `design` 纳入分派表断言** | 测试实际全绿（不红），但 `design` 分支缺一条静态锁。**建议**（非阻断）注释改「五类」并把 `design` 加入 for 循环 |

---

## 4. 复核观察（不改判定，供后续卡）

- **O-1 分派断言已由运行态覆盖**：`design` 分支虽未被 `tools-dispatch.test.ts` 静态断言（M-3），但 `design-registration.test.ts` 经真实工具 `execute({kind:'design'})` 走通分派 → 功能面无缺口。
- **O-2 `on_disk` 行集来源**：`designDocRegistration` 行集 = 必交 ∪ 磁盘件（`design-docs.ts:102-104`），空目录仍返回 5 行 `on_disk=false`。I-1 未规定行集来源，此行为与 T-3「逐份态」语义一致，**非偏离**；且对 agent 更有用（知道还差哪份）。
- **O-3 缺省扫描等价性**：`discoverArtifactsFrom` 扫整个需求目录后按 `kindForRelPath` 过滤，`^design\/.+\.md$` 保证只有 design 件入选 → 与 I-1「扫 `design/*.md`」行为等价（§2.3 已由 `registered_count` 与根目录两文件未登记佐证）。
- **O-4 跨卡依赖**：`SubmitDesignArtifacts.ts` 依赖 `design-docs.ts` 的 `designDocRegistration`（decomposition 将其归 T-4 落点）。两卡在同一工作树内已就位、无接口冲突；仅提示后续 T-4 若改该函数签名需同步本用例。
- **O-5 mutate 结果未复查**：`submitDesignArtifacts` 未像 `SubmitArtifact` 那样检查 `mutate` 返回体（`REQBOARD_STORE_INCONSISTENT`）；因 `target` 取自同一快照且随后 `snapshot()` 复核，实际不会触发。**非偏离**，记录备查。

---

## 5. 复核结论

1. **实现与设计逐条一致，无实现偏离**：入口/schema/分派/落点/归属/path 语义/幂等/投影字段/空目录不谎报/错误语义/G2 可读/提示词/范围/阶段宽容/验收与类型面，共 **17/17 项**核对为一致，逐项附实测依据（§1 表）。
2. **卡面验收达标**：`design-registration + tools-schema + output-contract + tools-dispatch` = **4 文件 35/35 绿**（§2.1）；TC-1 首次 `registered_count=5`、二次 `=0`、空目录 `0 且 success=false`；`tsc` 新错误 = 0（总 23 = 基线，§2.2）。
3. **独立边界验证**（§2.3）确认缺省扫描 ≡ 扫 `design/`，并暴露 M-2 的隐藏/嵌套件口径差（边界、无闸门影响）。
4. 未发现阻断性偏离；`on_disk` 行集来源（O-2）、跨卡依赖（O-4）、mutate 复查（O-5）均为非偏离观察。
5. 本卡为 review 阶段：**只读复核 + 落本记录**；未修改任何实现或测试源码，本轮新增产物仅本文件（临时探针已删除，复核不存在）。

### 给父卡的行动建议（非阻断）

- M-1：`SubmitTool.ts` 的 `conditional` 输出 schema 补 `enum: ['frontend','backend']`（与 I-1 字段类型对齐）。
- M-2：`designDocNames` 与发现核心统一口径（点文件过滤；是否纳入嵌套件二选一并在 I-1 注明）。
- M-3：`tools-dispatch.test.ts` 注释改「五类」，`design` 加入分派表断言。
