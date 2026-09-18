---
req_id: REQ-d3e61a
kind: design-data-model
---

# 数据模型（serves: FR-2, FR-4, FR-9）

本需求**不新增数据库表**——校验对象是文档文本，判定结果是返回值（不落库）。

## D-DATA-1 编号模型 `serves: FR-2`

```ts
type DocKind = 'requirement'|'design'|'decomposition'|'task'|'testcase'|'evidence'|'verification'

interface NumberedItem {
  id: string         // 本编号，如 FR-1 / T-3 / TC-007 / D-ARCH-2
  serves: string[]   // 上游编号（必填，须指向真实存在者）
  kind: DocKind
  title?: string     // 业务语言标题
}
```

**编号前缀表**（与标准 §八 一致）：根编号按立项类型（FR- / BUG- / RF- / SP- / DOC- / CH-），
下游全类型统一（T- / D-域- / BE- / FE- / TC- / E-）。

**解析规则**：从**表格行首列**取 id、从 serves 列取上游；front-matter 只放文档级索引。
同一条状态**只写一处**（表格行），避免"两份真相"漂移（FR-14）。

## D-DATA-2 校验结果模型 `serves: FR-12`

```ts
interface GateFailure {
  code: 'missing_artifact' | 'artifact_not_confirmed'   // 现有两级，不动
      | 'requirement_uncovered'   // FR-1  条款无落点
      | 'dangling_reference'      // FR-2  serves 指向不存在
      | 'orphan_clause'           // FR-2  根编号无下游
      | 'no_e2e_case'             // FR-11 测试策略缺 E2E
      | 'acceptance_incomplete'   // FR-10 验收项缺四件套
      | 'task_card_incomplete'    // FR-6  任务卡缺业务三要素
  kind: ArtifactKind
  message: string
  gaps?: string[]    // 结构化缺口（编号清单），供 agent 精确修复与 UI 标红
}
```

## D-DATA-3 三方一致性模型 `serves: FR-9`

```ts
interface ConsistencyRow {
  requirementId: string   // 做什么（根编号）
  designIds: string[]     // 怎么做（设计编号）
  taskIds: string[]       // 实际做了什么
  evidence: string[]      // 证据
  verdict: 'consistent' | 'design_missing' | 'impl_missing'
         | 'out_of_scope' | 'mismatch'
}
```

**判定规则**（四缺一即显式出现，不允许沉默）：
- 有 requirementId、无 designIds → design_missing
- 有 designIds、无 taskIds/evidence → impl_missing
- 无 requirementId、有 taskIds → out_of_scope
- 三方都有但 serves 对不上 → mismatch
