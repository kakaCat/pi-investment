# 测试视角 · REQ-260929010300-dbf9 设计 `serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7`

## 测试策略与分层 `serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7`

| 层级 | 验什么 | 测试文件 | 期望 |
|---|---|---|---|
| 单元 | 画布 id 参数化：缺省保持旧值，显式生效 | tests/dag-view.test.ts | 缺省含 `id="dag-canvas"`；显式含 `id="canvas-2"` 且不含缺省 id |
| 单元 | 实例表按 id 隔离（互不释放） | tests/dag-view.test.ts | 两个不同 canvasId 挂载后，释放其一不影响另一（fake DOM） |
| 单元 | 会话面板两处 DAG 块换成真图面板 | tests/node-panel.test.ts | 实施/拆分 HTML 含 `dsh-pm-dag-panel` 与独立 canvas，且不含 `dsh-pm-np-dag-layer` |
| 单元 | 皮肤无 `--dsw-` 残留 | tests/dag-styles.test.ts | `DAG_CSS` 不匹配 `/--dsw-/`，且含 `--dsh-pm-np-` |
| 集成 | 需求详情路径不回归 | tests/client-view.test.ts | 既有断言（面板类名 + 缺省画布 id + 四个钩子）继续通过 |
| E2E | 两处观感一致、同页两实例 | 手工核验（见下节） | 会话面板与需求详情 DAG 类名集合一致，两块 canvas id 不同 |

测试文件头部须带 `serves:` 声明（本仓 `testFileHasServesHeader` 只扫前 20 行），实现时一并补上。

## 手工核验（线上） `serves: FR-6`

1. `cd packages/web/dsh-pmboard && npx vitest run tests/dag-view.test.ts tests/node-panel.test.ts tests/client-view.test.ts tests/dag-styles.test.ts` 全绿。
2. `pnpm build:client` 退出 0，末行 `[verify-client] OK ... 关键符号齐全`。
3. `npx tsc --noEmit -p tsconfig.json` 本次涉及文件 0 error。
4. :13080 会话右上角流程节点 → 实施阶段 [DAG]：**无标题行、无统计条**（2026-09-29 裁定 B）、三个开关可用、悬停高亮上下游正常；拆分阶段 DAG 块同款。
5. `grep -n -- '--dsw-' src/client/styles/dag.ts` 无命中；`card-renderer.ts` 改动仅限裁定 D 的「删父卡左侧蓝条」一处。
