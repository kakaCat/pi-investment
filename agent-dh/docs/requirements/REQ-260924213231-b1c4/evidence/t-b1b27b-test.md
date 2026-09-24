# t-b1b27b 测试记录（父卡 t-fbde12 / T-10「立项降级路径不丢文档位置」· 阶段 test）

- 测试时间：2026-09-25T01:39+0800（本轮执行内）
- 测试环境：node v22.23.2 · vitest 2.1.9（darwin-arm64）· 仓库工作目录 `agent-dh`，测试工作目录 `packages/web/dsh-pmboard`；HEAD = `9e5ebf60`（branch `main`）
- 被测对象（FR-7「立项降级路径补第四问」；实现改动均为工作区未提交状态，本卡只读不改）：
  - **工具壳** `packages/web/dsh-pmboard/src/tools/CreateTool/CreateTool.ts`（工作区修改 `11/0`）：入参 schema 增可选 `doc_location`（L47-51），输出 schema 增 `doc_location`（L63）与 `defaults_used`（L64）
  - **用例** `packages/web/dsh-pmboard/src/application/use-cases/CreateRequirement.ts`（工作区修改 `17/2`）：`resolveDocBasePath(a.doc_location)`（L38）→ `createRequirementDirect({ …docBasePath })`（L45）；返回补 `doc_location`（L55）与 `defaults_used`（L56），`note` 中含「已回落」留痕（L58）
  - **回落/形态校验** `packages/web/dsh-pmboard/src/application/internal/support.ts`（工作区修改 `44/1`）：`resolveDocBasePath`（L223-241，缺省→`CAPTURE_DEFAULTS.docLocation`+`usedDefault=true`；绝对路径/含 `..`/非字符串/超长 → `REQBOARD_INVALID_INPUT`）；`createRequirementDirect` 把 `docBasePath` 恒写台账（L265、L275）
  - 用例侧：`packages/web/dsh-pmboard/tests/create-doc-location.test.ts`（**untracked**，106 行 / 5 例）
- 测试结论：**目标命令全绿** —— `npx vitest run tests/create-doc-location.test.ts` → **1 file / 5 tests 通过，exit 0**。父卡三条业务口径（不传 → 返回默认位置 + `defaults_used` 留痕且台账 `docBasePath` 同值；传 `docs/rfcs/` → 台账与产物路径按它生成；返回 `status` 与台账一致）均由用例逐条锁定并复跑通过；另跑直接消费方护栏（output-contract / tools-schema / tools-dispatch）28/28 绿，无回归。验收标准「目标命令输出全绿」达成。

---

## 1. 目标命令（父卡 t-fbde12「得到什么结果」验收命令）

```bash
cd packages/web/dsh-pmboard
npx vitest run tests/create-doc-location.test.ts --reporter=verbose
```

实际输出（逐例）：

```
 RUN  v2.1.9 /Users/yunpeng/pi-investment/agent-dh/packages/web/dsh-pmboard

 ✓ tests/create-doc-location.test.ts > reqboard_create · 文档位置（FR-7 降级路径补第四问） > TC-11 不传 doc_location → 显式回落默认值 + defaults_used 留痕，台账 docBasePath 同值
 ✓ tests/create-doc-location.test.ts > reqboard_create · 文档位置（FR-7 降级路径补第四问） > TC-12 传 docs/rfcs/ → 台账 docBasePath 与产物路径按它生成
 ✓ tests/create-doc-location.test.ts > reqboard_create · 文档位置（FR-7 降级路径补第四问） > TC-13 返回 status 与台账一致（当前落点 draft，不谎报推进）
 ✓ tests/create-doc-location.test.ts > reqboard_create · 文档位置（FR-7 降级路径补第四问） > 异常流：绝对路径 / 含 .. 的路径 → REQBOARD_INVALID_INPUT，且不写台账（不静默改路径）
 ✓ tests/create-doc-location.test.ts > reqboard_create · 文档位置（FR-7 降级路径补第四问） > schema：doc_location 入参 + doc_location/defaults_used 返回键已声明（DSH 绑定层不拒收）

 Test Files  1 passed (1)
      Tests  5 passed (5)
   Start at  01:39:24
   Duration  564ms (transform 243ms, setup 0ms, collect 348ms, tests 25ms, environment 0ms, prepare 26ms)
```

- 退出码：**0**（全绿）
- 判定：与父卡任务卡 `tasks/t-fbde12.md` 验收命令「`npx vitest run tests/create-doc-location.test.ts` 全绿」逐字一致。

## 2. 父卡业务口径逐条核对（对照用例断言与源码）

| 父卡验收口径 | 对应用例 / 源码证据 | 结果 |
|---|---|---|
| 不传 `doc_location` → 返回 `doc_location='docs/requirements/<REQ>/'` 且 `defaults_used` 含 doc_location、台账 `docBasePath` 同值 | `create-doc-location.test.ts` TC-11（断言 `out.doc_location === CAPTURE_DEFAULTS.docLocation`、`out.defaults_used === ['doc_location']`、`out.note` 含「回落」、`ledgerReq(out.requirement_id).docBasePath === CAPTURE_DEFAULTS.docLocation`、`requirementDocPath(req) === 'docs/requirements/<REQ-id>/requirement.md'`）；源码 `CreateRequirement.ts:38,45,55-58`、`support.ts:223-241,265` | ✅ |
| 传 `docs/rfcs/` → 台账 `docBasePath` 与产物路径按它生成 | `create-doc-location.test.ts` TC-12（断言 `out.doc_location==='docs/rfcs/'`、`defaults_used===[]`、台账 `docBasePath==='docs/rfcs/'`、`requirementDocPath(req)==='docs/rfcs/<REQ-id>/requirement.md'`）；源码 `support.ts:241`、`node-input-package.ts` 同源拼接 | ✅ |
| 返回 `status` 与台账一致 | `create-doc-location.test.ts` TC-13（断言 `out.status === ledgerReq(out.requirement_id).status`，且台账恰好 1 条）；源码 `CreateRequirement.ts` 返回 `status: req.status` | ✅ |

- 补充锁定（父卡实施方案「增 `doc_location` 入参 + 输出 schema 增 `doc_location/defaults_used`」）：第 5 例断言入参 `parameters.properties.doc_location.type === 'string'`、输出 schema `properties.doc_location.type==='string'` 且 `properties.defaults_used.type==='array'` —— 工具壳确实暴露入参、返回键已被 schema 声明（`additionalProperties:false` 下不会因未声明键被 DSH 绑定层拒收）。
- 故障注入（验收标准附带的边界）：绝对路径 `/etc/passwd`、`C:\Windows` 与含 `..` 的 `../escape`、`docs/../../escape` 均抛 `REQBOARD_INVALID_INPUT`，且台账**零写入**（`store.snapshot().requirements` 长度 0）—— 不静默改路径。

## 3. 补充回归（直接消费方护栏，非父卡验收命令）

```bash
cd packages/web/dsh-pmboard
npx vitest run tests/output-contract.test.ts tests/tools-schema.test.ts tests/tools-dispatch.test.ts
```

实际输出：

```
 ✓ tests/tools-dispatch.test.ts (4 tests) 5ms
 ✓ tests/tools-schema.test.ts (3 tests) 3ms
 ✓ tests/output-contract.test.ts (21 tests) 87ms

 Test Files  3 passed (3)
      Tests  28 passed (28)
```

- 退出码：**0**。`output-contract`（`additionalProperties:false` 下输出键契约）、`tools-schema`（Schema 铁律冒烟）、`tools-dispatch`（工具分发）为 T-10 改动面（`CreateTool.ts` 增返回键）的直接护栏，全绿 —— 新增两个返回键既被声明、也未破坏旧契约。

## 4. 改动归属（本卡未改任何源码/用例）

```bash
git diff --numstat -- packages/web/dsh-pmboard/src/tools/CreateTool/CreateTool.ts \
  packages/web/dsh-pmboard/src/application/use-cases/CreateRequirement.ts \
  packages/web/dsh-pmboard/src/application/internal/support.ts
```

实际输出：

```
44	1	agent-dh/packages/web/dsh-pmboard/src/application/internal/support.ts
17	2	agent-dh/packages/web/dsh-pmboard/src/application/use-cases/CreateRequirement.ts
11	0	agent-dh/packages/web/dsh-pmboard/src/tools/CreateTool/CreateTool.ts
```

- 用例文件在 HEAD 上为 untracked：`?? agent-dh/packages/web/dsh-pmboard/tests/create-doc-location.test.ts`。
- 以上均为**父卡 t-fbde12（T-10，implement 阶段）的待提交工作区改动**；本卡（test 阶段）**只读不改**，本轮新增产物仅本证据文件 `docs/requirements/REQ-260924213231-b1c4/evidence/t-b1b27b-test.md`。HEAD = `9e5ebf60`（branch `main`），与上游复核记录 t-8e8f83 / 联调记录 t-d52c67 一致。

## 5. 测试结论

1. 目标命令 `npx vitest run tests/create-doc-location.test.ts`：**1 file / 5 tests 全绿，exit 0** —— 验收标准「目标命令输出全绿」达成。
2. 父卡三条业务口径（回落留痕且台账同值 / 自定义路径生效 / 返回 status 与台账一致）均由用例逐条锁定且通过；边界（非法位置）拒绝且不写台账亦被锁定。
3. 补充回归 `output-contract` + `tools-schema` + `tools-dispatch` **28/28 绿**，T-10 改动面（`CreateTool.ts` 新增返回键）无契约/Schema 回归。
4. 本卡为 test 阶段，只执行上述命令并落本记录；未修改任何实现或测试源码。
