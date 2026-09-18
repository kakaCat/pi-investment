---
req_id: REQ-d3e61a
kind: design-test-cases
---

# 测试用例（serves: FR-1 .. FR-16）

## D-TEST-1 用例表 `serves: FR-1 .. FR-16`

| 用例ID | 层级 | 场景 | 预期 | serves |
|--------|------|------|------|--------|
| TC-001 | unit | 需求有条款、任务无引用 | gaps=['FR-7'] | FR-1 |
| TC-002 | unit | 同上但标"本轮不做+理由" | gaps=[] 通过 | FR-1 |
| TC-003 | unit | serves 指向不存在编号 | dangling 非空 | FR-2 |
| TC-004 | unit | 根编号无任何下游 | orphans 含该编号 | FR-2 |
| TC-005 | unit | 验收项缺"怎么验" | missing 非空 | FR-10 |
| TC-006 | unit | 测试策略无 E2E 行 | hasE2E=false | FR-11 |
| TC-007 | unit | 旧卡（title=规则自愈，无三要素） | 判定不合格 | FR-6 |
| TC-008 | unit | 删掉 BASE 公共节 | 六类**全部**不合格 | FR-15 |
| TC-009 | integration | 拆分提交含未覆盖条款 | 409 + gaps | FR-1 |
| TC-010 | integration | 任务卡缺 evidence 结单 | 被凭证门拒绝 | FR-4 |
| TC-011 | integration | 设计章节缺 serves 提交计划 | 409 | FR-5 |
| TC-012 | integration | 存量需求（artifacts 为空）提交 | 只警告**不拦** | FR-12 |
| **TC-013** | **E2E** | 需求→拆分→缺条款→**被拦**→补卡→通过 | 全链路可观察终态 | FR-1, FR-12 |
| **TC-014** | **E2E** | 交付→三方一致性验收单→R9 场景显示「设计缺失/实施缺失」 | 验收单行可见 | FR-9 |

## D-TEST-2 测试层级声明 `serves: FR-11`

| 层级 | 数量 | 说明 |
|------|------|------|
| 单元 | 8 | 纯函数边界，无 IO |
| 集成 | 4 | 门禁接线（含存量豁免） |
| **E2E** | **2** | 两条完整业务链路，断言**可观察终态**（非"函数被调用过"） |

## D-TEST-3 明确不覆盖 `serves: FR-11`

- 前端渲染（本轮不改 web 端，除验收单分组展示）；
- 真实 LLM 提示词效果（只验"注入了什么"，不验"模型听没听"）。
