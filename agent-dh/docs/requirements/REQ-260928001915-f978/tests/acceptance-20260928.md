# 验收测试证据（REQ-260928001915-f978）

> 本文件的 `covers:` 标注供 pmboard RTM 覆盖度门禁读取（parser.ts parseTestCovers）。
> 覆盖范围 = 本需求 8 张父卡 + 32 张子卡链任务，共 40 张。

## 测试环境

- 工作区：`/Users/yunpeng/pi-investment/agent-dh`
- 需求目录：`docs/requirements/REQ-260928001915-f978`
- 运行器：`npx tsc`（类型检查）、`npx tsx`（Node 直接跑 TS 模块与单测）、`python3`（构建脚本）
- 数据源：`docs/requirements/REQ-260928001915-f978/queue.json`（40 卡 / 40 边 / 9 层，pmboard validateQueueFile passed=true）

## 汇总读数

| 层次 | 命令 | 结果 |
|---|---|---|
| 模块自测 | `npx tsx demo/selftest.mjs` | 104 通过 / 0 失败 |
| 模块单测 | `npx tsx demo/{critical-path,dag-layout,edge-renderer,interaction,integration}.test.ts` | 36+25+48+36+81 = 226 通过 / 0 失败 |
| 端到端构建 | `python3 demo/build-demo.py` | exit 0，产出 dag-card-types-demo.html |

## 卡片四轴类型系统（demo/card-types.ts）

covers: t-efa03b, t-f24eee, t-4d6cf2, t-730c85, t-d65d4c
validates: FR-1, FR-2

**命令**

```bash
cd docs/requirements/REQ-260928001915-f978
npx tsc demo/card-types.ts --noEmit   # exit 0
npx tsx demo/selftest.mjs                  # [1] 四轴 7+4+3+6=20 个枚举值与颜色表断言全过
```

**结果**：typescript 编译退出码 0；selftest §1 全部 ok

**覆盖任务**：5 张（父卡 t-efa03b + 子卡 t-f24eee, t-4d6cf2, t-730c85, t-d65d4c）

---

## 卡片样式渲染器（demo/card-renderer.ts）

covers: t-2ad263, t-5fccbe, t-92496d, t-c969a8, t-cb5648
validates: FR-2

**命令**

```bash
cd docs/requirements/REQ-260928001915-f978
npx tsc demo/card-renderer.ts --noEmit  # exit 0
npx tsx demo/selftest.mjs                  # [5] 卡片 7 元素断言全过
```

**结果**：grep 统计绘制原语 6 行（≥5）；selftest §5 全部 ok

**覆盖任务**：5 张（父卡 t-2ad263 + 子卡 t-5fccbe, t-92496d, t-c969a8, t-cb5648）

---

## DAG 布局引擎（demo/dag-layout.ts）

covers: t-4256bf, t-c11c61, t-185222, t-a10499, t-d41ea0
validates: FR-3

**命令**

```bash
cd docs/requirements/REQ-260928001915-f978
npx tsc demo/dag-layout.ts --noEmit     # exit 0
npx tsx demo/dag-layout.test.ts            # 25 通过 / 0 失败
```

**结果**：25 项全通过；方向字面量 grep 5 行（≥2）

**覆盖任务**：5 张（父卡 t-4256bf + 子卡 t-c11c61, t-185222, t-a10499, t-d41ea0）

---

## 边线渲染器（demo/edge-renderer.ts）

covers: t-e4e9db, t-660826, t-ca1655, t-35222c, t-c41ace
validates: FR-4

**命令**

```bash
cd docs/requirements/REQ-260928001915-f978
npx tsc demo/edge-renderer.ts --noEmit   # exit 0
npx tsx demo/edge-renderer.test.ts         # 48 通过 / 0 失败
```

**结果**：48 项全通过；strokeStyle grep 3 行（≥3）

**覆盖任务**：5 张（父卡 t-e4e9db + 子卡 t-660826, t-ca1655, t-35222c, t-c41ace）

---

## 关键路径算法（demo/critical-path.ts）

covers: t-1f219b, t-868884, t-41d67e, t-706169, t-1f0b86
validates: FR-6

**命令**

```bash
cd docs/requirements/REQ-260928001915-f978
npx tsc demo/critical-path.ts --noEmit   # exit 0
npx tsx demo/critical-path.test.ts         # 36 / 36 全通过
```

**结果**：36 项全通过；Set|Map grep 22 行（≥2）

**覆盖任务**：5 张（父卡 t-1f219b + 子卡 t-868884, t-41d67e, t-706169, t-1f0b86）

---

## 悬停交互处理器（demo/interaction.ts）

covers: t-73c392, t-e00c5f, t-65df2c, t-b9308e, t-1b2632
validates: FR-5

**命令**

```bash
cd docs/requirements/REQ-260928001915-f978
npx tsc demo/interaction.ts --noEmit     # exit 0
npx tsx demo/interaction.test.ts           # 36 通过 / 0 失败
```

**结果**：36 项全通过；事件监听 grep 3 行（≥2）

**覆盖任务**：5 张（父卡 t-73c392 + 子卡 t-e00c5f, t-65df2c, t-b9308e, t-1b2632）

---

## 父卡子卡链进度条（demo/progress-bar.ts）

covers: t-d379c7, t-8a854a, t-d284d3, t-f49d5b, t-a2599c
validates: FR-7

**命令**

```bash
cd docs/requirements/REQ-260928001915-f978
npx tsc demo/progress-bar.ts --noEmit    # exit 0
npx tsx demo/selftest.mjs                  # [6] 进度条断言全过
```

**结果**：阶段名 grep 6 行（≥4）；selftest §6 全部 ok

**覆盖任务**：5 张（父卡 t-d379c7 + 子卡 t-8a854a, t-d284d3, t-f49d5b, t-a2599c）

---

## 集成测试与文档（demo/integration.ts）

covers: t-144707, t-cf42de, t-dbed64, t-975c52, t-66570e
validates: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7

**命令**

```bash
cd docs/requirements/REQ-260928001915-f978
npx tsc demo/integration.ts --noEmit    # exit 0
npx tsx demo/integration.test.ts           # 81 / 81 全通过
python3 docs/requirements/REQ-260928001915-f978/demo/build-demo.py   # exit 0
```

**结果**：81 项全通过；build-demo.py exit 0，[汇总] 104 通过 / 0 失败

**覆盖任务**：5 张（父卡 t-144707 + 子卡 t-cf42de, t-dbed64, t-975c52, t-66570e）

---

## 端到端场景（补 E2E 缺口）

covers: t-efa03b, t-2ad263, t-4256bf, t-e4e9db, t-1f219b, t-73c392, t-d379c7, t-144707, t-f24eee, t-4d6cf2, t-730c85, t-d65d4c, t-5fccbe, t-92496d, t-c969a8, t-cb5648, t-c11c61, t-185222, t-a10499, t-d41ea0, t-660826, t-ca1655, t-35222c, t-c41ace, t-868884, t-41d67e, t-706169, t-1f0b86, t-e00c5f, t-65df2c, t-b9308e, t-1b2632, t-8a854a, t-d284d3, t-f49d5b, t-a2599c, t-cf42de, t-dbed64, t-975c52, t-66570e
validates: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7

**命令**

```bash
cd docs/requirements/REQ-260928001915-f978
npx tsx demo/integration.test.ts
npx tsx demo/selftest.mjs
python3 demo/build-demo.py
```

**场景与可观察终态**

1. 集成入口全链路（integration.test.ts，81/81）：validateQueueFile → resolveTasks → renderDagHtml / createDagViewer，对四档真实队列（12/20/40/65 卡）断言「节点数 = 任务数」「每个可见节点都有坐标」「只看主线后节点数收缩到关键路径」。
2. Canvas 全链路（selftest.mjs §10）：假 canvas 驱动 createDagViewer，断言绘制调用 > 0（fillText/fillRect/bezierCurveTo）、画布按布局尺寸设置、悬停命中后重绘、点击钉住/再点取消/点空白清除、切横向/关键路径/只看主线均重绘、destroy 后事件解绑。
3. 构建产物（build-demo.py）：exit 0、日志 `模块自测全绿`、写出单文件 HTML。

**结果**：全部通过。
