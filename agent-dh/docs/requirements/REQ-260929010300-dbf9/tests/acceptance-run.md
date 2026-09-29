# 测试证据 · REQ-260929010300-dbf9

> 执行时点：2026-09-29 02:18（工作区 packages/web/dsh-pmboard）· 执行人：投资脑窗口 session-9e82f8c1

## 1. 单元/集成测试

```
$ cd packages/web/dsh-pmboard && npx vitest run tests/dag-view.test.ts tests/node-panel.test.ts tests/client-view.test.ts tests/dag-styles.test.ts
 ✓ tests/dag-styles.test.ts (7 tests)
 ✓ tests/dag-view.test.ts (25 tests)
 ✓ tests/node-panel.test.ts (28 tests)
 ✓ tests/client-view.test.ts (51 tests)
 Test Files  4 passed (4)
      Tests  111 passed (111)
```

覆盖点：面板 DAG 块骨架与 canvas id（FR-1/FR-2）、canvasId 参数化与实例表隔离（FR-3/FR-4）、需求详情不回归（既有断言）、皮肤无 `--dsw-` 且面板底色 = `--dsh-pm-np-bg`（FR-6）。

## 2. 客户端构建与符号守卫

```
$ cd packages/web/dsh-pmboard && pnpm build:client
✔ Build complete
wrapped dsh-pmboard -> lib/client.js 289924 bytes
[verify-client] OK  bundle=308699 bytes, 关键符号齐全, styles.ts 括号配对
$ echo $?
0
```

## 3. 类型检查

```
$ cd packages/web/dsh-pmboard && npx tsc --noEmit -p tsconfig.json
# 本次涉及文件（packages/web/dsh-pmboard/src/client/**）0 error
# 全仓 208 条 error 均为其它在途工作既有错误（改动前后计数一致：208 → 208）
```

## 4. 皮肤与零改动核验

```
$ grep -n -- '--dsw-' packages/web/dsh-pmboard/src/client/styles/dag.ts
# 无输出（皮肤口径全部 --dsh-pm-np-*）
$ git diff --stat -- packages/web/dsh-pmboard/src/client/dag/card-renderer.ts
# 仅一处：2026-09-29 裁定 D 删除「父卡左侧蓝条」（徽标/几何/配色仍零改动）
```

## 5. 人工核验清单（:13080，待人确认）

1. 刷新页面 → 会话右上角流程节点：实施 [DAG] / 拆分「📊 DAG 层级」可见真图画布，底色为泳道图同款浅灰；**无标题行 / 无统计条**（2026-09-29 裁定 B）；**同层卡片一行排开、不折行**（裁定 C，窄容器横向滚动），三个开关、图例与需求详情逐字一致；
2. `document.querySelectorAll('canvas.dsh-pm-dag-canvas').length` 与 `dag-canvas` / `np-dag-canvas` 两个 id 核对（同页两实例）；
3. DAG ↔ 泳道 页签来回切换后画布仍在。
4. DAG 卡片：**没有左侧蓝条**（2026-09-29 裁定 D），外观与泳道卡片一致；**单击卡片 → 右侧栏打开该卡的任务卡文档**（裁定 F；双击为打开任务详情）。
5. 切到 [泳道] 页签：父卡卡片上**没有子卡链进度**（无「n/N」文案、无 4 段色条）——2026-09-29 裁定 E。

## 6. 测试覆盖标注（covers · AC-7.5 覆盖度门禁）

覆盖口径：`cd packages/web/dsh-pmboard && npx vitest run tests/dag-view.test.ts tests/node-panel.test.ts tests/client-view.test.ts tests/dag-styles.test.ts` → 4 files passed / 111 tests passed；子卡按各阶段验收命令（tsc / 单文件 vitest / build:client / grep 锚点）逐条核过。

### 父卡（6）
- covers: t-d03789 — 定契约：入参结构类型收敛 + 面板画布常量（终态四文件 vitest 全绿 + tsc 本次涉及文件 0 error）
- covers: t-6f9d7f — 画布 id 参数化 + 挂载实例表（终态四文件 vitest 全绿 + tsc 本次涉及文件 0 error）
- covers: t-284b0a — 会话面板两处 DAG 块改调同一构建函数（终态四文件 vitest 全绿 + tsc 本次涉及文件 0 error）
- covers: t-3ed4b5 — 会话面板挂载钩子（DOM 就绪后挂载）（终态四文件 vitest 全绿 + tsc 本次涉及文件 0 error）
- covers: t-d1a7f7 — DAG 骨架皮肤换成 np 苹果风（终态四文件 vitest 全绿 + tsc 本次涉及文件 0 error）
- covers: t-757283 — 迁移与兼容核验 + 需求详情回归（终态四文件 vitest 全绿 + tsc 本次涉及文件 0 error）

### 子卡（23）
- covers: t-ee4384 — 定契约：入参结构类型收敛 + 面板画布常量·研发（dev 段：tsc + 相关单文件 vitest）
- covers: t-1fadb6 — 定契约：入参结构类型收敛 + 面板画布常量·联调（integrate 段：相关单文件 vitest + grep 接线锚点）
- covers: t-cc9e3a — 定契约：入参结构类型收敛 + 面板画布常量·复核（review 段：源码复核 + 相关单文件 vitest）
- covers: t-470baa — 定契约：入参结构类型收敛 + 面板画布常量·测试（test 段：四文件 vitest 全绿 + pnpm build:client 退出 0）
- covers: t-3f8d67 — 画布 id 参数化 + 挂载实例表·研发（dev 段：tsc + 相关单文件 vitest）
- covers: t-2e30df — 画布 id 参数化 + 挂载实例表·联调（integrate 段：相关单文件 vitest + grep 接线锚点）
- covers: t-cf0284 — 画布 id 参数化 + 挂载实例表·复核（review 段：源码复核 + 相关单文件 vitest）
- covers: t-c53e93 — 画布 id 参数化 + 挂载实例表·测试（test 段：四文件 vitest 全绿 + pnpm build:client 退出 0）
- covers: t-c0dad0 — 会话面板两处 DAG 块改调同一构建函数·研发（dev 段：tsc + 相关单文件 vitest）
- covers: t-32a952 — 会话面板两处 DAG 块改调同一构建函数·联调（integrate 段：相关单文件 vitest + grep 接线锚点）
- covers: t-89278b — 会话面板两处 DAG 块改调同一构建函数·复核（review 段：源码复核 + 相关单文件 vitest）
- covers: t-3b43fd — 会话面板两处 DAG 块改调同一构建函数·测试（test 段：四文件 vitest 全绿 + pnpm build:client 退出 0）
- covers: t-b1db02 — 会话面板挂载钩子（DOM 就绪后挂载）·研发（dev 段：tsc + 相关单文件 vitest）
- covers: t-3dfb5d — 会话面板挂载钩子（DOM 就绪后挂载）·联调（integrate 段：相关单文件 vitest + grep 接线锚点）
- covers: t-aeb8eb — 会话面板挂载钩子（DOM 就绪后挂载）·复核（review 段：源码复核 + 相关单文件 vitest）
- covers: t-bf779f — 会话面板挂载钩子（DOM 就绪后挂载）·测试（test 段：四文件 vitest 全绿 + pnpm build:client 退出 0）
- covers: t-2069e2 — DAG 骨架皮肤换成 np 苹果风·研发（dev 段：tsc + 相关单文件 vitest）
- covers: t-0c43f8 — DAG 骨架皮肤换成 np 苹果风·联调（integrate 段：相关单文件 vitest + grep 接线锚点）
- covers: t-6fed57 — DAG 骨架皮肤换成 np 苹果风·复核（review 段：源码复核 + 相关单文件 vitest）
- covers: t-a195b8 — DAG 骨架皮肤换成 np 苹果风·测试（test 段：四文件 vitest 全绿 + pnpm build:client 退出 0）
- covers: t-7125de — 迁移与兼容核验 + 需求详情回归·研发（dev 段：tsc + 相关单文件 vitest）
- covers: t-74e548 — 迁移与兼容核验 + 需求详情回归·复核（review 段：源码复核 + 相关单文件 vitest）
- covers: t-7ee744 — 迁移与兼容核验 + 需求详情回归·测试（test 段：四文件 vitest 全绿 + pnpm build:client 退出 0）
