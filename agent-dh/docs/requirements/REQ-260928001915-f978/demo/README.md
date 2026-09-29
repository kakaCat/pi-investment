# 队列 DAG 卡片类型演示（REQ-260928001915-f978）

把**真实队列文件** `docs/requirements/<REQ>/queue.json` 渲染成一张可交互的 DAG 真图，
用来验证卡片四轴类型系统（phase × side × role × status）与实际依赖图是否匹配。

## 一键构建 + 自测

```bash
python3 docs/requirements/REQ-260928001915-f978/demo/build-demo.py
```

脚本按自身位置定位路径，在仓库任意目录执行都可以。它做四件事：

1. 扫全仓 `docs/requirements/*/queue.json`，统计四轴频次、挑各类型标本、抽四档数据集
2. 用 esbuild 把 `integration.ts` 及其依赖打成 IIFE bundle（挂到 `window.DagDemo`）
3. 跑 `selftest.mjs`（无浏览器，Node 直接跑模块）——**不过就退出码 1，不写 HTML**
4. 把数据 + bundle 注入 `template.html`，写出 `dag-card-types-demo.html`

产物：`docs/requirements/REQ-260928001915-f978/demo/dag-card-types-demo.html`（双击即可在浏览器打开）。

退出码：`0` 成功；`2` 缺 esbuild/node；`3` 打包失败或产物为空；`4` 没有可用队列文件；
`5` 自测未通过；`6` 模板缺注入点。

## 模块一览

| 文件 | 职责 | 对应 FR |
|---|---|---|
| `card-types.ts` | 四轴枚举（7+4+3+6）、颜色表、标签表、`deriveTaskFields` | FR-1 |
| `card-renderer.ts` | 卡片渲染（7 个视觉元素）：`renderCard`（Canvas）/ `cardHtml`（DOM） | FR-2 |
| `dag-layout.ts` | 布局引擎 `calculateLayout`（纵向/横向）、`hitTest` | FR-3 |
| `edge-renderer.ts` | 边线着色 `renderEdges`（Canvas）/ `edgeSvg`（SVG） | FR-4 |
| `interaction.ts` | 悬停/钉住/dimming：`setupInteraction`（Canvas）/ `bindDomInteraction`（DOM） | FR-5 |
| `critical-path.ts` | 最长路径 `findCriticalPath`、上下游 `computeNeighbors`、环检测 | FR-6 / FR-4 |
| `progress-bar.ts` | 父卡子卡链 4 段进度：`renderProgressBar`（Canvas）/ `chainHtml`（DOM） | FR-7 |
| `integration.ts` | 集成入口：`createDagViewer`（Canvas 交互）/ `renderDagHtml`（DOM）/ `validateQueueFile` | FR-1…FR-7 |

两个后端共用同一份配色与标签（`card-types.ts` 是唯一真源）：
**Canvas** 供本 demo 渲染大图，**DOM/SVG** 供 pmboard 泳道内联渲染（见 `design/interfaces.md`）。

## 单独跑测试（不构建）

除 `build-demo.py` 内置的 `selftest.mjs` 外，每个模块各有独立单测，另有一份**集成测试**用四档真实队列
走完整主渲染流程（`validateQueueFile → resolveTasks → renderDagHtml / createDagViewer`，逐 FR-1…FR-7 断言）：

```bash
cd docs/requirements/REQ-260928001915-f978

# 逐模块单测（tsx 直跑，无需浏览器；退出码 0 = 全绿）
npx tsx demo/dag-layout.test.ts       # FR-3 布局
npx tsx demo/critical-path.test.ts    # FR-6 关键路径
npx tsx demo/interaction.test.ts      # FR-5 悬停交互
npx tsx demo/edge-renderer.test.ts    # FR-4 边线

# 集成测试：本需求 / 小图 12 卡 / 中图 20 卡 / 压力 65 卡 四档真实队列
npx tsx demo/integration.test.ts
```

## 自测覆盖

`selftest.mjs` 在 Node 里直接跑模块（不依赖浏览器），断言：

- 四轴 20 个枚举值都有视觉表现，颜色表无重复
- 纵向/横向布局：同层共线、层号单调、两方向坐标不同、命中测试正确
- 关键路径：四档真实队列都算出**单链**（起点唯一、每节点后继 ≤1）、节点真实存在
- 上下游遍历：A→B→C/D 的 up/down 集合正确
- 卡片元素：父卡蓝条、类型/端侧徽标、标题、状态底色、4 段子卡链、ready 绿点
- 边线：done→done 绿线、关键路径蓝线、贝塞尔 + 箭头、悬空引用被跳过
- 集成：节点数与任务数一致、只看主线收缩到关键路径、空图占位
- 降级：循环依赖被检测（关键路径返回空集而非崩溃）、缺 `layer` 仍能布局
- 数据校验 V-1…V-6：真实队列通过；悬空引用 / 跨需求串档 / 非法 ready 被抓
- 角色派生：父卡 / 子卡 / 独立卡三态（独立卡用**合成样例**断言，不依赖队列当下是否恰好含 solo 卡）

`integration.test.ts` 另按四档真实队列逐 FR 校验：卡数 = 任务数、边线条数 = 队列 edges 数、
子卡链条数 = 父卡数、ready 绿点数 = ready[] 数、只看主线收缩到关键路径、Canvas 视图切方向/销毁正常。

## 交互

- **悬停**卡片：橙色 = 它的上游，蓝色 = 它的下游，其余压暗
- **点击**卡片钉住高亮，再点同一张或点空白取消
- **纵向 / 横向**：切换布局方向（画布尺寸随之自适应）
- **关键路径**：给关键路径上的卡片加蓝色虚线轮廓
- **只看主线**：折叠到关键路径，支线用卡角 `+N 支线` 挂回
- **数据集**：本需求真实队列 / 小图 · 12 卡 7 层 / 中图 · 20 卡 5 层 / 压力 · 65 卡 12 层 83 边

## 依赖

- `esbuild`（本仓 `agent-dh/node_modules` 内已有，脚本自动定位；不在 PATH 也能跑）
- `node`（跑自测）
- 无第三方运行时依赖，产物 HTML 单文件自包含
