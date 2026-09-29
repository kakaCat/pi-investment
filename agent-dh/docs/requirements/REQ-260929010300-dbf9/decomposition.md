# 拆分计划 · REQ-260929010300-dbf9 流程节点面板的 DAG 改用与需求详情一致的 Canvas 真图

> **目标**：会话流程节点面板的两处 DAG 换成与需求详情**同源**的 Canvas 真图，并把两处 DAG 面板的**骨架皮肤统一为会话面板的 np 苹果风**
> （2026-09-29 用户订正：以会话面板观感为准，需求详情一并换肤）。
> **做法**：渲染语义与数据契约零改动——只做四件事：**接线**（面板两处改调同一构建函数）、**画布 id 参数化**、
> **挂载实例表**（修掉单槽互踩）、**换肤**（DAG 骨架改用 `--dsh-pm-np-*` 令牌，类名不变）。
> 依据设计：docs/requirements/REQ-260929010300-dbf9/design/{architecture,data-model,interfaces,test-cases,use-cases}.md（FR-1…FR-7 全覆盖）。

## 一、改动盘点

### 修改（M）

| 文件 | 改什么 | 关联条款 |
|---|---|---|
| packages/web/dsh-pmboard/src/client/views/dag-view.ts | 定义并导出 `DagTaskLike` 与 `PANEL_DAG_CONTAINER_ID` / `PANEL_DAG_CANVAS_ID`；`buildDagCanvas`/`mountDagCanvas` 增可选 `canvasId`；模块级单槽 `activeDispose` 改 `Map<string, () => void>` 实例表；`openTaskDetail` 带 `canvasId` | FR-1…FR-5 |
| packages/web/dsh-pmboard/src/client/dag-mount.ts | `tryMountDagCanvas` 透传 `canvasId` 到 `mountDagCanvas` | FR-3 |
| packages/web/dsh-pmboard/src/client/node-panel.ts | 拆分阶段与实施阶段两处 DAG 块改调 `buildDagCanvas(tasks, PANEL_DAG_CONTAINER_ID, PANEL_DAG_CANVAS_ID)`；`renderDag` 保留函数但不再被调用 | FR-1, FR-2 |
| packages/web/dsh-pmboard/src/client/conversation-progress.ts | 面板渲染后新增 `useEffect` 挂载钩子：取所选阶段 `body.tasks` 调 `tryMountDagCanvas(tasks, undefined, PANEL_DAG_CANVAS_ID)` | FR-1, FR-2, FR-5, FR-7 |
| packages/web/dsh-pmboard/src/client/styles/dag.ts | `DAG_CSS` 取值换成 `--dsh-pm-np-*` 苹果风令牌（面板白底圆角、`#f5f5f7` 头块、980px 胶囊、8px 圆角滚动条）；**类名一律不变** | FR-6 |
| packages/web/dsh-pmboard/tests/dag-view.test.ts | 新增画布 id 参数化与实例隔离用例；文件头补 `serves:` 声明 | FR-3, FR-4 |
| packages/web/dsh-pmboard/tests/node-panel.test.ts | 旧分层列表断言改为真图面板断言；文件头补 `serves:` 声明 | FR-1, FR-2 |

### 新增（A）

| 文件 | 干什么 | 关联条款 |
|---|---|---|
| packages/web/dsh-pmboard/tests/dag-styles.test.ts | 断言 `DAG_CSS` 不含 `--dsw-`、含 `--dsh-pm-np-`；文件头带 `serves:` 声明 | FR-6 |

### 刻意不改（N）与回归核验点

| 文件 / 面 | 为什么不动 |
|---|---|
| packages/web/dsh-pmboard/src/client/dag/card-renderer.ts | 画布卡绘制（类型/端侧徽标、208×72 几何）用户 2026-09-29 裁定零改动 |
| 其余 src/client/dag/*（layout / edge / critical-path / interaction / progress-bar） | 渲染语义（折叠 / 传递归约 / 箭头分级）沿用 |
| packages/web/dsh-pmboard/src/client/views/stage-detail.ts | 需求详情调用方走缺省参数，一行不改 |
| packages/web/dsh-pmboard/src/client/styles.ts | 拼接顺序不动（DAG_CSS 继续在末尾） |
| packages/web/dsh-pmboard/scripts/verify-client-build.mjs | 类名不变，`dsh-pm-dag-panel` 符号守卫继续有效 |

## 二、需求条款 ↔ 计划 key 覆盖对照

| 需求条款 | 接收任务 |
|---|---|
| FR-1 | t3, t4 |
| FR-2 | t3, t4 |
| FR-3 | t1, t2 |
| FR-4 | t2 |
| FR-5 | t4 |
| FR-6 | t5 |
| FR-7 | t4 |

## 三、任务表（批准即按此落卡）

| key | 标题 | phase | side | 依赖 |
|---|---|---|---|---|
| t1 | 定契约：入参结构类型收敛 + 面板画布常量 | implement | frontend | — |
| t2 | 画布 id 参数化 + 挂载实例表 | implement | frontend | t1 |
| t3 | 会话面板两处 DAG 块改调同一构建函数 | implement | frontend | t1 |
| t4 | 会话面板挂载钩子（DOM 就绪后挂载） | implement | frontend | t2, t3 |
| t5 | DAG 骨架皮肤换成 np 苹果风 | ui | frontend | t1 |
| t6 | 迁移与兼容核验 + 需求详情回归 | test | frontend | t2, t3, t4, t5 |

> 依赖只指向**前面已定义**的 key（本仓 `checkPlanTaskReferences` 拒前向引用）。

## 四、风险与回滚

- 风险 1（同页两实例互踩）：靠 t2 的实例表 + t6 的回归核验兜住；症状=先挂的图画布消失。
- 风险 2（面板窄、画布溢出）：不改样式尺寸，靠既有 `ResizeObserver` 按容器宽度重排 + 画布区横向滚动。
- 风险 3（暗色主题下 DAG 面板变白块）：np 皮肤固定浅色，属**已知取舍**（用户 2026-09-29 追认），不视为缺陷。
- 回滚：把 `node-panel.ts` 两处 DAG 块还原为 `renderDag(tasks)`、`styles/dag.ts` 回滚，即回到本次改动前；数据契约未变，回滚不动数据。
