# 评审记录 · REQ-260929010300-dbf9（自评审 + 子卡链复核）

> 时点：2026-09-29 02:20 · 评审对象：implementing 节点的 6 张父卡 / 23 张子卡全部 done 后的工作区实况。

## 1. 逐功能点对照（设计 ↔ 实现 ↔ 证据）

| FR | 设计口径 | 实现落点 | 证据（可复核） | 结论 |
|---|---|---|---|---|
| FR-1 | 实施 [DAG] 页签改渲染 Canvas 真图面板 | `node-panel.ts` `renderImplViews` 调 `buildDagCanvas(tasks, PANEL_DAG_CONTAINER_ID, PANEL_DAG_CANVAS_ID)` | tests/node-panel.test.ts：含 `dsh-pm-dag-panel` + `id="np-dag-canvas"`，不含 `dsh-pm-np-dag-layer`/`-dag-node` | pass |
| FR-2 | 拆分「📊 DAG 层级」块同源 | `renderDecomposingInfo` 同一构建函数、同一组常量 | 同上（两处 DAG 面板 DOM 类名集合逐项相同断言） | pass |
| FR-3 | 三个入口 canvasId 参数化、两实例互不干扰 | `dag-view.ts` / `dag-mount.ts`；缺省 `dag-canvas` | tests/dag-view.test.ts：两 canvasId 各挂一次、释放其一另一块监听未被摘 | pass |
| FR-4 | 同 id 挂载幂等 + 容器宽度自适应 | `disposers: Map<canvasId, dispose>`；ResizeObserver 仅宽度变化重排 | 同 id 二次挂载用例 + 实例表 | pass |
| FR-5 | 面板侧 DOM 就绪后挂载 | `conversation-progress.ts` useEffect（detailOpen/selectedStage/stageOverview）→ `tryMountDagCanvas`；rAF + getElementById 二次确认 | 阶段/任务缺失即返回；目标不存在静默 return | pass |
| FR-6 | 骨架皮肤统一 np 苹果风 | `styles/dag.ts` 全部 `--dsh-pm-np-*`；**底色 = 泳道图底色** | `grep --dsw-` 无命中；tests/dag-styles.test.ts 7 用例 | pass |
| FR-7 | 面板侧 ready 诚实标「推导」 | 面板不传 `ready`；`statHtml` 输出 `（推导）` | dag-stat.ts + 需求详情仍按队列 ready 标注 | pass |

## 2. 链上复核（子卡 dev/integrate/review/test 段）

- 研发段发现的**真实缺陷**已修：`mountDagCanvas` 原在「画布已被 SSE 重绘摘掉」/「顶层卡为空」两条提前返回**之后**才释放同名旧实例 → 旧 ResizeObserver 与 dblclick 监听留在脱管 canvas 上。已把释放提到提前返回之前，并补 2 条用例（tests/dag-view.test.ts）。
- 联调段以真实调用打通「DOM 生产端 `buildDagCanvas` → 样式注入端 `injectStyles` → `DAG_CSS` → `renderNodePanel` / `tryMountDagCanvas`」全链路，12/12 断言与期望一致。
- 测试段执行父卡终态命令（见 `tests/acceptance-run.md`）。

## 3. 已知取舍与偏离（显式记录）

1. **底色口径修订**：需求文档 FR-6 写「白底圆角」，用户 2026-09-29 实机裁定改为**泳道图底色**（`--dsh-pm-np-bg` / #f5f5f7）。实现与断言以裁定为准，卡验收标准已同步修订（t-d1a7f7）。
2. **固定浅色**：np 皮肤不随明暗主题变化（用户追认）。
3. **旧分层列表函数保留**：`renderDag` 保留导出但不再接线（避免连带删样式影响其它消费方）；回滚只需恢复两个调用点。
4. **归档条断言校正**：`tests/client-view.test.ts` 一条与本需求无关的既存失败断言（`dsh-pm-archived-bar` 在基线无生产者）经用户裁定按真实行为校正；归档条是否属看板回归另议。

## 4. 评审结论

7 条 FR 全部有实现落点与可复核证据，无未接收条款；改动面与设计一致（接线 + id 参数化 + 换肤），未改数据契约、未改 canvas 卡片绘制。**评审通过**，提请人工验收。
