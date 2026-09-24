# t-01bd5b 测试记录（父卡 t-7e9633 / T-4「投影逐份登记态到 reqboard_status」· 阶段 test）

- 测试时间：2026-09-25T00:08+0800
- 测试环境：node v22.23.2 · vitest 2.1.9（darwin-arm64）· 工作目录 `packages/web/dsh-pmboard`
- 被测对象（实现基线：工作区 HEAD `9e5ebf60` + 本需求未提交改动）：
  - `packages/web/dsh-pmboard/src/application/internal/design-docs.ts`（`designDocRegistration` / `designDocRegistrationOf`，sha256 前 16 位 `5748341840ef3886`）
  - `packages/web/dsh-pmboard/src/application/query/QueryState.ts`（`queryState` 调 `designDocRegistrationOf`，`e98306ee3fc42d50`）
  - `packages/web/dsh-pmboard/src/tools/StatusTool/StatusTool.ts`（零参入参 + 输出 schema 增 `design_docs[]`，`43797d32d8c9311d`）
  - 测试：`tests/tools-status.test.ts`（`22ff954b1ec755da`）/ `tests/design-registration.test.ts`（`45f9df11ffe803e8`）/ `tests/output-contract.test.ts`（`5160fe06463b8b62`）
- 测试结论：**目标命令全绿** —— 3 个测试文件 / 35 个用例全部通过，退出码 **0**。两条验收标准均满足。

---

## 1. 目标命令

```bash
cd packages/web/dsh-pmboard
npx vitest run tests/tools-status.test.ts tests/design-registration.test.ts tests/output-contract.test.ts
```

实际输出（摘要）：

```
 RUN  v2.1.9 /Users/yunpeng/pi-investment/agent-dh/packages/web/dsh-pmboard

 ✓ tests/tools-status.test.ts (7 tests) 28ms
 ✓ tests/output-contract.test.ts (19 tests) 115ms
 ✓ tests/design-registration.test.ts (9 tests) 126ms

 Test Files  3 passed (3)
      Tests  35 passed (35)
   Duration  631ms
```

- 退出码：**0**（全绿）—— 与验收「目标命令输出全绿」一致。

### 1.1 逐例结果（`--reporter=verbose`，35/35 全通过）

```
 ✓ tests/tools-status.test.ts > reqboard_status.next_actions（窗口可自行推进的动作） > brainstorming → design 已入人工门（五门裁定），agent 仅可退回 draft
 ✓ tests/tools-status.test.ts > reqboard_status.next_actions > draft → 提交评审；implementing → 进验收
 ✓ tests/tools-status.test.ts > reqboard_status.next_actions > 终态与未绑定窗口：无 next_actions
 ✓ tests/tools-status.test.ts > reqboard_status.design_docs（逐份登记态：磁盘 / 产物簿 / 确认章三源） > 未登记 / 待确认 / 已落章 / 缺失 四态逐份与磁盘+台账一致
 ✓ tests/tools-status.test.ts > reqboard_status.design_docs > front-matter：sides=frontend 出条件必交项，design_exempt 带豁免理由
 ✓ tests/tools-status.test.ts > reqboard_status.design_docs > 未绑定窗口 → design_docs 为空数组（不瞎报）
 ✓ tests/tools-status.test.ts > reqboard_status.design_docs > 未知/缺 category → 只报磁盘额外件，不瞎报必交清单
 ✓ tests/design-registration.test.ts > TC-1 正向：扫 design/ 登记 5 份，二次幂等 > 首次 registered_count=5 且 5 条 kind=design 入簿；二次 registered_count=0
 ✓ tests/design-registration.test.ts > TC-1 > 部分新增：已登记 5 份后再落盘第 6 份，registered_count 只数本次新增（=1）
 ✓ tests/design-registration.test.ts > TC-1 > 登记后 G2 读得到（不再 missing_artifact，转为待确认）
 ✓ tests/design-registration.test.ts > TC-19 前半 · 边界：空目录返回 0 且不谎报成功 > design/ 不存在 → registered_count=0、success=false、零产物入簿
 ✓ tests/design-registration.test.ts > TC-19 前半 > design/ 存在但只有非 .md → 同样 0 且不谎报
 ✓ tests/design-registration.test.ts > I-1 path 语义：单份登记 + 可打开性校验 > 给了 path 只登记该份
 ✓ tests/design-registration.test.ts > I-1 path 语义 > 伪路径（..）→ REQBOARD_ARTIFACT_NOT_OPENABLE
 ✓ tests/design-registration.test.ts > I-1 path 语义 > 文件不存在 → REQBOARD_FILE_MISSING
 ✓ tests/design-registration.test.ts > 归属校验 > 本窗口未绑定需求 → REQBOARD_NO_BOUND_REQ
 ✓ tests/output-contract.test.ts > 输出契约：返回字段 ⊆ output.schema 声明 > archive_submit（含 unlisted_files 警告路径）
 ✓ tests/output-contract.test.ts > 输出契约 > verify_submit（含 sheet 摘要路径）
 ✓ tests/output-contract.test.ts > 输出契约 > ask_confirm 成功路径（肯定项 → 落章 + 推进）
 ✓ tests/output-contract.test.ts > 输出契约 > ask_confirm 非肯定项（不推进）
 ✓ tests/output-contract.test.ts > 输出契约 > ask_confirm 弹框不可用（fallback=board）
 ✓ tests/output-contract.test.ts > 输出契约·静态扫描 > 扫描器覆盖全部工具文件，且至少发现 9 个工具工厂
 ✓ tests/output-contract.test.ts > 输出契约·静态扫描 > defineAcceptSheetTool：所有 return 分支键均已声明
 ✓ tests/output-contract.test.ts > 输出契约·静态扫描 > defineAdvanceTool：所有 return 分支键均已声明
 ✓ tests/output-contract.test.ts > 输出契约·静态扫描 > defineAskConfirmTool：所有 return 分支键均已声明
 ✓ tests/output-contract.test.ts > 输出契约·静态扫描 > defineCaptureTool：所有 return 分支键均已声明
 ✓ tests/output-contract.test.ts > 输出契约·静态扫描 > defineCreateTool：所有 return 分支键均已声明
 ✓ tests/output-contract.test.ts > 输出契约·静态扫描 > defineDecomposeTool：所有 return 分支键均已声明
 ✓ tests/output-contract.test.ts > 输出契约·静态扫描 > defineMoveTool：所有 return 分支键均已声明
 ✓ tests/output-contract.test.ts > 输出契约·静态扫描 > defineStatusTool：所有 return 分支键均已声明
 ✓ tests/output-contract.test.ts > 输出契约·静态扫描 > defineSubmitTool：所有 return 分支键均已声明
 ✓ tests/output-contract.test.ts > 输出契约·静态扫描 > defineTaskExecuteTool：所有 return 分支键均已声明
 ✓ tests/output-contract.test.ts > 输出契约·静态扫描 > defineTaskMoveTool：所有 return 分支键均已声明
 ✓ tests/output-contract.test.ts > 输出契约·静态扫描 > defineTaskReportTool：所有 return 分支键均已声明
 ✓ tests/output-contract.test.ts > 输出契约·静态扫描 > defineTaskStatusTool：所有 return 分支键均已声明
```

## 2. 验收标准 → 测试用例对照

| 验收标准（父卡 t-7e9633 产出） | 覆盖用例 | 结果 |
|---|---|---|
| 目标命令全绿 | 上述 3 文件 / 35 用例 | ✅ 35/35，exit 0 |
| `design_docs[]` 的 `on_disk`/`registered`/`confirmed` 三态与磁盘 + 台账逐份一致 | `tools-status.test.ts`「未登记 / 待确认 / 已落章 / 缺失 四态逐份与磁盘+台账一致」（architecture 磁盘有台账无=未登记；data-model 已登记未落章=待确认；interfaces 已登记且 confirmedAt=2=已落章；test-cases/use-cases 缺失仍逐份列出） | ✅ |
| 行集与顺序 = category 必交清单 | 同上用例断言 `map(name) === ['architecture.md','data-model.md','interfaces.md','test-cases.md','use-cases.md']` | ✅ |
| front-matter 策略（sides / design_exempt） | `tools-status.test.ts`「front-matter：sides=frontend 出条件必交项，design_exempt 带豁免理由」 | ✅ |
| 未绑定窗口不瞎报 | `tools-status.test.ts`「未绑定窗口 → design_docs 为空数组」 | ✅ |
| 未知/缺 category 边界 | `tools-status.test.ts`「未知/缺 category → 只报磁盘额外件」 | ✅ |
| 回归面（登记入口 I-1 未破） | `design-registration.test.ts` 9 例（正向幂等 / 边界 / path 语义 / 归属校验） | ✅ |
| 输出契约（`design_docs` 字段已声明） | `output-contract.test.ts` 19 例（含 `defineStatusTool` 全 return 分支键已声明） | ✅ |

## 3. 测试范围与改动

- 本卡为 **test 阶段**：只运行目标命令并将结果落入本记录，**未修改任何实现或测试源码**。
- 本轮新增产物仅本文件 `docs/requirements/REQ-260924213231-b1c4/evidence/t-01bd5b-test.md`。
- 被测实现基线为工作区未提交改动（`design-docs.ts` +85 / `QueryState.ts` +6 / `StatusTool.ts` +17 / `tools-status.test.ts` +107，共 4 文件 +213/-2），哈希见表头，供复核时对齐。

## 4. 结论

1. 目标命令 `npx vitest run tests/tools-status.test.ts tests/design-registration.test.ts tests/output-contract.test.ts`：**3 files / 35 tests 全绿，exit 0**。
2. `design_docs[]` 的 `on_disk`/`registered`/`confirmed` 三态（含缺失第四态）由 `tools-status.test.ts` 以独立临时工作区（磁盘 + 产物簿双可控）逐份断言，与磁盘 + 台账一致。
3. 回归面无失败：登记入口（I-1）9 例、输出契约 19 例、`next_actions` 既有 3 例全部通过。
