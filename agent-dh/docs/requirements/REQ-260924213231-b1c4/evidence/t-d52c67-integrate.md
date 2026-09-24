# t-d52c67 联调记录（父卡 t-fbde12 / T-10「立项降级路径不丢文档位置」· 阶段 integrate）

- 联调时间：2026-09-25T01:34+0800
- 联调环境：node v22.23.2 · vitest 2.1.9 (darwin-arm64) · HEAD `9e5ebf60`（branch `main`）· 测试工作目录 `packages/web/dsh-pmboard`
- 联调对象（接口 **I-6** `reqboard_create` 的 `doc_location` 降级补齐，FR-7 / UC-4 / TC-11~TC-13）：
  - 工具壳 `packages/web/dsh-pmboard/src/tools/CreateTool/CreateTool.ts`（入参 schema 增 `doc_location`；输出 schema 增 `doc_location` / `defaults_used`）
  - → 用例 `packages/web/dsh-pmboard/src/application/use-cases/CreateRequirement.ts`（`resolveDocBasePath` → `createRequirementDirect({ …docBasePath })`；返回补 `doc_location`/`defaults_used`）
  - → 内部 `packages/web/dsh-pmboard/src/application/internal/support.ts`（`resolveDocBasePath` 取值/回落/拒绝 + `createRequirementDirect` 把回落值写进台账 `docBasePath`）
  - 消费端同源校验：`src/application/internal/node-input-package.ts` 的 `requirementDocPath()`
  - 契约见 `docs/requirements/REQ-260924213231-b1c4/design/interfaces.md` §I-6、错误语义 E-6
- 结论：**接口联调通过** —— 请求样例、期望响应、实际返回**三者一致**（19/19 例 MATCH）；目标测试 `create-doc-location.test.ts` 5/5 绿；接口层回归 `tools-dispatch.test.ts` 4/4 绿。

---

## 1. 接口 I-6 三方对照（核心验收）

联调方式：在本轮内运行**临时探针** `tests/__probe-td52c67.test.ts`（跑完即删），对 **真工具定义**（`defineCreateTool`）+ **真适配器**（`JsonLedgerRepository` / `FileDocRepository` / `SystemClock` / `RandomIdFactory` / `SessionProbeAdapter` / `UserQuestionsAdapter`）发真实调用，走完整「工具壳 → 用例 → 内部 → 台账」链路，逐字段打印并比较「请求样例 / 期望响应 / 实际返回」。每例独立临时台账（`beforeEach` 新建 `mkdtemp` store），窗口 `session-td52c67`。

### A. 不传 `doc_location`（回落 + 留痕，TC-11）

请求样例：`reqboard_create({ title: "降级路径立项A", category: "feature" })`

| 断言项 | 期望响应 | 实际返回 | 判定 |
|---|---|---|---|
| `success` | `true` | `true` | MATCH |
| `doc_location` | `"docs/requirements/<REQ>/"`（`CAPTURE_DEFAULTS.docLocation`） | `"docs/requirements/<REQ>/"` | MATCH |
| `defaults_used` | `["doc_location"]`（`CAPTURE_QUESTION_IDS.doc_location`） | `["doc_location"]` | MATCH |
| `status` = 台账 `status` | `"draft"` | `"draft"` | MATCH |
| 台账 `docBasePath` = 返回 `doc_location` | `"docs/requirements/<REQ>/"` | `"docs/requirements/<REQ>/"` | MATCH |
| `requirementDocPath(台账)`（消费端同源） | `docs/requirements/<REQ-id>/requirement.md` | `docs/requirements/REQ-260925013355-94fc/requirement.md` | MATCH |
| `note` 明示回落 | 含「回落」 | 含「回落」 | MATCH |

实测原始返回（tsx 探针，真实 id）：

```json
{"success":true,"requirement_id":"REQ-260925013333-9fe8","title":"降级路径立项A","category":"feature","status":"draft","doc_location":"docs/requirements/<REQ>/","defaults_used":["doc_location"],"note":"已直接立项（创建即立项）：REQ 已在看板 draft 泳道立即可见，本窗口已绑定。未提供 doc_location → 已回落默认文档位置 docs/requirements/<REQ>/（见 defaults_used，不静默猜）。","board_link":"/dashboard#pmboard?req=REQ-260925013333-9fe8"}
```

台账实测：`docBasePath="docs/requirements/<REQ>/"`；`requirementDocPath` → `"docs/requirements/REQ-260925013333-9fe8/requirement.md"`
（回落值落在**台账**而不只留在返回体——堵住「换个地方丢第四问」）。

### B. 传 `doc_location="docs/rfcs/"`（显式路径生效，TC-12）

请求样例：`reqboard_create({ title: "降级路径立项B", category: "doc", doc_location: "docs/rfcs/" })`

| 断言项 | 期望响应 | 实际返回 | 判定 |
|---|---|---|---|
| `doc_location` | `"docs/rfcs/"` | `"docs/rfcs/"` | MATCH |
| `defaults_used` | `[]`（未走默认） | `[]` | MATCH |
| 台账 `docBasePath` | `"docs/rfcs/"` | `"docs/rfcs/"` | MATCH |
| `requirementDocPath(台账)` | `docs/rfcs/<REQ-id>/requirement.md` | `docs/rfcs/REQ-260925013355-c433/requirement.md` | MATCH |

实测原始返回：

```json
{"success":true,"requirement_id":"REQ-260925013333-20d2","title":"降级路径立项B","category":"doc","status":"draft","doc_location":"docs/rfcs/","defaults_used":[],"note":"已直接立项（创建即立项）：REQ 已在看板 draft 泳道立即可见，本窗口已绑定。文档位置：docs/rfcs/。","board_link":"/dashboard#pmboard?req=REQ-260925013333-20d2"}
```

### C. 非法形态（故障注入，E-6）

请求样例：`doc_location` ∈ `"/etc/passwd"` / `"../escape"` / `"docs/../../escape"` / `"C:\\Windows"`

| 请求样例 | 期望响应 | 实际返回 | 判定 |
|---|---|---|---|
| `/etc/passwd` | 抛 `REQBOARD_INVALID_INPUT` | `code=REQBOARD_INVALID_INPUT` | MATCH |
| `../escape` | 抛 `REQBOARD_INVALID_INPUT` | `code=REQBOARD_INVALID_INPUT` | MATCH |
| `docs/../../escape` | 抛 `REQBOARD_INVALID_INPUT` | `code=REQBOARD_INVALID_INPUT` | MATCH |
| `C:\\Windows` | 抛 `REQBOARD_INVALID_INPUT` | `code=REQBOARD_INVALID_INPUT` | MATCH |
| 台账条数 | `0`（不静默改路径、不落库） | `0` | MATCH |

实测消息（节选）：`reqboard_create 未执行：doc_location 必须是工作区相对目录（收到 /etc/passwd）——绝对路径与含 .. 的路径一律不接受，不静默改路径（REQBOARD_INVALID_INPUT）`

### D. schema 面（DSH 绑定层不拒收）

| 断言项 | 期望 | 实际 | 判定 |
|---|---|---|---|
| `parameters.properties.doc_location.type` | `"string"` | `"string"` | MATCH |
| `output.schema.properties.doc_location.type` | `"string"` | `"string"` | MATCH |
| `output.schema.properties.defaults_used.type` | `"array"` | `"array"` | MATCH |

**探针汇总：19/19 MATCH → `Test Files 1 passed` / `Tests 4 passed`。**

## 2. 目标命令：父卡回归测试（命令与输出摘要）

```bash
cd packages/web/dsh-pmboard
npx vitest run tests/create-doc-location.test.ts
```

实际输出：

```
 RUN  v2.1.9 /Users/yunpeng/pi-investment/agent-dh/packages/web/dsh-pmboard

 ✓ tests/create-doc-location.test.ts (5 tests) 24ms

 Test Files  1 passed (1)
      Tests  5 passed (5)
```

- 退出码：**0**（全绿）
- 5 例分别锁定：TC-11 回落+留痕+台账同值；TC-12 显式路径生效+产物路径同源；TC-13 返回 `status` 与台账一致；异常流 4 种非法形态拒绝且不写台账；schema 声明三键。

## 3. 接口层回归（命令与输出摘要）

```bash
cd packages/web/dsh-pmboard
npx vitest run tests/tools-dispatch.test.ts
```

实际输出：

```
 ✓ tests/tools-dispatch.test.ts (4 tests) 5ms

 Test Files  1 passed (1)
      Tests  4 passed (4)
```

- 退出码：**0** —— `reqboard_create` 分派链未因新增入参/返回键回归。

## 4. 联调结论

1. 接口 I-6 的**请求样例 → 期望响应 → 实际返回**三方一致（19/19 MATCH）：不传 `doc_location` 显式回落默认并在 `defaults_used` 留痕、台账 `docBasePath` 同值；传 `docs/rfcs/` 路径生效且产物路径按它生成；返回 `status` 与台账一致；非法形态响亮失败不落库。FR-7「降级路径不丢第四问」在本轮实测成立。
2. 目标测试 `create-doc-location.test.ts` 5/5 绿（exit 0），接口层回归 `tools-dispatch.test.ts` 4/4 绿。
3. 本卡为 integrate 阶段：联调走**临时探针**（运行后已删除），**未修改任何实现或测试源码**，本轮新增产物仅本文件。
4. 工作区状态：上述三份实现源码 + `tests/create-doc-location.test.ts` 为父卡 T-10（`t-fbde12`）的待提交改动（本卡未触碰）；HEAD = `9e5ebf60`（branch `main`）。
