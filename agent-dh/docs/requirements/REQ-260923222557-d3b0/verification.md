# REQ-260923222557-d3b0 验收文档

> 自动生成于 reqboard_submit(kind=verification) · 验收单 v1

**交付结论**：REQ-260923222557-d3b0 交付完成并已在 :13080 线上逐条核验：worktree 规范注入（implementing 档 + 子任务完成/归档两条事件投递）与弹框超时统一 1 小时（limits.ts 两常量 3_600_000、5 个消费方全读常量、TC-8 门禁锁定）已随 2026-09-23T23:59:23 重启生效；面板三处 UX 修正线上行为正确——旧管线 9 个需求头部文案一字未变（design 有 plan 记录者仍走「计划待批准/已批准」），本需求 design 头部=「设计已确认」且 5 份设计文档全部可点开，未提交拆分计划时显示「⬜ 拆分计划：decomposition.md（未交）」占位，未到达节点的状态胶囊一律「未开始」（不再用过去式）。构建门禁绿（两次构建 md5 一致 4c2ed0fc…）、部署链路无漂移（relink exit 0）、5 套件 99/99 测试全绿、R-017 noop 抽样零委托。自评与测试证据见 reviews/self-review.md、tests/evidence.md。⚠️ 一条如实报出：FR-5 的「弹框跨过旧 600 秒仍有效」只有机制级证据（声明值 3_600_000 + 框架按声明武装 deadline 无上限 + 新值已加载），运行期端到端未取得——本会话走 PTC(run_code)，其自身预算 default 120000ms/cap 600000ms 覆盖嵌套工具等待；且这意味着 PTC 窗口调用 reqboard_ask_confirm 的实际等待上限仍是 ≤10 分钟，1 小时只在原生工具调用窗口生效。是否调整 PTC 预算属框架级、会波及所有嵌套工具等待（超出本需求「不影响其他非 reqboard 弹框」边界），请人工裁定或另立需求。

## 1. 验收列表

### v1-1 · 弹框超时调整为 1 小时（domain 常量单点修改）

**验收内容**：【弹框超时调整为 1 小时（domain 常量单点修改）】验收：limits.ts 两常量=3_600_000；grep -rn "600_000\|900_000" src/ 无超时残留；vitest 全绿。

**操作步骤**：
1. limits.ts 两常量=3_600_000
2. grep -rn "600_000\|900_000" src/ 无超时残留
3. vitest 全绿。

**预期结果**：按上述步骤执行后满足验收标准：limits.ts 两常量=3_600_000；grep -rn "600_000\|900_000" src/ 无超时残留；vitest 全绿。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-2 · worktree 提示词文本三份（implementing 路由档 + task_done/archived 事件常量）

**验收内容**：【worktree 提示词文本三份（implementing 路由档 + task_done/archived 事件常量）】验收：cd packages/web/dsh-pmboard && npx vitest run tests/worktree-events.test.ts tests/prompt-baseline.test.ts tests/stage-prompts.test.ts → 全绿：worktree-events 断言事件文本含 `git worktree add .worktrees/REQ-` 与 `git worktree remove`，且 {id}/{task_id}/{task_title} 已替换；prompt-baseline 快照基线含 implementing 档「Worktree 规范」段（快照不一致即失败）。

**操作步骤**：
1. cd packages/web/dsh-pmboard && npx vitest run tests/worktree-events.test.ts tests/prompt-baseline.test.ts tests/stage-prompts.test.ts → 全绿：worktree-events 断言事件文本含 `git worktree add .worktrees/REQ-` 与 `git worktree remove`，且 {id}/{task_id}/{task_title} 已替换
2. prompt-baseline 快照基线含 implementing 档「Worktree 规范」段（快照不一致即失败）。

**预期结果**：按上述步骤执行后满足验收标准：cd packages/web/dsh-pmboard && npx vitest run tests/worktree-events.test.ts tests/prompt-baseline.test.ts tests/stage-prompts.test.ts → 全绿：worktree-events 断言事件文本含 `git worktree add .worktrees/REQ-` 与 `git worktree remove`，且 {id}/{task_id}/{task_title} 已替换；prompt-baseline 快照基线含 implementing 档「Worktree 规范」段（快照不一致即失败）。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-3 · 子任务完成与归档两处事件注入接线

**验收内容**：【子任务完成与归档两处事件注入接线】验收：cd packages/web/dsh-pmboard && npx vitest run tests/worktree-injection.test.ts → 5 passed：task_move→done 与 accepting→archived 两条路径各注入一次且文本含对应 git 命令；投递失败（无端口/抛错）仍完成状态转移。

**操作步骤**：
1. cd packages/web/dsh-pmboard && npx vitest run tests/worktree-injection.test.ts → 5 passed：task_move→done 与 accepting→archived 两条路径各注入一次且文本含对应 git 命令
2. 投递失败（无端口/抛错）仍完成状态转移。

**预期结果**：按上述步骤执行后满足验收标准：cd packages/web/dsh-pmboard && npx vitest run tests/worktree-injection.test.ts → 5 passed：task_move→done 与 accepting→archived 两条路径各注入一次且文本含对应 git 命令；投递失败（无端口/抛错）仍完成状态转移。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-4 · 面板头部：进展胶囊与状态词修正

**验收内容**：【面板头部：进展胶囊与状态词修正】验收：cd packages/web/dsh-pmboard && npx vitest run tests/stage-panel.test.ts tests/node-panel.test.ts → 81 passed（TC-1..TC-5：无 plan 2/5 已交→「设计文档 2/5 已交」；旧 plan→旧文案；交齐已确认→「设计已确认」；pending→「未开始」；current/done 取词不变）；线上核验：curl -s "http://127.0.0.1:13080/dashboard/api/reqboard/requirements/REQ-47939a/stage/design" 的载荷过 stageHeadSummary 得「计划已批准」、本需求得「设计已确认」（或在 :13080 看板打开需求→设计节点看头部胶囊）。

**操作步骤**：
1. cd packages/web/dsh-pmboard && npx vitest run tests/stage-panel.test.ts tests/node-panel.test.ts → 81 passed（TC-1..TC-5：无 plan 2/5 已交→「设计文档 2/5 已交」
2. 旧 plan→旧文案
3. 交齐已确认→「设计已确认」
4. pending→「未开始」
5. current/done 取词不变）
6. 线上核验：curl -s "http://127.0.0.1:13080/dashboard/api/reqboard/requirements/REQ-47939a/stage/design" 的载荷过 stageHeadSummary 得「计划已批准」、本需求得「设计已确认」（或在 :13080 看板打开需求→设计节点看头部胶囊）。

**预期结果**：按上述步骤执行后满足验收标准：cd packages/web/dsh-pmboard && npx vitest run tests/stage-panel.test.ts tests/node-panel.test.ts → 81 passed（TC-1..TC-5：无 plan 2/5 已交→「设计文档 2/5 已交」；旧 plan→旧文案；交齐已确认→「设计已确认」；pending→「未开始」；current/done 取词不变）；线上核验：curl -s "http://127.0.0.1:13080/dashboard/api/reqboard/requirements/REQ-47939a/stage/design" 的载荷过 stageHeadSummary 得「计划已批准」、本需求得「设计已确认」（或在 :13080 看板打开需求→设计节点看头部胶囊）。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-5 · 面板文档行：已交可点、未交占位

**验收内容**：【面板文档行：已交可点、未交占位】验收：TC-6/TC-7 绿；lib/client.js 重建且 verify-client-build 通过；线上打开本需求详情，✅ 行可点击右栏打开。

**操作步骤**：
1. TC-6/TC-7 绿
2. lib/client.js 重建且 verify-client-build 通过
3. 线上打开本需求详情，✅ 行可点击右栏打开。

**预期结果**：按上述步骤执行后满足验收标准：TC-6/TC-7 绿；lib/client.js 重建且 verify-client-build 通过；线上打开本需求详情，✅ 行可点击右栏打开。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-6 · 测试补齐与全量回归

**验收内容**：【测试补齐与全量回归】验收：pmboard vitest 全绿（含 TC-1..TC-8）；plugin-schema 冒烟通过；无新增失败（与基线对照）。

**操作步骤**：
1. pmboard vitest 全绿（含 TC-1..TC-8）
2. plugin-schema 冒烟通过
3. 无新增失败（与基线对照）。

**预期结果**：按上述步骤执行后满足验收标准：pmboard vitest 全绿（含 TC-1..TC-8）；plugin-schema 冒烟通过；无新增失败（与基线对照）。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-7 · 兼容核验 + 构建部署与线上验收

**验收内容**：【兼容核验 + 构建部署与线上验收】验收：旧管线文案不变（截图/curl 证据）；线上本需求面板行为符合 FR-8/9/10；弹框 >10min 不超时；R-017 核验结论留痕。

**操作步骤**：
1. 旧管线文案不变（截图/curl 证据）
2. 线上本需求面板行为符合 FR-8/9/10
3. 弹框 >10min 不超时
4. R-017 核验结论留痕。

**预期结果**：按上述步骤执行后满足验收标准：旧管线文案不变（截图/curl 证据）；线上本需求面板行为符合 FR-8/9/10；弹框 >10min 不超时；R-017 核验结论留痕。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-8 · 需求级验收

**验收内容**：需求级：交付结论可复核（证据齐全、与设计一致、无范围蔓延）

**操作步骤**：
1. 需求级：交付结论可复核（证据齐全、与设计一致、无范围蔓延）

**预期结果**：按上述步骤执行后满足验收标准：需求级：交付结论可复核（证据齐全、与设计一致、无范围蔓延）

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-11 · 需求级验收

**验收内容**：E2E 覆盖：**无（缺口）**——本需求交付涉及多组件串联，但只交了单元/集成测试。请补一条端到端场景用例（断言可观察终态）。

**操作步骤**：
1. E2E 覆盖：**无（缺口）**——本需求交付涉及多组件串联，但只交了单元/集成测试。请补一条端到端场景用例（断言可观察终态）。

**预期结果**：按上述步骤执行后满足验收标准：E2E 覆盖：**无（缺口）**——本需求交付涉及多组件串联，但只交了单元/集成测试。请补一条端到端场景用例（断言可观察终态）。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

## 2. 测试报告

- 【构建门禁】cd packages/web/dsh-pmboard && pnpm build:client → exit 0，末行「[verify-client] OK  bundle=285229 bytes, 关键符号齐全, styles.ts 括号配对」；连跑两次 md5 -q lib/client.js 均为 4c2ed0fc7ebf6bcb28ceb3e89441db9e（产物确定，且与重启前那份字节相同 → 浏览器不会取到旧包）
- 【部署链路】python3 scripts/relink-profile.py --check → exit 0，「状态统计: symlink-ok=3；OK: 3 个条目均为指向仓库的符号链接（且非副本）」
- 【线上进程】lsof -tiTCP:13080 -sTCP:LISTEN → PID 98527，ps lstart=Wed Sep 23 23:59:23 2026；重启理由与结果落盘 .dsh-data/state/quick-restart-request.json 与 quick-restart-result.json；晚于 packages/web/dsh-pmboard/src/domain/limits.ts 改动时间 23:47:03 → 宿主侧新值已加载
- 【FR-8 旧管线零回归】线上 30 个需求的 design 节点实时载荷（GET /dashboard/api/reqboard/requirements/<id>/stage/design，HTTP 200）× 真实渲染器 stageHeadSummary（tsx 直跑源码，非 mock）：9 个 design 有 plan 记录者全走计划文案（REQ-47939a=「计划已批准」，其余 计划待批准/已批准），19 个新管线走设计文档文案，口径不一致 0 条
- 【FR-8 本需求】REQ-260923222557-d3b0 design 节点头部 =「设计已确认」（body.designDocs 5/5 已交、artifact 全部 confirmedAt 非空）
- 【FR-9 已交可点】真实渲染器 renderNodePanel(d3b0, design) 基础信息块 → 5 条 dsh-pm-np-docitem（data-action="open-doc"）：architecture.md / interfaces.md / data-model.md / test-cases.md / use-cases.md；data-submitted="no" 占位 0 条
- 【FR-9 未交占位】REQ-ac5282（当前 design 阶段）预览拆分节点 → 「⬜ 拆分计划：decomposition.md（未交）」且该行无 open-doc（不可点）；已交需求的该行渲染为可点 docitem
- 【FR-10 状态词】REQ-ac5282 预览拆分节点 / 本需求预览验收节点 → 头部状态胶囊 data-state="pending" 文案「未开始」；已到达节点保持原词（本需求 设计=已设计、拆分=已拆分）
- 【测试】cd packages/web/dsh-pmboard && npx vitest run packages/web/dsh-pmboard/tests/stage-panel.test.ts packages/web/dsh-pmboard/tests/node-panel.test.ts packages/web/dsh-pmboard/tests/concurrency-limits.test.ts packages/web/dsh-pmboard/tests/worktree-injection.test.ts packages/web/dsh-pmboard/tests/worktree-events.test.ts → 5 files / 99 tests passed（stage-panel 54、node-panel 27、concurrency-limits 8、worktree-injection 5、worktree-events 5）
- 【FR-5/6/7 常量与消费方】packages/web/dsh-pmboard/src/domain/limits.ts:52,54 timeoutInteractiveMs/timeoutSheetMs=3_600_000；grep "timeoutMs: LIMITS.timeout" packages/web/dsh-pmboard/src/tools → AskConfirm:65 / Capture:68 / TaskExecute:41 / Advance:50 / AcceptSheet:47 全部引用常量，无硬编码字面量；TC-8（concurrency-limits 用例）锁定新值并禁止 600_000/900_000 回潮
- 【FR-5 框架确实按声明计时】框架包 dsh-tool-call-timeout-policy（tools/execute 包装器）第 123-125 行读取工具声明的 timeoutMs 并武装 deadline(exec.signal, timeoutMs)；dsh-timeout 第 27-29 行计时器上限 2147483647（无 600s 截断）→ 声明 3_600_000 会被足额武装
- 【R-017 noop 核验留痕】decision_audit DEC-20260924000950-acf59cfe + memory 97e0f300-ac8e-4d4d-ae52-a9d09f9cb1cc：抽样 trading_calendar 2026-09-24=交易日 / account_info(agent_brain) 总资产 500550 现金 485920（97.1%）/ regime_position_limit sideways 上限 60% 当前 2.9% verdict=compliant 熔断未触发（-0.36% vs -8%）/ trade_monitor queued=2 filled=0 / genome_list 四段齐全；委托零新增（queued 2→2）
- 【未闭环 ⚠️】FR-5「弹框跨过旧 600 秒仍有效」的运行期端到端未取得：本会话为 PTC(run_code) 模式，run_code 预算 default 120000ms、cap 600000ms 且覆盖嵌套工具等待，10 分钟上限恰等于需跨过的旧值 → 无法在单次调用内证伪；同时这表明 PTC 窗口调用 reqboard_ask_confirm 的实际等待上限仍 ≤10 分钟。请人工在原生工具调用会话确认，或裁定另立需求调整 PTC 预算（框架级、影响所有嵌套工具等待），详见交付自评
- 【交付自评与测试证据】docs/requirements/REQ-260923222557-d3b0/reviews/self-review.md、docs/requirements/REQ-260923222557-d3b0/tests/evidence.md（含逐条 FR 自评、证据表与未覆盖项）
- 【任务卡完工记录】docs/requirements/REQ-260923222557-d3b0/tasks/t-4e8339.md（第 3 段汇报，含 10 条完成项与未闭环项）；t-b2e945/t-06d59d/t-485233 的验收标准已按「怎么验」门槛补可执行命令（vitest/curl），见各卡「得到什么结果」段

## 3. 文档完整性检查

✓ 9 类文档齐全

## 4. 验收结果

| 编号 | 验收项 | 状态 | 验收人 | 验收时间 |
|---|---|---|---|---|
| v1-1 | 弹框超时调整为 1 小时（domain 常量单点修改） | ✓ 通过 | human/session-959cebfe-094f-4f09-894d-20a5c35d4d62 | 2026-09-24 00:12 |
| v1-2 | worktree 提示词文本三份（implementing 路由档 + task_done/archived 事件常量） | ✓ 通过 | human/session-959cebfe-094f-4f09-894d-20a5c35d4d62 | 2026-09-24 00:12 |
| v1-3 | 子任务完成与归档两处事件注入接线 | ✓ 通过 | human/session-959cebfe-094f-4f09-894d-20a5c35d4d62 | 2026-09-24 00:12 |
| v1-4 | 面板头部：进展胶囊与状态词修正 | ✓ 通过 | human/session-959cebfe-094f-4f09-894d-20a5c35d4d62 | 2026-09-24 00:12 |
| v1-5 | 面板文档行：已交可点、未交占位 | ✓ 通过 | human/session-959cebfe-094f-4f09-894d-20a5c35d4d62 | 2026-09-24 00:12 |
| v1-6 | 测试补齐与全量回归 | ✓ 通过 | human/session-959cebfe-094f-4f09-894d-20a5c35d4d62 | 2026-09-24 00:12 |
| v1-7 | 兼容核验 + 构建部署与线上验收 | ✓ 通过 | human/session-959cebfe-094f-4f09-894d-20a5c35d4d62 | 2026-09-24 00:12 |
| v1-8 | 需求级验收 | ✓ 通过 | human/session-959cebfe-094f-4f09-894d-20a5c35d4d62 | 2026-09-24 00:12 |
| v1-11 | 需求级验收 | ✓ 通过 | human/session-959cebfe-094f-4f09-894d-20a5c35d4d62 | 2026-09-24 00:12 |
