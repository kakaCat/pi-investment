# t-55b8c4 复核记录（父卡 t-145cb0 / T-13「迁移兼容卡与 E2E 复跑」· 阶段 review）

- 复核时间：2026-09-25T02:20+0800
- 复核人：T-13 review 子卡（本窗口）
- 复核对象：T-13 交付物 = 新增 `packages/web/dsh-pmboard/tests/e2e-design-handoff.test.ts` + 回归 `packages/web/dsh-pmboard/tests/migration.test.ts`
- 对照基线（设计侧）：`requirement.md`（A1/§8/§10）、`design/use-cases.md`（UC-1/UC-2）、`design/interfaces.md`（I-1/I-3/I-9、E-7/E-8）、`design/test-cases.md`（TC-19、落点表）、`decomposition.md`（T-13 行 + D-1 基线缺口 + 测试文件落点）、`tasks/t-145cb0.md`（卡面验收）
- 判定口径：逐条给「偏离 / 无偏离」结论；「无偏离」必须附实现事实与依据；偏离按「功能性（影响验收）」与「口径性（不影响行为）」分类。

---

## 1. 逐条复核结论（设计 → 实现）

| # | 设计/计划依据 | 实现事实（本轮独立核实） | 结论 |
|---|---|---|---|
| 1 | `design/test-cases.md` L116「TC-19(E2E) → `tests/e2e-design-handoff.test.ts`（T-13）」；`decomposition.md` L176 同 | 文件存在（264 行，mtime 2026-09-25 02:09），未跟踪新文件；头部 L1 `// serves: FR-1`，L3 标注「T-13 · serves: FR-1 · test-cases.md TC-19」 | **无偏离** |
| 2 | `design/test-cases.md` L106「TC-1, TC-19 → `design-registration.test.ts`」+ L116「TC-19(E2E) → e2e 文件」；`decomposition.md` L166「TC-1, TC-19(前半) → design-registration」 | `design-registration.test.ts:119` 有 `TC-19 前半 · 边界：空目录返回 0 且不谎报成功`；e2e 文件承担 TC-19 全链路。两文件分工与设计一致 | **无偏离** |
| 3 | `test-cases.md` TC-19 步骤：落盘 5 份 design → `reqboard_submit(kind=design)` → `reqboard_ask_confirm(kind=design)` → `reqboard_move(to=decomposing)` | e2e 第 3 例（自动推进链）与第 4 例（字面三步链 `advance:false` + 显式 move）各跑一遍；第 4 例逐字对齐卡面顺序 | **无偏离** |
| 4 | A1/UC-1「全程不出现 `REQBOARD_MISSING_ARTIFACT`，move 一次通过」 | happy path 以 `reg.success / ask.confirmed+advanced / to='decomposing' / status='decomposing'` 断言通过（无抛错即无该码）；另有反例第 1 例断言「文档已落盘但未登记」时仍抛 `REQBOARD_MISSING_ARTIFACT`——证明修的是入口、不是闸门（NFR-2 护栏不降） | **无偏离** |
| 5 | `interfaces.md` I-1 字段明细：`design_docs[].on_disk/registered/confirmed`、`registered_count`（幂等命中不计数） | 第 3 例断言 `registered_count===5`、`design_docs` 长度 5、逐份 `on_disk=true, registered=true, confirmed=false`；落章后逐份 `confirmedAt` 非空 | **无偏离** |
| 6 | `interfaces.md` I-3 / UC-1 步骤 2-3 / FR-3「宽限内作答与原语义逐字一致」 | 第 3 例断言 `confirmed=true, advanced=true, to='decomposing'`；第 4 例 `advance:false` → `advanced=false` 且 status 仍 `design`，推进交给显式 move（与 I-3「同 ask_confirm 语义」一致） | **无偏离** |
| 7 | `interfaces.md` E-7（未登记→`REQBOARD_MISSING_ARTIFACT`）与 E-8（已登记未落章→`REQBOARD_ARTIFACT_NOT_CONFIRMED`）两态分叉 | e2e 第 1/2 例分别断言两码；实现侧 `MoveRequirement.ts:93` 按 `gateFailure.code==='artifact_not_confirmed'` 分派两码，与设计同源 | **无偏离** |
| 8 | `requirement.md` §8 / `interfaces.md` 兼容性矩阵「存量需求（artifacts 空/undefined）继续放行，不追溯拦下」 | e2e 第 5 例：`artifacts: undefined` 的需求 `design→decomposing` move 成功，且断言产物簿仍为 0 条（放行不等于伪造） | **无偏离** |
| 9 | `test-cases.md` L9 铁律「落点表列出的每个文件，头部 20 行内必须带 `// serves: FR-x`」 | e2e 文件 L1 即 `// serves: FR-1`，命中 test-cases 落点表 | **无偏离** |
| 10 | `architecture.md` 研发规范：单文件 ≤400 行、application 不 import adapters/node:（`size-budget`/`layer-boundary` 门禁） | `wc -l` → 264 行 < 400；新文件位于 `tests/`，不新增 application 层越界 | **无偏离** |
| 11 | `decomposition.md` T-13 落点含 `migration.test.ts`，措辞为「**回归**」（未列入新增） | `git status --porcelain` 未列该文件（未改动，mtime 2026-09-21 21:50 保持不变）；本轮复跑 9 例全绿 | **无偏离（回归口径成立）** |
| 12 | 卡面 `implementation` 括注：`migration.test.ts`（legacy 放行、老需求无 interruption 逐字节兼容） | 该文件实际内容是**账本 v4→v7 迁移回归**（真实样本无损 + 白名单外 0 条、幂等、C3/C4/C6/C7/C8/C9/C10），**不含** legacy 门禁放行断言，也**不含** interruption 输入包逐字节断言 | **偏离（口径性，见 D-1）** |
| 13 | T-13 卡面 acceptance 第 4 项：「`npx vitest run` 失败集合 ⊆ 基线且不新增失败」 | 独立全量复跑：`Test Files 6 failed | 152 passed (158)`、`Tests 7 failed | 1856 passed (1863)`、`EXIT=1`；其中 `tests/language-layer.test.ts` **不在 D-1 基线表**（新增红） | **偏离（功能性，阻塞父卡验收，见 D-2）** |

---

## 2. 偏离条目（逐条）

### D-1（口径性，不改变覆盖）· 卡面把 `migration.test.ts` 的覆盖范围写宽了

- **设计侧真实口径**：`decomposition.md` 落点表 L176 把 TC-19(E2E) 明确归 `e2e-design-handoff.test.ts`（T-13）；
  TC-16（老需求无 interruption → 输入包逐字节不变）归 `interruption-checkpoint.test.ts`（T-9，见 L172）。
  `migration.test.ts` 在计划里只作为「迁移兼容」回归项，未绑定任何 TC。
- **实现事实**：
  - `migration.test.ts`（127 行）= `migrate/diffPaths/checkWhitelist` 三函数测试，无 `move`/`ask_confirm`/`buildNodeInputPackage` 调用（`grep -c serves` → 0）；
    它只能**间接**守住「迁移不注入 `interruption`」——若迁移凭空注入该字段，`WHITELIST`（`scripts/migrate-ledger.ts:132-140`，只放行 status/statusHistory/category/projectId/parentId/artifacts/sheet source/scope/dependsOn）会把它判为白名单外差异，第 2 例立即红。
  - 「legacy（artifacts 空）放行」的实现断言在 `e2e-design-handoff.test.ts` 第 5 例；
    「老需求无 interruption 输入包逐字节不变」的实现断言在 `interruption-checkpoint.test.ts`（TC-16，T-9 产物，本轮不在本卡范围）。
- **影响**：无功能缺口——四项兼容边界（迁移无损 / 不注入 interruption / legacy 放行 / 输入包逐字节）均有用例覆盖，且本轮全绿。
  但卡面文字会让后续读者以为 `migration.test.ts` 覆盖了它并不覆盖的两件事，属**文档口径偏差**。
- **建议**：父卡/T-13 测试卡把括注改为「回归 `migration.test.ts`（账本 v4→v7 迁移无损）；legacy 放行与无 interruption 逐字节分别由
  `e2e-design-handoff.test.ts` 第 5 例与 `interruption-checkpoint.test.ts`（T-9/TC-16）承接」。本卡只记录，不改卡。

### D-2（功能性，阻塞 T-13 验收）· 全量失败集合新增 `tests/language-layer.test.ts`

- **设计口径**：`decomposition.md` D-1 载明 `main` 基线 = **7 文件 / 9 用例失败**（design-completeness-gate 2、size-budget 1、
  typecheck 1、template-address-injection 2、layer-boundary 1、client-view 1、repository 1），T-13 验收要求「失败集合 ⊆ 基线且不新增失败」。
- **本轮独立复跑事实**（`npx vitest run`，`EXIT=1`）：
  `Test Files 6 failed | 152 passed (158)`、`Tests 7 failed | 1856 passed (1863)`；失败文件集合 =
  `application/repository.test.ts`、`client-view.test.ts`、`language-layer.test.ts`、`layer-boundary.test.ts`、
  `template-address-injection.test.ts`（2 例）、`typecheck.test.ts`。
  - 净转绿：`design-completeness-gate.test.ts`（基线 2 例）、`size-budget.test.ts`（基线 1 例）→ 失败 9→7、文件 7→6。
  - **新增红**：`language-layer.test.ts:62` 断言 `toContain('每节必须标注服务哪条功能点')` 失败；当前分片
    `src/domain/prompt/fragments/design/light/overrides.md` 文本为「每节**标注**服务哪条功能点」，
    `generated/fragments.ts` 中旧短语出现次数 = 0。该测试文件本轮 `git status` 干净（未改动），
    而分片与生成物均为本次需求修改（T-8/FR-5）→ 归因 **T-8**，非 T-13 两文件。
- **影响**：T-13 验收第 4 项**未达成**。T-13 两文件本身无致红证据（`e2e-design-handoff.test.ts` / `migration.test.ts` 均不触碰提示词与 `language-layer`）。
- **建议**：由 T-8（或其复核卡）收口——对齐断言到新措辞，或保留「必须」并同步重生成 `generated/fragments.ts` + P1 基线；
  收口后 T-13 该验收项方可判定通过。与 T-8 链上既有记录一致（`t-3d59ae-review.md` §O-4、`t-6a3070-integrate.md` §O-2、`t-87ca1c-integrate.md` §5-F-1）。

---

## 3. 观察项（非偏离，不阻塞本卡）

- **O-1 `tsc` 24 条 vs 基线 23**：多出的 1 条为 `tests/ask-confirm-pending.test.ts(55,36): TS2322`（T-6 引入），
  T-13 两文件命中 0 条（`npx tsc --noEmit` 输出按文件计数）。不改变测试失败集合（`typecheck.test.ts` 基线本就红）。
- **O-2 未跟踪残留**：`packages/web/dsh-pmboard/tmp-integrate-probe.ts` 仍在包根（T-8 integrate 卡探针，未删）；
  非本卡产物，本轮未处置，报父卡。
- **O-3 E2E 保真边界（说明）**：e2e 走「真实工具壳（`defineSubmitTool/defineAskConfirmTool/defineMoveTool`）+ 真实适配器
  （`JsonLedgerRepository`/`FileDocRepository`/`UserQuestionsAdapter`）+ 临时目录」，不经过插件组合根 `src/index.ts` 与 HTTP 渲染路径。
  设计与 requirement §10 对该层级的措辞是「脚本复跑 REQ-2cd3 设计阶段」，未要求组合根/HTTP 级 E2E，故**不构成偏离**；
  仅提示：FR-3 的「非阻塞投递 + 回执」真实链路不在本文件覆盖（由 `ask-confirm-pending.test.ts` 承接，TC-5~8/20）。

---

## 4. T-13 卡面验收逐条对照

| 验收项 | 结果 | 证据 |
|---|---|---|
| `npx vitest run tests/e2e-design-handoff.test.ts tests/migration.test.ts tests/consistency.test.ts` 全绿 | ✅ | 独立复跑：`3 passed (3)` / `25 passed (25)` / `EXIT=0`（e2e 5 + migration 9 + consistency 11） |
| E2E 一次通过且全程无 `REQBOARD_MISSING_ARTIFACT` | ✅ | e2e 第 3 例成功链 + 第 4 例字面三步链；第 1 例为反例（未登记时仍拦该码） |
| legacy（artifacts 空）需求仍放行 | ✅ | e2e 第 5 例（`artifacts: undefined` → move 成功，产物簿 0 条） |
| `npx vitest run` 失败集合 ⊆ 基线且不新增失败 | ❌ | 新增红 `tests/language-layer.test.ts`（归 T-8），见 D-2 |

---

## 5. 复核命令与输出摘要（本轮独立复现）

```
$ cd packages/web/dsh-pmboard
$ npx vitest run tests/e2e-design-handoff.test.ts tests/migration.test.ts tests/consistency.test.ts
 ✓ tests/consistency.test.ts (11 tests) 3ms
 ✓ tests/migration.test.ts (9 tests) 32ms
 ✓ tests/e2e-design-handoff.test.ts (5 tests) 83ms
 Test Files  3 passed (3)
      Tests  25 passed (25)
EXIT=0

$ npx vitest run            # 全量，独立复跑
 Test Files  6 failed | 152 passed (158)
      Tests  7 failed | 1856 passed (1863)
EXIT=1
FAIL tests/language-layer.test.ts > 语言强度按层真的注入了吗（端到端） > design/light/feature 注入「章节可追溯」与「语言强度按层」
  ❯ tests/language-layer.test.ts:62:15  （期望含「每节必须标注服务哪条功能点」）

$ git status --porcelain packages/web/dsh-pmboard/tests/{language-layer,e2e-design-handoff,migration}.test.ts
?? agent-dh/packages/web/dsh-pmboard/tests/e2e-design-handoff.test.ts   # migration/language-layer 无标记 = 未改动
$ wc -l tests/e2e-design-handoff.test.ts   → 264
$ grep -c '每节必须标注服务哪条功能点' src/domain/prompt/generated/fragments.ts   → 0
```

---

## 6. 结论

1. **设计与实现的偏离共 2 条**：D-1（口径性，卡面把 `migration.test.ts` 覆盖范围写宽；功能覆盖无缺口）、
   D-2（功能性，全量失败集合新增 `language-layer.test.ts`，归 T-8，阻塞 T-13 第 4 项验收）。
2. **其余 11 条复核项均「无偏离」**：文件落点、TC-19 步骤、逐份登记态字段、两态错误码、legacy 放行、serves 头注、
   尺寸/分层规范、`migration.test.ts` 未改动的回归口径，逐条附实现事实。
3. **T-13 卡面验收 4 项：3 ✅ / 1 ❌**（全量失败集合一项未达成）。建议父卡：D-2 转 T-8 收口后复验该一项；
   D-1 由父卡决定是否修订卡面文字（不影响交付）。
