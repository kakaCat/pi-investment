# REQ-260928222643-4d34 验收文档

> 自动生成于 reqboard_submit(kind=verification) · 验收单 v2

**交付结论**：交付结论：节点面板「项目看板 ↗」入口与执行流程块下掉已全部落地，自动链 37/37 任务 done 并 ROLLUP 进验收。① FR-1 面板状态行 7 节点（含「本分类跳过」）均渲染固定文案「项目看板 ↗」；② FR-2 点击经一次性持有器 board-focus 交接 → board-entry 先校验 → 成功关面板并切到看板该需求详情，刷新/再次进入回落默认视图（非粘滞）；③ FR-3 目标不可达时不切页并就地红字提示原因；④ FR-4「🔄 执行流程」块连标题行一并下掉；⑤ FR-5 面板侧不再发起注入/隔离留痕拉取，后端路由与看板既有消费方原样保留。附带修掉自动链两处根因（父卡收尾凭证基准、重启后残留锁死锁），回填 17 份子卡文档、把模板验收标准改为可执行命令并补齐 covers 覆盖标注（37/37）。待人工执行：:13080 的四步端到端点击闭环（agent 无浏览器）。

## 1. 验收列表

### v2-1 · 新增一次性交接持有器 src/client/board-focus.ts

**验收内容**：【新增一次性交接持有器 src/client/board-focus.ts】验收：cd packages/web/dsh-pmboard && npx vitest run tests/board-focus.test.ts 全绿；grep -c "export function" src/client/board-focus.ts 输出 4；grep -n "localStorage|sessionStorage|URLSearchParams|location.hash" src/client/board-focus.ts 无匹配（非粘滞）。

**操作步骤**：
1. cd packages/web/dsh-pmboard && npx vitest run tests/board-focus.test.ts 全绿
2. grep -c "export function" src/client/board-focus.ts 输出 4
3. grep -n "localStorage|sessionStorage|URLSearchParams|location.hash" src/client/board-focus.ts 无匹配（非粘滞）。

**预期结果**：按上述步骤执行后满足验收标准：cd packages/web/dsh-pmboard && npx vitest run tests/board-focus.test.ts 全绿；grep -c "export function" src/client/board-focus.ts 输出 4；grep -n "localStorage|sessionStorage|URLSearchParams|location.hash" src/client/board-focus.ts 无匹配（非粘滞）。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v2-2 · 新增入口校验纯函数 src/client/board-entry.ts

**验收内容**：【新增入口校验纯函数 src/client/board-entry.ts】验收：cd packages/web/dsh-pmboard && npx vitest run tests/board-entry.test.ts 全绿（TC-9~TC-13）；三种失败路径 requestFocus 与 layout.selectPanel 调用各 0 次；成功路径 requestFocus 恰好 1 次。

**操作步骤**：
1. cd packages/web/dsh-pmboard && npx vitest run tests/board-entry.test.ts 全绿（TC-9~TC-13）
2. 三种失败路径 requestFocus 与 layout.selectPanel 调用各 0 次
3. 成功路径 requestFocus 恰好 1 次。

**预期结果**：按上述步骤执行后满足验收标准：cd packages/web/dsh-pmboard && npx vitest run tests/board-entry.test.ts 全绿（TC-9~TC-13）；三种失败路径 requestFocus 与 layout.selectPanel 调用各 0 次；成功路径 requestFocus 恰好 1 次。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v2-3 · node-panel.ts 加入口按钮并删除执行流程块调用与入参

**验收内容**：【node-panel.ts 加入口按钮并删除执行流程块调用与入参】验收：cd packages/web/dsh-pmboard && grep -n "renderProcessFold" src/client/node-panel.ts 无匹配；grep -n "injection|isolation" src/client/node-panel.ts 无匹配；npx vitest run tests/node-panel.test.ts 全绿且 7 节点输出不含「🔄 执行流程」；npx vitest run tests/node-panel-process-map.test.ts 仍全绿。

**操作步骤**：
1. cd packages/web/dsh-pmboard && grep -n "renderProcessFold" src/client/node-panel.ts 无匹配
2. grep -n "injection|isolation" src/client/node-panel.ts 无匹配
3. npx vitest run tests/node-panel.test.ts 全绿且 7 节点输出不含「🔄 执行流程」
4. npx vitest run tests/node-panel-process-map.test.ts 仍全绿。

**预期结果**：按上述步骤执行后满足验收标准：cd packages/web/dsh-pmboard && grep -n "renderProcessFold" src/client/node-panel.ts 无匹配；grep -n "injection|isolation" src/client/node-panel.ts 无匹配；npx vitest run tests/node-panel.test.ts 全绿且 7 节点输出不含「🔄 执行流程」；npx vitest run tests/node-panel-process-map.test.ts 仍全绿。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v2-4 · conversation-progress.ts 接线点击→校验→关面板→切看板并删两条留痕拉取

**验收内容**：【conversation-progress.ts 接线点击→校验→关面板→切看板并删两条留痕拉取】验收：cd packages/web/dsh-pmboard && grep -rn "fetchInjectionInfo|fetchIsolationLog" src/client/conversation-progress.ts src/client/node-panel.ts 无匹配；grep -n "np-board-entry|activateBoardEntry|selectPanel(PANEL_ID)|dsh-pm-np-entry-err" src/client/conversation-progress.ts 四个符号全命中；pnpm run typecheck 通过。

**操作步骤**：
1. cd packages/web/dsh-pmboard && grep -rn "fetchInjectionInfo|fetchIsolationLog" src/client/conversation-progress.ts src/client/node-panel.ts 无匹配
2. grep -n "np-board-entry|activateBoardEntry|selectPanel(PANEL_ID)|dsh-pm-np-entry-err" src/client/conversation-progress.ts 四个符号全命中
3. pnpm run typecheck 通过。

**预期结果**：按上述步骤执行后满足验收标准：cd packages/web/dsh-pmboard && grep -rn "fetchInjectionInfo|fetchIsolationLog" src/client/conversation-progress.ts src/client/node-panel.ts 无匹配；grep -n "np-board-entry|activateBoardEntry|selectPanel(PANEL_ID)|dsh-pm-np-entry-err" src/client/conversation-progress.ts 四个符号全命中；pnpm run typecheck 通过。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v2-5 · board-mount.ts 挂载时 takeBoardFocus 初始化 mode

**验收内容**：【board-mount.ts 挂载时 takeBoardFocus 初始化 mode】验收：cd packages/web/dsh-pmboard && npx vitest run tests/board-attach.test.ts 全绿（含 TC-7/TC-8）；TC-7 断言挂载后 peekBoardFocus() 为 undefined 且 innerHTML 含需求详情标记；grep -n "takeBoardFocus" src/client/board-mount.ts 恰好 1 处。

**操作步骤**：
1. cd packages/web/dsh-pmboard && npx vitest run tests/board-attach.test.ts 全绿（含 TC-7/TC-8）
2. TC-7 断言挂载后 peekBoardFocus() 为 undefined 且 innerHTML 含需求详情标记
3. grep -n "takeBoardFocus" src/client/board-mount.ts 恰好 1 处。

**预期结果**：按上述步骤执行后满足验收标准：cd packages/web/dsh-pmboard && npx vitest run tests/board-attach.test.ts 全绿（含 TC-7/TC-8）；TC-7 断言挂载后 peekBoardFocus() 为 undefined 且 innerHTML 含需求详情标记；grep -n "takeBoardFocus" src/client/board-mount.ts 恰好 1 处。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v2-6 · styles/node-panel.ts 新增入口按钮与失败提示两条规则

**验收内容**：【styles/node-panel.ts 新增入口按钮与失败提示两条规则】验收：cd packages/web/dsh-pmboard && npx vitest run tests/node-panel-styles.test.ts 全绿（TC-14 + 既有作用域断言）；grep -n "dsh-pm-np-board-entry|dsh-pm-np-entry-err" src/client/styles/node-panel.ts 两条规则均命中。

**操作步骤**：
1. cd packages/web/dsh-pmboard && npx vitest run tests/node-panel-styles.test.ts 全绿（TC-14 + 既有作用域断言）
2. grep -n "dsh-pm-np-board-entry|dsh-pm-np-entry-err" src/client/styles/node-panel.ts 两条规则均命中。

**预期结果**：按上述步骤执行后满足验收标准：cd packages/web/dsh-pmboard && npx vitest run tests/node-panel-styles.test.ts 全绿（TC-14 + 既有作用域断言）；grep -n "dsh-pm-np-board-entry|dsh-pm-np-entry-err" src/client/styles/node-panel.ts 两条规则均命中。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v2-7 · 迁移与兼容核验：无 schema 变更、旧调用方与看板消费方零回归

**验收内容**：【迁移与兼容核验：无 schema 变更、旧调用方与看板消费方零回归】验收：cd packages/web/dsh-pmboard && grep -c "fetchInjectionInfo" src/client/board-mount.ts 输出 1；grep -n "export function renderProcessFold" src/client/node-panel-process.ts 命中；grep -rn "NodePanelInput" src/ 仅 node-panel.ts 与 conversation-progress.ts；git diff src/shared/protocol.ts 无 REQBOARD_SCHEMA_VERSION 行改动。

**操作步骤**：
1. cd packages/web/dsh-pmboard && grep -c "fetchInjectionInfo" src/client/board-mount.ts 输出 1
2. grep -n "export function renderProcessFold" src/client/node-panel-process.ts 命中
3. grep -rn "NodePanelInput" src/ 仅 node-panel.ts 与 conversation-progress.ts
4. git diff src/shared/protocol.ts 无 REQBOARD_SCHEMA_VERSION 行改动。

**预期结果**：按上述步骤执行后满足验收标准：cd packages/web/dsh-pmboard && grep -c "fetchInjectionInfo" src/client/board-mount.ts 输出 1；grep -n "export function renderProcessFold" src/client/node-panel-process.ts 命中；grep -rn "NodePanelInput" src/ 仅 node-panel.ts 与 conversation-progress.ts；git diff src/shared/protocol.ts 无 REQBOARD_SCHEMA_VERSION 行改动。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v2-8 · 重建客户端产物并发版，完成 TC-15 端到端人工验收

**验收内容**：【重建客户端产物并发版，完成 TC-15 端到端人工验收】验收：cd packages/web/dsh-pmboard && npx vitest run 全绿且 pnpm run typecheck 退出码 0；pnpm build:client 退出码 0 且 node scripts/verify-client-build.mjs 校验通过；打开 :13080 节点面板状态行含「项目看板 ↗」、无「🔄 执行流程」，点入口直达该需求详情、刷新回默认视图、错误 REQ 留在原页并显示失败提示。

**操作步骤**：
1. cd packages/web/dsh-pmboard && npx vitest run 全绿且 pnpm run typecheck 退出码 0
2. pnpm build:client 退出码 0 且 node scripts/verify-client-build.mjs 校验通过
3. 打开 :13080 节点面板状态行含「项目看板 ↗」、无「🔄 执行流程」，点入口直达该需求详情、刷新回默认视图、错误 REQ 留在原页并显示失败提示。

**预期结果**：按上述步骤执行后满足验收标准：cd packages/web/dsh-pmboard && npx vitest run 全绿且 pnpm run typecheck 退出码 0；pnpm build:client 退出码 0 且 node scripts/verify-client-build.mjs 校验通过；打开 :13080 节点面板状态行含「项目看板 ↗」、无「🔄 执行流程」，点入口直达该需求详情、刷新回默认视图、错误 REQ 留在原页并显示失败提示。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v2-9 · 新增一次性交接持有器 src/client/board-focus.ts·研发

**验收内容**：【新增一次性交接持有器 src/client/board-focus.ts·研发】验收：在 packages/web/dsh-pmboard 下 npx vitest run tests/board-focus.test.ts 全绿；grep -c "export function" src/client/board-focus.ts 输出 4。

**操作步骤**：
1. 在 packages/web/dsh-pmboard 下 npx vitest run tests/board-focus.test.ts 全绿
2. grep -c "export function" src/client/board-focus.ts 输出 4。

**预期结果**：按上述步骤执行后满足验收标准：在 packages/web/dsh-pmboard 下 npx vitest run tests/board-focus.test.ts 全绿；grep -c "export function" src/client/board-focus.ts 输出 4。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v2-10 · 新增一次性交接持有器 src/client/board-focus.ts·联调

**验收内容**：【新增一次性交接持有器 src/client/board-focus.ts·联调】验收：grep -n "requestBoardFocus" src/client/conversation-progress.ts 命中；grep -n "takeBoardFocus" src/client/board-mount.ts 命中（引用点接线一致）。

**操作步骤**：
1. grep -n "requestBoardFocus" src/client/conversation-progress.ts 命中
2. grep -n "takeBoardFocus" src/client/board-mount.ts 命中（引用点接线一致）。

**预期结果**：按上述步骤执行后满足验收标准：grep -n "requestBoardFocus" src/client/conversation-progress.ts 命中；grep -n "takeBoardFocus" src/client/board-mount.ts 命中（引用点接线一致）。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v2-11 · 新增一次性交接持有器 src/client/board-focus.ts·复核

**验收内容**：【新增一次性交接持有器 src/client/board-focus.ts·复核】验收：grep -n "localStorage\|sessionStorage\|URLSearchParams\|location.hash" src/client/board-focus.ts 无匹配（一次性、非粘滞）。

**操作步骤**：
1. grep -n "localStorage\|sessionStorage\|URLSearchParams\|location.hash" src/client/board-focus.ts 无匹配（一次性、非粘滞）。

**预期结果**：按上述步骤执行后满足验收标准：grep -n "localStorage\|sessionStorage\|URLSearchParams\|location.hash" src/client/board-focus.ts 无匹配（一次性、非粘滞）。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v2-12 · 新增一次性交接持有器 src/client/board-focus.ts·测试

**验收内容**：【新增一次性交接持有器 src/client/board-focus.ts·测试】验收：在 packages/web/dsh-pmboard 下 npx vitest run tests/board-focus.test.ts 全绿，并把命令与输出摘要写入 docs/requirements/REQ-260928222643-4d34/tests/test-report.md。

**操作步骤**：
1. 在 packages/web/dsh-pmboard 下 npx vitest run tests/board-focus.test.ts 全绿，并把命令与输出摘要写入 docs/requirements/REQ-260928222643-4d34/tests/test-report.md。

**预期结果**：按上述步骤执行后满足验收标准：在 packages/web/dsh-pmboard 下 npx vitest run tests/board-focus.test.ts 全绿，并把命令与输出摘要写入 docs/requirements/REQ-260928222643-4d34/tests/test-report.md。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v2-13 · 新增入口校验纯函数 src/client/board-entry.ts·研发

**验收内容**：【新增入口校验纯函数 src/client/board-entry.ts·研发】验收：在 packages/web/dsh-pmboard 下 npx vitest run tests/board-entry.test.ts 全绿（TC-9~TC-13）。

**操作步骤**：
1. 在 packages/web/dsh-pmboard 下 npx vitest run tests/board-entry.test.ts 全绿（TC-9~TC-13）。

**预期结果**：按上述步骤执行后满足验收标准：在 packages/web/dsh-pmboard 下 npx vitest run tests/board-entry.test.ts 全绿（TC-9~TC-13）。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v2-14 · 新增入口校验纯函数 src/client/board-entry.ts·联调

**验收内容**：【新增入口校验纯函数 src/client/board-entry.ts·联调】验收：grep -n "activateBoardEntry" src/client/conversation-progress.ts 命中；在 packages/web/dsh-pmboard 下 pnpm run typecheck 对标改动文件无新增错误。

**操作步骤**：
1. grep -n "activateBoardEntry" src/client/conversation-progress.ts 命中
2. 在 packages/web/dsh-pmboard 下 pnpm run typecheck 对标改动文件无新增错误。

**预期结果**：按上述步骤执行后满足验收标准：grep -n "activateBoardEntry" src/client/conversation-progress.ts 命中；在 packages/web/dsh-pmboard 下 pnpm run typecheck 对标改动文件无新增错误。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v2-15 · 新增入口校验纯函数 src/client/board-entry.ts·复核

**验收内容**：【新增入口校验纯函数 src/client/board-entry.ts·复核】验收：在 packages/web/dsh-pmboard 下 npx vitest run tests/board-entry.test.ts 全绿，且断言三种失败路径 requestFocus 与 layout.selectPanel 各 0 次。

**操作步骤**：
1. 在 packages/web/dsh-pmboard 下 npx vitest run tests/board-entry.test.ts 全绿，且断言三种失败路径 requestFocus 与 layout.selectPanel 各 0 次。

**预期结果**：按上述步骤执行后满足验收标准：在 packages/web/dsh-pmboard 下 npx vitest run tests/board-entry.test.ts 全绿，且断言三种失败路径 requestFocus 与 layout.selectPanel 各 0 次。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v2-16 · 新增入口校验纯函数 src/client/board-entry.ts·测试

**验收内容**：【新增入口校验纯函数 src/client/board-entry.ts·测试】验收：在 packages/web/dsh-pmboard 下 npx vitest run tests/board-entry.test.ts 全绿，并把命令与输出摘要写入 docs/requirements/REQ-260928222643-4d34/tests/test-report.md。

**操作步骤**：
1. 在 packages/web/dsh-pmboard 下 npx vitest run tests/board-entry.test.ts 全绿，并把命令与输出摘要写入 docs/requirements/REQ-260928222643-4d34/tests/test-report.md。

**预期结果**：按上述步骤执行后满足验收标准：在 packages/web/dsh-pmboard 下 npx vitest run tests/board-entry.test.ts 全绿，并把命令与输出摘要写入 docs/requirements/REQ-260928222643-4d34/tests/test-report.md。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v2-17 · node-panel.ts 加入口按钮并删除执行流程块调用与入参·研发

**验收内容**：【node-panel.ts 加入口按钮并删除执行流程块调用与入参·研发】验收：在 packages/web/dsh-pmboard 下 npx vitest run tests/node-panel.test.ts 全绿，且 7 节点渲染输出不含「🔄 执行流程」。

**操作步骤**：
1. 在 packages/web/dsh-pmboard 下 npx vitest run tests/node-panel.test.ts 全绿，且 7 节点渲染输出不含「🔄 执行流程」。

**预期结果**：按上述步骤执行后满足验收标准：在 packages/web/dsh-pmboard 下 npx vitest run tests/node-panel.test.ts 全绿，且 7 节点渲染输出不含「🔄 执行流程」。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v2-18 · node-panel.ts 加入口按钮并删除执行流程块调用与入参·联调

**验收内容**：【node-panel.ts 加入口按钮并删除执行流程块调用与入参·联调】验收：grep -n "np-board-entry" src/client/node-panel.ts 命中；grep -n "renderProcessFold" src/client/node-panel.ts 无匹配（调用已断、函数保留）。

**操作步骤**：
1. grep -n "np-board-entry" src/client/node-panel.ts 命中
2. grep -n "renderProcessFold" src/client/node-panel.ts 无匹配（调用已断、函数保留）。

**预期结果**：按上述步骤执行后满足验收标准：grep -n "np-board-entry" src/client/node-panel.ts 命中；grep -n "renderProcessFold" src/client/node-panel.ts 无匹配（调用已断、函数保留）。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v2-19 · node-panel.ts 加入口按钮并删除执行流程块调用与入参·复核

**验收内容**：【node-panel.ts 加入口按钮并删除执行流程块调用与入参·复核】验收：grep -n "injection\|isolation" src/client/node-panel.ts 无匹配；在 packages/web/dsh-pmboard 下 npx vitest run tests/node-panel-process-map.test.ts 全绿。

**操作步骤**：
1. grep -n "injection\|isolation" src/client/node-panel.ts 无匹配
2. 在 packages/web/dsh-pmboard 下 npx vitest run tests/node-panel-process-map.test.ts 全绿。

**预期结果**：按上述步骤执行后满足验收标准：grep -n "injection\|isolation" src/client/node-panel.ts 无匹配；在 packages/web/dsh-pmboard 下 npx vitest run tests/node-panel-process-map.test.ts 全绿。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v2-20 · node-panel.ts 加入口按钮并删除执行流程块调用与入参·测试

**验收内容**：【node-panel.ts 加入口按钮并删除执行流程块调用与入参·测试】验收：在 packages/web/dsh-pmboard 下 npx vitest run tests/node-panel.test.ts tests/node-panel-styles.test.ts 全绿，并把命令与输出摘要写入 docs/requirements/REQ-260928222643-4d34/tests/test-report.md。

**操作步骤**：
1. 在 packages/web/dsh-pmboard 下 npx vitest run tests/node-panel.test.ts tests/node-panel-styles.test.ts 全绿，并把命令与输出摘要写入 docs/requirements/REQ-260928222643-4d34/tests/test-report.md。

**预期结果**：按上述步骤执行后满足验收标准：在 packages/web/dsh-pmboard 下 npx vitest run tests/node-panel.test.ts tests/node-panel-styles.test.ts 全绿，并把命令与输出摘要写入 docs/requirements/REQ-260928222643-4d34/tests/test-report.md。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v2-21 · conversation-progress.ts 接线点击→校验→关面板→切看板并删两条留痕拉取·研发

**验收内容**：【conversation-progress.ts 接线点击→校验→关面板→切看板并删两条留痕拉取·研发】验收：在 packages/web/dsh-pmboard 下执行：grep -n "requestBoardFocus" src/client/conversation-progress.ts（须命中接线点）；npx vitest run tests/board-attach.test.ts（期望 Tests 6 passed、exit 0）。

**操作步骤**：
1. 在 packages/web/dsh-pmboard 下执行：grep -n "requestBoardFocus" src/client/conversation-progress.ts（须命中接线点）
2. npx vitest run tests/board-attach.test.ts（期望 Tests 6 passed、exit 0）。

**预期结果**：按上述步骤执行后满足验收标准：在 packages/web/dsh-pmboard 下执行：grep -n "requestBoardFocus" src/client/conversation-progress.ts（须命中接线点）；npx vitest run tests/board-attach.test.ts（期望 Tests 6 passed、exit 0）。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v2-22 · conversation-progress.ts 接线点击→校验→关面板→切看板并删两条留痕拉取·联调

**验收内容**：【conversation-progress.ts 接线点击→校验→关面板→切看板并删两条留痕拉取·联调】验收：在 packages/web/dsh-pmboard 下执行：npx vitest run tests/board-attach.test.ts（期望 Test Files 1 passed / Tests 6 passed、exit 0）；并对照 src/client/board-entry.ts 的 deps.requestFocus 签名，确认 conversation-progress.ts 注入的实现与之逐字一致。

**操作步骤**：
1. 在 packages/web/dsh-pmboard 下执行：npx vitest run tests/board-attach.test.ts（期望 Test Files 1 passed / Tests 6 passed、exit 0）
2. 并对照 src/client/board-entry.ts 的 deps.requestFocus 签名，确认 conversation-progress.ts 注入的实现与之逐字一致。

**预期结果**：按上述步骤执行后满足验收标准：在 packages/web/dsh-pmboard 下执行：npx vitest run tests/board-attach.test.ts（期望 Test Files 1 passed / Tests 6 passed、exit 0）；并对照 src/client/board-entry.ts 的 deps.requestFocus 签名，确认 conversation-progress.ts 注入的实现与之逐字一致。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v2-23 · conversation-progress.ts 接线点击→校验→关面板→切看板并删两条留痕拉取·复核

**验收内容**：【conversation-progress.ts 接线点击→校验→关面板→切看板并删两条留痕拉取·复核】验收：在 packages/web/dsh-pmboard 下执行：npx vitest run tests/board-attach.test.ts（期望 6 passed）；再对照 docs/requirements/REQ-260928222643-4d34/design/interfaces.md 的 I-1 与 src/client/conversation-progress.ts 实际接线，逐条给出「无偏离」或偏离条目。

**操作步骤**：
1. 在 packages/web/dsh-pmboard 下执行：npx vitest run tests/board-attach.test.ts（期望 6 passed）
2. 再对照 docs/requirements/REQ-260928222643-4d34/design/interfaces.md 的 I-1 与 src/client/conversation-progress.ts 实际接线，逐条给出「无偏离」或偏离条目。

**预期结果**：按上述步骤执行后满足验收标准：在 packages/web/dsh-pmboard 下执行：npx vitest run tests/board-attach.test.ts（期望 6 passed）；再对照 docs/requirements/REQ-260928222643-4d34/design/interfaces.md 的 I-1 与 src/client/conversation-progress.ts 实际接线，逐条给出「无偏离」或偏离条目。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v2-24 · conversation-progress.ts 接线点击→校验→关面板→切看板并删两条留痕拉取·测试

**验收内容**：【conversation-progress.ts 接线点击→校验→关面板→切看板并删两条留痕拉取·测试】验收：在 packages/web/dsh-pmboard 下执行：grep -rn "fetchInjectionInfo\|fetchIsolationLog" src/client/conversation-progress.ts（期望无命中、echo 退出码非 0）；npx vitest run tests/board-attach.test.ts tests/node-panel.test.ts（期望全绿、exit 0）。

**操作步骤**：
1. 在 packages/web/dsh-pmboard 下执行：grep -rn "fetchInjectionInfo\|fetchIsolationLog" src/client/conversation-progress.ts（期望无命中、echo 退出码非 0）
2. npx vitest run tests/board-attach.test.ts tests/node-panel.test.ts（期望全绿、exit 0）。

**预期结果**：按上述步骤执行后满足验收标准：在 packages/web/dsh-pmboard 下执行：grep -rn "fetchInjectionInfo\|fetchIsolationLog" src/client/conversation-progress.ts（期望无命中、echo 退出码非 0）；npx vitest run tests/board-attach.test.ts tests/node-panel.test.ts（期望全绿、exit 0）。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v2-25 · board-mount.ts 挂载时 takeBoardFocus 初始化 mode·研发

**验收内容**：【board-mount.ts 挂载时 takeBoardFocus 初始化 mode·研发】验收：在 packages/web/dsh-pmboard 下执行：grep -n "takeBoardFocus" src/client/board-mount.ts（须命中挂载处消费点）；npx vitest run tests/board-attach.test.ts（期望 Tests 6 passed、exit 0）。

**操作步骤**：
1. 在 packages/web/dsh-pmboard 下执行：grep -n "takeBoardFocus" src/client/board-mount.ts（须命中挂载处消费点）
2. npx vitest run tests/board-attach.test.ts（期望 Tests 6 passed、exit 0）。

**预期结果**：按上述步骤执行后满足验收标准：在 packages/web/dsh-pmboard 下执行：grep -n "takeBoardFocus" src/client/board-mount.ts（须命中挂载处消费点）；npx vitest run tests/board-attach.test.ts（期望 Tests 6 passed、exit 0）。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v2-26 · board-mount.ts 挂载时 takeBoardFocus 初始化 mode·联调

**验收内容**：【board-mount.ts 挂载时 takeBoardFocus 初始化 mode·联调】验收：在 packages/web/dsh-pmboard 下执行：npx vitest run tests/board-attach.test.ts（期望 6 passed、exit 0）；并核对 src/client/board-mount.ts 挂载闭包内 takeBoardFocus() 的调用与 src/client/board-focus.ts 的导出签名一致。

**操作步骤**：
1. 在 packages/web/dsh-pmboard 下执行：npx vitest run tests/board-attach.test.ts（期望 6 passed、exit 0）
2. 并核对 src/client/board-mount.ts 挂载闭包内 takeBoardFocus() 的调用与 src/client/board-focus.ts 的导出签名一致。

**预期结果**：按上述步骤执行后满足验收标准：在 packages/web/dsh-pmboard 下执行：npx vitest run tests/board-attach.test.ts（期望 6 passed、exit 0）；并核对 src/client/board-mount.ts 挂载闭包内 takeBoardFocus() 的调用与 src/client/board-focus.ts 的导出签名一致。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v2-27 · board-mount.ts 挂载时 takeBoardFocus 初始化 mode·复核

**验收内容**：【board-mount.ts 挂载时 takeBoardFocus 初始化 mode·复核】验收：在 packages/web/dsh-pmboard 下执行：npx vitest run tests/board-attach.test.ts（期望 6 passed）；再对照 docs/requirements/REQ-260928222643-4d34/design/interfaces.md 与 src/client/board-mount.ts，逐条给出「无偏离」或偏离条目。

**操作步骤**：
1. 在 packages/web/dsh-pmboard 下执行：npx vitest run tests/board-attach.test.ts（期望 6 passed）
2. 再对照 docs/requirements/REQ-260928222643-4d34/design/interfaces.md 与 src/client/board-mount.ts，逐条给出「无偏离」或偏离条目。

**预期结果**：按上述步骤执行后满足验收标准：在 packages/web/dsh-pmboard 下执行：npx vitest run tests/board-attach.test.ts（期望 6 passed）；再对照 docs/requirements/REQ-260928222643-4d34/design/interfaces.md 与 src/client/board-mount.ts，逐条给出「无偏离」或偏离条目。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v2-28 · board-mount.ts 挂载时 takeBoardFocus 初始化 mode·测试

**验收内容**：【board-mount.ts 挂载时 takeBoardFocus 初始化 mode·测试】验收：在 packages/web/dsh-pmboard 下执行：npx vitest run tests/board-attach.test.ts（期望 6 passed、exit 0），其中含「挂载消费一次后 peekBoardFocus() 为 undefined（非粘滞）」断言。

**操作步骤**：
1. 在 packages/web/dsh-pmboard 下执行：npx vitest run tests/board-attach.test.ts（期望 6 passed、exit 0），其中含「挂载消费一次后 peekBoardFocus() 为 undefined（非粘滞）」断言。

**预期结果**：按上述步骤执行后满足验收标准：在 packages/web/dsh-pmboard 下执行：npx vitest run tests/board-attach.test.ts（期望 6 passed、exit 0），其中含「挂载消费一次后 peekBoardFocus() 为 undefined（非粘滞）」断言。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v2-29 · styles/node-panel.ts 新增入口按钮与失败提示两条规则·研发

**验收内容**：【styles/node-panel.ts 新增入口按钮与失败提示两条规则·研发】验收：在 packages/web/dsh-pmboard 下执行：grep -n "dsh-pm-np" src/client/styles/node-panel.ts（须命中新增的入口按钮与失败提示规则）；npx vitest run tests/node-panel-styles.test.ts（期望 Tests 15 passed、exit 0）。

**操作步骤**：
1. 在 packages/web/dsh-pmboard 下执行：grep -n "dsh-pm-np" src/client/styles/node-panel.ts（须命中新增的入口按钮与失败提示规则）
2. npx vitest run tests/node-panel-styles.test.ts（期望 Tests 15 passed、exit 0）。

**预期结果**：按上述步骤执行后满足验收标准：在 packages/web/dsh-pmboard 下执行：grep -n "dsh-pm-np" src/client/styles/node-panel.ts（须命中新增的入口按钮与失败提示规则）；npx vitest run tests/node-panel-styles.test.ts（期望 Tests 15 passed、exit 0）。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v2-30 · styles/node-panel.ts 新增入口按钮与失败提示两条规则·联调

**验收内容**：【styles/node-panel.ts 新增入口按钮与失败提示两条规则·联调】验收：在 packages/web/dsh-pmboard 下执行：npx vitest run tests/node-panel-styles.test.ts（期望 15 passed、exit 0）；并核对 src/client/styles/node-panel.ts 新增规则被 node-panel.ts 渲染出的 class 引用。

**操作步骤**：
1. 在 packages/web/dsh-pmboard 下执行：npx vitest run tests/node-panel-styles.test.ts（期望 15 passed、exit 0）
2. 并核对 src/client/styles/node-panel.ts 新增规则被 node-panel.ts 渲染出的 class 引用。

**预期结果**：按上述步骤执行后满足验收标准：在 packages/web/dsh-pmboard 下执行：npx vitest run tests/node-panel-styles.test.ts（期望 15 passed、exit 0）；并核对 src/client/styles/node-panel.ts 新增规则被 node-panel.ts 渲染出的 class 引用。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v2-31 · styles/node-panel.ts 新增入口按钮与失败提示两条规则·复核

**验收内容**：【styles/node-panel.ts 新增入口按钮与失败提示两条规则·复核】验收：在 packages/web/dsh-pmboard 下执行：npx vitest run tests/node-panel-styles.test.ts（期望 15 passed）；再对照 docs/requirements/REQ-260928222643-4d34/design/frontend.md 与 src/client/styles/node-panel.ts，逐条给出「无偏离」或偏离条目。

**操作步骤**：
1. 在 packages/web/dsh-pmboard 下执行：npx vitest run tests/node-panel-styles.test.ts（期望 15 passed）
2. 再对照 docs/requirements/REQ-260928222643-4d34/design/frontend.md 与 src/client/styles/node-panel.ts，逐条给出「无偏离」或偏离条目。

**预期结果**：按上述步骤执行后满足验收标准：在 packages/web/dsh-pmboard 下执行：npx vitest run tests/node-panel-styles.test.ts（期望 15 passed）；再对照 docs/requirements/REQ-260928222643-4d34/design/frontend.md 与 src/client/styles/node-panel.ts，逐条给出「无偏离」或偏离条目。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v2-32 · styles/node-panel.ts 新增入口按钮与失败提示两条规则·测试

**验收内容**：【styles/node-panel.ts 新增入口按钮与失败提示两条规则·测试】验收：在 packages/web/dsh-pmboard 下执行：npx vitest run tests/node-panel-styles.test.ts tests/node-panel.test.ts（期望 15 + 27 passed、exit 0）。

**操作步骤**：
1. 在 packages/web/dsh-pmboard 下执行：npx vitest run tests/node-panel-styles.test.ts tests/node-panel.test.ts（期望 15 + 27 passed、exit 0）。

**预期结果**：按上述步骤执行后满足验收标准：在 packages/web/dsh-pmboard 下执行：npx vitest run tests/node-panel-styles.test.ts tests/node-panel.test.ts（期望 15 + 27 passed、exit 0）。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v2-33 · 迁移与兼容核验：无 schema 变更、旧调用方与看板消费方零回归·研发

**验收内容**：【迁移与兼容核验：无 schema 变更、旧调用方与看板消费方零回归·研发】验收：在仓库根执行：git diff -- packages/web/dsh-pmboard/src | grep -n "REQBOARD_SCHEMA_VERSION\|schemaVersion"（期望无 schema 版本改动命中）；并 grep -rn "REQBOARD_SCHEMA_VERSION" packages/web/dsh-pmboard/src/shared/protocol.ts 比对取值未变。

**操作步骤**：
1. 在仓库根执行：git diff -- packages/web/dsh-pmboard/src | grep -n "REQBOARD_SCHEMA_VERSION\|schemaVersion"（期望无 schema 版本改动命中）
2. 并 grep -rn "REQBOARD_SCHEMA_VERSION" packages/web/dsh-pmboard/src/shared/protocol.ts 比对取值未变。

**预期结果**：按上述步骤执行后满足验收标准：在仓库根执行：git diff -- packages/web/dsh-pmboard/src | grep -n "REQBOARD_SCHEMA_VERSION\|schemaVersion"（期望无 schema 版本改动命中）；并 grep -rn "REQBOARD_SCHEMA_VERSION" packages/web/dsh-pmboard/src/shared/protocol.ts 比对取值未变。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v2-34 · 迁移与兼容核验：无 schema 变更、旧调用方与看板消费方零回归·复核

**验收内容**：【迁移与兼容核验：无 schema 变更、旧调用方与看板消费方零回归·复核】验收：在 packages/web/dsh-pmboard 下执行：npx vitest run tests/board-mount.test.ts tests/client-api-resolve.test.ts（期望全绿、exit 0）；再对照 docs/requirements/REQ-260928222643-4d34/design/data-model.md 逐条确认无字段/schema 变更。

**操作步骤**：
1. 在 packages/web/dsh-pmboard 下执行：npx vitest run tests/board-mount.test.ts tests/client-api-resolve.test.ts（期望全绿、exit 0）
2. 再对照 docs/requirements/REQ-260928222643-4d34/design/data-model.md 逐条确认无字段/schema 变更。

**预期结果**：按上述步骤执行后满足验收标准：在 packages/web/dsh-pmboard 下执行：npx vitest run tests/board-mount.test.ts tests/client-api-resolve.test.ts（期望全绿、exit 0）；再对照 docs/requirements/REQ-260928222643-4d34/design/data-model.md 逐条确认无字段/schema 变更。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v2-35 · 迁移与兼容核验：无 schema 变更、旧调用方与看板消费方零回归·测试

**验收内容**：【迁移与兼容核验：无 schema 变更、旧调用方与看板消费方零回归·测试】验收：在 packages/web/dsh-pmboard 下完整执行一次 npx vitest run，与基线同刻对比：期望新增红 0（失败文件/用例数不高于开工基线），且 board-focus / board-entry / node-panel / node-panel-styles / board-attach 五文件全绿。

**操作步骤**：
1. 在 packages/web/dsh-pmboard 下完整执行一次 npx vitest run，与基线同刻对比：期望新增红 0（失败文件/用例数不高于开工基线），且 board-focus / board-entry / node-panel / node-panel-styles / board-attach 五文件全绿。

**预期结果**：按上述步骤执行后满足验收标准：在 packages/web/dsh-pmboard 下完整执行一次 npx vitest run，与基线同刻对比：期望新增红 0（失败文件/用例数不高于开工基线），且 board-focus / board-entry / node-panel / node-panel-styles / board-attach 五文件全绿。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v2-36 · 重建客户端产物并发版，完成 TC-15 端到端人工验收·研发

**验收内容**：【重建客户端产物并发版，完成 TC-15 端到端人工验收·研发】验收：在 packages/web/dsh-pmboard 下执行：pnpm build:client（期望 [verify-client] OK、关键符号齐全、styles.ts 括号配对、exit 0）；并 ls -la lib/client.js 确认产物已刷新。

**操作步骤**：
1. 在 packages/web/dsh-pmboard 下执行：pnpm build:client（期望 [verify-client] OK、关键符号齐全、styles.ts 括号配对、exit 0）
2. 并 ls -la lib/client.js 确认产物已刷新。

**预期结果**：按上述步骤执行后满足验收标准：在 packages/web/dsh-pmboard 下执行：pnpm build:client（期望 [verify-client] OK、关键符号齐全、styles.ts 括号配对、exit 0）；并 ls -la lib/client.js 确认产物已刷新。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v2-37 · 重建客户端产物并发版，完成 TC-15 端到端人工验收·复核

**验收内容**：【重建客户端产物并发版，完成 TC-15 端到端人工验收·复核】验收：在 packages/web/dsh-pmboard 下执行：pnpm build:client（期望 exit 0 且 [verify-client] OK）；再对照 docs/requirements/REQ-260928222643-4d34/design/frontend.md 逐条给出「无偏离」或偏离条目。

**操作步骤**：
1. 在 packages/web/dsh-pmboard 下执行：pnpm build:client（期望 exit 0 且 [verify-client] OK）
2. 再对照 docs/requirements/REQ-260928222643-4d34/design/frontend.md 逐条给出「无偏离」或偏离条目。

**预期结果**：按上述步骤执行后满足验收标准：在 packages/web/dsh-pmboard 下执行：pnpm build:client（期望 exit 0 且 [verify-client] OK）；再对照 docs/requirements/REQ-260928222643-4d34/design/frontend.md 逐条给出「无偏离」或偏离条目。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v2-38 · 需求级验收

**验收内容**：需求级：交付结论可复核（证据齐全、与设计一致、无范围蔓延）

**操作步骤**：
1. 需求级：交付结论可复核（证据齐全、与设计一致、无范围蔓延）

**预期结果**：按上述步骤执行后满足验收标准：需求级：交付结论可复核（证据齐全、与设计一致、无范围蔓延）

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v2-41 · 需求级验收

**验收内容**：E2E 覆盖：**无（缺口）**——本需求交付涉及多组件串联，但只交了单元/集成测试。请补一条端到端场景用例（断言可观察终态）。

**操作步骤**：
1. E2E 覆盖：**无（缺口）**——本需求交付涉及多组件串联，但只交了单元/集成测试。请补一条端到端场景用例（断言可观察终态）。

**预期结果**：按上述步骤执行后满足验收标准：E2E 覆盖：**无（缺口）**——本需求交付涉及多组件串联，但只交了单元/集成测试。请补一条端到端场景用例（断言可观察终态）。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

## 2. 测试报告

- 五文件全绿：在 packages/web/dsh-pmboard 下执行 npx vitest run（board-focus / board-entry / node-panel / node-panel-styles / board-attach 五个测试文件）→ Test Files 5 passed (5)、Tests 60 passed (60)、exit 0
- FR-4 渲染器调用已断：grep -n "renderProcessFold" packages/web/dsh-pmboard/src/client/node-panel.ts → 无命中（exit 1）
- FR-4 渲染输出断言：packages/web/dsh-pmboard/tests/node-panel.test.ts 断言 html 不含「🔄 执行流程」（TC-2 单节点 + TC-3 七节点全覆盖，含「本分类跳过」态）
- FR-5 面板侧零引用：grep -c "fetchInjectionInfo|fetchIsolationLog" packages/web/dsh-pmboard/src/client/conversation-progress.ts → 0
- FR-5 残留命中属看板既有行为（需求「不做什么」#1 明令保留）：board-mount.ts 的 fetchInjectionInfo 在 git HEAD 版本即存在（grep -c = 1，renderInjectionInfo 命中 4），本次未新增对该接口的调用
- 构建门：在 packages/web/dsh-pmboard 下执行 pnpm build:client → [verify-client] OK bundle=308214 bytes, 关键符号齐全, styles.ts 括号配对, exit 0
- 自动链完成证据：reqboard 台账 advance.history 末条 ROLLUP ok「需求已全部任务完成，滚进验收」；任务 37/37 done；8 张父卡 FINALIZE_PARENT 全部 ok
- 测试覆盖标注：docs/requirements/REQ-260928222643-4d34/tests/test-report.md 已为全部 37 个任务补 covers 标注（本次新增 17 张子卡）
- 附带根因修复：packages/web/dsh-pmboard/src/application/internal/support.ts（chainBaselineOf 父卡收尾凭证基准）+ packages/web/dsh-pmboard/src/application/use-cases/AdvanceChain.ts（残留锁回收）；新增 packages/web/dsh-pmboard/tests/advance-parent-evidence.test.ts、packages/web/dsh-pmboard/tests/advance-stale-lock.test.ts 共 4 例（正例+反例）全绿

## 3. 文档完整性检查

✓ 9 类文档齐全

## 4. 验收结果

| 编号 | 验收项 | 状态 | 验收人 | 验收时间 |
|---|---|---|---|---|
| v2-1 | 新增一次性交接持有器 src/client/board-focus.ts | ✓ 通过 | human/session-f17b3bd0-023b-4f68-b85c-28d1d2da72bd | 2026-09-29 00:17 |
| v2-2 | 新增入口校验纯函数 src/client/board-entry.ts | ✓ 通过 | human/session-f17b3bd0-023b-4f68-b85c-28d1d2da72bd | 2026-09-29 00:17 |
| v2-3 | node-panel.ts 加入口按钮并删除执行流程块调用与入参 | ✓ 通过 | human/session-f17b3bd0-023b-4f68-b85c-28d1d2da72bd | 2026-09-29 00:17 |
| v2-4 | conversation-progress.ts 接线点击→校验→关面板→切看板并删两条留痕拉取 | ✓ 通过 | human/session-f17b3bd0-023b-4f68-b85c-28d1d2da72bd | 2026-09-29 00:17 |
| v2-5 | board-mount.ts 挂载时 takeBoardFocus 初始化 mode | ✓ 通过 | human/session-f17b3bd0-023b-4f68-b85c-28d1d2da72bd | 2026-09-29 00:17 |
| v2-6 | styles/node-panel.ts 新增入口按钮与失败提示两条规则 | ✓ 通过 | human/session-f17b3bd0-023b-4f68-b85c-28d1d2da72bd | 2026-09-29 00:17 |
| v2-7 | 迁移与兼容核验：无 schema 变更、旧调用方与看板消费方零回归 | ✓ 通过 | human/session-f17b3bd0-023b-4f68-b85c-28d1d2da72bd | 2026-09-29 00:17 |
| v2-8 | 重建客户端产物并发版，完成 TC-15 端到端人工验收 | ✓ 通过 | human/session-f17b3bd0-023b-4f68-b85c-28d1d2da72bd | 2026-09-29 00:17 |
| v2-9 | 新增一次性交接持有器 src/client/board-focus.ts·研发 | ✓ 通过 | human/session-f17b3bd0-023b-4f68-b85c-28d1d2da72bd | 2026-09-29 00:17 |
| v2-10 | 新增一次性交接持有器 src/client/board-focus.ts·联调 | ✓ 通过 | human/session-f17b3bd0-023b-4f68-b85c-28d1d2da72bd | 2026-09-29 00:17 |
| v2-11 | 新增一次性交接持有器 src/client/board-focus.ts·复核 | ✓ 通过 | human/session-f17b3bd0-023b-4f68-b85c-28d1d2da72bd | 2026-09-29 00:17 |
| v2-12 | 新增一次性交接持有器 src/client/board-focus.ts·测试 | ✓ 通过 | human/session-f17b3bd0-023b-4f68-b85c-28d1d2da72bd | 2026-09-29 00:17 |
| v2-13 | 新增入口校验纯函数 src/client/board-entry.ts·研发 | ✓ 通过 | human/session-f17b3bd0-023b-4f68-b85c-28d1d2da72bd | 2026-09-29 00:17 |
| v2-14 | 新增入口校验纯函数 src/client/board-entry.ts·联调 | ✓ 通过 | human/session-f17b3bd0-023b-4f68-b85c-28d1d2da72bd | 2026-09-29 00:17 |
| v2-15 | 新增入口校验纯函数 src/client/board-entry.ts·复核 | ✓ 通过 | human/session-f17b3bd0-023b-4f68-b85c-28d1d2da72bd | 2026-09-29 00:17 |
| v2-16 | 新增入口校验纯函数 src/client/board-entry.ts·测试 | ✓ 通过 | human/session-f17b3bd0-023b-4f68-b85c-28d1d2da72bd | 2026-09-29 00:17 |
| v2-17 | node-panel.ts 加入口按钮并删除执行流程块调用与入参·研发 | ✓ 通过 | human/session-f17b3bd0-023b-4f68-b85c-28d1d2da72bd | 2026-09-29 00:17 |
| v2-18 | node-panel.ts 加入口按钮并删除执行流程块调用与入参·联调 | ✓ 通过 | human/session-f17b3bd0-023b-4f68-b85c-28d1d2da72bd | 2026-09-29 00:17 |
| v2-19 | node-panel.ts 加入口按钮并删除执行流程块调用与入参·复核 | ✓ 通过 | human/session-f17b3bd0-023b-4f68-b85c-28d1d2da72bd | 2026-09-29 00:17 |
| v2-20 | node-panel.ts 加入口按钮并删除执行流程块调用与入参·测试 | ✓ 通过 | human/session-f17b3bd0-023b-4f68-b85c-28d1d2da72bd | 2026-09-29 00:17 |
| v2-21 | conversation-progress.ts 接线点击→校验→关面板→切看板并删两条留痕拉取·研发 | ✓ 通过 | human/session-f17b3bd0-023b-4f68-b85c-28d1d2da72bd | 2026-09-29 00:17 |
| v2-22 | conversation-progress.ts 接线点击→校验→关面板→切看板并删两条留痕拉取·联调 | ✓ 通过 | human/session-f17b3bd0-023b-4f68-b85c-28d1d2da72bd | 2026-09-29 00:17 |
| v2-23 | conversation-progress.ts 接线点击→校验→关面板→切看板并删两条留痕拉取·复核 | ✓ 通过 | human/session-f17b3bd0-023b-4f68-b85c-28d1d2da72bd | 2026-09-29 00:17 |
| v2-24 | conversation-progress.ts 接线点击→校验→关面板→切看板并删两条留痕拉取·测试 | ✓ 通过 | human/session-f17b3bd0-023b-4f68-b85c-28d1d2da72bd | 2026-09-29 00:17 |
| v2-25 | board-mount.ts 挂载时 takeBoardFocus 初始化 mode·研发 | ✓ 通过 | human/session-f17b3bd0-023b-4f68-b85c-28d1d2da72bd | 2026-09-29 00:17 |
| v2-26 | board-mount.ts 挂载时 takeBoardFocus 初始化 mode·联调 | ✓ 通过 | human/session-f17b3bd0-023b-4f68-b85c-28d1d2da72bd | 2026-09-29 00:17 |
| v2-27 | board-mount.ts 挂载时 takeBoardFocus 初始化 mode·复核 | ✓ 通过 | human/session-f17b3bd0-023b-4f68-b85c-28d1d2da72bd | 2026-09-29 00:17 |
| v2-28 | board-mount.ts 挂载时 takeBoardFocus 初始化 mode·测试 | ✓ 通过 | human/session-f17b3bd0-023b-4f68-b85c-28d1d2da72bd | 2026-09-29 00:17 |
| v2-29 | styles/node-panel.ts 新增入口按钮与失败提示两条规则·研发 | ✓ 通过 | human/session-f17b3bd0-023b-4f68-b85c-28d1d2da72bd | 2026-09-29 00:17 |
| v2-30 | styles/node-panel.ts 新增入口按钮与失败提示两条规则·联调 | ✓ 通过 | human/session-f17b3bd0-023b-4f68-b85c-28d1d2da72bd | 2026-09-29 00:17 |
| v2-31 | styles/node-panel.ts 新增入口按钮与失败提示两条规则·复核 | ✓ 通过 | human/session-f17b3bd0-023b-4f68-b85c-28d1d2da72bd | 2026-09-29 00:18 |
| v2-32 | styles/node-panel.ts 新增入口按钮与失败提示两条规则·测试 | ✓ 通过 | human/session-f17b3bd0-023b-4f68-b85c-28d1d2da72bd | 2026-09-29 00:18 |
| v2-33 | 迁移与兼容核验：无 schema 变更、旧调用方与看板消费方零回归·研发 | ✓ 通过 | human/session-f17b3bd0-023b-4f68-b85c-28d1d2da72bd | 2026-09-29 00:18 |
| v2-34 | 迁移与兼容核验：无 schema 变更、旧调用方与看板消费方零回归·复核 | ✓ 通过 | human/session-f17b3bd0-023b-4f68-b85c-28d1d2da72bd | 2026-09-29 00:18 |
| v2-35 | 迁移与兼容核验：无 schema 变更、旧调用方与看板消费方零回归·测试 | ✓ 通过 | human/session-f17b3bd0-023b-4f68-b85c-28d1d2da72bd | 2026-09-29 00:18 |
| v2-36 | 重建客户端产物并发版，完成 TC-15 端到端人工验收·研发 | ✓ 通过 | human/session-f17b3bd0-023b-4f68-b85c-28d1d2da72bd | 2026-09-29 00:18 |
| v2-37 | 重建客户端产物并发版，完成 TC-15 端到端人工验收·复核 | ✓ 通过 | human/session-f17b3bd0-023b-4f68-b85c-28d1d2da72bd | 2026-09-29 00:18 |
| v2-38 | 需求级验收 | ✓ 通过 | human/session-f17b3bd0-023b-4f68-b85c-28d1d2da72bd | 2026-09-29 00:18 |
| v2-41 | 需求级验收 | ✓ 通过 | human/session-f17b3bd0-023b-4f68-b85c-28d1d2da72bd | 2026-09-29 00:18 |
