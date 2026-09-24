# REQ-260922182638-0777 验收文档

> 自动生成于 reqboard_submit(kind=verification) · 验收单 v1

**交付结论**：交付结论：dsh-pmboard 全链路中文名收敛为唯一事实源 src/shared/artifact-labels.ts（纯函数零依赖），六处本地映射表全部删除改 import；追溯链 design 文件名中文化（架构文档/接口文档…，tooltip 保留完整路径）、任务卡由「任务卡×N」改为逐张列出且带任务名称；五区块术语统一（归档 requirement 由漂移的「需求说明」统一为「需求文档」）；未知 kind/文件名中文兜底+原文附注；配套防漂移单测（新增枚举/规范文件名未配中文名即红）。6 张任务卡全部 done，FR-1~5 接收标记全部 ✅（RTM 覆盖表已补记）。

## 1. 验收列表

### v1-1 · 新增 artifact-labels 唯一事实源模块与防漂移单测

**验收内容**：【新增 artifact-labels 唯一事实源模块与防漂移单测】验收：cd agent-dh/packages/web/dsh-pmboard && pnpm vitest run tests/artifact-labels.test.ts 全绿（TC-001~005）；pnpm typecheck 通过

**操作步骤**：
1. cd agent-dh/packages/web/dsh-pmboard && pnpm vitest run tests/artifact-labels.test.ts 全绿（TC-001~005）
2. pnpm typecheck 通过

**预期结果**：按上述步骤执行后满足验收标准：cd agent-dh/packages/web/dsh-pmboard && pnpm vitest run tests/artifact-labels.test.ts 全绿（TC-001~005）；pnpm typecheck 通过

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-2 · 收敛文档区两处引用（artifacts / verification）

**验收内容**：【收敛文档区两处引用（artifacts / verification）】验收：grep -n "ARTIFACT_KIND_LABELS\|ARCHIVE_DOC_KIND_LABELS" src/client/views/ 无任何命中；pnpm vitest run tests/artifact-confirm-board.test.ts tests/verification-sheet.test.ts 全绿；pnpm typecheck 通过

**操作步骤**：
1. grep -n "ARTIFACT_KIND_LABELS\|ARCHIVE_DOC_KIND_LABELS" src/client/views/ 无任何命中
2. pnpm vitest run tests/artifact-confirm-board.test.ts tests/verification-sheet.test.ts 全绿
3. pnpm typecheck 通过

**预期结果**：按上述步骤执行后满足验收标准：grep -n "ARTIFACT_KIND_LABELS\|ARCHIVE_DOC_KIND_LABELS" src/client/views/ 无任何命中；pnpm vitest run tests/artifact-confirm-board.test.ts tests/verification-sheet.test.ts 全绿；pnpm typecheck 通过

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-3 · 收敛 client 工具回执引用（toolviews 三文件）

**验收内容**：【收敛 client 工具回执引用（toolviews 三文件）】验收：grep -n "SUBMIT_KIND\|KIND_CN" src/client/toolviews/ 无任何命中；pnpm vitest run tests/toolviews-cards.test.ts tests/toolviews-contract.test.ts 全绿；pnpm typecheck 通过

**操作步骤**：
1. grep -n "SUBMIT_KIND\|KIND_CN" src/client/toolviews/ 无任何命中
2. pnpm vitest run tests/toolviews-cards.test.ts tests/toolviews-contract.test.ts 全绿
3. pnpm typecheck 通过

**预期结果**：按上述步骤执行后满足验收标准：grep -n "SUBMIT_KIND\|KIND_CN" src/client/toolviews/ 无任何命中；pnpm vitest run tests/toolviews-cards.test.ts tests/toolviews-contract.test.ts 全绿；pnpm typecheck 通过

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-4 · 收敛 host 工具回执引用（render-summaries）

**验收内容**：【收敛 host 工具回执引用（render-summaries）】验收：grep -n "SUBMIT_KIND_CN" src/tools/ 无任何命中；pnpm vitest run tests/render-summaries.test.ts 全绿（含 plan→「拆分计划（旧版）」断言）；pnpm typecheck 通过

**操作步骤**：
1. grep -n "SUBMIT_KIND_CN" src/tools/ 无任何命中
2. pnpm vitest run tests/render-summaries.test.ts 全绿（含 plan→「拆分计划（旧版）」断言）
3. pnpm typecheck 通过

**预期结果**：按上述步骤执行后满足验收标准：grep -n "SUBMIT_KIND_CN" src/tools/ 无任何命中；pnpm vitest run tests/render-summaries.test.ts 全绿（含 plan→「拆分计划（旧版）」断言）；pnpm typecheck 通过

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-5 · 追溯链标签改造（文件名中文 + 任务卡逐张展开）

**验收内容**：【追溯链标签改造（文件名中文 + 任务卡逐张展开）】验收：pnpm vitest run tests/stage-panel.test.ts 全绿（含 TC-006 新增断言：design 显示「架构文档」等中文名、任务卡逐张带名称、不再出现「任务卡×」、缺失红字保留）；grep -n "ARTIFACT_KIND_LABELS" src/client/stage-panel.ts 无命中；pnpm typecheck 通过

**操作步骤**：
1. pnpm vitest run tests/stage-panel.test.ts 全绿（含 TC-006 新增断言：design 显示「架构文档」等中文名、任务卡逐张带名称、不再出现「任务卡×」、缺失红字保留）
2. grep -n "ARTIFACT_KIND_LABELS" src/client/stage-panel.ts 无命中
3. pnpm typecheck 通过

**预期结果**：按上述步骤执行后满足验收标准：pnpm vitest run tests/stage-panel.test.ts 全绿（含 TC-006 新增断言：design 显示「架构文档」等中文名、任务卡逐张带名称、不再出现「任务卡×」、缺失红字保留）；grep -n "ARTIFACT_KIND_LABELS" src/client/stage-panel.ts 无命中；pnpm typecheck 通过

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-6 · 兼容收尾核查（grep 唯一性 + 构建 + 浏览器核对）

**验收内容**：【兼容收尾核查（grep 唯一性 + 构建 + 浏览器核对）】验收：①grep -rn "'需求文档'" src 映射定义只剩 src/shared/artifact-labels.ts 一处；②pnpm vitest run tests/artifact-labels.test.ts tests/stage-panel.test.ts 全绿；③pnpm typecheck && pnpm build 通过；④浏览器核对清单逐项打勾并在任务卡留痕（哪页看到什么）

**操作步骤**：
1. ①grep -rn "'需求文档'" src 映射定义只剩 src/shared/artifact-labels.ts 一处
2. ②pnpm vitest run tests/artifact-labels.test.ts tests/stage-panel.test.ts 全绿
3. ③pnpm typecheck && pnpm build 通过
4. ④浏览器核对清单逐项打勾并在任务卡留痕（哪页看到什么）

**预期结果**：按上述步骤执行后满足验收标准：①grep -rn "'需求文档'" src 映射定义只剩 src/shared/artifact-labels.ts 一处；②pnpm vitest run tests/artifact-labels.test.ts tests/stage-panel.test.ts 全绿；③pnpm typecheck && pnpm build 通过；④浏览器核对清单逐项打勾并在任务卡留痕（哪页看到什么）

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-7 · 需求级验收

**验收内容**：需求级：交付结论可复核（证据齐全、与设计一致、无范围蔓延）

**操作步骤**：
1. 需求级：交付结论可复核（证据齐全、与设计一致、无范围蔓延）

**预期结果**：按上述步骤执行后满足验收标准：需求级：交付结论可复核（证据齐全、与设计一致、无范围蔓延）

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-10 · 需求级验收

**验收内容**：E2E 覆盖：**无（缺口）**——本需求交付涉及多组件串联，但只交了单元/集成测试。请补一条端到端场景用例（断言可观察终态）。

**操作步骤**：
1. E2E 覆盖：**无（缺口）**——本需求交付涉及多组件串联，但只交了单元/集成测试。请补一条端到端场景用例（断言可观察终态）。

**预期结果**：按上述步骤执行后满足验收标准：E2E 覆盖：**无（缺口）**——本需求交付涉及多组件串联，但只交了单元/集成测试。请补一条端到端场景用例（断言可观察终态）。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

## 2. 测试报告

- ① 单测命令：pnpm vitest run packages/web/dsh-pmboard/tests/artifact-labels.test.ts packages/web/dsh-pmboard/tests/stage-panel.test.ts → Test Files 2 passed / Tests 70 passed（TC-001~005 映射完整性/兜底/防漂移；TC-006a~d 追溯链中文名与任务卡逐张展开）
- ② 唯一性命令：grep -rn "'需求文档'" packages/web/dsh-pmboard/src → 仅 packages/web/dsh-pmboard/src/shared/artifact-labels.ts 2 处（kind 层 + 文件名层），其余文件零命中
- ③ 构建命令：cd packages/web/dsh-pmboard && pnpm typecheck → exit 0；pnpm build → BUILD_EXIT=0，[verify-client] OK bundle=247251 bytes、关键符号齐全、styles.ts 括号配对
- ④ 残留扫描命令：grep -rn "ARTIFACT_KIND_LABELS|SUBMIT_KIND|ARCHIVE_DOC_KIND_LABELS" packages/web/dsh-pmboard/src → 零命中；DOC_KIND_META 为验收允许保留的兼容导出（取值已改由共享表供给）
- ⑤ 浏览器加载物核验：grep -c "架构文档" packages/web/dsh-pmboard/lib/client.js → 1；"任务卡 · " → 1；"产物（" → 1；"任务卡×" → 0（折叠逻辑已消失）；node_modules/dsh-pmboard 为指向仓库源码的符号链接，刷新 :13080 即生效
- ⑥ 全量回归归因：1669 条 4 红均非本需求（3 条为共享工作区他窗口未提交改动，1 条为 vitest workers 环境 process.chdir，--pool=forks 下恢复），归因表见 docs/requirements/REQ-260922182638-0777/tests/evidence.md
- ⑦ 覆盖修复验证：补 docs/requirements/REQ-260922182638-0777/decomposition.md 的 RTM 覆盖表（12 条 task↔FR 绑定）后 clause_receive_status = FR-1~5 全 done、unreceived_clauses=[]，requirement.md 标记块同步为 ✅
- 证据文档：docs/requirements/REQ-260922182638-0777/reviews/self-review.md（逐条自评 + 4 项如实记录）、docs/requirements/REQ-260922182638-0777/tests/evidence.md（命令级证据）

## 3. 文档完整性检查

✓ 9 类文档齐全

## 4. 验收结果

| 编号 | 验收项 | 状态 | 验收人 | 验收时间 |
|---|---|---|---|---|
| v1-1 | 新增 artifact-labels 唯一事实源模块与防漂移单测 | ✓ 通过 | human/session-89aa3b25-9e19-48c0-a032-cf932135f88b | 2026-09-22 22:15 |
| v1-2 | 收敛文档区两处引用（artifacts / verification） | ✓ 通过 | human/session-89aa3b25-9e19-48c0-a032-cf932135f88b | 2026-09-22 22:15 |
| v1-3 | 收敛 client 工具回执引用（toolviews 三文件） | ✓ 通过 | human/session-89aa3b25-9e19-48c0-a032-cf932135f88b | 2026-09-22 22:15 |
| v1-4 | 收敛 host 工具回执引用（render-summaries） | ✓ 通过 | human/session-89aa3b25-9e19-48c0-a032-cf932135f88b | 2026-09-22 22:15 |
| v1-5 | 追溯链标签改造（文件名中文 + 任务卡逐张展开） | ✓ 通过 | human/session-89aa3b25-9e19-48c0-a032-cf932135f88b | 2026-09-22 22:15 |
| v1-6 | 兼容收尾核查（grep 唯一性 + 构建 + 浏览器核对） | ✓ 通过 | human/session-89aa3b25-9e19-48c0-a032-cf932135f88b | 2026-09-22 22:18 |
| v1-7 | 需求级验收 | ✓ 通过 | human/session-89aa3b25-9e19-48c0-a032-cf932135f88b | 2026-09-22 22:18 |
| v1-10 | 需求级验收 | ✓ 通过 | human/session-89aa3b25-9e19-48c0-a032-cf932135f88b | 2026-09-22 22:18 |
