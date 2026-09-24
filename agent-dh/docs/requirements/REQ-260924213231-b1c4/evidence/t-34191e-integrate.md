# t-34191e 联调记录（父卡 t-9a6bdb / T-2「下沉产物发现核心并薄壳化 ArtifactSync」· 阶段 integrate）

- 联调时间：2026-09-24T23:35+0800
- 联调环境：node v22.23.2 · vitest 2.1.9（darwin-arm64）· 测试工作目录 `packages/web/dsh-pmboard`
- 联调对象（接口）：
  - **I-1** `discoverArtifactsFrom(docs: DocRepository, req: RequirementRecord, reqRelPrefix?): StageArtifact[]`
    —— `packages/web/dsh-pmboard/src/application/internal/artifact-discovery.ts`（下沉核心，纯函数）
  - **I-2** `discoverArtifacts(req, reqRoot, reqRelPrefix): StageArtifact[]`
    —— `packages/web/dsh-pmboard/src/adapters/ArtifactSync.ts`（兼容薄壳，转发 I-1）
  - **I-3** `syncReqArtifacts(store, reqId, cwd?): Promise<number>`
    —— `packages/web/dsh-pmboard/src/adapters/ArtifactSync.ts`（构造 DocRepository → 调 I-1 → 落库）
- 结论：**接口联调通过** —— 请求样例、期望响应、实际返回三者一致（6/6 例 MATCH）；薄壳与核心产出逐字一致（行为零变更）；目标测试 `sync-artifacts.test.ts` 11/11 绿。

---

## 1. 接口三方对照（核心验收）

联调方式：在本轮内运行**临时探针** `tests/__probe-t34191e.test.ts`（跑完即删），对 I-1/I-2/I-3 各发一次真实调用，逐字段打印并比较「请求样例 / 期望响应 / 实际返回」。临时目录内预置 4 个需求目录文件：`requirement.md`、`plan.md`、`design/architecture.md`、`prototype.html`。

### C1 — I-1 `discoverArtifactsFrom(docs, req)`（缺省前缀）

| 项 | 内容 |
|---|---|
| 请求样例 | `{docs: FileDocRepository{workspaceRoot:<tmp>}, reqId:'REQ-abc123', reqStatus:'brainstorming', reqRelPrefix:'(default docs/requirements/REQ-abc123)'}` |
| 期望响应 | 4 条 `StageArtifact`：`design/architecture.md→design/design`、`plan.md→plan/design`、`prototype.html→notes/brainstorming`、`requirement.md→requirement/brainstorming`，均 `autoDiscovered:true` |
| 实际返回 | 与期望逐字段相同（见下） |
| 判定 | **一致（MATCH）** |

```
EXPECTED: [{"path":"docs/requirements/REQ-abc123/design/architecture.md","kind":"design","stage":"design","autoDiscovered":true},
           {"path":"docs/requirements/REQ-abc123/plan.md","kind":"plan","stage":"design","autoDiscovered":true},
           {"path":"docs/requirements/REQ-abc123/prototype.html","kind":"notes","stage":"brainstorming","autoDiscovered":true},
           {"path":"docs/requirements/REQ-abc123/requirement.md","kind":"requirement","stage":"brainstorming","autoDiscovered":true}]
ACTUAL  : <与 EXPECTED 逐字符相同>
VERDICT : MATCH
```

### C2 — I-2 薄壳 `discoverArtifacts` vs I-1 核心（行为零变更）

| 项 | 内容 |
|---|---|
| 请求样例 | `{reqId:'REQ-abc123', reqRoot:'<tmp>/docs/requirements/REQ-abc123', reqRelPrefix:'docs/requirements/REQ-abc123'}` |
| 期望响应 | 与 C1 核心产出（投影含 `fileSize`）**逐字一致** |
| 实际返回 | `[{"path":".../design/architecture.md","kind":"design","stage":"design","autoDiscovered":true,"fileSize":1}, ... 共 4 条]` |
| 判定 | **一致（MATCH）**：`JSON.stringify(project(shim)) === JSON.stringify(project(core))` |

### C3 — I-1 幂等：同 path 已登记 → 跳过

| 项 | 内容 |
|---|---|
| 请求样例 | `{docs: FileDocRepository, reqId:'REQ-abc123', alreadyRegistered:['docs/requirements/REQ-abc123/requirement.md']}` |
| 期望响应 | 仅剩 3 条（`requirement.md` 被跳过） |
| 实际返回 | 3 条：architecture.md / plan.md / prototype.html |
| 判定 | **一致（MATCH）** |

### C4 — I-1 目录不存在 → 返回 `[]` 不抛

| 项 | 内容 |
|---|---|
| 请求样例 | `{docs: FileDocRepository, reqId:'REQ-missing', reqRelPrefix:'docs/requirements/REQ-missing'}` |
| 期望响应 | `[]`（不抛异常） |
| 实际返回 | `[]` |
| 判定 | **一致（MATCH）** |

### C5 — I-3 `syncReqArtifacts(store, reqId, cwd)` 落库 + 幂等

| 项 | 内容 | 期望响应 | 实际返回 | 判定 |
|---|---|---|---|---|
| C5a 首次 | `{store:'JsonLedgerRepository', reqId:'REQ-abc123', cwd:'<tmp>'}` | `{added:4, artifactCount:4, hasAutoComment:true}` | `{added:4, artifactCount:4, hasAutoComment:true}` | **一致** |
| C5b 二次 | 同 C5a | `{added:0, artifactCount:4, commentCount:1}` | `{added:0, artifactCount:4, commentCount:1}` | **一致** |

- C5a 证明「构造 FileDocRepository → 调核心 → 落库（补登 + 写 `[产物自动发现]` 评论）」整链打通。
- C5b 证明幂等：二次扫描不重复落库、不追加评论。

探针执行结果：

```
 ✓ tests/__probe-t34191e.test.ts (1 test) 27ms
 Test Files  1 passed (1)
      Tests  1 passed (1)
```

## 2. 目标命令与输出摘要

### 2.1 核心回归（T-2 验收命令）

```bash
cd packages/web/dsh-pmboard
npx vitest run tests/sync-artifacts.test.ts
```

实际输出：

```
 RUN  v2.1.9 /Users/yunpeng/pi-investment/agent-dh/packages/web/dsh-pmboard

 ✓ tests/sync-artifacts.test.ts (11 tests) 77ms

 Test Files  1 passed (1)
      Tests  11 passed (11)
```

- 期望：全绿且既有断言逐字不变（新增 `discoverArtifactsFrom` 2 例）
- 实际：11/11 通过，退出码 0 —— 与期望一致

### 2.2 层边界回归（T-2 验收命令）

```bash
cd packages/web/dsh-pmboard
npx vitest run tests/layer-boundary.test.ts
```

实际输出（节选）：

```
 × 层边界：依赖方向 > application/ 不得 import 禁止项
     → application/ 出现越界 import：
       application/internal/diag-log.ts -> node:fs
       application/internal/diag-log.ts -> node:path
 Test Files  1 failed (1)
      Tests  1 failed | 8 passed (9)
```

- 期望：**不因本卡新增越界** —— 新增文件 `application/internal/artifact-discovery.ts` 不 import `node:`、不 import adapters
- 实际：越界清单**只有 `diag-log.ts`**（存量基线，见拆解计划 §风险「`tests/layer-boundary.test.ts`（diag-log.ts import node:fs/node:path）→ 记录；T-2 保证新增 application 文件不越界」）；`artifact-discovery.ts` **未出现在越界清单** —— 与期望一致
- 基线证明：`git diff --numstat -- .../application/internal/diag-log.ts` 输出为空（该文件在本卡前后均未被改动）

## 3. 薄壳化核验（行为零变更）

- `ArtifactSync.ts` 改动 `+37/-88`（净减 51 行）：删除了 `stageForKind`、`alreadyRegistered`、`staleAutoKind`、`reqDirRel` 的本体实现与内嵌的 `readdirSync/statSync/join/relative` 目录遍历，改为从 `application/internal/artifact-discovery.js` 引入/再导出；
- 保留的只有「构造 `FileDocRepository` → 调 `discoverArtifactsFrom` → `store.mutate` 落库（补登 + 回填过期种类 + 写评论）」；
- C2 实测薄壳与核心产出逐字一致 → 既有路径/幂等/评论行为未变。
- `ArtifactSync.ts` 若新增回落第 2.2 节越界（adapters 层允许 I/O），实际未新增：越界清单未出现该文件。

## 4. 联调结论

1. 接口 I-1（核心）、I-2（薄壳兼容入口）、I-3（落库路径）的**请求样例 → 期望响应 → 实际返回**三方一致，6/6 例 MATCH。
2. `discoverArtifactsFrom` 的幂等（已登记跳过）与容错（目录不存在 → `[]` 不抛）语义成立。
3. 薄壳 `discoverArtifacts` 与核心产出逐字一致，`syncReqArtifacts` 首次补登 4、二次 0 且评论不重复 —— 行为零变更成立。
4. `sync-artifacts.test.ts` 11/11 绿；`layer-boundary.test.ts` 唯一失败为 `diag-log.ts` 存量基线（本卡未触碰该文件，新增 `artifact-discovery.ts` 零越界）。
5. 本卡为 integrate 阶段，只执行上述命令与探针并落本记录；**未修改任何实现或测试源码**，本轮新增产物仅本文件；临时探针 `tests/__probe-t34191e.test.ts` 已在本轮内删除（`rm -f`，复核不存在）。
