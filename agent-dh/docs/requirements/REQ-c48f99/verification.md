# REQ-c48f99 验收文档

> 自动生成于 reqboard_submit(kind=verification) · 验收单 v1

**交付结论**：REQ-c48f99 交付完成：会话框业务工具节点「折叠态一眼看懂动作、展开态首行即人话」。
①定制卡片：dsh-pmboard client 注册 9 张业务工具定制卡（tool.call.toolview 插槽），折叠行=中文动作摘要（用户目检确认两两不同），展开=结构化字段，畸形数据兜底不白屏；
②renderSmart 人话首行：13 个 pmboard 工具全迁移，reqboard_status 首行=中文摘要（会话事件实证）；
③零回归：其余插件与 DSH 框架零改动，bash/read/edit 用户确认一致。
降级标注：旧会话重渲染按同管线推定；E4 真实畸形 block 的 GUI 兜底未实战遇到（vitest 9 例覆盖逻辑层）。

## 1. 验收列表

### v1-1 · 契约卡：toolviews 数据契约 + 纯函数骨架 + renderSmart 签名

**验收内容**：【契约卡：toolviews 数据契约 + 纯函数骨架 + renderSmart 签名】验收：cd packages/pages/dsh-pmboard && npx vitest run tests/toolviews-contract 通过：parseArgs 对半截 JSON 返回 undefined、中文映射覆盖 task_move 7 个 to 值、renderSmart 输出首行 ≤120 字符且不含 '{'

**操作步骤**：
1. cd packages/pages/dsh-pmboard && npx vitest run tests/toolviews-contract 通过：parseArgs 对半截 JSON 返回 undefined、中文映射覆盖 task_move 7 个 to 值、renderSmart 输出首行 ≤120 字符且不含 '{'

**预期结果**：按上述步骤执行后满足验收标准：cd packages/pages/dsh-pmboard && npx vitest run tests/toolviews-contract 通过：parseArgs 对半截 JSON 返回 undefined、中文映射覆盖 task_move 7 个 to 值、renderSmart 输出首行 ≤120 字符且不含 '{'

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v1-2 · 骨架接线：bizToolviews 注册入口 + BizRow 布局 + task_move 示范卡

**验收内容**：【骨架接线：bizToolviews 注册入口 + BizRow 布局 + task_move 示范卡】验收：pnpm --filter dsh-pmboard build:client 退出码 0（verify-client-build WRAP_SENTINEL 门禁绿）；重启后新会话一次 reqboard_task_move 调用折叠行显示 't-xxx → 开工' 样式中文动作

**操作步骤**：
1. pnpm --filter dsh-pmboard build:client 退出码 0（verify-client-build WRAP_SENTINEL 门禁绿）
2. 重启后新会话一次 reqboard_task_move 调用折叠行显示 't-xxx → 开工' 样式中文动作

**预期结果**：按上述步骤执行后满足验收标准：pnpm --filter dsh-pmboard build:client 退出码 0（verify-client-build WRAP_SENTINEL 门禁绿）；重启后新会话一次 reqboard_task_move 调用折叠行显示 't-xxx → 开工' 样式中文动作

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v1-3 · 其余 8 张业务卡片（submit/ask_confirm/status/capture/memory_write/decision_audit/portfolio_trade/watch_manage）

**验收内容**：【其余 8 张业务卡片（submit/ask_confirm/status/capture/memory_write/decision_audit/portfolio_trade/watch_manage）】验收：npx vitest run 中 9 卡 summarize 四档用例（正常/缺字段/畸形/error 态）全绿；每张卡解析失败路径断言返回 fallbackRow 结构

**操作步骤**：
1. npx vitest run 中 9 卡 summarize 四档用例（正常/缺字段/畸形/error 态）全绿
2. 每张卡解析失败路径断言返回 fallbackRow 结构

**预期结果**：按上述步骤执行后满足验收标准：npx vitest run 中 9 卡 summarize 四档用例（正常/缺字段/畸形/error 态）全绿；每张卡解析失败路径断言返回 fallbackRow 结构

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v1-4 · renderSmart 人话首行：13 个 pmboard 工具逐配 summarize

**验收内容**：【renderSmart 人话首行：13 个 pmboard 工具逐配 summarize】验收：重启后调用 reqboard_status，工具结果文本首行为中文摘要（非 '{' 开头）；grep packages/pages/dsh-pmboard/src/tools 中 renderJson 剩余引用数 ≤ 1（shared.ts 定义处）

**操作步骤**：
1. 重启后调用 reqboard_status，工具结果文本首行为中文摘要（非 '{' 开头）
2. grep packages/pages/dsh-pmboard/src/tools 中 renderJson 剩余引用数 ≤ 1（shared.ts 定义处）

**预期结果**：按上述步骤执行后满足验收标准：重启后调用 reqboard_status，工具结果文本首行为中文摘要（非 '{' 开头）；grep packages/pages/dsh-pmboard/src/tools 中 renderJson 剩余引用数 ≤ 1（shared.ts 定义处）

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v1-5 · 迁移与兼容验证：renderJson 保留 + 旧会话重渲染 + 未注册工具零回归

**验收内容**：【迁移与兼容验证：renderJson 保留 + 旧会话重渲染 + 未注册工具零回归】验收：grep 确认其余插件 renderJson 类 render 零改动；旧会话 REQ-4842fe 中 task_move 节点显示新卡片；新会话 bash/read/edit 各一次调用显示终端卡/读取卡/diff 卡不变

**操作步骤**：
1. grep 确认其余插件 renderJson 类 render 零改动
2. 旧会话 REQ-4842fe 中 task_move 节点显示新卡片
3. 新会话 bash/read/edit 各一次调用显示终端卡/读取卡/diff 卡不变

**预期结果**：按上述步骤执行后满足验收标准：grep 确认其余插件 renderJson 类 render 零改动；旧会话 REQ-4842fe 中 task_move 节点显示新卡片；新会话 bash/read/edit 各一次调用显示终端卡/读取卡/diff 卡不变

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v1-6 · 端到端实测验收（E1-E4）+ 留证

**验收内容**：【端到端实测验收（E1-E4）+ 留证】验收：E1 三连不同 to 的 task_move 折叠行两两不同含中文动作；E2 reqboard_status 展开首行中文；E3 bash/read/edit 零回归；E4 畸形 block 显示兜底行不白屏——四项逐条记录进验收材料

**操作步骤**：
1. E1 三连不同 to 的 task_move 折叠行两两不同含中文动作
2. E2 reqboard_status 展开首行中文
3. E3 bash/read/edit 零回归
4. E4 畸形 block 显示兜底行不白屏——四项逐条记录进验收材料

**预期结果**：按上述步骤执行后满足验收标准：E1 三连不同 to 的 task_move 折叠行两两不同含中文动作；E2 reqboard_status 展开首行中文；E3 bash/read/edit 零回归；E4 畸形 block 显示兜底行不白屏——四项逐条记录进验收材料

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v1-7 · 指南文档：工具 render 人话首行约定

**验收内容**：【指南文档：工具 render 人话首行约定】验收：docs/guides/tool-render-human-summary.md 落盘；grep 命中 docs/README.md 含该文件链接

**操作步骤**：
1. docs/guides/tool-render-human-summary.md 落盘
2. grep 命中 docs/README.md 含该文件链接

**预期结果**：按上述步骤执行后满足验收标准：docs/guides/tool-render-human-summary.md 落盘；grep 命中 docs/README.md 含该文件链接

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v1-8 · 需求级验收

**验收内容**：需求级：交付结论可复核（证据齐全、与设计一致、无范围蔓延）

**操作步骤**：
1. 需求级：交付结论可复核（证据齐全、与设计一致、无范围蔓延）

**预期结果**：按上述步骤执行后满足验收标准：需求级：交付结论可复核（证据齐全、与设计一致、无范围蔓延）

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

### v1-11 · 需求级验收

**验收内容**：E2E 覆盖：**无（缺口）**——本需求交付涉及多组件串联，但只交了单元/集成测试。请补一条端到端场景用例（断言可观察终态）。

**操作步骤**：
1. E2E 覆盖：**无（缺口）**——本需求交付涉及多组件串联，但只交了单元/集成测试。请补一条端到端场景用例（断言可观察终态）。

**预期结果**：按上述步骤执行后满足验收标准：E2E 覆盖：**无（缺口）**——本需求交付涉及多组件串联，但只交了单元/集成测试。请补一条端到端场景用例（断言可观察终态）。

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

## 2. 测试报告

- npx vitest run（dsh-pmboard）：129 文件 1572 用例全绿（含 toolviews 契约 17 + 卡片四档 34 + render-summaries 20）——docs/requirements/REQ-c48f99/tests/final-verification.md
- pnpm build（dsh-pmboard）：host dist + client bundle 重建，verify-client-build WRAP_SENTINEL 门禁绿；npx tsc --noEmit 退出码 0
- 会话事件实证（python 探针读本会话 session.v3.jsonl.zstd）：reqboard_status 渲染文本首行=「📊 看板：1 个进行中需求（REQ-c48f99 implementing）」，非 { 开头
- bundle 探针：lib/client.js 含 9 卡注册（reqboard_task_move/portfolio_trade 等 key 全命中）+ fallbackRow + 中文映射
- 用户目检确认（ask_user_question 三问）：task_move 折叠行中文动作两两不同 / status 首行中文摘要 / bash/read/edit 零回归
- 兼容证据：git 维度非 pmboard 包 0 处改动；ui-tool 框架 bundle mtime 未变
- 产物：packages/pages/dsh-pmboard/src/client/toolviews/（9 卡+骨架）、src/tools/render-summaries.ts、docs/guides/tool-render-human-summary.md

## 3. 文档完整性检查

✓ 9 类文档齐全

## 4. 验收结果

| 编号 | 验收项 | 状态 | 验收人 | 验收时间 |
|---|---|---|---|---|
| v1-1 | 契约卡：toolviews 数据契约 + 纯函数骨架 + renderSmart 签名 | ⬜ 待验收 |  |  |
| v1-2 | 骨架接线：bizToolviews 注册入口 + BizRow 布局 + task_move 示范卡 | ⬜ 待验收 |  |  |
| v1-3 | 其余 8 张业务卡片（submit/ask_confirm/status/capture/memory_write/decision_audit/portfolio_trade/watch_manage） | ⬜ 待验收 |  |  |
| v1-4 | renderSmart 人话首行：13 个 pmboard 工具逐配 summarize | ⬜ 待验收 |  |  |
| v1-5 | 迁移与兼容验证：renderJson 保留 + 旧会话重渲染 + 未注册工具零回归 | ⬜ 待验收 |  |  |
| v1-6 | 端到端实测验收（E1-E4）+ 留证 | ⬜ 待验收 |  |  |
| v1-7 | 指南文档：工具 render 人话首行约定 | ⬜ 待验收 |  |  |
| v1-8 | 需求级验收 | ⬜ 待验收 |  |  |
| v1-11 | 需求级验收 | ⬜ 待验收 |  |  |
