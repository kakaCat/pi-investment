# REQ-f0579a 验收文档

> 自动生成于 reqboard_submit(kind=verification) · 验收单 v1

**交付结论**：REQ-f0579a 审计整改全部交付：17 个失败测试（10 文件）已全部转绿，全量 114 文件 / 1407 用例 0 失败。

五任务落点：
- t-b96644（FR-1）：verdicts.ts 删除 confirm_override 早退分支，覆盖通过走统一留痕路径（acceptanceOverride 台账/评论/状态事件三处）
- t-f54dcc（FR-2）：看板三处回归恢复（done 需求归验收泳道、底部归档条回归、产物标签=种类可读名·文件名）
- t-632e7c（FR-3）：操作条断言精确化——验收态仅允许「立项取消」move-req（canceled），两条用户裁定的合并点在测试注释写明
- t-0c3303（FR-4）：架构门禁债——两新工具 output.schema 补声明 error/stages/next_step/workflow；状态判断下沉 domain（isWorkflowRunCompleted）；修出扫描器盲区根因（正则裸反引号被当模板串起点吞掉全文 return，改写 \x60）
- t-cee913（FR-5）：index.ts 432→379、styles/base.ts 408→397（尺寸门禁达标）；删 CaptureHook.ts.backup 死文件；renderMarkdown 链接协议白名单（javascript:/data: 不再渲染为可点链接）

提交：083ca476（t-0c3303+t-cee913）及前序任务各自提交。设计/评审/测试证据文档已按 AC-7.5 补齐（design×4 / reviews / tests）。

## 1. 验收列表

### v1-1 · 修 verdicts.ts 覆盖通过丢留痕

**验收内容**：【修 verdicts.ts 覆盖通过丢留痕】验收：npx vitest run tests/verify-override.test.ts tests/acceptance-archive.test.ts tests/e2e-accept-override.test.ts 全绿；覆盖通过台账含 acceptanceOverride（failed/pending/noMaterials 三字段）

**操作步骤**：
1. npx vitest run tests/verify-override.test.ts tests/acceptance-archive.test.ts tests/e2e-accept-override.test.ts 全绿
2. 覆盖通过台账含 acceptanceOverride（failed/pending/noMaterials 三字段）

**预期结果**：按上述步骤执行后满足验收标准：npx vitest run tests/verify-override.test.ts tests/acceptance-archive.test.ts tests/e2e-accept-override.test.ts 全绿；覆盖通过台账含 acceptanceOverride（failed/pending/noMaterials 三字段）

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-2 · 恢复看板视图三处回归

**验收内容**：【恢复看板视图三处回归】验收：npx vitest run tests/client-view.test.ts 全绿；buildBoard 输出含 dsh-pm-archived-bar 与「待归档」；产物标签含种类可读名且保留文件名（af8a2ac0 诉求）

**操作步骤**：
1. npx vitest run tests/client-view.test.ts 全绿
2. buildBoard 输出含 dsh-pm-archived-bar 与「待归档」
3. 产物标签含种类可读名且保留文件名（af8a2ac0 诉求）

**预期结果**：按上述步骤执行后满足验收标准：npx vitest run tests/client-view.test.ts 全绿；buildBoard 输出含 dsh-pm-archived-bar 与「待归档」；产物标签含种类可读名且保留文件名（af8a2ac0 诉求）

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-3 · 精确化操作条 move-req 断言

**验收内容**：【精确化操作条 move-req 断言】验收：npx vitest run tests/board-info-fixes.test.ts 全绿；b2b37d9b 新增的立项取消 3 用例保持绿

**操作步骤**：
1. npx vitest run tests/board-info-fixes.test.ts 全绿
2. b2b37d9b 新增的立项取消 3 用例保持绿

**预期结果**：按上述步骤执行后满足验收标准：npx vitest run tests/board-info-fixes.test.ts 全绿；b2b37d9b 新增的立项取消 3 用例保持绿

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-4 · 清偿架构门禁债

**验收内容**：【清偿架构门禁债】验收：npx vitest run tests/output-contract.test.ts tests/layer-boundary.test.ts tests/tools-dispatch.test.ts tests/message-hygiene.test.ts 全绿

**操作步骤**：
1. npx vitest run tests/output-contract.test.ts tests/layer-boundary.test.ts tests/tools-dispatch.test.ts tests/message-hygiene.test.ts 全绿

**预期结果**：按上述步骤执行后满足验收标准：npx vitest run tests/output-contract.test.ts tests/layer-boundary.test.ts tests/tools-dispatch.test.ts tests/message-hygiene.test.ts 全绿

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-5 · 尺寸拆分、杂项清理与全量终验

**验收内容**：【尺寸拆分、杂项清理与全量终验】验收：size-budget 转绿（index.ts、styles/base.ts ≤400 行）；npx vitest run 全量 0 失败；tsc --noEmit 绿；pnpm build 成功且 verify-client-build 通过

**操作步骤**：
1. size-budget 转绿（index.ts、styles/base.ts ≤400 行）
2. npx vitest run 全量 0 失败
3. tsc --noEmit 绿
4. pnpm build 成功且 verify-client-build 通过

**预期结果**：按上述步骤执行后满足验收标准：size-budget 转绿（index.ts、styles/base.ts ≤400 行）；npx vitest run 全量 0 失败；tsc --noEmit 绿；pnpm build 成功且 verify-client-build 通过

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-6 · 需求级验收

**验收内容**：需求级：交付结论可复核（证据齐全、与设计一致、无范围蔓延）

**操作步骤**：
1. 需求级：交付结论可复核（证据齐全、与设计一致、无范围蔓延）

**预期结果**：按上述步骤执行后满足验收标准：需求级：交付结论可复核（证据齐全、与设计一致、无范围蔓延）

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-9 · 需求级验收

**验收内容**：E2E 覆盖：**无（缺口）**——本需求交付涉及多组件串联，但只交了单元/集成测试。请补一条端到端场景用例（断言可观察终态）。

**操作步骤**：
1. E2E 覆盖：**无（缺口）**——本需求交付涉及多组件串联，但只交了单元/集成测试。请补一条端到端场景用例（断言可观察终态）。

**预期结果**：按上述步骤执行后满足验收标准：E2E 覆盖：**无（缺口）**——本需求交付涉及多组件串联，但只交了单元/集成测试。请补一条端到端场景用例（断言可观察终态）。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-10 · 需求级验收

**验收内容**：三方一致性（做什么 × 怎么做 × 实际做了什么）：以下对不上——FR-1 设计缺失：没有任何设计章节服务它（知道要做什么，不知道怎么做的）；FR-2 设计缺失：没有任何设计章节服务它（知道要做什么，不知道怎么做的）；FR-3 设计缺失：没有任何设计章节服务它（知道要做什么，不知道怎么做的）；FR-4 设计缺失：没有任何设计章节服务它（知道要做什么，不知道怎么做的）；FR-5 设计缺失：没有任何设计章节服务它（知道要做什么，不知道怎么做的）。请补设计、补实施、或显式登记为不做。

**操作步骤**：
1. 三方一致性（做什么 × 怎么做 × 实际做了什么）：以下对不上——FR-1 设计缺失：没有任何设计章节服务它（知道要做什么，不知道怎么做的）
2. FR-2 设计缺失：没有任何设计章节服务它（知道要做什么，不知道怎么做的）
3. FR-3 设计缺失：没有任何设计章节服务它（知道要做什么，不知道怎么做的）
4. FR-4 设计缺失：没有任何设计章节服务它（知道要做什么，不知道怎么做的）
5. FR-5 设计缺失：没有任何设计章节服务它（知道要做什么，不知道怎么做的）。请补设计、补实施、或显式登记为不做。

**预期结果**：按上述步骤执行后满足验收标准：三方一致性（做什么 × 怎么做 × 实际做了什么）：以下对不上——FR-1 设计缺失：没有任何设计章节服务它（知道要做什么，不知道怎么做的）；FR-2 设计缺失：没有任何设计章节服务它（知道要做什么，不知道怎么做的）；FR-3 设计缺失：没有任何设计章节服务它（知道要做什么，不知道怎么做的）；FR-4 设计缺失：没有任何设计章节服务它（知道要做什么，不知道怎么做的）；FR-5 设计缺失：没有任何设计章节服务它（知道要做什么，不知道怎么做的）。请补设计、补实施、或显式登记为不做。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

## 2. 测试报告

- npx vitest run → Test Files 114 passed (114) / Tests 1407 passed (1407)（审计时 10 failed / 17 failed）
- npx tsc --noEmit → exit 0
- pnpm build → exit 0；verify-client-build OK bundle=232888 bytes（WRAP_SENTINEL 哨兵在位）
- 覆盖通过留痕：tests/verify-override.test.ts + acceptance-archive.test.ts + e2e-accept-override.test.ts 全绿（acceptanceOverride 写台账）
- 看板回归：tests/client-view.test.ts 全绿（done 泳道 / 归档条 / 产物标签=种类名·文件名）
- 架构门禁：tests/output-contract.test.ts + layer-boundary + tools-dispatch + message-hygiene 36/36 绿
- 尺寸门禁：tests/size-budget.test.ts 绿（index.ts 379 / styles/base.ts 397 / board.ts 400，均 ≤400）
- XSS 回归：tests/markdown-links.test.ts 3/3（javascript:/data: 不渲染为链接，http/https/mailto/相对路径正常）
- git 提交：083ca476（12 文件 +245/-82）
- 文档：docs/requirements/REQ-f0579a/design/{architecture,data-model,interfaces,test-cases}.md、reviews/self-review.md、tests/final-verification.md

## 3. 文档完整性检查

✓ 9 类文档齐全

## 4. 验收结果

| 编号 | 验收项 | 状态 | 验收人 | 验收时间 |
|---|---|---|---|---|
| v1-1 | 修 verdicts.ts 覆盖通过丢留痕 | ✓ 通过 | human/session-dd6cfa29-d8ff-43fe-99d7-371a69442076 | 2026-09-20 21:19 |
| v1-2 | 恢复看板视图三处回归 | ✓ 通过 | human/session-dd6cfa29-d8ff-43fe-99d7-371a69442076 | 2026-09-20 21:19 |
| v1-3 | 精确化操作条 move-req 断言 | ✓ 通过 | human/session-dd6cfa29-d8ff-43fe-99d7-371a69442076 | 2026-09-20 21:19 |
| v1-4 | 清偿架构门禁债 | ✓ 通过 | human/session-dd6cfa29-d8ff-43fe-99d7-371a69442076 | 2026-09-20 21:19 |
| v1-5 | 尺寸拆分、杂项清理与全量终验 | ✓ 通过 | human/session-dd6cfa29-d8ff-43fe-99d7-371a69442076 | 2026-09-20 21:19 |
| v1-6 | 需求级验收 | ✓ 通过 | human/session-dd6cfa29-d8ff-43fe-99d7-371a69442076 | 2026-09-20 21:19 |
| v1-9 | 需求级验收 | ✓ 通过 | human/session-dd6cfa29-d8ff-43fe-99d7-371a69442076 | 2026-09-20 21:19 |
| v1-10 | 需求级验收 | ✓ 通过 | human/session-dd6cfa29-d8ff-43fe-99d7-371a69442076 | 2026-09-20 21:19 |
