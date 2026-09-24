# t-52d7fe 联调记录（父卡「新增 kind=design 登记用例与工具入口」· 阶段 integrate）

- 联调时间：2026-09-24T23:51+0800
- 联调环境：node v22.23.2 · vitest 2.1.9（darwin-arm64）· HEAD 9e5ebf60 · 测试工作目录 `packages/web/dsh-pmboard`
- 联调对象（接口）：**I-1** `reqboard_submit(kind=design)`（工具）
  —— 工具壳 `packages/web/dsh-pmboard/src/tools/SubmitTool/SubmitTool.ts`（schema + 表驱动分派）
  → 用例 `packages/web/dsh-pmboard/src/application/use-cases/SubmitDesignArtifacts.ts`
  （契约见 `docs/requirements/REQ-260924213231-b1c4/design/interfaces.md` §I-1、错误语义 ¥E-1/E-2）
- 结论：**接口联调通过** —— 请求样例、期望响应、实际返回三者一致（17/17 例 MATCH）；
  目标测试 `design-registration.test.ts` 9/9 绿；无本卡引入的回归（`design-completeness-gate.test.ts` 的 2 处失败
  在基线 HEAD 上同样失败，属既有问题，见 §3.2）。

---

## 1. 接口三方对照（核心验收）

联调方式：在本轮内运行**临时探针** `tests/__probe-t52d7fe.test.ts`（跑完即删，不入库），
以 `defineSubmitTool(deps)` 构造真实工具并 `execute`，逐用例打印「请求样例 / 期望响应 / 实际返回」，
由探针逐条比对（`verdict` 由 `JSON.stringify(expected) === JSON.stringify(actual)` 得出）。
测试夹具：临时工作区 + `JsonLedgerRepository` + `FileDocRepository`，需求 `REQ-d30001`（status=design，绑定窗口 `session-t52d7fe-001`），
磁盘预置 `docs/requirements/REQ-d30001/design/` 下 5 份 .md。

### C1 — 工具入口接线：schema enum 与权威常量

| 项 | 内容 |
|---|---|
| 请求样例 | `defineSubmitTool(deps).parameters.properties.kind.enum`；`SUBMIT_KINDS` |
| 期望响应 | `["requirement","plan","verification","archive","design"]` |
| 实际返回 | `["requirement","plan","verification","archive","design"]`（两处均相同） |
| 判定 | **一致（MATCH）** |

### C2 — 首次 `{kind:'design'}`：扫 design/ 登记 5 份

| 项 | 内容 |
|---|---|
| 请求样例 | `{kind:'design'}`（窗口 `session-t52d7fe-001`，需求 `REQ-d30001`，design/ 下 5 份 .md） |
| 期望响应 | `{success:true, requirement_id:'REQ-d30001', registered_count:5}`；`design_docs` 5 行（name/path/on_disk:true/registered:true/confirmed:false）；台账 5 条 kind=design；note 含 `reqboard_ask_confirm` |
| 实际返回 | 与期望逐字段相同（见下） |
| 判定 | **一致（MATCH，4/4 子项）** |

```
C2.head         expected={"success":true,"requirement_id":"REQ-d30001","registered_count":5}
                actual  ={"success":true,"requirement_id":"REQ-d30001","registered_count":5}   MATCH
C2.design_docs  expected=[{name:architecture.md,path:docs/requirements/REQ-d30001/design/architecture.md,on_disk:true,registered:true,confirmed:false},
                          {data-model.md,...},{interfaces.md,...},{test-cases.md,...},{use-cases.md,...}]
                actual  = <与 EXPECTED 逐字符相同>                                              MATCH
C2.artifactCount expected=5   actual=5                                                          MATCH
C2.note-has-next expected=true actual=true（note 指向 reqboard_ask_confirm）                      MATCH
```

### C3 — 二次调用幂等

| 项 | 内容 |
|---|---|
| 请求样例 | 同 C2 再调一次 `{kind:'design'}` |
| 期望响应 | `{success:true, registered_count:0}`；台账仍 5 条；5 行 `registered` 全为 true |
| 实际返回 | `{success:true, registered_count:0}`；台账 5 条；`[true,true,true,true,true]` |
| 判定 | **一致（MATCH，3/3 子项）** |

### C4 — `path` 单份登记

| 项 | 内容 |
|---|---|
| 请求样例 | `{kind:'design', path:'docs/requirements/REQ-d30001/design/architecture.md'}`（5 份在盘） |
| 期望响应 | `{registered_count:1, artifactPaths:['docs/requirements/REQ-d30001/design/architecture.md']}` |
| 实际返回 | `{registered_count:1, artifactPaths:['docs/requirements/REQ-d30001/design/architecture.md']}` |
| 判定 | **一致（MATCH）** |

### C5 — 登记入口确实被闸门读到（G2 不再报 missing）

| 项 | 内容 |
|---|---|
| 请求样例 | 登记 5 份后 `assertArtifactGates(req,'design','decomposing')` |
| 期望响应 | `code='artifact_not_confirmed'`（不再是 missing_artifact） |
| 实际返回 | `code='artifact_not_confirmed'` |
| 判定 | **一致（MATCH）** |

### C6 — 错误语义（E-1/E-2 + 归属校验）

| 用例 | 请求样例 | 期望响应 | 实际返回 | 判定 |
|---|---|---|---|---|
| C6a | `{kind:'design', path:'docs/../etc/passwd'}` | 抛错含 `REQBOARD_ARTIFACT_NOT_OPENABLE` | true | **一致** |
| C6b | `{kind:'design', path:'.../design/nope.md'}` | 抛错含 `REQBOARD_FILE_MISSING` | true | **一致** |
| C6c | 需求绑定在别的窗口 `{kind:'design'}` | 抛错含 `REQBOARD_NO_BOUND_REQ` | true | **一致** |

### C7 — 空目录：0 登记不谎报成功

| 项 | 内容 |
|---|---|
| 请求样例 | `{kind:'design'}`（design/ 不存在） |
| 期望响应 | `{success:false, registered_count:0}`；note 含「未发现可登记的设计文档」；台账 0 条 |
| 实际返回 | `{success:false, registered_count:0}`；note 命中该文案；台账 0 条 |
| 判定 | **一致（MATCH，3/3 子项）** |

探针 17 条 verdict 全为 MATCH，脚本退出码 0：

```
 ✓ tests/__probe-t52d7fe.test.ts (7 tests)
 Test Files  1 passed (1)
      Tests  7 passed (7)
```

## 2. 目标命令与输出摘要

### 2.1 本卡接口联调探针（命令 1）

```bash
cd packages/web/dsh-pmboard
npx vitest run tests/__probe-t52d7fe.test.ts        # 临时文件，跑完已删
```

实际输出摘要：`Test Files 1 passed (1)` / `Tests 7 passed (7)`，17/17 `verdict=MATCH`，退出码 0。

### 2.2 父卡自带实现测试（命令 2）

```bash
cd packages/web/dsh-pmboard
npx vitest run tests/design-registration.test.ts
```

实际输出：

```
 ✓ tests/design-registration.test.ts (9 tests) 86ms
 Test Files  1 passed (1)
      Tests  9 passed (9)
```

- 期望：全绿（TC-1 正向/幂等/部分新增/G2 读得到、TC-19 空目录、I-1 path 语义、归属校验）
- 实际：9/9 通过，退出码 0 —— 与期望一致

## 3. 回归与边界

### 3.1 关联回归集（命令 3）

```bash
cd packages/web/dsh-pmboard
npx vitest run tests/design-registration.test.ts tests/tools-dispatch.test.ts tests/tools-schema.test.ts \
  tests/contract-shapes.test.ts tests/output-contract.test.ts tests/design-doc-policy.test.ts \
  tests/design-completeness-gate.test.ts
```

实际输出摘要：`Test Files 1 failed | 6 passed (7)` / `Tests 2 failed | 71 passed (73)`。
失败集中在 `tests/design-completeness-gate.test.ts` 的两处 `ask_confirm` 断言
（`out.gate_failure?.code` 为 undefined，gaps 不含 `use-cases.md 未确认`），与 `kind=design` 登记入口无关。

### 3.2 失败归因：既有问题，非本卡引入

在**基线 HEAD（9e5ebf60，未含本卡改动）**用独立 worktree 复跑同一测试：

```bash
git worktree add --detach /tmp/pmbase-t52d7fe 9e5ebf60
ln -s <agent-dh>/packages/web/dsh-pmboard/node_modules /tmp/pmbase-t52d7fe/agent-dh/packages/web/dsh-pmboard/node_modules
cd /tmp/pmbase-t52d7fe/agent-dh/packages/web/dsh-pmboard && npx vitest run tests/design-completeness-gate.test.ts
```

基线与工作区**同为 2 处失败**（基线：`Tests 2 failed | 14 passed (16)`；工作区：`2 failed | 71 passed` 中的同一 2 例）。
即该 2 例失败在 HEAD 上已存在，属 FR-2 闸门（`application/internal/design-gates.ts` / `AskConfirm.ts`）路径的既有缺口，
本卡改动的文件（SubmitDesignArtifacts.ts / SubmitTool.ts / prompt.ts）均不参与该路径。
worktree 已 `git worktree remove --force` 清理，探针文件已删除。

## 4. 结论

1. I-1 `reqboard_submit(kind=design)` 的**输入契约**（kind enum 含 design）与**输出契约**
   （success / requirement_id / design_docs[] / registered_count / note）经真实工具 `execute` 调用验证，
   请求样例、期望响应、实际返回**三者一致**（17/17 MATCH）。
2. 幂等（二次 registered_count=0）、单份 path 登记、E-1/E-2/归属错误语义、空目录不谎报成功，均按 `interfaces.md` §I-1 契约落地。
3. 登记入口确实被 G2 闸门读到（`artifact_not_confirmed`，不再是 `missing_artifact`），达成 FR-1「登记入口 agent 可触发」的接口面验收。
4. 本卡未引入回归；`design-completeness-gate.test.ts` 的 2 处失败为基线既有问题，需由 FR-2 所属卡片处理。
