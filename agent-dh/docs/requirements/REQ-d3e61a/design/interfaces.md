---
req_id: REQ-d3e61a
kind: design-interfaces
---

# 接口设计（serves: FR-1, FR-10, FR-12）

## D-IF-1 内部接口：内容校验纯函数 `serves: FR-12`

```ts
// application/internal/content-gates.ts
export function parseDocument(text: string): ParsedDoc
export function checkClauseCoverage(
  requirement: ParsedDoc, tasks: ParsedDoc[], opts?: { exempt?: boolean }
): { gaps: string[] }
export function checkNumberChain(items: NumberedItem[]): { dangling: string[]; orphans: string[] }
export function checkAcceptanceKit(verification: ParsedDoc): { missing: string[] }
export function checkE2ECoverage(requirement: ParsedDoc): { hasE2E: boolean }
```

**错误契约**：纯函数**不抛异常**——一律返回结构化缺口（数组为空 = 通过）。
异常只保留给"输入完全无法解析"（如二进制内容）。

## D-IF-2 既有接口变更：三级门禁 `serves: FR-12`

```ts
// application/internal/artifact-gates.ts —— 签名不变，只加第三级
export function assertArtifactGates(
  req: RequirementRecord, from: RequirementStatus, to: RequirementStatus,
): GateFailure | undefined
```

- **向后兼容**：返回值类型只**扩充** code 联合（新增 7 个 code），旧调用方按既有 code 分支不受影响。
- **豁免**：req.artifacts 为空（isLegacy）→ 第三级**跳过**，与现有两级行为一致。

## D-IF-3 工具参数变更 `serves: FR-1, FR-6`

| 工具 | 参数 | 变更 |
|------|------|------|
| reqboard_submit(kind=plan) | tasks[] | **新增必填** requirementRefs: string[]（本卡交付的根编号） |
| reqboard_decompose | tasks[] | 同上；且校验 key 集合与已批准计划一致（既有行为保留） |
| reqboard_task_move(to=done) | — | 校验任务卡 front-matter 有 requirementRefs、验收含可执行命令 |

**错误码**（HTTP 409）：

| 码 | 触发 | 返回体 |
|----|------|--------|
| REQUIREMENT_COVERAGE_FAILED | 条款无落点 | { gaps: ['FR-7'] } |
| DANGLING_REFERENCE | serves 指向不存在 | { dangling: ['T-3→FR-99'] } |
| ACCEPTANCE_INCOMPLETE | 验收项缺四件套 | { missing: ['FR-7: 怎么验'] } |
| NO_E2E_CASE | 测试策略无 E2E | { hasE2E: false } |

## D-IF-4 前后端协作 `serves: FR-12`

- **后端**：本节 1–3 即全部后端契约；**无新增对外 HTTP 端点**（校验在插件进程内执行）。
- **前端**：本轮**不改** web 端渲染——除验收单多一类"需求级"分组的必要展示（见 ui.md）。
- **联调清单**：① 构造违规文档 → 返回 409 + 结构化缺口；② 构造合规文档 → 放行；
  ③ 存量需求 → 只警告不拦。
