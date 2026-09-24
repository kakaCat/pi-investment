# t-5a41f7 测试记录（父卡 t-145cb0 / T-13「迁移兼容卡与 E2E 复跑」· 阶段 test）

- 测试时间：2026-09-25T02:19+0800（本轮执行内）
- 测试环境：node v22.23.2 · vitest 2.1.9（darwin-arm64）· 仓库工作目录 `agent-dh`，测试工作目录 `packages/web/dsh-pmboard`；HEAD = `9e5ebf60`（branch `main`）
- 被测对象（T-13 交付物 = 新增 E2E `packages/web/dsh-pmboard/tests/e2e-design-handoff.test.ts`（**untracked**，264 行，头部 `// serves: FR-1`）+ 回归 `tests/migration.test.ts`（147 行，工作区未改动）；实现均为工作区未提交状态，本卡只跑不改）
- 测试结论：**目标命令全绿** —— `npx vitest run tests/e2e-design-handoff.test.ts tests/migration.test.ts tests/consistency.test.ts` → **3 files / 25 tests 通过，exit 0**。E2E 一次通过且全程无 `REQBOARD_MISSING_ARTIFACT`；legacy（`artifacts` 空）需求仍放行（e2e 第 5 例）。验收标准「目标命令输出全绿」达成。

---

## 1. 目标命令（父卡 t-145cb0 验收第 1 项）

```bash
cd packages/web/dsh-pmboard
npx vitest run tests/e2e-design-handoff.test.ts tests/migration.test.ts tests/consistency.test.ts
```

实际输出（摘要）：

```
 RUN  v2.1.9 /Users/yunpeng/pi-investment/agent-dh/packages/web/dsh-pmboard

 ✓ tests/consistency.test.ts (11 tests) 3ms
 ✓ tests/migration.test.ts (9 tests) 33ms
 ✓ tests/e2e-design-handoff.test.ts (5 tests) 86ms

 Test Files  3 passed (3)
      Tests  25 passed (25)
   Start at  02:19:24
   Duration  557ms (transform 287ms, setup 0ms, collect 427ms, tests 123ms, environment 0ms, prepare 106ms)
```

- 退出码：**0**（全绿）
- 判定：与父卡任务卡 `tasks/t-145cb0.md` 验收命令「`npx vitest run tests/e2e-design-handoff.test.ts tests/migration.test.ts tests/consistency.test.ts` 全绿」逐字一致。

## 2. E2E 逐例（`e2e-design-handoff.test.ts` = TC-19，5 例）

| # | 用例 | 复跑结果 |
|---|---|---|
| 1 | 登记前 `move` 仍被产物存在门拦：`REQBOARD_MISSING_ARTIFACT`（修的是入口，不是闸门） | ✅ |
| 2 | 登记 ≠ 落章：submit 后未确认时 move 报 `REQBOARD_ARTIFACT_NOT_CONFIRMED`（两态文案分叉） | ✅ |
| 3 | 一次通过（A1）：`submit(kind=design)` → `ask_confirm`（默认自动推进）→ 需求直接进入 `decomposing`，全程无 `REQBOARD_MISSING_ARTIFACT` | ✅ |
| 4 | 字面三步链（卡面顺序）：落盘 5 份 → `submit(design)` → `ask_confirm(advance:false)` → `move(decomposing)` 一次通过 | ✅ |
| 5 | 迁移兼容：legacy（`artifacts: undefined`）存量需求 `design→decomposing` 仍放行，不要求登记/确认（产物簿保持 0 条，放行不等于伪造） | ✅ |

- 第 3 例核心断言：`registered_count===5`、`design_docs` 长 5 且逐份 `on_disk=true/registered=true/confirmed=false`、`ask.confirmed=true`+`advanced=true`+`to='decomposing'`、5 条 `design` 产物 `confirmedAt` 非空、需求终态 `status='decomposing'`；`t.asked` 长度 1（证明确实走弹框路径而非文字证据路径）——**一次通过，无 `REQBOARD_MISSING_ARTIFACT`**（A1 达成）。

## 3. 兼容边界回归（卡面 implementation 括注的两件事的**真实落点**）

卡面括注写「回归 `migration.test.ts`（legacy 放行、老需求无 interruption 逐字节兼容）」；**实测该文件只覆盖账本 v4→v7 迁移**（真实样本无损 + 白名单外 0 条、幂等、C3/C4/C6/C7/C8/C9/C10 逐项语义，9 例全绿），并不含这两条断言。两条兼容边界的真实用例落点如下（复核记录 `evidence/t-55b8c4-review.md` §D-1 已确认，属**口径性偏差、功能覆盖无缺口**）：

| 兼容边界 | 真实用例落点 | 复跑结果 |
|---|---|---|
| legacy（`artifacts` 空）需求仍放行 | `tests/e2e-design-handoff.test.ts` 第 5 例 | ✅（含在上文 5/5） |
| 老需求无 `interruption` → 输入包逐字节不变 | `tests/interruption-checkpoint.test.ts` > 「续跑输入包（## 断点 节） > 老需求无字段 → 输入包逐字节不变（不出现断点节，段间分隔与改造前一致）」 | ✅ |
| 迁移不凭空注入 `interruption` | `tests/migration.test.ts` 第 2 例「差异路径全部落在白名单内」——若迁移注入该字段即判白名单外差异而红 | ✅（含在上文 9/9） |

补充命令：

```bash
cd packages/web/dsh-pmboard
npx vitest run tests/interruption-checkpoint.test.ts
```

```
 ✓ tests/interruption-checkpoint.test.ts (15 tests) 7ms

 Test Files  1 passed (1)
      Tests  15 passed (15)
```

- 退出码：**0**。该文件为 T-9 产物（TC-16 承接「老需求无 interruption 逐字节」），非本卡改动，仅作兼容边界佐证。

## 4. 全量复跑与基线对照（父卡验收第 4 项，非本子卡验收命令，如实记录）

```bash
cd packages/web/dsh-pmboard
npx vitest run
```

实际输出摘要：

```
 ❯ tests/client-view.test.ts (50 tests | 1 failed)
 ❯ tests/template-address-injection.test.ts (10 tests | 2 failed)
 ❯ tests/layer-boundary.test.ts (9 tests | 1 failed)
 ❯ tests/application/repository.test.ts (13 tests | 1 failed)
 ❯ tests/language-layer.test.ts (7 tests | 1 failed)
 ❯ tests/typecheck.test.ts (2 tests | 1 failed)

 Test Files  6 failed | 152 passed (158)
      Tests  7 failed | 1856 passed (1863)
exit 1
```

- 基线（`decomposition.md` §D-1）：`main` 上 **7 文件 / 9 用例失败**（design-completeness-gate 2、size-budget 1、typecheck 1、template-address-injection 2、layer-boundary 1、client-view 1、repository 1）。
- 本轮 **6 文件 / 7 用例**：`design-completeness-gate`（2）与 `size-budget`（1）转绿（净 −3），新增红 `tests/language-layer.test.ts`（1）——失败集 **未** 满足「⊆ 基线且不新增失败」。
- 归因：`language-layer.test.ts:62` 断言「每节**必须**标注服务哪条功能点」，而当前分片 `src/domain/prompt/fragments/design/light/overrides.md` 文本为「每节**标注**服务哪条功能点」——该测试文件本轮 `git status` 干净，分片与 `generated/fragments.ts` 属 **T-8/FR-5** 改动范围。与复核记录 `t-55b8c4-review.md` §D-2、以及 T-8 链上既有记录（`t-3d59ae-review.md` §O-4、`t-6a3070-integrate.md` §O-2、`t-87ca1c-integrate.md` §5-F-1）一致，**非 T-13 两文件致红**（e2e/migration 均不触碰提示词与 `language-layer`）。
- 本卡范围与结论：T-13 子卡验收（目标命令全绿）**已达成**；父卡第 4 项须待 T-8 收口后方可复验，不属本卡可处置范围（未扩大范围）。

## 5. 改动归属（本卡未改任何源码/用例）

```bash
git status --porcelain packages/web/dsh-pmboard/tests/e2e-design-handoff.test.ts \
  packages/web/dsh-pmboard/tests/migration.test.ts \
  packages/web/dsh-pmboard/tests/consistency.test.ts \
  packages/web/dsh-pmboard/tests/interruption-checkpoint.test.ts
```

```
?? agent-dh/packages/web/dsh-pmboard/tests/e2e-design-handoff.test.ts
?? agent-dh/packages/web/dsh-pmboard/tests/interruption-checkpoint.test.ts
```

- `e2e-design-handoff.test.ts`（T-13）与 `interruption-checkpoint.test.ts`（T-9）为 **untracked 新增**；`migration.test.ts` / `consistency.test.ts` HEAD 上已跟踪且**未改动**（回归口径成立）。
- 以上均为上游卡（T-13 implement / T-9）的待提交工作区改动；本卡（test 阶段）**只跑不改**，本轮新增产物仅本证据文件 `docs/requirements/REQ-260924213231-b1c4/evidence/t-5a41f7-test.md`。

## 6. 测试结论

1. 目标命令 `npx vitest run tests/e2e-design-handoff.test.ts tests/migration.test.ts tests/consistency.test.ts`：**3 files / 25 tests 全绿，exit 0** —— 验收标准「目标命令输出全绿」达成。
2. E2E（TC-19）5 例全绿：`submit(design) → ask_confirm → move(decomposing)` 一次通过、全程无 `REQBOARD_MISSING_ARTIFACT`；两态错误码分叉与 legacy 放行同时锁定。
3. 兼容边界有据：legacy 放行由 e2e 第 5 例锁定，「老需求无 interruption 输入包逐字节不变」由 `interruption-checkpoint.test.ts`（15/15 绿）锁定，「迁移不注入 interruption」由 `migration.test.ts` 白名单用例锁定。
4. 全量失败集未达成父卡第 4 项（新增红 `language-layer.test.ts`，归 T-8，非本卡致红），已如实记录并交由父卡转 T-8 收口。
