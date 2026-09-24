# t-e5d2e6 测试记录（父卡 t-9a6bdb / T-2「下沉产物发现核心并薄壳化 ArtifactSync」· 阶段 test）

- 测试时间：2026-09-24T23:39+0800
- 测试环境：node v22.23.2 · vitest 2.1.9（darwin-arm64）· 仓库工作目录 `agent-dh`，测试工作目录 `packages/web/dsh-pmboard`；HEAD = `9e5ebf60`（branch `main`）
- 被测对象（FR-1；实现改动为工作区未提交状态，本卡只读不改）：
  - **I-1** `discoverArtifactsFrom(docs: DocRepository, req: RequirementRecord, reqRelPrefix?): StageArtifact[]`
    —— `packages/web/dsh-pmboard/src/application/internal/artifact-discovery.ts`（新增，下沉核心，纯函数，走 DocRepository 端口）
  - **I-2/I-3** 薄壳 `discoverArtifacts(req, reqRoot, reqRelPrefix)` / `syncReqArtifacts(store, reqId, cwd?)`
    —— `packages/web/dsh-pmboard/src/adapters/ArtifactSync.ts`（改薄壳：调核心 + 落库，行为零变更）
  - 回归测试：`packages/web/dsh-pmboard/tests/sync-artifacts.test.ts`（新增 `discoverArtifactsFrom` 2 例，既有断言逐字不动）
- 测试结论：**目标命令全绿** —— `npx vitest run tests/sync-artifacts.test.ts` → 1 file / 11 tests 通过，**exit 0**；层边界守护无新增越界（新增 `artifact-discovery.ts` 不在越界清单，唯一失败为 `diag-log.ts` 存量基线）；直接消费方回归 3 文件 / 25 例全绿。验收标准「目标命令输出全绿」达成。

---

## 1. 目标命令 ①：核心回归（T-2 验收命令）

```bash
cd packages/web/dsh-pmboard
npx vitest run tests/sync-artifacts.test.ts
```

实际输出（`--reporter=verbose`，逐例）：

```
 RUN  v2.1.9 /Users/yunpeng/pi-investment/agent-dh/packages/web/dsh-pmboard

 ✓ tests/sync-artifacts.test.ts > kindForRelPath > 必备产物按文件名归位，其余归 notes
 ✓ tests/sync-artifacts.test.ts > discoverArtifacts（纯扫描） > 扫描需求目录，未登记文件带 autoDiscovered 标记
 ✓ tests/sync-artifacts.test.ts > discoverArtifacts（纯扫描） > 已登记的文件跳过
 ✓ tests/sync-artifacts.test.ts > discoverArtifacts（纯扫描） > 目录不存在 → 返回空数组不炸
 ✓ tests/sync-artifacts.test.ts > syncReqArtifacts（落库） > 落库补登 + 写评论；重复调用幂等返回 0
 ✓ tests/sync-artifacts.test.ts > syncReqArtifacts（落库） > design/*.md 补登为设计文档，归设计节点（FR-1/FR-3）
 ✓ tests/sync-artifacts.test.ts > syncReqArtifacts（落库） > 分类规则升级后回填旧条目种类（notes → design），且幂等
 ✓ tests/sync-artifacts.test.ts > syncReqArtifacts（落库） > 手工登记的产物不被回填覆盖（只回填 autoDiscovered）
 ✓ tests/sync-artifacts.test.ts > syncReqArtifacts（落库） > syncAllReqArtifacts 扫描全部需求
 ✓ tests/sync-artifacts.test.ts > discoverArtifactsFrom（application 核心：只走 DocRepository 端口） > 经端口扫描需求目录，未登记文件带 autoDiscovered 标记且按名分类
 ✓ tests/sync-artifacts.test.ts > discoverArtifactsFrom（application 核心：只走 DocRepository 端口） > 与适配器兼容入口 discoverArtifacts 产出逐字一致（行为零变更）

 Test Files  1 passed (1)
      Tests  11 passed (11)
   Start at  23:38:54
   Duration  358ms (transform 73ms, setup 0ms, collect 86ms, tests 83ms, environment 0ms, prepare 40ms)
```

- 退出码：**0**（全绿）
- 判定：与验收「`npx vitest run tests/sync-artifacts.test.ts` 全绿」一致。
- 覆盖要点：
  - 既有 9 例（文件名→种类推断 / 纯扫描 / 幂等 / 已登记跳过 / 目录不存在不炸 / 落库补登+评论 / design 归位 / 旧条目回填 / syncAll）全部保留且通过 —— 薄壳化未破坏任何既有行为。
  - 新增 2 例锁定**下沉核心**：① 核心经 DocRepository 端口扫描并按名分类（requirement/notes/design）；② 核心产出与适配器兼容入口 `discoverArtifacts` 投影后 `toEqual` 逐字一致（**行为零变更**的直接断言）。

## 2. 目标命令 ②：层边界守护（不新增越界）

```bash
cd packages/web/dsh-pmboard
npx vitest run tests/layer-boundary.test.ts
```

实际输出（节选）：

```
 × tests/layer-boundary.test.ts > 层边界：依赖方向（architecture.md §2） > application/ 不得 import 禁止项
   → application/ 出现越界 import：
     application/internal/diag-log.ts -> node:fs
     application/internal/diag-log.ts -> node:path
 Test Files  1 failed (1)
      Tests  1 failed | 8 passed (9)
```

- 期望：**不因本卡新增越界** —— 新增文件 `application/internal/artifact-discovery.ts` 不 import `node:`、不 import `adapters`。
- 实际：越界清单**只有 `diag-log.ts`**（存量基线，见拆解计划 §风险「`tests/layer-boundary.test.ts`（diag-log.ts import node:fs/node:path）→ 记录；T-2 保证新增 application 文件不越界」）；`artifact-discovery.ts` **未出现在越界清单** —— 与期望一致。
- 独立佐证（本卡实测）：
  - 新文件 import 全量 = `../ports.js`、`../../shared/protocol.js`、`../../domain/artifact/ArtifactSpec.js`、`../../domain/artifact/ArtifactPath.js`；`grep -nE "from .(node:|.*adapters)"` → `NONE`（零越界）。
  - 存量基线证明：`git diff --numstat -- src/application/internal/diag-log.ts` 输出为空（该文件本卡前后均未改动）；且 `git show HEAD:.../diag-log.ts | grep node:` → 第 12/13 行 `import * as fs from 'node:fs'` / `import * as path from 'node:path'`，即**该越界在 HEAD 上已存在**，非本卡引入。

## 3. 直接消费方回归（额外护栏）

```bash
cd packages/web/dsh-pmboard
npx vitest run tests/sync-artifacts.test.ts tests/fault-injection.test.ts tests/artifact-openable.test.ts
```

实际输出：

```
 ✓ tests/sync-artifacts.test.ts (11 tests) 79ms
 ✓ tests/artifact-openable.test.ts (7 tests) 83ms
 ✓ tests/fault-injection.test.ts (7 tests) 148ms

 Test Files  3 passed (3)
      Tests  25 passed (25)
```

- 退出码：**0**。`fault-injection.test.ts`、`artifact-openable.test.ts` 是 `ArtifactSync` / `artifact-discovery` 的直接消费方（同一进程内用法），均未新增失败。

## 4. 「既有断言逐字不变」核验

```bash
git diff --numstat -- packages/web/dsh-pmboard/src/adapters/ArtifactSync.ts \
                       packages/web/dsh-pmboard/tests/sync-artifacts.test.ts
```

实际输出：

```
37	88	.../src/adapters/ArtifactSync.ts
32	0	.../tests/sync-artifacts.test.ts
```

- `tests/sync-artifacts.test.ts` = `32 0`：**纯新增 32 行、0 删除/0 修改** → 既有断言逐字不变（新增的正是 §1 的第 10、11 两例）。
- `ArtifactSync.ts` = `37 88`（净减 51 行）：删除的 `stageForKind`/`alreadyRegistered`/`staleAutoKind`/`reqDirRel` 本体与内嵌目录遍历已下沉到 `artifact-discovery.ts`，薄壳只剩「构造 FileDocRepository → 调核心 → store.mutate 落库」。
- 新增文件 `src/application/internal/artifact-discovery.ts` 为 untracked（`??`），114 行纯函数。

## 5. 类型基线（旁证，非 T-2 验收命令）

```bash
cd packages/web/dsh-pmboard
npx tsc --noEmit -p tsconfig.json
```

- 错误总数 **23**（= 拆分计划 D-1 记录的基线 23，与 T-1 测试卡同值）；报错文件 8 个（`tests/template-address-injection.test.ts` 6、`src/domain/template/render.ts` 6、`src/domain/template/resolve.ts` 5、`tests/gate-aware-questions.test.ts` 2、`src/gate-wiring.ts` 1、`src/application/internal/node-input-package.ts` 1、`src/application/gate/handlers/h3-inject.ts` 1、`src/adapters/CaptureHook.ts` 1）—— 全部为存量。
- 本卡两个改动文件命中 **0** 条（`grep -E "artifact-discovery|ArtifactSync"` → 0）：新核心类型干净，薄壳未引入类型错误。
- 注：`tests/typecheck.test.ts` 期望 0 错误，在 23 存量基线下本就为红（非本卡引入、本卡未触碰该基线）。

## 6. 测试结论

1. 目标命令 `npx vitest run tests/sync-artifacts.test.ts`：**1 file / 11 tests 全绿，exit 0** —— 验收标准「目标命令输出全绿」达成。
2. 验收侧条件「既有断言逐字不变」：`git diff --numstat` = `32 0`（纯新增 2 例、0 删除/0 修改）—— 达成。
3. 验收侧条件「`layer-boundary.test.ts` 不新增越界」：新增 `artifact-discovery.ts` 不在越界清单（零 `node:`/adapters import）；唯一失败为 `diag-log.ts` 存量基线（HEAD 上即存在、本卡未触碰）—— 达成。
4. 额外护栏：`ArtifactSync` 直接消费方回归 3 文件 / 25 例全绿，行为零变更成立。
5. 本卡为 test 阶段，只执行上述命令并落本记录；**未修改任何实现、适配器或测试源码**，本轮新增产物仅本文件。工作区 `ArtifactSync.ts` / `sync-artifacts.test.ts` 的改动、`artifact-discovery.ts` 的 untracked 状态均为父卡 T-2 的待提交改动（本卡未触碰），HEAD = `9e5ebf60`。
