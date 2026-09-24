# REQ-260922133212-dd5b 验收文档

> 自动生成于 reqboard_submit(kind=verification) · 验收单 v1

**交付结论**：REQ-260922133212-dd5b 交付完成：BUG-1 归档目录校验兼容新旧两种 REQ id（正则按生成器真身 YYMMDDHHmmss-xxxx 校准，25/25 测试绿）；BUG-2 部署后补交 REQ-260922012924-2e29 归档材料成功（修复前必现 REQBOARD_INVALID_INPUT），台账 archive 就位，体检退出码 0。新格式需求的归档制度恢复生效。

## 1. 验收列表

### v1-1 · [BUG-1] 归档目录校验兼容新旧两种需求 id 格式

**验收内容**：【[BUG-1] 归档目录校验兼容新旧两种需求 id 格式】验收：cd agent-dh && npx vitest run packages/web/dsh-pmboard/tests/requirement-dir-pattern.test.ts → passed（5 用例：旧格式过/新格式过/非法 id 拒/层级错误拒/尾部多段拒）；连带 migration+acceptance-archive 套件无新失败。

**操作步骤**：
1. cd agent-dh && npx vitest run packages/web/dsh-pmboard/tests/requirement-dir-pattern.test.ts → passed（5 用例：旧格式过/新格式过/非法 id 拒/层级错误拒/尾部多段拒）
2. 连带 migration+acceptance-archive 套件无新失败。

**预期结果**：按上述步骤执行后满足验收标准：cd agent-dh && npx vitest run packages/web/dsh-pmboard/tests/requirement-dir-pattern.test.ts → passed（5 用例：旧格式过/新格式过/非法 id 拒/层级错误拒/尾部多段拒）；连带 migration+acceptance-archive 套件无新失败。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-2 · [BUG-2] 部署并补交 REQ-260922012924-2e29 归档材料闭环验证

**验收内容**：【[BUG-2] 部署并补交 REQ-260922012924-2e29 归档材料闭环验证】验收：①reqboard_submit(kind=archive) 返回 success=true；②台账 REQ-260922012924-2e29.archive.dir=docs/requirements/REQ-260922012924-2e29 且 archive 字段非空（可读 dsh-reqboard.json 核验）；③./scripts/restart-with-build.sh --check 退出码 0。

**操作步骤**：
1. ①reqboard_submit(kind=archive) 返回 success=true
2. ②台账 REQ-260922012924-2e29.archive.dir=docs/requirements/REQ-260922012924-2e29 且 archive 字段非空（可读 dsh-reqboard.json 核验）
3. ③./scripts/restart-with-build.sh --check 退出码 0。

**预期结果**：按上述步骤执行后满足验收标准：①reqboard_submit(kind=archive) 返回 success=true；②台账 REQ-260922012924-2e29.archive.dir=docs/requirements/REQ-260922012924-2e29 且 archive 字段非空（可读 dsh-reqboard.json 核验）；③./scripts/restart-with-build.sh --check 退出码 0。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-3 · 需求级验收

**验收内容**：需求级：交付结论可复核（证据齐全、与设计一致、无范围蔓延）

**操作步骤**：
1. 需求级：交付结论可复核（证据齐全、与设计一致、无范围蔓延）

**预期结果**：按上述步骤执行后满足验收标准：需求级：交付结论可复核（证据齐全、与设计一致、无范围蔓延）

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-6 · 需求级验收

**验收内容**：E2E 覆盖：**无（缺口）**——本需求交付涉及多组件串联，但只交了单元/集成测试。请补一条端到端场景用例（断言可观察终态）。

**操作步骤**：
1. E2E 覆盖：**无（缺口）**——本需求交付涉及多组件串联，但只交了单元/集成测试。请补一条端到端场景用例（断言可观察终态）。

**预期结果**：按上述步骤执行后满足验收标准：E2E 覆盖：**无（缺口）**——本需求交付涉及多组件串联，但只交了单元/集成测试。请补一条端到端场景用例（断言可观察终态）。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

## 2. 测试报告

- vitest run requirement-dir-pattern + migration + acceptance-archive → Tests 25 passed (25)
- reqboard_submit(kind=archive, REQ-260922012924-2e29) → success=true（修复前同调用 REQBOARD_INVALID_INPUT）
- 台账核验：archive.dir=docs/requirements/REQ-260922012924-2e29，mergedInto 正确，17 份文档全列入
- ./scripts/restart-with-build.sh --check → 退出码 0；--build-only 20/20 通过
- 评审报告 reviews/self-review.md（如实记录：工具中断期顺序偏离已补账；正则首版臆造被测试纠正）

## 3. 文档完整性检查

✓ 9 类文档齐全

## 4. 验收结果

| 编号 | 验收项 | 状态 | 验收人 | 验收时间 |
|---|---|---|---|---|
| v1-1 | [BUG-1] 归档目录校验兼容新旧两种需求 id 格式 | ✓ 通过 | human/session-9faaac35-2641-473c-a5dc-ea6e6d11efbf | 2026-09-22 14:46 |
| v1-2 | [BUG-2] 部署并补交 REQ-260922012924-2e29 归档材料闭环验证 | ✓ 通过 | human/session-9faaac35-2641-473c-a5dc-ea6e6d11efbf | 2026-09-22 14:46 |
| v1-3 | 需求级验收 | ✓ 通过 | human/session-9faaac35-2641-473c-a5dc-ea6e6d11efbf | 2026-09-22 14:46 |
| v1-6 | 需求级验收 | ✓ 通过 | human/session-9faaac35-2641-473c-a5dc-ea6e6d11efbf | 2026-09-22 14:46 |
