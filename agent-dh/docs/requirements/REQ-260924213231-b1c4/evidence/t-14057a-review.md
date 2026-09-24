# t-14057a 复核记录（父卡 t-7e9633 / T-4「投影逐份登记态到 reqboard_status」· 阶段 review）

- 复核时间：2026-09-25T≈00:07+0800（本轮执行内）
- 复核环境：node v22.23.2 · vitest 2.1.9（darwin-arm64）· HEAD `9e5ebf60`
- 复核对象：T-4 实现三文件 + 回归测试
  - `packages/web/dsh-pmboard/src/application/internal/design-docs.ts`（`designDocRegistration` / `designDocRegistrationOf` / `designDocNamesOf`）
  - `packages/web/dsh-pmboard/src/application/query/QueryState.ts`（`design_docs` 投影）
  - `packages/web/dsh-pmboard/src/tools/StatusTool/StatusTool.ts`（输出 schema 增 `design_docs[]`）
  - `packages/web/dsh-pmboard/tests/tools-status.test.ts`（I-2 三态断言，新增 describe）
- 设计依据（比对基线）：`design/interfaces.md` §I-1 字段明细 / §I-2、`design/architecture.md`（L42/L44/L76/L98/L99）、`design/data-model.md`（L31/L32/L78）、`design/test-cases.md`（TC-1/TC-19 与落点表）、任务卡 `tasks/t-7e9633.md` 验收标准
- 复核方式：读 `git diff` 逐点比对设计契约 + 独立复跑父卡验收命令与相关回归（不采信上游自述）

---

## 1. 逐条复核结论（设计与实现）

| 编号 | 设计点（出处） | 实现 | 结论 |
|---|---|---|---|
| R1 | `design_docs[]` 字段集：`name`/`path`/`on_disk`/`registered`/`confirmed` 必填，`exempted?`/`conditional?` 可选（interfaces.md §I-1 字段表 / data-model.md:32） | `designDocRegistration` 逐行产出同名同型字段；`protocol.ts` `DesignDocRegistration` 与工具 schema 一致（`additionalProperties:false`） | **无偏离**。依据：design-docs.ts:92-100、protocol.ts:441-456、StatusTool.ts:67-83；`contract-shapes.test.ts`（8/8）锁定字段与类型。 |
| R2 | 三源合成：`on_disk`=目录扫描命中；`registered`=产物簿有该份（kind=design 且 path 命中）；`confirmed`=`confirmedAt !== undefined`（interfaces.md §I-1 / architecture.md:99） | 逐行 `disk.has(name)` / `artifacts.find(kind==='design' && path.endsWith('/design/'+name))` / `art?.confirmedAt !== undefined` | **无偏离**。依据：design-docs.ts:87-101；`tools-status.test.ts`「未登记/待确认/已落章/缺失 四态」逐份断言（L111-131）。 |
| R3 | 行集 = 该类型要求的设计文档（含条件必交、含缺失项）∪ 磁盘实际 `.md`（含清单外额外件）；必交在前、额外件在后、去重（architecture.md:99、design-docs 头注） | `effectiveDesignDocs(category, policy.sides)` 先 `collect`，再遍历 `onDisk` `collect`；`seen` 去重 | **无偏离**。依据：design-docs.ts:102-105；测试断言顺序 = `FEATURE_DESIGN5`（tools-status.test.ts:121）、额外件用例（L147-151）。 |
| R4 | I-2：未绑定窗口 `design_docs` 为空数组（不瞎报）（interfaces.md §I-2 兼容性 / TC-19 语义） | `let design_docs = []`，仅 `open.length > 0` 时赋值 `open[0]` | **无偏离**。依据：QueryState.ts:31-34、:53-59；测试 L143-145。 |
| R5 | front-matter 策略：`sides` 声明才出条件必交并带 `conditional`；`design_exempt` 理由非空才带 `exempted`（空理由不算有效豁免）（interfaces.md §I-1 / category-doc-sets） | `conditional` 由 `effectiveDesignDocs` 按 sides 命中生成；`exempted` 仅当 `reason.trim() !== ''` 才附加 | **无偏离**。依据：design-docs.ts:91-99、:103；测试 L133-141（frontend 条件项 / 无 backend 行 / exempted 理由）。 |
| R6 | 未知/缺 `category` → 必交清单为空，只报磁盘额外件（不瞎报必交） | `effectiveDesignDocs` 对未知 category 返回 `[]`，`onDisk` 额外件仍逐份列出 | **无偏离**。依据：category-doc-sets.ts:85-86、design-docs.ts:103-104；测试 L147-151（仅 `extra.md`）。 |
| R7 | application 不碰 fs（INV-7）：`designDocRegistration` 为纯函数；扫描/读策略走端口（design-docs 头注 / architecture.md:99） | `designDocRegistration` 无 I/O；`designDocRegistrationOf` 只收 `DesignDocScanPort`（exists/read/list），由 QueryState 传 `deps.docs` | **无偏离**。依据：design-docs.ts:76-105（纯合成）、:112-140（端口版）；T-4 未新增 `application/**` 对 node:/adapters 的越界 import（见 §3 基线红说明）。 |
| R8 | I-1 与 I-2 **共用同一份三源合成规则与扫描口径**，不存在「两套真相」（architecture.md:99 / design-docs.ts:129-130） | QueryState 经 `designDocRegistrationOf`；SubmitDesignArtifacts 直接调 `designDocRegistration`（同一合成规则）。扫描口径两端均为「`list(design/)` + `isFile !== false` + `.md` + 非空名」 | **无偏离（合成规则同源）**；口径一致但见观察项 O-2（谓词两处同构未复用，非行为差异）。 |
| R9 | 工具壳：`reqboard_status` 输出 schema 增 `design_docs[]`，既有键只增不改；零参 `parameters: {}`（interfaces.md §I-2 / T-7） | schema `properties.design_docs` 为数组、items 显式 `additionalProperties:false`；`parameters: {}` | **无偏离**。依据：StatusTool.ts:21、:67-83；`tools-schema.test.ts` 3/3 绿、`output-contract.test.ts` 19/19 绿（return 键全部已声明）。 |
| R10 | I-2 输出含 `interruption?`（interfaces.md §I-2） | T-4 未产出 `interruption` | **不判偏离**：`interruption` 属 FR-6 / T-9（`interruption.ts` / CaptureHook / node-input-package）落点，不在 T-4 卡范围（任务卡验收只涉 `design_docs[]`）；T-9 尚未合入时该键缺失是预期状态。 |
| R11 | 父卡验收：3 测试文件全绿且三态与磁盘+台账逐份一致（tasks/t-7e9633.md） | 独立复跑 | **无偏离**，见 §3 证据。 |

---

## 2. 偏离与观察项

**未发现阻塞性（行为）偏离。** 以下为轻微观察项，均无当前行为影响，供后续可选加固：

- **O-1（注释口径，非行为偏离）**：`registered` 匹配只校验 `kind === 'design'`，未校验 `stage === 'design'`；而 `protocol.ts:448` 注释写「stage=design 且 kind=design」。**可执行契约 interfaces.md §I-1 只写 `kind=design`**，故以设计契约为准**无偏离**。当前数据模型下 stage 与 kind 恒同时出现（`SubmitDesignArtifacts` 与 `ArtifactSync` 均同时写两者；`artifact-gates.registerArtifact` 判重键为 stage+kind+path），无实际差异。可选：把 `a.kind === 'design'` 收紧为 `a.stage === 'design' && a.kind === 'design'`，或与注释统一。
- **O-2（轻微实现偏离，非行为差异）**：扫描谓词存在两处同构实现——`SubmitDesignArtifacts.designDocNames`（T-3）与 `design-docs.designDocNamesOf`（T-4）。设计措辞要求「同一扫描口径」，两者谓词逐字等价（`list` + `isFile !== false` + `.md` + 非空名），当前无漂移；但两处并存有后续漂移风险。可选：让 `SubmitDesignArtifacts` 复用 `designDocNamesOf`。
- **O-3（文档痕迹，非实现偏离）**：`design/test-cases.md` 的落点表未为 I-2 / `design_docs` 单列 TC 编号，其四态断言落在 `tests/tools-status.test.ts`（T-4 卡验收指定文件）。不影响可证伪性，仅追溯编号可更显式。

---

## 3. 独立复核证据（命令 + 输出摘要）

### 3.1 父卡验收命令（复跑，与上游自述一致）

```bash
cd packages/web/dsh-pmboard
npx vitest run tests/tools-status.test.ts tests/design-registration.test.ts tests/output-contract.test.ts
```

实际输出：

```
 ✓ tests/tools-status.test.ts (7 tests) 25ms
 ✓ tests/output-contract.test.ts (19 tests) 128ms
 ✓ tests/design-registration.test.ts (9 tests) 133ms

 Test Files  3 passed (3)
      Tests  35 passed (35)
```

判定：**3/3 文件、35/35 用例通过，退出码 0** —— 与父卡验收期望一致。

### 3.2 相关回归（扩大抽样）

```bash
npx vitest run tests/contract-shapes.test.ts tests/tools-schema.test.ts tests/sync-artifacts.test.ts tests/layer-boundary.test.ts
```

- `contract-shapes.test.ts` 8/8 绿（I-1 `design_docs[]` 字段/类型契约锁定）
- `tools-schema.test.ts` 3/3 绿（新增 schema 通过 DSL 校验）
- `sync-artifacts.test.ts` 11/11 绿（T-2 发现核心未被 T-4 触碰）
- `layer-boundary.test.ts` **1 红**：`application/internal/diag-log.ts -> node:path`。
  **判定为基线既有、与 T-4 无关**：`diag-log.ts` 不在本卡/本需求的改动清单，`git diff --quiet -- src/application/internal/diag-log.ts` 退出 0（未修改），其最近提交为 `c90788b4`（T-4 之前）。T-4 新增代码只 import `application/internal`、`application/ports`、`shared/protocol`，未新增越界。

### 3.3 diff 性质确认

`git diff` 显示 T-4 三源码改动均为**纯新增、不动既有分支**：
- `design-docs.ts`：追加 `designDocRegistration` / `DesignDocScanPort` / `designDocNamesOf` / `designDocRegistrationOf`，`designDocStatus`（设计节点展示用）逐字未改；
- `QueryState.ts`：新增 `design_docs` 局部变量与返回键，其余 return 键与文案不变；
- `StatusTool.ts`：schema `properties` 新增 `design_docs`，既有键未改。

---

## 4. 结论

1. T-4 实现与 `interfaces.md` §I-1/§I-2、`architecture.md`、`data-model.md` 的契约**逐条一致，无行为偏离**（R1–R9、R11 均「无偏离」并给出依据；R10 属 FR-6/T-9 范围不判）。
2. 父卡验收命令独立复跑 **35/35 全绿**；相关回归除 `layer-boundary.test.ts` 一处**基线既有红**（`diag-log.ts`，与本卡无关）外均绿。
3. 遗留 2 项轻微观察项（O-1 注释/校验宽度、O-2 扫描谓词重复）+ 1 项文档痕迹（O-3），均无当前行为影响，**不阻塞**。
4. **复核结论：通过（T-4 可进入收尾）**。
