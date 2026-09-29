# t-65df2c 实现悬停交互处理器·联调

> 需求：REQ-260928001915-f978 队列 DAG 真图卡片类型与可视化设计

## 在做什么
实现悬停交互处理器·联调

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果

运行 `cd docs/requirements/REQ-260928001915-f978 && npx tsx demo/__probe-t-65df2c.ts`，退出码必须为 0——脚本对该模块的对外接口做「请求样例 → 期望响应 → 实际返回」三方对照，末行输出对照结论（全部一致）。

## 汇报 1（2026-09-28T05:49:38.284Z，窗口 session-6cbda737-2159-497d-9384-10ef3330279f）

【联调·链执行回填】实现悬停交互处理器·联调：联调对象/基线：被测交付物 docs/requirements/REQ-260928001915-f978/demo/interaction.ts（dev 子卡 t-e00c5f 产出）；契约 = 父卡 t-73c392「悬停高亮上游橙/下游蓝 + dimming 0.18/0.05 + 点击钉住、再点同卡或点画布空白取消」+ design/test-cases.md TC-9/TC-10/TC-11/TC-12 + design/interfaces.md §交互事件接口。本卡为结论族 integrate，未改动任何交付文件。

### 完成项

- 联调对象/基线：被测交付物 docs/requirements/REQ-260928001915-f978/demo/interaction.ts（dev 子卡 t-e00c5f 产出）；契约 = 父卡 t-73c392「悬停高亮上游橙/下游蓝 + dimming 0.18/0.05 + 点击钉住、再点同卡或点画布空白取消」+ design/test-cases.md TC-9/TC-10/TC-11/TC-12 + design/interfaces.md §交互事件接口。本卡为结论族 integrate，未改动任何交付文件。
- 请求样例 A（真实消费方 createDagViewer，数据=本需求真实 queue.json，32 节点）：mousemove 命中卡片中心 → state.pinned=t-2ad263；移空白 → null；click 卡片钉住；钉住态悬停他卡高亮保持；click 空白取消；同卡再点取消 —— A2-A9 全 PASS，hitTest 命中卡片=id / 空白=null 一致。
- 请求样例 B（setupInteraction 控制器契约）：绑定 mousemove/click/mouseleave 各 1；pinned/hover 初值 null；悬停命中 onChange(target) 且 hover=target；同卡重复 mousemove 去重；移空白 onChange(null)；click→pinned；mouseleave 不取消；再点同卡取消；reset()→null；destroy() 三监听器解绑且不再回调 —— B1-B12 全 PASS。
- 请求样例 C（Highlight 数据结构 ↔ 协作者/渲染器）：resolveHighlight(tasks,id) 的 self/up/down 与 computeNeighbors 逐元素一致、id=null 返回空高亮（C1-C4 PASS）；上游入边落笔 #ff9500|2|1（TC-9 PASS）；非高亮边 dim 0.05、未高亮卡 fill 0.18、self 黑框描边 #1f2733（C7-C9 PASS）；DIM_NODE_ALPHA=0.18 / DIM_EDGE_ALPHA=0.05 / paintDim（E1-E3 PASS）。
- 请求样例 D（DOM 后端联调）：renderDagHtml 产出的 node[data-id] 与 bindDomInteraction 的 closest('[data-id]') 契约一致；mouseover→onChange(id)、click→钉住、钉住态忽略悬停、点击空白取消、mouseout→null、destroy 解绑 —— D1-D8 全 PASS。
- 联调结论：interaction.ts 接口联调通过 —— 汇总 42/42 一致（取证脚本 docs/requirements/REQ-260928001915-f978/demo/__probe-t-65df2c.ts，只读取证、不改交付物）；回归复跑 dev 阶段 interaction.test.ts 36 通过/0 失败。
- 联调发现（1 项跨模块偏差，非本卡实现范围，探针 C6 记录）：悬停节点时其【首跳出边】未按 TC-10 变蓝——实际 rgba(52,199,89,.5)|1.3|0.05（被 dim 到底色）；而 from∈down 的更深下游边正常变蓝（C6b PASS）。根因：edge-renderer.edgeStyle 的 isDown 判据 `highlight.down.has(e.from)` 未覆盖 from===self 的首跳，与 isUp 的 `up.has(to)||up.has(from)` 不对称；design/interfaces.md L271 同款规则，属 FR-4 边线渲染器（t-e4e9db）范畴。建议移交复核/测试阶段并回 t-e4e9db 修复（如 isDown 增补 self/首跳判据）。

---
