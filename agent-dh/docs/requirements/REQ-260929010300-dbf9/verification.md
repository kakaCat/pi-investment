# REQ-260929010300-dbf9 验收文档

> 自动生成于 reqboard_submit(kind=verification) · 验收单 v7

**交付结论**：交付结论（v7 · 追加裁定 F）：恢复「单击 DAG 卡片 → 打开该卡任务卡文档」——根因是换成 Canvas 后 CardData 没带 cardDoc、单击被「钉住高亮」占用。落地：CardData 增 cardDoc（buildDagData 透传，client TaskRecord 补该字段）；挂载侧新增 canvas click → 派发 data-action="open-doc"（延迟 220ms，双击取消并改走 open-task）；副标题如实写「单击打开任务卡文档 · 双击打开任务详情」。六轮累计：①数据侧 dependsOn 归一 ②删标题/统计条 ③竖向去折行 ④删父卡蓝条 ⑤泳道去链进度 ⑥恢复点击开文档。证据：dag-view 29 用例（+4）、8 文件 158 用例全绿；全量 85 failed/2632 passed 与上一轮失败文件集合逐项相同；tsc 208（本次 0 error）；pnpm build 退出 0。

## 1. 验收列表

### v7-1 · 定契约：入参结构类型收敛 + 面板画布常量

**验收内容**：【定契约：入参结构类型收敛 + 面板画布常量】验收：cd packages/web/dsh-pmboard && npx tsc --noEmit -p tsconfig.json 0 error；cd packages/web/dsh-pmboard && npx vitest run tests/dag-view.test.ts tests/client-view.test.ts 全绿（缺省行为不变：buildDagCanvas(tasks) 返回值仍包含 id="dag-canvas"）

**操作步骤**：
1. cd packages/web/dsh-pmboard && npx tsc --noEmit -p tsconfig.json 0 error
2. cd packages/web/dsh-pmboard && npx vitest run tests/dag-view.test.ts tests/client-view.test.ts 全绿（缺省行为不变：buildDagCanvas(tasks) 返回值仍包含 id="dag-canvas"）

**预期结果**：按上述步骤执行后满足验收标准：cd packages/web/dsh-pmboard && npx tsc --noEmit -p tsconfig.json 0 error；cd packages/web/dsh-pmboard && npx vitest run tests/dag-view.test.ts tests/client-view.test.ts 全绿（缺省行为不变：buildDagCanvas(tasks) 返回值仍包含 id="dag-canvas"）

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v7-2 · 画布 id 参数化 + 挂载实例表

**验收内容**：【画布 id 参数化 + 挂载实例表】验收：cd packages/web/dsh-pmboard && npx vitest run tests/dag-view.test.ts 全绿，且新增用例断言：两个不同 canvasId 各挂载一次后释放其一，另一实例对应的画布元素仍存在于 DOM（两者互不释放）

**操作步骤**：
1. cd packages/web/dsh-pmboard && npx vitest run tests/dag-view.test.ts 全绿，且新增用例断言：两个不同 canvasId 各挂载一次后释放其一，另一实例对应的画布元素仍存在于 DOM（两者互不释放）

**预期结果**：按上述步骤执行后满足验收标准：cd packages/web/dsh-pmboard && npx vitest run tests/dag-view.test.ts 全绿，且新增用例断言：两个不同 canvasId 各挂载一次后释放其一，另一实例对应的画布元素仍存在于 DOM（两者互不释放）

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v7-3 · 会话面板两处 DAG 块改调同一构建函数

**验收内容**：【会话面板两处 DAG 块改调同一构建函数】验收：cd packages/web/dsh-pmboard && npx vitest run tests/node-panel.test.ts 全绿；实施阶段与拆分阶段两处 HTML 均包含 dsh-pm-dag-panel 与 id="np-dag-canvas"，且不包含 dsh-pm-np-dag-layer

**操作步骤**：
1. cd packages/web/dsh-pmboard && npx vitest run tests/node-panel.test.ts 全绿
2. 实施阶段与拆分阶段两处 HTML 均包含 dsh-pm-dag-panel 与 id="np-dag-canvas"，且不包含 dsh-pm-np-dag-layer

**预期结果**：按上述步骤执行后满足验收标准：cd packages/web/dsh-pmboard && npx vitest run tests/node-panel.test.ts 全绿；实施阶段与拆分阶段两处 HTML 均包含 dsh-pm-dag-panel 与 id="np-dag-canvas"，且不包含 dsh-pm-np-dag-layer

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v7-4 · 会话面板挂载钩子（DOM 就绪后挂载）

**验收内容**：【会话面板挂载钩子（DOM 就绪后挂载）】验收：打开 :13080 会话右上角流程节点 → 实施阶段 [DAG] 页签可见画布（2026-09-29 裁定 B：无标题行 / 无统计条）；切到泳道再切回 [DAG] 画布仍存在；cd packages/web/dsh-pmboard && npx vitest run tests/node-panel.test.ts tests/client-view.test.ts 全绿

**操作步骤**：
1. 打开 :13080 会话右上角流程节点 → 实施阶段 [DAG] 页签可见画布（2026-09-29 裁定 B：无标题行 / 无统计条）
2. 切到泳道再切回 [DAG] 画布仍存在
3. cd packages/web/dsh-pmboard && npx vitest run tests/node-panel.test.ts tests/client-view.test.ts 全绿

**预期结果**：按上述步骤执行后满足验收标准：打开 :13080 会话右上角流程节点 → 实施阶段 [DAG] 页签可见画布（2026-09-29 裁定 B：无标题行 / 无统计条）；切到泳道再切回 [DAG] 画布仍存在；cd packages/web/dsh-pmboard && npx vitest run tests/node-panel.test.ts tests/client-view.test.ts 全绿

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v7-5 · DAG 骨架皮肤换成 np 苹果风

**验收内容**：【DAG 骨架皮肤换成 np 苹果风】验收：grep -n -- '--dsw-' packages/web/dsh-pmboard/src/client/styles/dag.ts 无输出； DAG_CSS 的 .dsh-pm-dag-panel 底色 = var(--dsh-pm-np-bg)（= 泳道图底色 #f5f5f7，2026-09-29 用户裁定，不得为白底）； cd packages/web/dsh-pmboard && npx vitest run tests/dag-styles.test.ts 全绿； cd packages/web/dsh-pmboard && pnpm build:client 退出 0 且输出含 [verify-client] OK

**操作步骤**：
1. grep -n -- '--dsw-' packages/web/dsh-pmboard/src/client/styles/dag.ts 无输出
2. DAG_CSS 的 .dsh-pm-dag-panel 底色 = var(--dsh-pm-np-bg)（= 泳道图底色 #f5f5f7，2026-09-29 用户裁定，不得为白底）
3. cd packages/web/dsh-pmboard && npx vitest run tests/dag-styles.test.ts 全绿
4. cd packages/web/dsh-pmboard && pnpm build:client 退出 0 且输出含 [verify-client] OK

**预期结果**：按上述步骤执行后满足验收标准：grep -n -- '--dsw-' packages/web/dsh-pmboard/src/client/styles/dag.ts 无输出； DAG_CSS 的 .dsh-pm-dag-panel 底色 = var(--dsh-pm-np-bg)（= 泳道图底色 #f5f5f7，2026-09-29 用户裁定，不得为白底）； cd packages/web/dsh-pmboard && npx vitest run tests/dag-styles.test.ts 全绿； cd packages/web/dsh-pmboard && pnpm build:client 退出 0 且输出含 [verify-client] OK

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v7-6 · 迁移与兼容核验 + 需求详情回归

**验收内容**：【迁移与兼容核验 + 需求详情回归】验收：cd packages/web/dsh-pmboard && npx vitest run dag-view dag-styles node-panel client-view 全绿；需求详情调用方 src/client/views/stage-detail.ts 无改动条目；src/client/dag/card-renderer.ts 的改动仅限 2026-09-29 裁定 D 删除「父卡左侧蓝条」一处（徽标/208×72 几何/配色零改动）

**操作步骤**：
1. cd packages/web/dsh-pmboard && npx vitest run dag-view dag-styles node-panel client-view 全绿
2. 需求详情调用方 src/client/views/stage-detail.ts 无改动条目
3. src/client/dag/card-renderer.ts 的改动仅限 2026-09-29 裁定 D 删除「父卡左侧蓝条」一处（徽标/208×72 几何/配色零改动）

**预期结果**：按上述步骤执行后满足验收标准：cd packages/web/dsh-pmboard && npx vitest run dag-view dag-styles node-panel client-view 全绿；需求详情调用方 src/client/views/stage-detail.ts 无改动条目；src/client/dag/card-renderer.ts 的改动仅限 2026-09-29 裁定 D 删除「父卡左侧蓝条」一处（徽标/208×72 几何/配色零改动）

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v7-7 · 定契约：入参结构类型收敛 + 面板画布常量·研发

**验收内容**：【定契约：入参结构类型收敛 + 面板画布常量·研发】验收：cd packages/web/dsh-pmboard && npx tsc --noEmit -p tsconfig.json → 本次涉及文件 0 error；cd packages/web/dsh-pmboard && npx vitest run tests/dag-view.test.ts → 全绿；git diff --stat 可见本卡改动文件（mtime ≥ 链出身）

**操作步骤**：
1. cd packages/web/dsh-pmboard && npx tsc --noEmit -p tsconfig.json → 本次涉及文件 0 error
2. cd packages/web/dsh-pmboard && npx vitest run tests/dag-view.test.ts → 全绿
3. git diff --stat 可见本卡改动文件（mtime ≥ 链出身）

**预期结果**：按上述步骤执行后满足验收标准：cd packages/web/dsh-pmboard && npx tsc --noEmit -p tsconfig.json → 本次涉及文件 0 error；cd packages/web/dsh-pmboard && npx vitest run tests/dag-view.test.ts → 全绿；git diff --stat 可见本卡改动文件（mtime ≥ 链出身）

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v7-8 · 定契约：入参结构类型收敛 + 面板画布常量·联调

**验收内容**：【定契约：入参结构类型收敛 + 面板画布常量·联调】验收：cd packages/web/dsh-pmboard && npx vitest run tests/dag-view.test.ts → 全绿；grep -n "PANEL_DAG_CANVAS_ID" packages/web/dsh-pmboard/src/client/views/dag-view.ts → 有命中（本卡接线确实在源码里）

**操作步骤**：
1. cd packages/web/dsh-pmboard && npx vitest run tests/dag-view.test.ts → 全绿
2. grep -n "PANEL_DAG_CANVAS_ID" packages/web/dsh-pmboard/src/client/views/dag-view.ts → 有命中（本卡接线确实在源码里）

**预期结果**：按上述步骤执行后满足验收标准：cd packages/web/dsh-pmboard && npx vitest run tests/dag-view.test.ts → 全绿；grep -n "PANEL_DAG_CANVAS_ID" packages/web/dsh-pmboard/src/client/views/dag-view.ts → 有命中（本卡接线确实在源码里）

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v7-9 · 定契约：入参结构类型收敛 + 面板画布常量·复核

**验收内容**：【定契约：入参结构类型收敛 + 面板画布常量·复核】验收：对设计与实现的偏离逐条给出结论；无偏离时显式写明「无偏离」及依据

**操作步骤**：
1. 对设计与实现的偏离逐条给出结论
2. 无偏离时显式写明「无偏离」及依据

**预期结果**：按上述步骤执行后满足验收标准：对设计与实现的偏离逐条给出结论；无偏离时显式写明「无偏离」及依据

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v7-10 · 定契约：入参结构类型收敛 + 面板画布常量·测试

**验收内容**：【定契约：入参结构类型收敛 + 面板画布常量·测试】验收：cd packages/web/dsh-pmboard && npx vitest run tests/dag-view.test.ts tests/node-panel.test.ts tests/client-view.test.ts tests/dag-styles.test.ts → 4 files passed / 111 tests passed；cd packages/web/dsh-pmboard && pnpm build:client → 退出 0 且输出含 [verify-client] OK

**操作步骤**：
1. cd packages/web/dsh-pmboard && npx vitest run tests/dag-view.test.ts tests/node-panel.test.ts tests/client-view.test.ts tests/dag-styles.test.ts → 4 files passed / 111 tests passed
2. cd packages/web/dsh-pmboard && pnpm build:client → 退出 0 且输出含 [verify-client] OK

**预期结果**：按上述步骤执行后满足验收标准：cd packages/web/dsh-pmboard && npx vitest run tests/dag-view.test.ts tests/node-panel.test.ts tests/client-view.test.ts tests/dag-styles.test.ts → 4 files passed / 111 tests passed；cd packages/web/dsh-pmboard && pnpm build:client → 退出 0 且输出含 [verify-client] OK

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v7-11 · 画布 id 参数化 + 挂载实例表·研发

**验收内容**：【画布 id 参数化 + 挂载实例表·研发】验收：cd packages/web/dsh-pmboard && npx tsc --noEmit -p tsconfig.json → 本次涉及文件 0 error；cd packages/web/dsh-pmboard && npx vitest run tests/dag-view.test.ts → 全绿；git diff --stat 可见本卡改动文件（mtime ≥ 链出身）

**操作步骤**：
1. cd packages/web/dsh-pmboard && npx tsc --noEmit -p tsconfig.json → 本次涉及文件 0 error
2. cd packages/web/dsh-pmboard && npx vitest run tests/dag-view.test.ts → 全绿
3. git diff --stat 可见本卡改动文件（mtime ≥ 链出身）

**预期结果**：按上述步骤执行后满足验收标准：cd packages/web/dsh-pmboard && npx tsc --noEmit -p tsconfig.json → 本次涉及文件 0 error；cd packages/web/dsh-pmboard && npx vitest run tests/dag-view.test.ts → 全绿；git diff --stat 可见本卡改动文件（mtime ≥ 链出身）

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v7-12 · 画布 id 参数化 + 挂载实例表·联调

**验收内容**：【画布 id 参数化 + 挂载实例表·联调】验收：cd packages/web/dsh-pmboard && npx vitest run tests/dag-view.test.ts → 全绿；grep -n "disposers" packages/web/dsh-pmboard/src/client/views/dag-view.ts → 有命中（本卡接线确实在源码里）

**操作步骤**：
1. cd packages/web/dsh-pmboard && npx vitest run tests/dag-view.test.ts → 全绿
2. grep -n "disposers" packages/web/dsh-pmboard/src/client/views/dag-view.ts → 有命中（本卡接线确实在源码里）

**预期结果**：按上述步骤执行后满足验收标准：cd packages/web/dsh-pmboard && npx vitest run tests/dag-view.test.ts → 全绿；grep -n "disposers" packages/web/dsh-pmboard/src/client/views/dag-view.ts → 有命中（本卡接线确实在源码里）

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v7-13 · 画布 id 参数化 + 挂载实例表·复核

**验收内容**：【画布 id 参数化 + 挂载实例表·复核】验收：对设计与实现的偏离逐条给出结论；无偏离时显式写明「无偏离」及依据

**操作步骤**：
1. 对设计与实现的偏离逐条给出结论
2. 无偏离时显式写明「无偏离」及依据

**预期结果**：按上述步骤执行后满足验收标准：对设计与实现的偏离逐条给出结论；无偏离时显式写明「无偏离」及依据

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v7-14 · 画布 id 参数化 + 挂载实例表·测试

**验收内容**：【画布 id 参数化 + 挂载实例表·测试】验收：cd packages/web/dsh-pmboard && npx vitest run tests/dag-view.test.ts tests/node-panel.test.ts tests/client-view.test.ts tests/dag-styles.test.ts → 4 files passed / 111 tests passed；cd packages/web/dsh-pmboard && pnpm build:client → 退出 0 且输出含 [verify-client] OK

**操作步骤**：
1. cd packages/web/dsh-pmboard && npx vitest run tests/dag-view.test.ts tests/node-panel.test.ts tests/client-view.test.ts tests/dag-styles.test.ts → 4 files passed / 111 tests passed
2. cd packages/web/dsh-pmboard && pnpm build:client → 退出 0 且输出含 [verify-client] OK

**预期结果**：按上述步骤执行后满足验收标准：cd packages/web/dsh-pmboard && npx vitest run tests/dag-view.test.ts tests/node-panel.test.ts tests/client-view.test.ts tests/dag-styles.test.ts → 4 files passed / 111 tests passed；cd packages/web/dsh-pmboard && pnpm build:client → 退出 0 且输出含 [verify-client] OK

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v7-15 · 会话面板两处 DAG 块改调同一构建函数·研发

**验收内容**：【会话面板两处 DAG 块改调同一构建函数·研发】验收：cd packages/web/dsh-pmboard && npx tsc --noEmit -p tsconfig.json → 本次涉及文件 0 error；cd packages/web/dsh-pmboard && npx vitest run tests/node-panel.test.ts → 全绿；git diff --stat 可见本卡改动文件（mtime ≥ 链出身）

**操作步骤**：
1. cd packages/web/dsh-pmboard && npx tsc --noEmit -p tsconfig.json → 本次涉及文件 0 error
2. cd packages/web/dsh-pmboard && npx vitest run tests/node-panel.test.ts → 全绿
3. git diff --stat 可见本卡改动文件（mtime ≥ 链出身）

**预期结果**：按上述步骤执行后满足验收标准：cd packages/web/dsh-pmboard && npx tsc --noEmit -p tsconfig.json → 本次涉及文件 0 error；cd packages/web/dsh-pmboard && npx vitest run tests/node-panel.test.ts → 全绿；git diff --stat 可见本卡改动文件（mtime ≥ 链出身）

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v7-16 · 会话面板两处 DAG 块改调同一构建函数·联调

**验收内容**：【会话面板两处 DAG 块改调同一构建函数·联调】验收：cd packages/web/dsh-pmboard && npx vitest run tests/node-panel.test.ts → 全绿；grep -n "buildDagCanvas" packages/web/dsh-pmboard/src/client/node-panel.ts → 有命中（本卡接线确实在源码里）

**操作步骤**：
1. cd packages/web/dsh-pmboard && npx vitest run tests/node-panel.test.ts → 全绿
2. grep -n "buildDagCanvas" packages/web/dsh-pmboard/src/client/node-panel.ts → 有命中（本卡接线确实在源码里）

**预期结果**：按上述步骤执行后满足验收标准：cd packages/web/dsh-pmboard && npx vitest run tests/node-panel.test.ts → 全绿；grep -n "buildDagCanvas" packages/web/dsh-pmboard/src/client/node-panel.ts → 有命中（本卡接线确实在源码里）

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v7-17 · 会话面板两处 DAG 块改调同一构建函数·复核

**验收内容**：【会话面板两处 DAG 块改调同一构建函数·复核】验收：对设计与实现的偏离逐条给出结论；无偏离时显式写明「无偏离」及依据

**操作步骤**：
1. 对设计与实现的偏离逐条给出结论
2. 无偏离时显式写明「无偏离」及依据

**预期结果**：按上述步骤执行后满足验收标准：对设计与实现的偏离逐条给出结论；无偏离时显式写明「无偏离」及依据

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v7-18 · 会话面板两处 DAG 块改调同一构建函数·测试

**验收内容**：【会话面板两处 DAG 块改调同一构建函数·测试】验收：cd packages/web/dsh-pmboard && npx vitest run tests/dag-view.test.ts tests/node-panel.test.ts tests/client-view.test.ts tests/dag-styles.test.ts → 4 files passed / 111 tests passed；cd packages/web/dsh-pmboard && pnpm build:client → 退出 0 且输出含 [verify-client] OK

**操作步骤**：
1. cd packages/web/dsh-pmboard && npx vitest run tests/dag-view.test.ts tests/node-panel.test.ts tests/client-view.test.ts tests/dag-styles.test.ts → 4 files passed / 111 tests passed
2. cd packages/web/dsh-pmboard && pnpm build:client → 退出 0 且输出含 [verify-client] OK

**预期结果**：按上述步骤执行后满足验收标准：cd packages/web/dsh-pmboard && npx vitest run tests/dag-view.test.ts tests/node-panel.test.ts tests/client-view.test.ts tests/dag-styles.test.ts → 4 files passed / 111 tests passed；cd packages/web/dsh-pmboard && pnpm build:client → 退出 0 且输出含 [verify-client] OK

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v7-19 · 会话面板挂载钩子（DOM 就绪后挂载）·研发

**验收内容**：【会话面板挂载钩子（DOM 就绪后挂载）·研发】验收：cd packages/web/dsh-pmboard && npx tsc --noEmit -p tsconfig.json → 本次涉及文件 0 error；cd packages/web/dsh-pmboard && npx vitest run tests/node-panel.test.ts tests/client-view.test.ts → 全绿；git diff --stat 可见本卡改动文件（mtime ≥ 链出身）

**操作步骤**：
1. cd packages/web/dsh-pmboard && npx tsc --noEmit -p tsconfig.json → 本次涉及文件 0 error
2. cd packages/web/dsh-pmboard && npx vitest run tests/node-panel.test.ts tests/client-view.test.ts → 全绿
3. git diff --stat 可见本卡改动文件（mtime ≥ 链出身）

**预期结果**：按上述步骤执行后满足验收标准：cd packages/web/dsh-pmboard && npx tsc --noEmit -p tsconfig.json → 本次涉及文件 0 error；cd packages/web/dsh-pmboard && npx vitest run tests/node-panel.test.ts tests/client-view.test.ts → 全绿；git diff --stat 可见本卡改动文件（mtime ≥ 链出身）

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v7-20 · 会话面板挂载钩子（DOM 就绪后挂载）·联调

**验收内容**：【会话面板挂载钩子（DOM 就绪后挂载）·联调】验收：cd packages/web/dsh-pmboard && npx vitest run tests/node-panel.test.ts tests/client-view.test.ts → 全绿；grep -n "tryMountDagCanvas" packages/web/dsh-pmboard/src/client/conversation-progress.ts → 有命中（本卡接线确实在源码里）

**操作步骤**：
1. cd packages/web/dsh-pmboard && npx vitest run tests/node-panel.test.ts tests/client-view.test.ts → 全绿
2. grep -n "tryMountDagCanvas" packages/web/dsh-pmboard/src/client/conversation-progress.ts → 有命中（本卡接线确实在源码里）

**预期结果**：按上述步骤执行后满足验收标准：cd packages/web/dsh-pmboard && npx vitest run tests/node-panel.test.ts tests/client-view.test.ts → 全绿；grep -n "tryMountDagCanvas" packages/web/dsh-pmboard/src/client/conversation-progress.ts → 有命中（本卡接线确实在源码里）

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v7-21 · 会话面板挂载钩子（DOM 就绪后挂载）·复核

**验收内容**：【会话面板挂载钩子（DOM 就绪后挂载）·复核】验收：对设计与实现的偏离逐条给出结论；无偏离时显式写明「无偏离」及依据

**操作步骤**：
1. 对设计与实现的偏离逐条给出结论
2. 无偏离时显式写明「无偏离」及依据

**预期结果**：按上述步骤执行后满足验收标准：对设计与实现的偏离逐条给出结论；无偏离时显式写明「无偏离」及依据

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v7-22 · 会话面板挂载钩子（DOM 就绪后挂载）·测试

**验收内容**：【会话面板挂载钩子（DOM 就绪后挂载）·测试】验收：cd packages/web/dsh-pmboard && npx vitest run tests/dag-view.test.ts tests/node-panel.test.ts tests/client-view.test.ts tests/dag-styles.test.ts → 4 files passed / 111 tests passed；cd packages/web/dsh-pmboard && pnpm build:client → 退出 0 且输出含 [verify-client] OK

**操作步骤**：
1. cd packages/web/dsh-pmboard && npx vitest run tests/dag-view.test.ts tests/node-panel.test.ts tests/client-view.test.ts tests/dag-styles.test.ts → 4 files passed / 111 tests passed
2. cd packages/web/dsh-pmboard && pnpm build:client → 退出 0 且输出含 [verify-client] OK

**预期结果**：按上述步骤执行后满足验收标准：cd packages/web/dsh-pmboard && npx vitest run tests/dag-view.test.ts tests/node-panel.test.ts tests/client-view.test.ts tests/dag-styles.test.ts → 4 files passed / 111 tests passed；cd packages/web/dsh-pmboard && pnpm build:client → 退出 0 且输出含 [verify-client] OK

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v7-23 · DAG 骨架皮肤换成 np 苹果风·研发

**验收内容**：【DAG 骨架皮肤换成 np 苹果风·研发】验收：cd packages/web/dsh-pmboard && npx tsc --noEmit -p tsconfig.json → 本次涉及文件 0 error；cd packages/web/dsh-pmboard && npx vitest run tests/dag-styles.test.ts → 全绿；git diff --stat 可见本卡改动文件（mtime ≥ 链出身）

**操作步骤**：
1. cd packages/web/dsh-pmboard && npx tsc --noEmit -p tsconfig.json → 本次涉及文件 0 error
2. cd packages/web/dsh-pmboard && npx vitest run tests/dag-styles.test.ts → 全绿
3. git diff --stat 可见本卡改动文件（mtime ≥ 链出身）

**预期结果**：按上述步骤执行后满足验收标准：cd packages/web/dsh-pmboard && npx tsc --noEmit -p tsconfig.json → 本次涉及文件 0 error；cd packages/web/dsh-pmboard && npx vitest run tests/dag-styles.test.ts → 全绿；git diff --stat 可见本卡改动文件（mtime ≥ 链出身）

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v7-24 · DAG 骨架皮肤换成 np 苹果风·联调

**验收内容**：【DAG 骨架皮肤换成 np 苹果风·联调】验收：cd packages/web/dsh-pmboard && npx vitest run tests/dag-styles.test.ts → 全绿；grep -n "dsh-pm-np-bg" packages/web/dsh-pmboard/src/client/styles/dag.ts → 有命中（本卡接线确实在源码里）

**操作步骤**：
1. cd packages/web/dsh-pmboard && npx vitest run tests/dag-styles.test.ts → 全绿
2. grep -n "dsh-pm-np-bg" packages/web/dsh-pmboard/src/client/styles/dag.ts → 有命中（本卡接线确实在源码里）

**预期结果**：按上述步骤执行后满足验收标准：cd packages/web/dsh-pmboard && npx vitest run tests/dag-styles.test.ts → 全绿；grep -n "dsh-pm-np-bg" packages/web/dsh-pmboard/src/client/styles/dag.ts → 有命中（本卡接线确实在源码里）

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v7-25 · DAG 骨架皮肤换成 np 苹果风·复核

**验收内容**：【DAG 骨架皮肤换成 np 苹果风·复核】验收：对设计与实现的偏离逐条给出结论；无偏离时显式写明「无偏离」及依据

**操作步骤**：
1. 对设计与实现的偏离逐条给出结论
2. 无偏离时显式写明「无偏离」及依据

**预期结果**：按上述步骤执行后满足验收标准：对设计与实现的偏离逐条给出结论；无偏离时显式写明「无偏离」及依据

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v7-26 · DAG 骨架皮肤换成 np 苹果风·测试

**验收内容**：【DAG 骨架皮肤换成 np 苹果风·测试】验收：cd packages/web/dsh-pmboard && npx vitest run tests/dag-view.test.ts tests/node-panel.test.ts tests/client-view.test.ts tests/dag-styles.test.ts → 4 files passed / 111 tests passed；cd packages/web/dsh-pmboard && pnpm build:client → 退出 0 且输出含 [verify-client] OK

**操作步骤**：
1. cd packages/web/dsh-pmboard && npx vitest run tests/dag-view.test.ts tests/node-panel.test.ts tests/client-view.test.ts tests/dag-styles.test.ts → 4 files passed / 111 tests passed
2. cd packages/web/dsh-pmboard && pnpm build:client → 退出 0 且输出含 [verify-client] OK

**预期结果**：按上述步骤执行后满足验收标准：cd packages/web/dsh-pmboard && npx vitest run tests/dag-view.test.ts tests/node-panel.test.ts tests/client-view.test.ts tests/dag-styles.test.ts → 4 files passed / 111 tests passed；cd packages/web/dsh-pmboard && pnpm build:client → 退出 0 且输出含 [verify-client] OK

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v7-27 · 迁移与兼容核验 + 需求详情回归·研发

**验收内容**：【迁移与兼容核验 + 需求详情回归·研发】验收：cd packages/web/dsh-pmboard && npx tsc --noEmit -p tsconfig.json → 本次涉及文件 0 error；cd packages/web/dsh-pmboard && npx vitest run tests/dag-view.test.ts tests/node-panel.test.ts tests/client-view.test.ts tests/dag-styles.test.ts → 全绿；git diff --stat 可见本卡改动文件（mtime ≥ 链出身）

**操作步骤**：
1. cd packages/web/dsh-pmboard && npx tsc --noEmit -p tsconfig.json → 本次涉及文件 0 error
2. cd packages/web/dsh-pmboard && npx vitest run tests/dag-view.test.ts tests/node-panel.test.ts tests/client-view.test.ts tests/dag-styles.test.ts → 全绿
3. git diff --stat 可见本卡改动文件（mtime ≥ 链出身）

**预期结果**：按上述步骤执行后满足验收标准：cd packages/web/dsh-pmboard && npx tsc --noEmit -p tsconfig.json → 本次涉及文件 0 error；cd packages/web/dsh-pmboard && npx vitest run tests/dag-view.test.ts tests/node-panel.test.ts tests/client-view.test.ts tests/dag-styles.test.ts → 全绿；git diff --stat 可见本卡改动文件（mtime ≥ 链出身）

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v7-28 · 迁移与兼容核验 + 需求详情回归·复核

**验收内容**：【迁移与兼容核验 + 需求详情回归·复核】验收：对设计与实现的偏离逐条给出结论；无偏离时显式写明「无偏离」及依据

**操作步骤**：
1. 对设计与实现的偏离逐条给出结论
2. 无偏离时显式写明「无偏离」及依据

**预期结果**：按上述步骤执行后满足验收标准：对设计与实现的偏离逐条给出结论；无偏离时显式写明「无偏离」及依据

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v7-29 · 迁移与兼容核验 + 需求详情回归·测试

**验收内容**：【迁移与兼容核验 + 需求详情回归·测试】验收：cd packages/web/dsh-pmboard && npx vitest run tests/dag-view.test.ts tests/node-panel.test.ts tests/client-view.test.ts tests/dag-styles.test.ts → 4 files passed / 111 tests passed；cd packages/web/dsh-pmboard && pnpm build:client → 退出 0 且输出含 [verify-client] OK；grep -l "serves:" packages/web/dsh-pmboard/tests/*.test.ts → 命中 dag-view/node-panel/client-view/dag-styles 四个文件

**操作步骤**：
1. cd packages/web/dsh-pmboard && npx vitest run tests/dag-view.test.ts tests/node-panel.test.ts tests/client-view.test.ts tests/dag-styles.test.ts → 4 files passed / 111 tests passed
2. cd packages/web/dsh-pmboard && pnpm build:client → 退出 0 且输出含 [verify-client] OK
3. grep -l "serves:" packages/web/dsh-pmboard/tests/*.test.ts → 命中 dag-view/node-panel/client-view/dag-styles 四个文件

**预期结果**：按上述步骤执行后满足验收标准：cd packages/web/dsh-pmboard && npx vitest run tests/dag-view.test.ts tests/node-panel.test.ts tests/client-view.test.ts tests/dag-styles.test.ts → 4 files passed / 111 tests passed；cd packages/web/dsh-pmboard && pnpm build:client → 退出 0 且输出含 [verify-client] OK；grep -l "serves:" packages/web/dsh-pmboard/tests/*.test.ts → 命中 dag-view/node-panel/client-view/dag-styles 四个文件

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v7-30 · 需求级验收

**验收内容**：需求级：交付结论可复核（证据齐全、与设计一致、无范围蔓延）

**操作步骤**：
1. 需求级：交付结论可复核（证据齐全、与设计一致、无范围蔓延）

**预期结果**：按上述步骤执行后满足验收标准：需求级：交付结论可复核（证据齐全、与设计一致、无范围蔓延）

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v7-32 · 需求级验收

**验收内容**：验收项不可照着验（历史数据）：以下验收项没写「怎么验」——验收项 定契约：入参结构类型收敛 + 面板画布常量·复核 缺「怎么验」（"对设计与实现的偏离逐条给出结论；无偏离时显式写明「无偏离」及依据"）——只写断言词不算，必须给**可执行操作**：命令（npx/vitest/curl/pytest…）、可查数据（SQL/字段名）、或可达界面路径（打开某页→看什么）。否则验收只能靠相信，等于没验。；验收项 画布 id 参数化 + 挂载实例表·复核 缺「怎么验」（"对设计与实现的偏离逐条给出结论；无偏离时显式写明「无偏离」及依据"）——只写断言词不算，必须给**可执行操作**：命令（npx/vitest/curl/pytest…）、可查数据（SQL/字段名）、或可达界面路径（打开某页→看什么）。否则验收只能靠相信，等于没验。；验收项 会话面板两处 DAG 块改调同一构建函数·复核 缺「怎么验」（"对设计与实现的偏离逐条给出结论；无偏离时显式写明「无偏离」及依据"）——只写断言词不算，必须给**可执行操作**：命令（npx/vitest/curl/pytest…）、可查数据（SQL/字段名）、或可达界面路径（打开某页→看什么）。否则验收只能靠相信，等于没验。；验收项 会话面板挂载钩子（DOM 就绪后挂载）·复核 缺「怎么验」（"对设计与实现的偏离逐条给出结论；无偏离时显式写明「无偏离」及依据"）——只写断言词不算，必须给**可执行操作**：命令（npx/vitest/curl/pytest…）、可查数据（SQL/字段名）、或可达界面路径（打开某页→看什么）。否则验收只能靠相信，等于没验。；验收项 DAG 骨架皮肤换成 np 苹果风·复核 缺「怎么验」（"对设计与实现的偏离逐条给出结论；无偏离时显式写明「无偏离」及依据"）——只写断言词不算，必须给**可执行操作**：命令（npx/vitest/curl/pytest…）、可查数据（SQL/字段名）、或可达界面路径（打开某页→看什么）。否则验收只能靠相信，等于没验。。请补可执行操作（命令/可查数据/界面路径）；本条不阻断验收，但必须有人看过并决定。

**操作步骤**：
1. 验收项不可照着验（历史数据）：以下验收项没写「怎么验」——验收项 定契约：入参结构类型收敛 + 面板画布常量·复核 缺「怎么验」（"对设计与实现的偏离逐条给出结论
2. 无偏离时显式写明「无偏离」及依据"）——只写断言词不算，必须给**可执行操作**：命令（npx/vitest/curl/pytest…）、可查数据（SQL/字段名）、或可达界面路径（打开某页→看什么）。否则验收只能靠相信，等于没验。
3. 验收项 画布 id 参数化 + 挂载实例表·复核 缺「怎么验」（"对设计与实现的偏离逐条给出结论
4. 无偏离时显式写明「无偏离」及依据"）——只写断言词不算，必须给**可执行操作**：命令（npx/vitest/curl/pytest…）、可查数据（SQL/字段名）、或可达界面路径（打开某页→看什么）。否则验收只能靠相信，等于没验。
5. 验收项 会话面板两处 DAG 块改调同一构建函数·复核 缺「怎么验」（"对设计与实现的偏离逐条给出结论
6. 无偏离时显式写明「无偏离」及依据"）——只写断言词不算，必须给**可执行操作**：命令（npx/vitest/curl/pytest…）、可查数据（SQL/字段名）、或可达界面路径（打开某页→看什么）。否则验收只能靠相信，等于没验。
7. 验收项 会话面板挂载钩子（DOM 就绪后挂载）·复核 缺「怎么验」（"对设计与实现的偏离逐条给出结论
8. 无偏离时显式写明「无偏离」及依据"）——只写断言词不算，必须给**可执行操作**：命令（npx/vitest/curl/pytest…）、可查数据（SQL/字段名）、或可达界面路径（打开某页→看什么）。否则验收只能靠相信，等于没验。
9. 验收项 DAG 骨架皮肤换成 np 苹果风·复核 缺「怎么验」（"对设计与实现的偏离逐条给出结论
10. 无偏离时显式写明「无偏离」及依据"）——只写断言词不算，必须给**可执行操作**：命令（npx/vitest/curl/pytest…）、可查数据（SQL/字段名）、或可达界面路径（打开某页→看什么）。否则验收只能靠相信，等于没验。。请补可执行操作（命令/可查数据/界面路径）
11. 本条不阻断验收，但必须有人看过并决定。

**预期结果**：按上述步骤执行后满足验收标准：验收项不可照着验（历史数据）：以下验收项没写「怎么验」——验收项 定契约：入参结构类型收敛 + 面板画布常量·复核 缺「怎么验」（"对设计与实现的偏离逐条给出结论；无偏离时显式写明「无偏离」及依据"）——只写断言词不算，必须给**可执行操作**：命令（npx/vitest/curl/pytest…）、可查数据（SQL/字段名）、或可达界面路径（打开某页→看什么）。否则验收只能靠相信，等于没验。；验收项 画布 id 参数化 + 挂载实例表·复核 缺「怎么验」（"对设计与实现的偏离逐条给出结论；无偏离时显式写明「无偏离」及依据"）——只写断言词不算，必须给**可执行操作**：命令（npx/vitest/curl/pytest…）、可查数据（SQL/字段名）、或可达界面路径（打开某页→看什么）。否则验收只能靠相信，等于没验。；验收项 会话面板两处 DAG 块改调同一构建函数·复核 缺「怎么验」（"对设计与实现的偏离逐条给出结论；无偏离时显式写明「无偏离」及依据"）——只写断言词不算，必须给**可执行操作**：命令（npx/vitest/curl/pytest…）、可查数据（SQL/字段名）、或可达界面路径（打开某页→看什么）。否则验收只能靠相信，等于没验。；验收项 会话面板挂载钩子（DOM 就绪后挂载）·复核 缺「怎么验」（"对设计与实现的偏离逐条给出结论；无偏离时显式写明「无偏离」及依据"）——只写断言词不算，必须给**可执行操作**：命令（npx/vitest/curl/pytest…）、可查数据（SQL/字段名）、或可达界面路径（打开某页→看什么）。否则验收只能靠相信，等于没验。；验收项 DAG 骨架皮肤换成 np 苹果风·复核 缺「怎么验」（"对设计与实现的偏离逐条给出结论；无偏离时显式写明「无偏离」及依据"）——只写断言词不算，必须给**可执行操作**：命令（npx/vitest/curl/pytest…）、可查数据（SQL/字段名）、或可达界面路径（打开某页→看什么）。否则验收只能靠相信，等于没验。。请补可执行操作（命令/可查数据/界面路径）；本条不阻断验收，但必须有人看过并决定。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v7-33 · 需求级验收

**验收内容**：E2E 覆盖：**无（缺口）**——本需求交付涉及多组件串联，但只交了单元/集成测试。请补一条端到端场景用例（断言可观察终态）。

**操作步骤**：
1. E2E 覆盖：**无（缺口）**——本需求交付涉及多组件串联，但只交了单元/集成测试。请补一条端到端场景用例（断言可观察终态）。

**预期结果**：按上述步骤执行后满足验收标准：E2E 覆盖：**无（缺口）**——本需求交付涉及多组件串联，但只交了单元/集成测试。请补一条端到端场景用例（断言可观察终态）。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

## 2. 测试报告

- cd packages/web/dsh-pmboard && npx vitest run dag-view → 29 tests passed（原 25，+4 条点击开文档用例）
- cd packages/web/dsh-pmboard && npx vitest run dag-view node-panel client-view dag-styles dag-layout card-layer node-panel-styles → 8 files passed / 158 tests passed
- cd packages/web/dsh-pmboard && npx vitest run → 85 failed / 2632 passed；与上一轮失败文件集合逐项相同，零新增回归
- cd packages/web/dsh-pmboard && npx tsc --noEmit -p tsconfig.json → 全仓 208 条（与改动前一致），本次涉及文件 0 error
- cd packages/web/dsh-pmboard && pnpm build → 退出 0；[verify-client] OK bundle=306787 bytes, 关键符号齐全
- packages/web/dsh-pmboard/src/client/views/dag-view.ts
- packages/web/dsh-pmboard/tests/dag-view.test.ts
- docs/requirements/REQ-260929010300-dbf9/verification-evidence.md（§10 追加裁定 F 证据）
- docs/requirements/REQ-260929010300-dbf9/requirement.md（追加裁定 F）

## 3. 文档完整性检查

✓ 9 类文档齐全

## 4. 验收结果

| 编号 | 验收项 | 状态 | 验收人 | 验收时间 |
|---|---|---|---|---|
| v7-1 | 定契约：入参结构类型收敛 + 面板画布常量 | ✓ 通过 | human/session-9e82f8c1-635e-458c-9df0-ff9aba1ae00e | 2026-09-29 07:47 |
| v7-2 | 画布 id 参数化 + 挂载实例表 | ✓ 通过 | human/session-9e82f8c1-635e-458c-9df0-ff9aba1ae00e | 2026-09-29 07:47 |
| v7-3 | 会话面板两处 DAG 块改调同一构建函数 | ✓ 通过 | human/session-9e82f8c1-635e-458c-9df0-ff9aba1ae00e | 2026-09-29 07:47 |
| v7-4 | 会话面板挂载钩子（DOM 就绪后挂载） | ✓ 通过 | human/session-9e82f8c1-635e-458c-9df0-ff9aba1ae00e | 2026-09-29 07:47 |
| v7-5 | DAG 骨架皮肤换成 np 苹果风 | ✓ 通过 | human/session-9e82f8c1-635e-458c-9df0-ff9aba1ae00e | 2026-09-29 07:47 |
| v7-6 | 迁移与兼容核验 + 需求详情回归 | ✓ 通过 | human/session-9e82f8c1-635e-458c-9df0-ff9aba1ae00e | 2026-09-29 07:47 |
| v7-7 | 定契约：入参结构类型收敛 + 面板画布常量·研发 | ✓ 通过 | human/session-9e82f8c1-635e-458c-9df0-ff9aba1ae00e | 2026-09-29 07:47 |
| v7-8 | 定契约：入参结构类型收敛 + 面板画布常量·联调 | ✓ 通过 | human/session-9e82f8c1-635e-458c-9df0-ff9aba1ae00e | 2026-09-29 07:47 |
| v7-9 | 定契约：入参结构类型收敛 + 面板画布常量·复核 | ✓ 通过 | human/session-9e82f8c1-635e-458c-9df0-ff9aba1ae00e | 2026-09-29 07:47 |
| v7-10 | 定契约：入参结构类型收敛 + 面板画布常量·测试 | ✓ 通过 | human/session-9e82f8c1-635e-458c-9df0-ff9aba1ae00e | 2026-09-29 07:47 |
| v7-11 | 画布 id 参数化 + 挂载实例表·研发 | ✓ 通过 | human/session-9e82f8c1-635e-458c-9df0-ff9aba1ae00e | 2026-09-29 07:47 |
| v7-12 | 画布 id 参数化 + 挂载实例表·联调 | ✓ 通过 | human/session-9e82f8c1-635e-458c-9df0-ff9aba1ae00e | 2026-09-29 07:47 |
| v7-13 | 画布 id 参数化 + 挂载实例表·复核 | ✓ 通过 | human/session-9e82f8c1-635e-458c-9df0-ff9aba1ae00e | 2026-09-29 07:47 |
| v7-14 | 画布 id 参数化 + 挂载实例表·测试 | ✓ 通过 | human/session-9e82f8c1-635e-458c-9df0-ff9aba1ae00e | 2026-09-29 07:47 |
| v7-15 | 会话面板两处 DAG 块改调同一构建函数·研发 | ✓ 通过 | human/session-9e82f8c1-635e-458c-9df0-ff9aba1ae00e | 2026-09-29 07:47 |
| v7-16 | 会话面板两处 DAG 块改调同一构建函数·联调 | ✓ 通过 | human/session-9e82f8c1-635e-458c-9df0-ff9aba1ae00e | 2026-09-29 07:47 |
| v7-17 | 会话面板两处 DAG 块改调同一构建函数·复核 | ✓ 通过 | human/session-9e82f8c1-635e-458c-9df0-ff9aba1ae00e | 2026-09-29 07:47 |
| v7-18 | 会话面板两处 DAG 块改调同一构建函数·测试 | ✓ 通过 | human/session-9e82f8c1-635e-458c-9df0-ff9aba1ae00e | 2026-09-29 07:47 |
| v7-19 | 会话面板挂载钩子（DOM 就绪后挂载）·研发 | ✓ 通过 | human/session-9e82f8c1-635e-458c-9df0-ff9aba1ae00e | 2026-09-29 07:47 |
| v7-20 | 会话面板挂载钩子（DOM 就绪后挂载）·联调 | ✓ 通过 | human/session-9e82f8c1-635e-458c-9df0-ff9aba1ae00e | 2026-09-29 07:47 |
| v7-21 | 会话面板挂载钩子（DOM 就绪后挂载）·复核 | ✓ 通过 | human/session-9e82f8c1-635e-458c-9df0-ff9aba1ae00e | 2026-09-29 07:47 |
| v7-22 | 会话面板挂载钩子（DOM 就绪后挂载）·测试 | ✓ 通过 | human/session-9e82f8c1-635e-458c-9df0-ff9aba1ae00e | 2026-09-29 07:47 |
| v7-23 | DAG 骨架皮肤换成 np 苹果风·研发 | ✓ 通过 | human/session-9e82f8c1-635e-458c-9df0-ff9aba1ae00e | 2026-09-29 07:47 |
| v7-24 | DAG 骨架皮肤换成 np 苹果风·联调 | ✓ 通过 | human/session-9e82f8c1-635e-458c-9df0-ff9aba1ae00e | 2026-09-29 07:47 |
| v7-25 | DAG 骨架皮肤换成 np 苹果风·复核 | ✓ 通过 | human/session-9e82f8c1-635e-458c-9df0-ff9aba1ae00e | 2026-09-29 07:47 |
| v7-26 | DAG 骨架皮肤换成 np 苹果风·测试 | ✓ 通过 | human/session-9e82f8c1-635e-458c-9df0-ff9aba1ae00e | 2026-09-29 07:47 |
| v7-27 | 迁移与兼容核验 + 需求详情回归·研发 | ✓ 通过 | human/session-9e82f8c1-635e-458c-9df0-ff9aba1ae00e | 2026-09-29 07:47 |
| v7-28 | 迁移与兼容核验 + 需求详情回归·复核 | ✓ 通过 | human/session-9e82f8c1-635e-458c-9df0-ff9aba1ae00e | 2026-09-29 07:47 |
| v7-29 | 迁移与兼容核验 + 需求详情回归·测试 | ✓ 通过 | human/session-9e82f8c1-635e-458c-9df0-ff9aba1ae00e | 2026-09-29 07:47 |
| v7-30 | 需求级验收 | ✓ 通过 | human/session-9e82f8c1-635e-458c-9df0-ff9aba1ae00e | 2026-09-29 07:47 |
| v7-32 | 需求级验收 | ✓ 通过 | human/session-9e82f8c1-635e-458c-9df0-ff9aba1ae00e | 2026-09-29 07:47 |
| v7-33 | 需求级验收 | ✓ 通过 | human/session-9e82f8c1-635e-458c-9df0-ff9aba1ae00e | 2026-09-29 07:47 |
