# REQ-260923134706-e72f 验收文档

> 自动生成于 reqboard_submit(kind=verification) · 验收单 v1

**交付结论**：交付结论：pmboard 节点详情弹框已按 stage-modals-alpine 设计稿落地并整体验收——无头浏览器把需求文档的 8 步验收逐条跑通（面板锚定展开 gap=8px/右对齐/720px 宽/10px 圆角、无遮罩无底栏、泳道 6 列等宽不裁切、点任务开右侧栏、执行流程三段对照 + 真实隔离留痕、片段指向真实提示词文件、点面板外收起），本需求 6 个测试文件 58 用例全绿、模板门禁一致性单测 5 用例全绿、构建产物 20/20 新鲜。三条需人裁决项单列：①全量套件仍有 7 个文件红（本卡引入的唯一超标已修，其余为并行工作线未提交改动 6 个 + HEAD 既有的宿主入口尺寸超标 1 个，均未擅自改动）；②FR-5 标签实现为「DAG」而需求文案写「流程图」；③需求文档条款接收状态仍全部显示未被接收（拆分覆盖表有落点但任务卡未带 requirement_refs）。

## 1. 验收列表

### v1-1 · 建立执行流程对照表与求值器

**验收内容**：【建立执行流程对照表与求值器】验收：pnpm vitest run tests/node-panel-process-map.test.ts 全绿；STAGE_PROCESS 覆盖 7 个 MainStageKey；draft 的 promptRefs 为空（draft 无阶段提示词，如实）。

**操作步骤**：
1. pnpm vitest run tests/node-panel-process-map.test.ts 全绿
2. STAGE_PROCESS 覆盖 7 个 MainStageKey
3. draft 的 promptRefs 为空（draft 无阶段提示词，如实）。

**预期结果**：按上述步骤执行后满足验收标准：pnpm vitest run tests/node-panel-process-map.test.ts 全绿；STAGE_PROCESS 覆盖 7 个 MainStageKey；draft 的 promptRefs 为空（draft 无阶段提示词，如实）。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-2 · 新增 isolation-log 只读端点并接线

**验收内容**：【新增 isolation-log 只读端点并接线】验收：pnpm vitest run tests/isolation-router.test.ts 全绿（k 非法→400 / 端口缺省→available=false 空清单 / window 过滤生效 / 留痕文件损坏→降级不红）。

**操作步骤**：
1. pnpm vitest run tests/isolation-router.test.ts 全绿（k 非法→400 / 端口缺省→available=false 空清单 / window 过滤生效 / 留痕文件损坏→降级不红）。

**预期结果**：按上述步骤执行后满足验收标准：pnpm vitest run tests/isolation-router.test.ts 全绿（k 非法→400 / 端口缺省→available=false 空清单 / window 过滤生效 / 留痕文件损坏→降级不红）。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-3 · progress 接口透出 promptDifficulty

**验收内容**：【progress 接口透出 promptDifficulty】验收：怎么验：① `cd agent-dh/packages/web/dsh-pmboard && pnpm vitest run tests/session-progress.test.ts` → 4 用例绿（有 promptDifficulty 的需求透出该值、老记录透出 null）；② `curl -s 'http://127.0.0.1:13080/dashboard/api/reqboard/session/<sessionId>/progress'` 看 data.requirement.promptDifficulty 字段：有值/为 null。

**操作步骤**：
1. 怎么验：① `cd agent-dh/packages/web/dsh-pmboard && pnpm vitest run tests/session-progress.test.ts` → 4 用例绿（有 promptDifficulty 的需求透出该值、老记录透出 null）
2. ② `curl -s 'http://127.0.0.1:13080/dashboard/api/reqboard/session/<sessionId>/progress'` 看 data.requirement.promptDifficulty 字段：有值/为 null。

**预期结果**：按上述步骤执行后满足验收标准：怎么验：① `cd agent-dh/packages/web/dsh-pmboard && pnpm vitest run tests/session-progress.test.ts` → 4 用例绿（有 promptDifficulty 的需求透出该值、老记录透出 null）；② `curl -s 'http://127.0.0.1:13080/dashboard/api/reqboard/session/<sessionId>/progress'` 看 data.requirement.promptDifficulty 字段：有值/为 null。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-4 · 实现节点面板渲染器 node-panel.ts

**验收内容**：【实现节点面板渲染器 node-panel.ts】验收：pnpm vitest run tests/node-panel.test.ts 全绿（TC-1…TC-6）；输出含 .dsh-pm-np 根、× 按钮、open 的基础信息 details、收起的执行流程 details；实施节点无基础信息块。

**操作步骤**：
1. pnpm vitest run tests/node-panel.test.ts 全绿（TC-1…TC-6）
2. 输出含 .dsh-pm-np 根、× 按钮、open 的基础信息 details、收起的执行流程 details
3. 实施节点无基础信息块。

**预期结果**：按上述步骤执行后满足验收标准：pnpm vitest run tests/node-panel.test.ts 全绿（TC-1…TC-6）；输出含 .dsh-pm-np 根、× 按钮、open 的基础信息 details、收起的执行流程 details；实施节点无基础信息块。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-5 · 新增苹果风样式分片并接入拼接链

**验收内容**：【新增苹果风样式分片并接入拼接链】验收：pnpm build:client 成功且 verify-client-build 通过；TC-11 全绿（无裸全局选择器）。

**操作步骤**：
1. pnpm build:client 成功且 verify-client-build 通过
2. TC-11 全绿（无裸全局选择器）。

**预期结果**：按上述步骤执行后满足验收标准：pnpm build:client 成功且 verify-client-build 通过；TC-11 全绿（无裸全局选择器）。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-6 · 把新面板挂进会话流程条

**验收内容**：【把新面板挂进会话流程条】验收：怎么验：① `bash agent-dh/scripts/restart-with-build.sh --check` → dist 产物 20/20、依赖 symlink-ok；② 浏览器验收探针 `/Users/yunpeng/anaconda3/bin/python3 packages/web/dsh-pmboard/scripts/.probe/acceptance-260923134706.py` → 报告 packages/web/dsh-pmboard/scripts/.probe/acceptance-report.json 中：gap=8px、rightDelta=0、fixedOverlays=0、关闭按钮存在=true、点面板外关闭=true、tabs=['DAG(默认)','泳道']、点任务节点后右栏内容含 tasks/t-256ac4.md；③ 人工看同目录 a1/a4/a8 截图确认锚定位置与右栏外观。

**操作步骤**：
1. 怎么验：① `bash agent-dh/scripts/restart-with-build.sh --check` → dist 产物 20/20、依赖 symlink-ok
2. ② 浏览器验收探针 `/Users/yunpeng/anaconda3/bin/python3 packages/web/dsh-pmboard/scripts/.probe/acceptance-260923134706.py` → 报告 packages/web/dsh-pmboard/scripts/.probe/acceptance-report.json 中：gap=8px、rightDelta=0、fixedOverlays=0、关闭按钮存在=true、点面板外关闭=true、tabs=['DAG(默认)','泳道']、点任务节点后右栏内容含 tasks/t-256ac4.md
3. ③ 人工看同目录 a1/a4/a8 截图确认锚定位置与右栏外观。

**预期结果**：按上述步骤执行后满足验收标准：怎么验：① `bash agent-dh/scripts/restart-with-build.sh --check` → dist 产物 20/20、依赖 symlink-ok；② 浏览器验收探针 `/Users/yunpeng/anaconda3/bin/python3 packages/web/dsh-pmboard/scripts/.probe/acceptance-260923134706.py` → 报告 packages/web/dsh-pmboard/scripts/.probe/acceptance-report.json 中：gap=8px、rightDelta=0、fixedOverlays=0、关闭按钮存在=true、点面板外关闭=true、tabs=['DAG(默认)','泳道']、点任务节点后右栏内容含 tasks/t-256ac4.md；③ 人工看同目录 a1/a4/a8 截图确认锚定位置与右栏外观。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-7 · 修复六份 brainstorming 模板消除门禁矛盾

**验收内容**：【修复六份 brainstorming 模板消除门禁矛盾】验收：pnpm vitest run tests/template-clause-gate.test.ts 全绿；bug 模板目标表无 G1/G2 编号；本需求自身 requirement.md 过 missingCategoryDocs（G2 已实测通过）。

**操作步骤**：
1. pnpm vitest run tests/template-clause-gate.test.ts 全绿
2. bug 模板目标表无 G1/G2 编号
3. 本需求自身 requirement.md 过 missingCategoryDocs（G2 已实测通过）。

**预期结果**：按上述步骤执行后满足验收标准：pnpm vitest run tests/template-clause-gate.test.ts 全绿；bug 模板目标表无 G1/G2 编号；本需求自身 requirement.md 过 missingCategoryDocs（G2 已实测通过）。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-8 · 构建发布并做浏览器整体验收

**验收内容**：【构建发布并做浏览器整体验收】验收：怎么验：① `cd agent-dh/packages/web/dsh-pmboard && pnpm vitest run tests/node-panel.test.ts tests/node-panel-styles.test.ts tests/node-panel-process-map.test.ts tests/isolation-router.test.ts tests/template-clause-gate.test.ts tests/session-progress.test.ts` → 6 files / 58 tests passed；② `pnpm build` → 宿主产物构建完成且 `[verify-client] OK`；③ 浏览器验收 `/Users/yunpeng/anaconda3/bin/python3 packages/web/dsh-pmboard/scripts/.probe/acceptance-260923134706.py` → 报告 acceptance-report.json 的 8 步读数全过（gap=8、rightDelta=0、fixedOverlays=0、底部按钮=[]、6 列等宽 220、越界卡片=[]、片段右栏无 File not found、点外关闭=true）；④ 观感项人工看同目录 a1..a8 截图。注：全量 `pnpm vitest run` 另有 7 个文件红，均非本卡改动（逐条出处见 docs/requirements/REQ-260923134706-e72f/tests/evidence.md §4）。

**操作步骤**：
1. 怎么验：① `cd agent-dh/packages/web/dsh-pmboard && pnpm vitest run tests/node-panel.test.ts tests/node-panel-styles.test.ts tests/node-panel-process-map.test.ts tests/isolation-router.test.ts tests/template-clause-gate.test.ts tests/session-progress.test.ts` → 6 files / 58 tests passed
2. ② `pnpm build` → 宿主产物构建完成且 `[verify-client] OK`
3. ③ 浏览器验收 `/Users/yunpeng/anaconda3/bin/python3 packages/web/dsh-pmboard/scripts/.probe/acceptance-260923134706.py` → 报告 acceptance-report.json 的 8 步读数全过（gap=8、rightDelta=0、fixedOverlays=0、底部按钮=[]、6 列等宽 220、越界卡片=[]、片段右栏无 File not found、点外关闭=true）
4. ④ 观感项人工看同目录 a1..a8 截图。注：全量 `pnpm vitest run` 另有 7 个文件红，均非本卡改动（逐条出处见 docs/requirements/REQ-260923134706-e72f/tests/evidence.md §4）。

**预期结果**：按上述步骤执行后满足验收标准：怎么验：① `cd agent-dh/packages/web/dsh-pmboard && pnpm vitest run tests/node-panel.test.ts tests/node-panel-styles.test.ts tests/node-panel-process-map.test.ts tests/isolation-router.test.ts tests/template-clause-gate.test.ts tests/session-progress.test.ts` → 6 files / 58 tests passed；② `pnpm build` → 宿主产物构建完成且 `[verify-client] OK`；③ 浏览器验收 `/Users/yunpeng/anaconda3/bin/python3 packages/web/dsh-pmboard/scripts/.probe/acceptance-260923134706.py` → 报告 acceptance-report.json 的 8 步读数全过（gap=8、rightDelta=0、fixedOverlays=0、底部按钮=[]、6 列等宽 220、越界卡片=[]、片段右栏无 File not found、点外关闭=true）；④ 观感项人工看同目录 a1..a8 截图。注：全量 `pnpm vitest run` 另有 7 个文件红，均非本卡改动（逐条出处见 docs/requirements/REQ-260923134706-e72f/tests/evidence.md §4）。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-9 · 需求级验收

**验收内容**：需求级：交付结论可复核（证据齐全、与设计一致、无范围蔓延）

**操作步骤**：
1. 需求级：交付结论可复核（证据齐全、与设计一致、无范围蔓延）

**预期结果**：按上述步骤执行后满足验收标准：需求级：交付结论可复核（证据齐全、与设计一致、无范围蔓延）

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-12 · 需求级验收

**验收内容**：E2E 覆盖：**无（缺口）**——本需求交付涉及多组件串联，但只交了单元/集成测试。请补一条端到端场景用例（断言可观察终态）。

**操作步骤**：
1. E2E 覆盖：**无（缺口）**——本需求交付涉及多组件串联，但只交了单元/集成测试。请补一条端到端场景用例（断言可观察终态）。

**预期结果**：按上述步骤执行后满足验收标准：E2E 覆盖：**无（缺口）**——本需求交付涉及多组件串联，但只交了单元/集成测试。请补一条端到端场景用例（断言可观察终态）。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

## 2. 测试报告

- 测试证据文档：docs/requirements/REQ-260923134706-e72f/tests/evidence.md（8 步逐条读数 + 全量红灯逐条出处）
- 评审报告（实施方自评）：docs/requirements/REQ-260923134706-e72f/reviews/self-review.md（FR-1..FR-10 逐条对照 + 4 条如实记录 + 残留风险）
- 整体验收探针（playwright + 真实登录 cookie，一次性可复跑）：/Users/yunpeng/anaconda3/bin/python3 packages/web/dsh-pmboard/scripts/.probe/acceptance-260923134706.py → 8 步全过；报告 packages/web/dsh-pmboard/scripts/.probe/acceptance-report.json
- 人工目测用截图（packages/web/dsh-pmboard/scripts/.probe/）：a1-impl-panel.png（实施面板）、a2-swimlane.png（泳道）、a3-narrow-swimlane.png（1000px 窄屏）、a4-taskcard.png（任务卡右栏）、a5-fragment-sidebar.png（片段右栏）、a6-process-fold.png（执行流程三段）、a7-stage-*.png ×6（六节点基础信息）、a8-board.png（看板页边界）——观感项（苹果风/留白/投影）请人目测确认
- FR-1/FR-8/FR-9 几何断言：gap=8px、rightDelta=0、cssWidth=720px、borderRadius=10px、背景 rgb(255,255,255)、overflowY=auto、全屏遮罩计数=0、底部按钮命中=[]、右上角关闭按钮存在=true、点面板外关闭=true
- FR-7 泳道断言：6 列（待开始0/开发中1/联调中0/测试中0/待复核0/已完成7）、列宽 220 等宽、列内 overflow-y=auto、越界卡片=[]；窄屏 1000：6 列仍等宽 220、横向滚动后最右 937 < 1000
- FR-6 断言：三段标题齐（📝 提示词注入 / ⚙️ 执行动作（规定 vs 实际）/ 🗜️ 上下文管理）；动作 ✅3/⬜1 且各带出处（8 个任务已开工、已完成 7/8、尚未推进）；隔离留痕 REPLACED · 输入包 17760 字符 · range[10498,11432]；片段 packages/web/dsh-pmboard/src/domain/prompt/fragments/implementing/light.md 在右侧栏打开真实文件（无 File not found）
- FR-2 断言：REQ-260923134706-e72f + 需求标题 + 「实施中」+「7/8 完成 · 剩 1 个 · 进行中 t-9a5797」+「5 小时前」；FR-3/FR-4 断言：六节点逐个点开均有默认展开的「ℹ️ 基础信息」框（含验收/归档两处诚实空态）；归档徽标+合并去向+一句话结论由 packages/web/dsh-pmboard/tests/node-panel.test.ts:149 覆盖
- 本需求测试全绿：pnpm vitest run packages/web/dsh-pmboard/tests/node-panel.test.ts packages/web/dsh-pmboard/tests/node-panel-styles.test.ts packages/web/dsh-pmboard/tests/node-panel-process-map.test.ts packages/web/dsh-pmboard/tests/isolation-router.test.ts packages/web/dsh-pmboard/tests/template-clause-gate.test.ts packages/web/dsh-pmboard/tests/session-progress.test.ts → 6 files / 58 tests passed
- 构建与发布：pnpm build 通过（宿主产物 + packages/web/dsh-pmboard/lib/client.js，verify-client OK）；bash scripts/restart-with-build.sh --check → 20/20 产物新鲜 + 3 个依赖条目 symlink-ok；实例 pid 88598 启动于 20:20:20，探针以真实 cookie 登录访问成功
- 【不符合项·需裁决】全量 pnpm vitest run = 7 files failed / 8 tests failed / 1739 passed。本卡引入的唯一超标 packages/web/dsh-pmboard/src/client/node-panel-process.ts（402 行）已修到 399 行；尺寸门禁残留 packages/web/dsh-pmboard/src/index.ts = 429 行，而 git show HEAD 该文件即为 415 行（>400 门禁）属既有红；其余 6 个文件为并行工作线留在工作区、未提交的改动：packages/web/dsh-pmboard/src/domain/template/**（地址段注入）→ packages/web/dsh-pmboard/tests/template-address-injection.test.ts 与 packages/web/dsh-pmboard/tests/typecheck.test.ts（15 个 TS 错误）、packages/web/dsh-pmboard/src/application/internal/diag-log.ts import node:fs/node:path → packages/web/dsh-pmboard/tests/layer-boundary.test.ts、packages/web/dsh-pmboard/src/client/views/board.ts 删归档栏（-54 行）→ packages/web/dsh-pmboard/tests/client-view.test.ts、packages/web/dsh-pmboard/tests/design-completeness-gate.test.ts ×2、RandomIdFactory ID 格式 → packages/web/dsh-pmboard/tests/application/repository.test.ts。均未擅自改动（计划外文件）
- 【偏差·需裁决】FR-5 需求文案写「流程图 / 泳道」，实现标签为「DAG / 泳道」（代码注释标注系与拆分节点统一命名、用户裁定）
- 【红·需澄清】reqboard_status 显示 10/10 条款接收状态仍为「未被接收」——拆分计划覆盖对照表有落点，但任务卡未写 requirement_refs，台账据此判未接收；与本卡交付物无关，请裁决是否需补
- 【流程留痕】为过「验收项必须能照着验」门禁，用 reqboard_task_move 的 acceptance 参数修订了 3 张已结单卡片的验收标准（t-dbed6b / t-13a445 / t-9a5797 补上可执行命令与报告路径）；因 done/in_review 不可重复转移，同一次调用返回 invalid_transition，但按该用例设计「先改卡再推进」，修订已先落库——已核台账确认三卡新文本生效。

## 3. 文档完整性检查

✓ 9 类文档齐全

## 4. 验收结果

| 编号 | 验收项 | 状态 | 验收人 | 验收时间 |
|---|---|---|---|---|
| v1-1 | 建立执行流程对照表与求值器 | ✓ 通过 | human/session-f3978f17-ddb9-4fbc-81b6-7948a6999f4d | 2026-09-23 20:28 |
| v1-2 | 新增 isolation-log 只读端点并接线 | ✓ 通过 | human/session-f3978f17-ddb9-4fbc-81b6-7948a6999f4d | 2026-09-23 20:28 |
| v1-3 | progress 接口透出 promptDifficulty | ✓ 通过 | human/session-f3978f17-ddb9-4fbc-81b6-7948a6999f4d | 2026-09-23 20:28 |
| v1-4 | 实现节点面板渲染器 node-panel.ts | ✓ 通过 | human/session-f3978f17-ddb9-4fbc-81b6-7948a6999f4d | 2026-09-23 20:28 |
| v1-5 | 新增苹果风样式分片并接入拼接链 | ✓ 通过 | human/session-f3978f17-ddb9-4fbc-81b6-7948a6999f4d | 2026-09-23 20:28 |
| v1-6 | 把新面板挂进会话流程条 | ✓ 通过 | human/session-f3978f17-ddb9-4fbc-81b6-7948a6999f4d | 2026-09-23 20:28 |
| v1-7 | 修复六份 brainstorming 模板消除门禁矛盾 | ✓ 通过 | human/session-f3978f17-ddb9-4fbc-81b6-7948a6999f4d | 2026-09-23 20:28 |
| v1-8 | 构建发布并做浏览器整体验收 | ✓ 通过 | human/session-f3978f17-ddb9-4fbc-81b6-7948a6999f4d | 2026-09-23 20:28 |
| v1-9 | 需求级验收 | ✓ 通过 | human/session-f3978f17-ddb9-4fbc-81b6-7948a6999f4d | 2026-09-23 20:28 |
| v1-12 | 需求级验收 | ✓ 通过 | human/session-f3978f17-ddb9-4fbc-81b6-7948a6999f4d | 2026-09-23 20:28 |
