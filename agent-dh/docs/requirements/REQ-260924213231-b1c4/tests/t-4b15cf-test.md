# t-4b15cf 测试记录（父卡 t-6eca2a / T-3「新增 kind=design 登记用例与工具入口」· 阶段 test）

- 测试时间：2026-09-24T23:56+0800（本卡为 t-4b15cf 的**重跑**：前次 workflow run 被 cancel，本轮重跑目标命令）
- 测试环境：node v22.23.2 · vitest 2.1.9（darwin-arm64）· 仓库工作目录 `agent-dh`，测试工作目录 `packages/web/dsh-pmboard`；HEAD = `9e5ebf60`（branch `main`）
- 被测对象（FR-1；实现改动为工作区未提交状态，本卡只读不改）：
  - **I-1** `SubmitDesignArtifacts` —— `packages/web/dsh-pmboard/src/application/use-cases/SubmitDesignArtifacts.ts`（新增，untracked）：扫描 `design/*.md`、逐份登记 kind=design 产物、幂等
  - **I-1 入口** `defineSubmitTool` 的 `kind=design` 分派 + schema —— `packages/web/dsh-pmboard/src/tools/SubmitTool/SubmitTool.ts`（工作区修改 +27/−6：`SUBMIT_KINDS` 增 design、分派、输出 schema）
  - **I-7 提示词** —— `packages/web/dsh-pmboard/src/tools/SubmitTool/prompt.ts`（工作区修改 +6/−3）
  - 用例文件：`packages/web/dsh-pmboard/tests/design-registration.test.ts`（新增，untracked，170 行 / 9 例；头部第 2 行带 `serves FR-1`）
- 测试结论：**目标命令全绿** —— `npx vitest run tests/design-registration.test.ts tests/tools-schema.test.ts tests/output-contract.test.ts` → **3 files / 31 tests 通过，exit 0**。TC-1 首次 `registered_count=5`、二次 `=0`、空目录 `0 且 success=false 不谎报` 三条口径均由用例逐条锁定，验收标准「目标命令输出全绿」达成。

---

## 1. 目标命令（父卡 t-6eca2a「得到什么结果」验收命令）

```bash
cd packages/web/dsh-pmboard
npx vitest run tests/design-registration.test.ts tests/tools-schema.test.ts tests/output-contract.test.ts --reporter=verbose --silent
```

实际输出（逐例）：

```
 RUN  v2.1.9 /Users/yunpeng/pi-investment/agent-dh/packages/web/dsh-pmboard

 ✓ tests/tools-schema.test.ts > reqboard 工具 schema（构造即编译） > reqboard_create schema 合法
 ✓ tests/tools-schema.test.ts > reqboard 工具 schema（构造即编译） > reqboard_status schema 合法
 ✓ tests/tools-schema.test.ts > reqboard 工具 schema（构造即编译） > reqboard_move schema 合法
 ✓ tests/design-registration.test.ts > TC-1 正向：扫 design/ 登记 5 份，二次幂等 > 首次 registered_count=5 且 5 条 kind=design 入簿；二次 registered_count=0
 ✓ tests/output-contract.test.ts > 输出契约：返回字段 ⊆ output.schema 声明 > archive_submit（含 unlisted_files 警告路径）
 ✓ tests/design-registration.test.ts > TC-1 正向：扫 design/ 登记 5 份，二次幂等 > 部分新增：已登记 5 份后再落盘第 6 份，registered_count 只数本次新增（=1）
 ✓ tests/output-contract.test.ts > 输出契约：返回字段 ⊆ output.schema 声明 > verify_submit（含 sheet 摘要路径）
 ✓ tests/design-registration.test.ts > TC-1 正向：扫 design/ 登记 5 份，二次幂等 > 登记后 G2 读得到（不再 missing_artifact，转为待确认）
 ✓ tests/design-registration.test.ts > TC-19 前半 · 边界：空目录返回 0 且不谎报成功 > design/ 不存在 → registered_count=0、success=false、零产物入簿
 ✓ tests/design-registration.test.ts > TC-19 前半 · 边界：空目录返回 0 且不谎报成功 > design/ 存在但只有非 .md → 同样 0 且不谎报
 ✓ tests/output-contract.test.ts > 输出契约：返回字段 ⊆ output.schema 声明 > ask_confirm 成功路径（肯定项 → 落章 + 推进）
 ✓ tests/output-contract.test.ts > 输出契约：返回字段 ⊆ output.schema 声明 > ask_confirm 非肯定项（不推进）
 ✓ tests/output-contract.test.ts > 输出契约：返回字段 ⊆ output.schema 声明 > ask_confirm 弹框不可用（fallback=board）
 ✓ tests/output-contract.test.ts > 输出契约·静态扫描：每个工具的全部 return 分支键都必须已声明 > 扫描器覆盖全部工具文件，且至少发现 9 个工具工厂（少一个即红——防退化为只覆盖部分）
 ✓ tests/output-contract.test.ts > 输出契约·静态扫描：每个工具的全部 return 分支键都必须已声明 > defineAcceptSheetTool：所有 return 分支键均已声明
 ✓ tests/output-contract.test.ts > 输出契约·静态扫描：每个工具的全部 return 分支键都必须已声明 > defineAdvanceTool：所有 return 分支键均已声明
 ✓ tests/output-contract.test.ts > 输出契约·静态扫描：每个工具的全部 return 分支键都必须已声明 > defineAskConfirmTool：所有 return 分支键均已声明
 ✓ tests/output-contract.test.ts > 输出契约·静态扫描：每个工具的全部 return 分支键都必须已声明 > defineCaptureTool：所有 return 分支键均已声明
 ✓ tests/output-contract.test.ts > 输出契约·静态扫描：每个工具的全部 return 分支键都必须已声明 > defineCreateTool：所有 return 分支键均已声明
 ✓ tests/output-contract.test.ts > 输出契约·静态扫描：每个工具的全部 return 分支键都必须已声明 > defineDecomposeTool：所有 return 分支键均已声明
 ✓ tests/output-contract.test.ts > 输出契约·静态扫描：每个工具的全部 return 分支键都必须已声明 > defineMoveTool：所有 return 分支键均已声明
 ✓ tests/output-contract.test.ts > 输出契约·静态扫描：每个工具的全部 return 分支键都必须已声明 > defineStatusTool：所有 return 分支键均已声明
 ✓ tests/output-contract.test.ts > 输出契约·静态扫描：每个工具的全部 return 分支键都必须已声明 > defineSubmitTool：所有 return 分支键均已声明
 ✓ tests/output-contract.test.ts > 输出契约·静态扫描：每个工具的全部 return 分支键都必须已声明 > defineTaskExecuteTool：所有 return 分支键均已声明
 ✓ tests/output-contract.test.ts > 输出契约·静态扫描：每个工具的全部 return 分支键都必须已声明 > defineTaskMoveTool：所有 return 分支键均已声明
 ✓ tests/output-contract.test.ts > 输出契约·静态扫描：每个工具的全部 return 分支键都必须已声明 > defineTaskReportTool：所有 return 分支键均已声明
 ✓ tests/output-contract.test.ts > 输出契约·静态扫描：每个工具的全部 return 分支键都必须已声明 > defineTaskStatusTool：所有 return 分支键均已声明
 ✓ tests/design-registration.test.ts > I-1 path 语义：单份登记 + 可打开性校验 > 给了 path 只登记该份
 ✓ tests/design-registration.test.ts > I-1 path 语义：单份登记 + 可打开性校验 > 伪路径（..）→ REQBOARD_ARTIFACT_NOT_OPENABLE
 ✓ tests/design-registration.test.ts > I-1 path 语义：单份登记 + 可打开性校验 > 文件不存在 → REQBOARD_FILE_MISSING
 ✓ tests/design-registration.test.ts > 归属校验 > 本窗口未绑定需求 → REQBOARD_NO_BOUND_REQ

 Test Files  3 passed (3)
      Tests  31 passed (31)
   Start at  23:56:21
   Duration  636ms (transform 260ms, setup 961ms, tests 245ms, environment 0ms, prepare 118ms)
```

- 退出码：**0**（全绿）
- 判定：与父卡 t-6eca2a 验收命令「`npx vitest run tests/design-registration.test.ts tests/tools-schema.test.ts tests/output-contract.test.ts` 全绿」一致。

## 2. 父卡三条业务口径逐条核对

| 父卡验收口径 | 本卡实测（对应用例） | 结果 |
|---|---|---|
| 首次 `registered_count=5` | `TC-1 … 首次 registered_count=5 且 5 条 kind=design 入簿；二次 registered_count=0` | ✅ |
| 二次调用幂等 `=0` | 同上（同一条用例二次调用断言） | ✅ |
| 空目录返回 0 且不谎报成功 | `TC-19 前半 … design/ 不存在 → registered_count=0、success=false、零产物入簿`；`design/ 存在但只有非 .md → 同样 0 且不谎报` | ✅ |

补充锁定（同批用例，非父卡必答项）：部分新增只数本次新增（第 6 份 → `registered_count=1`）；登记后 G2 由 `missing_artifact` 转为「待确认」；`path` 单份登记的可打开性校验（伪路径 `REQBOARD_ARTIFACT_NOT_OPENABLE`、文件不存在 `REQBOARD_FILE_MISSING`）；归属校验 `REQBOARD_NO_BOUND_REQ`。

## 3. 改动归属（本卡未改任何源码）

```bash
git status --porcelain -- packages/web/dsh-pmboard/src/... packages/web/dsh-pmboard/tests/design-registration.test.ts
git diff --numstat -- ...
```

实际输出：

```
27	6	agent-dh/packages/web/dsh-pmboard/src/tools/SubmitTool/SubmitTool.ts
6	3	agent-dh/packages/web/dsh-pmboard/src/tools/SubmitTool/prompt.ts
---untracked---
?? agent-dh/packages/web/dsh-pmboard/src/application/use-cases/SubmitDesignArtifacts.ts
?? agent-dh/packages/web/dsh-pmboard/tests/design-registration.test.ts
```

- 上述 4 处实现/用例改动均为**父卡 t-6eca2a（T-3，implement 阶段）的待提交工作区改动**，本卡（test 阶段）**只读不改**；本卡本轮新增产物仅本证据文件 `docs/requirements/REQ-260924213231-b1c4/evidence/t-4b15cf-test.md`。
- HEAD = `9e5ebf60`（branch `main`），与父卡实现记录一致。

## 4. 测试结论

1. 目标命令 `npx vitest run tests/design-registration.test.ts tests/tools-schema.test.ts tests/output-contract.test.ts`：**3 files / 31 tests 全绿，exit 0** —— 验收标准「目标命令输出全绿」达成。
2. 父卡三条业务口径（首次 5 / 二次 0 / 空目录 0 且不谎报）均由用例逐条锁定且通过。
3. 本卡为 test 阶段，只执行上述命令并落本记录；未修改任何实现、适配器或测试源码。
