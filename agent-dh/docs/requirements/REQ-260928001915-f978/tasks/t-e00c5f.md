# t-e00c5f 实现悬停交互处理器·研发

> 需求：REQ-260928001915-f978 队列 DAG 真图卡片类型与可视化设计

## 在做什么
实现悬停交互处理器·研发

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果

运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsc demo/interaction.ts --noEmit`，退出码必须为 0（类型契约成立）。再运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsx demo/selftest.mjs`，末行必须为「模块自测全绿」（失败数 0）。可查锚点：`grep -c "export " demo/interaction.ts` ≥ 1，且文件中含本模块的导出函数名。

## 汇报 1（2026-09-28T05:49:37.204Z，窗口 session-6cbda737-2159-497d-9384-10ef3330279f）

【研发·链执行回填】实现悬停交互处理器·研发：interaction.ts：setupInteraction 绑定 canvas mousemove/click/mouseleave，悬停按命中 id 触发 onChange；resolveHighlight 用 computeNeighbors 算出 self/up(橙)/down(蓝)；DIM_NODE_ALPHA=0.18、DIM_EDGE_ALPHA=0.05 与 paintDim(globalAlpha)；点击钉住、再点同一卡取消、点画布空白取消、钉住态悬停不改高亮；destroy 解绑；另附 DOM 后端 bindDomInteraction（FR-5）

### 完成项

- interaction.ts：setupInteraction 绑定 canvas mousemove/click/mouseleave，悬停按命中 id 触发 onChange；resolveHighlight 用 computeNeighbors 算出 self/up(橙)/down(蓝)；DIM_NODE_ALPHA=0.18、DIM_EDGE_ALPHA=0.05 与 paintDim(globalAlpha)；点击钉住、再点同一卡取消、点画布空白取消、钉住态悬停不改高亮；destroy 解绑；另附 DOM 后端 bindDomInteraction（FR-5）
- 新增 interaction.test.ts：以最小 canvas/DOM 桩直接派发事件，覆盖 FR-5 悬停高亮·钉住·取消·dimming 共 36 条断言，并跨模块比对 renderEdges/renderCard 实际 dimming 取值与常量一致

### 改动文件

- `docs/requirements/REQ-260928001915-f978/demo/interaction.ts`
- `docs/requirements/REQ-260928001915-f978/demo/interaction.test.ts`

---
