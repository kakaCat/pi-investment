# t-222d3d 复核记录（父卡 t-9a6bdb / T-2「下沉产物发现核心并薄壳化 ArtifactSync」· 阶段 review）

- 复核时间：2026-09-24T23:37+0800
- 复核环境：node v22.23.2 · vitest 2.1.9（darwin-arm64）· 工作目录 `agent-dh` · 被测工作树 = 主工作区（branch `main`，T-2 三处改动未提交）
- 复核对象（实现）：
  - 新增 `packages/web/dsh-pmboard/src/application/internal/artifact-discovery.ts`（`discoverArtifactsFrom(docs, req, reqRelPrefix?)` + `stageForKind` / `staleAutoKind` / `reqDirRel`）
  - 改 `packages/web/dsh-pmboard/src/adapters/ArtifactSync.ts`（改为薄壳：构造 DocRepository → 调核心 → 落库）
  - 改 `packages/web/dsh-pmboard/tests/sync-artifacts.test.ts`（+2 例，既有断言不动）
- 复核基准（设计）：`requirement.md`（FR-1 / §5 边界 / §7 契约）· `design/architecture.md:40-41,98,207,224-225` · `decomposition.md` T-2 行（原 111/135/152 行）· 任务卡 `tasks/t-9a6bdb.md`
- 复核方式：**只读复核**（不修改任何实现/测试），并**独立复现**关键命令；另用临时探针**重建 HEAD 版基线算法**与新核心逐字段比对（跑完即删，复核不存在）。
- 总裁决：**实现与设计逐条一致，无实现偏离**；另发现 3 处**文档级** nit（M-1/M-2/M-3，均无功能影响、不阻断）与 3 条观察（O-1~O-3，不改判定）。

---

## 0. 设计基线（判定依据）

| 依据 | 位置 | 关键约定 |
|---|---|---|
| 需求 FR-1 | `requirement.md` §6 | 登记能力共享同一发现核心；「新增登记能力必须幂等（同 path 已登记 → 跳过），与 ArtifactSync 语义一致」（§7） |
| 需求边界 | `requirement.md` §5 | **不重写 ArtifactSync 的扫描规则与幂等语义**；本次范围收口在 4 个点 + 2 对齐 + 1 韧性 |
| 架构组件 | `design/architecture.md:40-41` | 新增 `src/application/internal/artifact-discovery.ts`（由 DocRepository 端口列出需求目录并分类为产物的**唯一**实现）；ArtifactSync 改为一层薄壳（调核心 + 落库，行为不变） |
| 架构签名 | `design/architecture.md:98` | `discoverArtifactsFrom(docs, req): StageArtifact[]`；纯函数按 `docs.list(需求目录/design)` 产出待登记条目（`kindForRelPath` 分类 + 已登记 path 跳过） |
| 架构分层/尺寸 | `design/architecture.md:224-225` | application 不 import adapters/node:（layer-boundary 门禁）；单文件 ≤400 行 |
| 拆分计划 | `decomposition.md` 新增表 + T-2 行 | 落点 3 文件；验收 = `sync-artifacts` 全绿且既有断言逐字不变 + `layer-boundary` 不新增越界 |
| 任务卡 | `tasks/t-9a6bdb.md:16,19` | 同上；核心为 `discoverArtifactsFrom(docs,req)` 纯函数 |

## 1. 逐条对照（设计 → 实现 → 结论）

| # | 设计条目 | 实测实现 | 结论 |
|---|---|---|---|
| 1 | 新文件落点/命名 = `src/application/internal/artifact-discovery.ts`，且是发现逻辑的**唯一**实现 | 文件存在（114 行）；全包 grep `discoverArtifactsFrom` 仅此文件定义（消费方：`ArtifactSync.ts` + 测试） | **无偏离**（依据：`grep -rn discoverArtifactsFrom src tests`） |
| 2 | 核心签名 `discoverArtifactsFrom(docs, req): StageArtifact[]` | 实现为 `(docs: DocRepository, req: RequirementRecord, reqRelPrefix: string = reqDirRel(req.id))`——**两参调用即为设计签名**，第三参为可选超集 | **无偏离**（超集不改变设计调用形态；见 M-3） |
| 3 | 走 `DocRepository` 端口、application 零 `node:`/零 adapters 依赖 | 全部 import：`../ports.js`(type) + `../../shared/protocol.js`(type) + domain 的 `kindForRelPath`/`normalizeArtifactPath`；无 `node:`、无 `../adapters/` | **无偏离**（依据：`artifact-discovery.ts:17-20`；`layer-boundary` 越界清单未含本文件，见 §2.3） |
| 4 | 分类真相单点：`kindForRelPath` 归 domain，核心只组装 | 核心调 domain `kindForRelPath`；未在 application 另立分类表（注释明示 INV-7） | **无偏离**（依据：`artifact-discovery.ts:19,99`） |
| 5 | 幂等：同 path 已登记 → 跳过 | `alreadyRegistered(req, workspacePath)` 逐条过滤（与基线同一判定函数，逐字搬入） | **无偏离**（依据：`artifact-discovery.ts:47-49,98`；探针 C3 覆盖） |
| 6 | 防御性形态过滤（brace/越界不登记） | `normalizeArtifactPath(workspacePath, '/').form !== 'workspace' → continue`，与基线同口径 | **无偏离**（依据：`artifact-discovery.ts:97`；`artifact-openable.test.ts` 7/7 绿） |
| 7 | 产出条目字段与基线逐字一致 | `stage/kind/path/registeredAt/registeredBy/autoDiscovered/fileMtime/fileSize` 八字段与 HEAD 版完全相同 | **无偏离**（依据：§2.2 探针逐字段比对 + `git show HEAD` diff） |
| 8 | 扫描范围 = 整个需求目录（递归、跳点文件），行为零变更 | `walk(reqRelPrefix)` 递归；`entry.name.startsWith('.')` 跳过；`entry.isFile` 判定同基线 | **无偏离**（依据：`artifact-discovery.ts:83-112`；文档 line 98 措辞见 M-2） |
| 9 | ArtifactSync 改薄壳：构造 DocRepository → 调核心 → 落库（补登 + 回填过期种类 + 写评论） | `syncReqArtifacts` = `new FileDocRepository({workspaceRoot: cwd})` → `discoverArtifactsFrom(docs, req)` → `store.mutate` 内回填/补登/评论；`discoverArtifacts` 兼容入口转发核心 | **无偏离**（依据：`ArtifactSync.ts:55-62,68-119`） |
| 10 | **行为零变更**（路径 / 幂等 / 评论 / 回填 / 返回计数） | 落库段与 HEAD 语义未变（仅把 `reqDirRel(reqId)` 提到局部变量 `reqRel`）；富目录三路比对 core==shim==HEAD 基线（§2.2）；`sync-artifacts` 11/11、`fault-injection` 未新增失败 | **无偏离**（依据：§2.2/§2.4） |
| 11 | 既有导出面不破（兼容） | ArtifactSync 仍导出 `discoverArtifacts` / `syncReqArtifacts` / `syncAllReqArtifacts` / `reqDirRel`（`export { reqDirRel }` 保持既有 import 点） | **无偏离**（依据：`ArtifactSync.ts:33,55,68,122`） |
| 12 | 回归 `tests/sync-artifacts.test.ts` 全绿且**既有断言逐字不变** | `git diff --numstat` = `32 0`（纯新增 2 例、0 删除/0 修改）；`npx vitest run tests/sync-artifacts.test.ts` → 11 passed | **无偏离**（依据：§2.1） |
| 13 | `layer-boundary` 不新增越界（新文件在 application 且不 import node:/adapters） | 越界清单仍仅基线存量 `application/internal/diag-log.ts -> node:fs / node:path`；`artifact-discovery.ts` 未出现 | **无偏离**（依据：§2.3） |
| 14 | 单文件 ≤400 行（architecture.md:225） | `artifact-discovery.ts` 114 行、`ArtifactSync.ts` 132 行 | **无偏离**（`size-budget` 仍红 = 基线 `index.ts` 434 行，非本卡文件） |
| 15 | 范围：不重写扫描规则/幂等语义，不越 T-3 的工具入口 | 本卡改动 = 3 文件（1 新增 + 1 薄壳 + 1 测试）；未改 `SubmitTool`、未新增工具 | **无偏离**（依据：`git status` 本卡相关仅 3 文件，见 §2.5） |
| 16 | 类型面不新增错误（旁证，非卡面验收） | `npx tsc --noEmit` 错误数 = 23 = 基线；三个受触文件命中 **0** 条 | **无偏离**（依据：§2.4） |

> 结论：16 项设计/卡面约定**逐条无偏离**。

## 2. 独立复现（命令与输出摘要）

### 2.1 目标命令：核心回归

```bash
cd packages/web/dsh-pmboard
npx vitest run tests/sync-artifacts.test.ts
```

```
 ✓ tests/sync-artifacts.test.ts (11 tests) 80ms
 Test Files  1 passed (1)
      Tests  11 passed (11)
```

退出码 0 —— 与卡验收①一致。既有断言逐字不变由 `git diff --numstat` 佐证：`32 0`（新增 2 例：
`discoverArtifactsFrom` 走端口扫描 + 与兼容入口 `discoverArtifacts` 产出逐字一致）。

### 2.2 独立复现：薄壳化「行为零变更」三方比对（本卡核心判据）

复核方式：写**临时探针** `tests/__probe-t222d3d.test.ts`（跑完即删），其中**逐字重建 HEAD 版**
`discoverArtifacts` 的绝对路径算法（`git show HEAD:agent-dh/.../ArtifactSync.ts`），与
当前 `discoverArtifactsFrom`（核心）及 `discoverArtifacts`（兼容薄壳）在同一富目录上比对：

目录构造：`requirement.md`（**已登记**，应跳过）、`prototype.html`、`design/architecture.md`、
`design/nested/deep.md`（嵌套）、`tasks/t-abc123.md`、`.hidden.md`（点文件，应跳过）、
`proto-{a,b}.html`（brace，应过滤）、`sub/note.txt`、空目录 `emptydir/`。

```
CORE  = [...design/architecture.md(design,design), design/nested/deep.md(design,design),
         prototype.html(notes,design), sub/note.txt(notes,design), tasks/t-abc123.md(task_detail,implementing)]
SHIM  = <与 CORE 逐字符相同（同序）>
BASE  = <与 CORE 逐字符相同（同序）>
 ✓ tests/__probe-t222d3d.test.ts (2 tests) 12ms   → 1 passed (2)
```

- `project(core) === project(base)`、`project(shim) === project(base)`（投影掉 `registeredAt=Date.now()`，
  比 `path/kind/stage/autoDiscovered/fileSize`，并保持 readdir 遍历顺序）→ **行为零变更成立**。
- 目录不存在两路均返回 `[]`（第二例）。
- 临时探针已在本轮内 `rm -f` 删除：`ls .../tests/__probe-t222d3d.test.ts` → `No such file or directory`。

### 2.3 目标命令：层边界

```bash
npx vitest run tests/layer-boundary.test.ts
```

```
 × application/ 不得 import 禁止项
   → application/ 出现越界 import：
     application/internal/diag-log.ts -> node:fs
     application/internal/diag-log.ts -> node:path
 Test Files  1 failed (1)   Tests  1 failed | 8 passed (9)
```

越界清单**仅基线存量 `diag-log.ts`**（`git diff` 该文件为空，本卡未触碰）；新增
`artifact-discovery.ts` 不在清单中 → **不新增越界**，与卡验收②一致。

### 2.4 旁证：全量回归与类型门禁

```bash
npx vitest run        # 全量
npx tsc --noEmit -p tsconfig.json
```

```
 Test Files  7 failed | 142 passed (149)
      Tests  9 failed | 1775 passed (1784)
```

失败集合（7 文件 / 9 例）与 `decomposition.md` §基线缺口表**逐条同名**：
`client-view`×1、`template-address-injection`×2、`design-completeness-gate`×2、
`layer-boundary`×1、`application/repository`×1、`size-budget`×1、`typecheck`×1
→ **无新增失败**（均为未修的基线红，分属 T-5/T-12 及其它非本需求范围）。
`tsc` 错误数 = **23**（= 基线），错误文件 8 个全部为基线存量，本卡 3 文件命中 **0** 条。

### 2.5 范围与改动面核验

```bash
git diff --numstat -- packages/web/dsh-pmboard/src/adapters/ArtifactSync.ts \
                     packages/web/dsh-pmboard/tests/sync-artifacts.test.ts
# → 37  88  .../ArtifactSync.ts
# → 32   0  .../tests/sync-artifacts.test.ts
git status --short -- packages/web/dsh-pmboard
# → M  .../ArtifactSync.ts
# → M  .../tests/sync-artifacts.test.ts
# → ?? .../src/application/internal/artifact-discovery.ts
# （同目录另有 T-7 的 tests/zero-arg-binding.test.ts，非本卡）
```

ArtifactSync 的 `+37/-88` 净减 51 行（删除 `stageForKind`/`alreadyRegistered`/`staleAutoKind`/`reqDirRel`
本体与内嵌目录遍历，改为引入/再导出）——与联调记录 `t-34191e-integrate.md` §3 的 `+37/-88` 一致。

## 3. 偏离清单

### 无实现偏离

除下述 **M-1~M-3（文档级，均无功能影响）** 外，T-2 / FR-1 / 任务卡的全部约定与实现逐条一致
（§1 表 16/16），**实现层面无偏离**。

| # | 性质 | 位置 | 实测 vs 文档 | 判定 |
|---|---|---|---|---|
| M-1 | 证据文档编号冲突（非实现） | `evidence/t-34191e-integrate.md:6-11` | 该记录把内部接缝标为 **I-1/I-2/I-3**（`discoverArtifactsFrom` / `discoverArtifacts` / `syncReqArtifacts`），与 `design/interfaces.md` 的 I-1/I-2/I-3（`reqboard_submit(kind=design)` / `reqboard_status` / `reqboard_ask_confirm`）**同号不同物** | 文档级，不阻断；**归档前建议改标**（如 `C-1/C-2/C-3` 或 `SEAM-1~3`），避免后续引用串号 |
| M-2 | 设计文档措辞不准（非实现） | `design/architecture.md:98` | 文档写「按 `docs.list(需求目录/design)` 产出待登记条目」；实测（与 HEAD 基线 + 行为零变更约束）核心是**递归遍历整个需求目录**（`requirement.md`/`prototype.html`/`tasks/*.md` 均登记），并非只列 `design/` 子目录。同文件 line 40 的「列出需求目录」与实现一致 | 「/design」为散写（疑似指 design 阶段产物）；**实现取合理一侧**，不建议返工代码；后续修订把该处改为 `docs.list(需求目录)` |
| M-3 | 设计签名 vs 实现超集（非契约破坏） | `design/architecture.md:98`、`tasks/t-9a6bdb.md:19` | 文档签名 `discoverArtifactsFrom(docs, req)`；实现第三参 `reqRelPrefix? = reqDirRel(req.id)` 为**可选**（为承载兼容入口的旧前缀签名） | 只增不改，两参调用即设计签名；T-3 按两参调用即可。**非偏离**，记录备查 |

## 4. 复核观察（不改判定，供后续卡）

- **O-1（模块职责收紧）**：核心同时导出 `stageForKind` / `staleAutoKind`（基线是 adapter 私有），
  使「发现核心」额外承担阶段/过期种类推导。实测消费方仅 `ArtifactSync.ts`，且这两者本就是
  「目录→产物」的同一分类真相，合并可避免两份规则 —— 判定**可接受、非偏离**；若后续 T-3 只用
  `discoverArtifactsFrom`，无需为这两个导出扩大 API。
- **O-2（兼容入口的潜在边界）**：`ArtifactSync.discoverArtifacts` 现用 `workspaceRootOf(reqRoot, reqRelPrefix)`
  反推工作区根；当调用方传入**违反既有契约**的组合（`reqRoot` 不以 `/<reqRelPrefix>` 结尾）时，
  新实现会回落为「以 `reqRoot` 为根列 `reqRelPrefix`」，与 HEAD 的绝对路径扫描**在语义上不同**
  （两者在该输入下都容易返回 `[]`）。实测在仓调用方仅测试：`artifact-openable.test.ts:161` 传一致组合、
  `sync-artifacts.test.ts:86` 传不存在目录（两版均 `[]`）→ **未被触发、不构成回归**。仅提示：
  若未来有外部调用依赖旧行为，需显式保留绝对扫描分支。
- **O-3（"纯函数"口径）**：`artifact-discovery.ts:104` 用 `Date.now()` 填 `registeredAt`，严格意义非纯；
  与基线一致，测试以 `project()` 投影掉该字段。语义上「无 I/O 副作用」成立，**非偏离**。

## 5. 复核结论

1. **实现与设计逐条一致，无实现偏离**：核心落点/签名/端口依赖/分类单点/幂等/形态过滤/字段/扫描行为/
   薄壳职责/导出面/两条卡面验收/尺寸与范围，共 16 项全部核对为「无偏离」（§1 表），每项附实测依据。
2. **「行为零变更」经独立三方比对成立**：重建 HEAD 基线算法在富目录（嵌套 / 点文件 / brace / 已登记 /
   空目录）下与核心、兼容薄壳**逐字符相同**（§2.2）。
3. **两条卡面验收达标**：`sync-artifacts.test.ts` 11/11（既有断言 `32 0` 纯新增不改）、
   `layer-boundary` 越界清单不变（仅基线 `diag-log.ts`）；全量回归失败集合 = 基线 9 例、`tsc` = 基线 23 条。
4. 唯一发现为 **M-1（联调记录编号与 interfaces.md 冲突）/ M-2（architecture.md:98 措辞散写）/
   M-3（签名超集）** 三处文档级问题，**均不构成实现偏离、不阻断父卡收尾**；建议归档前顺手修正 M-1/M-2。
5. 本卡为 review 阶段，**只读复核 + 落本记录**；未修改任何实现或测试源码，本轮新增产物仅本文件
   （临时探针已删除，复核不存在）。
