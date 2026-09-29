# 验收材料 · REQ-260929010300-dbf9（implementing → accepting）

> 交付结论：会话「流程节点」面板的实施 [DAG] 页签与拆分「📊 DAG 层级」块，已改用与需求详情同一份 `buildDagCanvas` 的 **Canvas 真图**；面板骨架皮肤统一为**泳道图底色**（`--dsh-pm-np-bg` / #f5f5f7，用户 2026-09-29 裁定）。需求详情零回归；canvas 卡片绘制仅按 2026-09-29 裁定 D 删除**父卡左侧蓝条**（其余零改动）。

## 1. 验收命令与实测输出（2026-09-29，工作区 packages/web/dsh-pmboard）

| # | 命令 / 核验点 | 实测输出 |
|---|---|---|
| 1 | `npx vitest run tests/dag-view.test.ts tests/node-panel.test.ts tests/client-view.test.ts tests/dag-styles.test.ts` | **4 files passed / 111 tests passed** |
| 2 | `pnpm build:client` | exit 0；`[verify-client] OK bundle=308699 bytes, 关键符号齐全, styles.ts 括号配对` |
| 3 | `npx tsc --noEmit -p tsconfig.json` | 本次涉及文件（`src/client/**`）**0 error**；全仓 208 条为其它在途工作既有错误（改动前后计数一致） |
| 4 | `grep -n -- '--dsw-' src/client/styles/dag.ts` | **无命中**（皮肤口径全部 `--dsh-pm-np-*`） |
| 5 | 两处 DAG 面板 DOM 类名集合逐项相同 | tests/node-panel.test.ts 断言通过（并钉住 panel/head/canvas-wrap/canvas/legend 五个骨架类，防两个空集合假绿；2026-09-29 裁定 B 后 title/flowstat 已删） |
| 6 | ~~画布卡绘制零改动~~（**裁定 D 覆盖**） | 早期核验时 `card-renderer.ts` 无改动条目；2026-09-29 裁定 D 后**仅删除父卡左侧蓝条**（见 §8） |
| 7 | 需求详情调用方零改动 | `views/stage-detail.ts` 未被本需求改动（mtime 2026-09-29 00:04，早于本需求全部编辑）；`buildDag` 仍走缺省 `#dag-canvas` |

## 2. 功能点逐条证据

- **FR-1/FR-2**：`node-panel.ts` 两处 DAG 块改调 `buildDagCanvas(tasks, PANEL_DAG_CONTAINER_ID, PANEL_DAG_CANVAS_ID)`；两处 HTML 均含 `dsh-pm-dag-panel` + `id="np-dag-canvas"`，均不含旧 `dsh-pm-np-dag-layer` / `dsh-pm-np-dag-node`（tests/node-panel.test.ts）。
- **FR-3**：三个入口 `canvasId` 可选，缺省 = `dag-canvas`（旧行为逐字节等价）；两个不同 canvasId 各挂一次后释放其一，另一实例监听未被摘（tests/dag-view.test.ts 的 fake DOM 用例）。
- **FR-4**：同 id 二次挂载先释放同名旧实例、不产生两块画布；容器宽度变化由 ResizeObserver 按新宽度重排（挂载侧保留）。
- **FR-5**：`conversation-progress.ts` 新增 useEffect（依赖 detailOpen / selectedStage / stageOverview）在 DOM commit 后调 `tryMountDagCanvas`；rAF + `getElementById` 二次确认，目标不存在时静默返回。
- **FR-6**：`styles/dag.ts` 取值全部 `--dsh-pm-np-*`，面板底色 = 泳道图底色 `--dsh-pm-np-bg`（tests/dag-styles.test.ts 断言锁定，禁止改回白底）。
- **FR-7（2026-09-29 裁定 B 作废）**：面板不再有统计条；`ready` 只驱动画布可开工绿点，不再有文字标注。

## 3. 人工核验（:13080，请人工确认）

1. 刷新页面 → 会话右上角流程节点：实施阶段 [DAG] 页签 / 拆分阶段「📊 DAG 层级」可见真图画布（底色为浅灰 #f5f5f7），**无标题行 / 无统计条**（2026-09-29 裁定 B），三个开关、图例与需求详情执行 Tab 逐字一致；
2. 控制台 `document.querySelectorAll('canvas.dsh-pm-dag-canvas').length` 与各自 id（`dag-canvas` / `np-dag-canvas`）核对；
3. DAG ↔ 泳道 页签来回切换后画布仍在。

## 4. 已知事项（显式记录）

1. **皮肤固定浅色**：np 苹果风为固定浅色，DAG 面板不再随明暗主题变化（用户 2026-09-29 追认）。
2. **归档条断言校正**：`tests/client-view.test.ts` 原有一条与本需求无关的既存失败断言（`dsh-pm-archived-bar`；`git grep` 证实在基线 HEAD 无任何代码产出该元素）。经用户 2026-09-29 裁定（选 B）按当前真实行为校正为「archived/canceled 不进泳道」。归档条是否属看板回归，另议。
3. **回滚路径**：见 `tasks/t-757283.md` 的「## 回滚路径」段（数据契约未变，回滚只还原接线与皮肤）。

## 5. 追加修复（2026-09-29 用户裁定 B「数据侧」）：`dependsOn` 归一为「直接前置」

> 起因：用户 2026-09-29 反馈「本项目的 l0 与 l1-1 连接、l1-1 连接 l2-1，l0-1 又连接 l2-1，这个是不是 bug」，
> 并裁定按 **B 数据侧** 解决、以本项目为起点重构（原文：「B 数据侧 解决这个问题，以本次项目你开始重构」）。

### 5.1 事实（修复前，线上真数据扫描）

- 55 份队列、卡片层 **646** 条原始边里 **98 条（15.2%）** 存在替代路径（即 A→B、B→C、A→C 三角形）；**33/55** 份队列带冗余前置。
- 画布侧 `reduceEdges` 已能折叠（画线 548、0 条真三角形），但 **数据本身仍带闭包**：任务表 / 依赖列 / RTM / 甘特图等每个消费者都要各自再折一次。

### 5.2 改了什么（把归约前移到写入侧；唯一实现）

| 文件 | 改动 |
|---|---|
| `src/domain/queue/transitiveReduction.ts`（新增） | 传递归约**唯一实现**（纯函数、零 import）。判据：前置 p 冗余 ⟺ 另有前置 q 可走到 p。**只删「存在且有替代路径」的**；**悬空引用一律保留**（不替 V-3 静默消灭问题）；环安全不抛错 |
| `src/domain/queue/normalizeQueue.ts`（新增） | `normalizeQueueFile`：归约 + `layer/edges/layers/ready` 整份重算（队列写路径与迁移脚本共用，杜绝两套口径漂移） |
| `src/repositories/QueueTaskStore.ts` | `recompute` 委托 `normalizeQueueFile`（写入即归一）；`createMany` 返回**归一化后的落盘态**（不再返回入参副本，避免磁盘与调用方口径分叉） |
| `src/shared/protocol.ts` | `normalizePlanTasks` 增第三遍：计划 `depends_on` 同样归约（作者写全量前置也不再进入计划/队列） |
| `scripts/normalize-queue-deps.ts`（新增） | 存量迁移脚本：默认 dry-run；`--req <id>`（可重复）单需求；`--apply` 真写；复用 QueueRepository 的校验 + 原子写 |
| `tests/queue/dependency-reduction.test.ts`（新增） | 10 用例：归约判据/边界 + normalizeQueueFile + QueueTaskStore 落盘 |
| `tests/chinese-column-support.test.ts`、`tests/read-sites-equivalence.test.ts` | 两处旧断言按新契约更新（read-sites 的 D8「逐字节等价」= V8 真身数据**经同一份归约后**的值，其余字段与顺序仍逐字节） |

### 5.3 证据（可复核）

- **迁移**：`npx tsx scripts/normalize-queue-deps.ts --apply` → 73 需求扫描 / 32 需归约 / **115 条依赖被折叠**；本项目 `REQ-260929010300-dbf9` 写回 4 条（edges 35→31）。
- **迁移后全量复扫**：55 份含任务队列，卡片层原始边 **548 = 画线 548**，**仍有冗余的文件 0**（修复前 646→548）。
- **本项目**：`repo.load` 校验通过；`buildDagData` edgesRaw=7 = drawn=7；分层与修复前逐字相同（**执行序不变**）。
- **测试**：`npx vitest run` → **85 failed / 2623 passed**；对照基线（同一份代码**关闭归约**）= **91 failed / 2617 passed**。失败文件集合之外**零新增**，差异仅 `chinese-column-support`（1）+ `dependency-reduction`（5）由红转绿。全仓 35 个失败文件均为**在途其它工作既有失败**（例：`plan-mode.test.ts` 断言 `requirement_status`，而 `MoveTask` 在 HEAD 与工作区均无该字段）。
- **类型**：`npx tsc --noEmit` 全仓 208 条（与改动前计数一致），**本次涉及文件 0 error**。
- **构建**：`pnpm build`（host+client）退出 0；`[verify-client] OK bundle=308699 bytes, 关键符号齐全`；`dist/index.mjs` 含 `transitiveReduce` / `normalizeQueueFile`。

### 5.4 已知事项（显式记录）

1. **数据口径收窄**：`dependsOn` 语义从「全部前置（传递闭包）」收窄为「**直接前置**」。这是本轮唯一的数据变更——用户 2026-09-29 裁定；可达性/分层/ready 不变，故执行序与可开工集不变。
2. **运行中实例需重启**：新 host 代码在 `dist/index.mjs`，且 `QueueTaskStore` 有按需求的内存缓存；重启后生效。磁盘数据已迁移，重启前后画布视觉不变（画布自身仍有归约兜底）。

## 6. 追加裁定 B（2026-09-29 用户）：DAG 面板删标题行 + 统计条

> 用户原文：「B — 两处都删标题行 + 统计条（一切从简，牵连 FR-7 那句「统计条标推导」一并作废）」。

### 6.1 改了什么

| 位置 | 改动 |
|---|---|
| `src/client/views/dag-view.ts` `buildDagCanvas` | 删 `.dsh-pm-dag-title`（🔀 父卡依赖关系（真 DAG · 子卡不单独成节点））与 `.dsh-pm-dag-flowstat`（`[data-dag-stat]`）；面板 = 工具条 + 画布 + 图例 |
| 同文件 `mountDagCanvas` | 删统计位回填（`stat.innerHTML = statHtml(...)`）与随之无用的 `byId`；`paint` 退化为 `viewer.patch` 直通 |
| `src/client/styles/dag.ts` | 删 `.dsh-pm-dag-title` / `.dsh-pm-dag-flowstat*` 规则（表头 `padding` 由 8px→11px 补顶距） |
| `src/client/dag/dag-stat.ts` | **删除**（唯一消费方是上面的统计位；全仓无其它引用） |
| `tests/dag-view.test.ts` / `tests/client-view.test.ts` / `tests/node-panel.test.ts` / `tests/dag-styles.test.ts` | 断言按新契约更新 + 新增「面板不再有标题行 / 统计条」锁定用例 |
| `requirement.md`、`design/{architecture,data-model,test-cases,use-cases}.md` | FR-7 标注作废；判据 / `serves` / `ready` 语义对齐 |

### 6.2 证据

- `npx vitest run tests/dag-view.test.ts tests/dag-styles.test.ts tests/node-panel.test.ts tests/client-view.test.ts` → **4 files passed / 112 tests passed**（原 111，+1 为新增锁定用例）。
- 全量 `npx vitest run` → **85 failed / 2624 passed**；与上一轮（仅数据侧改动）失败文件集合**逐项相同**（零新增回归）。
- `npx tsc --noEmit -p tsconfig.json` → 全仓 208 条（与改动前一致），本次涉及文件 **0 error**。
- `pnpm build`（host+client）→ 退出 0；`[verify-client] OK bundle=306788 bytes, 关键符号齐全`（客户端 bundle 308699 → 306788，缩小 1.9KB）。

### 6.3 已知事项

1. **FR-7 作废**：统计条已不存在，故「面板侧 ready 标『推导』」这条验收判据不再成立；`ready` 两态语义保留，只影响画布可开工绿点。
2. 任务卡 `t-3ed4b5` 的原验收标准含「统计条显示『推导』」，已按本裁定修订验收标准（去掉统计条）。

## 7. 追加裁定 C（2026-09-29 用户）：DAG 竖向布局去掉「同层折行」限制

> 用户原文：「会话右上角节点 没有展开 一行只能放2个，把这个限制去掉」。

### 7.1 改了什么

| 位置 | 改动 |
|---|---|
| `src/client/dag/dag-layout.ts` 竖向分支 | `cols` 由「按容器宽度算」改为「= 最宽层的卡数」→ **同层始终一行**；`width = max(最宽层所需宽度, availW)`（availW 降级为最小宽度）；层距恒为 `CARD_H + BAND_GAP` |
| `tests/dag-layout.test.ts`（新增） | 4 用例锁定：同层 5 卡在 availW=690 下同一行、x 逐张递增；窄内容铺满容器；跨层行距恒定 |
| `requirement.md` / `design/architecture.md` | 追加裁定 C 与布局口径 |

### 7.2 证据

- 真数据实测（本项目 `REQ-260929010300-dbf9`，6 卡 4 层）：
  - `availW=666`（会话面板实际可用宽度）→ **每行卡数 1+3+1+1**、canvasW=722（旧口径为 2 列折行）；
  - `availW=1000` → 每行卡数 1+3+1+1、canvasW=1000。
- `npx vitest run tests/dag-layout.test.ts` → 4 tests passed。
- 全量 `npx vitest run` → **85 failed / 2628 passed**；与上一轮失败文件集合**逐项相同**（零新增回归）。
- `npx tsc --noEmit -p tsconfig.json` → 全仓 208 条（与改动前一致），本次涉及文件 **0 error**。
- `pnpm build` → 退出 0；`[verify-client] OK bundle=306768 bytes, 关键符号齐全`。

## 8. 追加裁定 D（2026-09-29 用户）：删除父卡左侧蓝条

> 用户原文：「卡片左边的一条线删除了，泳道卡片就是对的」。

### 8.1 改了什么

| 位置 | 改动 |
|---|---|
| `src/client/dag/card-renderer.ts` | Canvas 后端删除 `if (role===PARENT) fillRect(x+1, y+6, 3, CARD_H-12)` 蓝条；DOM 后端 `cardHtml` 删除 `.card-crown`（两个后端保持同一外观口径） |
| `src/client/dag/card-types.ts` / `views/dag-view.ts` | 文档注释同步（Role.PARENT 不再有「左侧蓝条」这一视觉标识） |
| `tests/dag-view.test.ts` / `tests/dag-layout.test.ts` | 断言更新：`showKidChains=true` 时 `fillRects=1`（只剩进度段）、`false` 时 `fillRects=0`（无蓝条、无进度段） |

### 8.2 证据

- `npx vitest run dag-view card-layer dag-layout dag-styles node-panel client-view` → **8 files / 154 tests passed**。
- 全量 `npx vitest run` → **85 failed / 2628 passed**；与上一轮失败文件集合**逐项相同**（零新增回归）。
- `npx tsc --noEmit -p tsconfig.json` → 全仓 208 条（与改动前一致），本次涉及文件 **0 error**。
- `pnpm build` → 退出 0；`[verify-client] OK bundle=306688 bytes, 关键符号齐全`。

### 8.3 已知事项

「canvas 卡片绘制零改动」这条非目标被本裁定**覆盖一处**（父卡左侧蓝条）；类型/端侧/阶段徽标、208×72 几何、配色、折叠/归约/箭头分级均未动。任务卡 `t-757283` 的验收标准含该项，已同步修订。

## 9. 追加裁定 E（2026-09-29 用户）：泳道卡片不再展示子卡链进度

> 用户原文：「泳道里的卡片有4/4这个内容删除了，不需要展示」。

### 9.1 改了什么

| 位置 | 改动 |
|---|---|
| `src/client/node-panel.ts` `renderSwimlane` | 不再拼 `chainHtml(kids)` → 父卡卡片只剩 编号 / 标题 / （必要时）「链未生成」标；列归属仍由 `laneOf` 按子卡链推导 |
| 同文件 import | 去掉不再使用的 `chainHtml` |
| `tests/node-panel.test.ts` / `tests/card-layer.test.ts` | 断言反转：泳道卡片**不含** `card-chain` / `n/N`，但仍只列父卡 |

### 9.2 证据

- `npx vitest run node-panel card-layer dag-view dag-layout dag-styles node-panel-styles client-view` → **8 files / 154 tests passed**。
- 全量 `npx vitest run` → **85 failed / 2628 passed**；与上一轮失败文件集合**逐项相同**（零新增回归）。
- `npx tsc --noEmit -p tsconfig.json` → 全仓 208 条（与改动前一致），本次涉及文件 **0 error**。
- `pnpm build` → 退出 0；`[verify-client] OK bundle=306117 bytes, 关键符号齐全`。

### 9.3 已知事项

子卡链**信息**仍参与推导（列归属 `laneOf`、「链未生成」诊断），只是**不再有卡底进度展示**；`chainHtml` 仍供未接线的 DOM 后端（`renderDagHtml`）使用，未删。

## 10. 追加裁定 F（2026-09-29 用户）：恢复「单击卡片 → 打开任务卡文档」

> 用户原文：「点击卡片应该打开对应文档这个dag功能丢失了」。

### 10.1 根因

旧分层列表（`renderDag`）的节点是 `<button data-action="open-doc" data-path=cardDoc>` → 单击即开文档；
换成 Canvas 后：① `CardData` 没有 `cardDoc` 字段（画布不知道文档路径）；② 单击被 `setupInteraction` 的「钉住高亮」占用；
③ 只在双击时走 `open-task`（只有 board-mount 处理该委托，会话面板无处理方 → 等于没反应）。

### 10.2 改了什么

| 位置 | 改动 |
|---|---|
| `src/client/dag/card-types.ts` | `CardData` 增 `cardDoc?: string` |
| `src/client/types.ts` | client `TaskRecord` 补 `cardDoc?: string`（此前类型缺口：线上一直有该字段，类型里没有） |
| `src/client/views/dag-view.ts` | `toCard` 透传 `cardDoc`；新增 `openCardDoc()`（派发 `data-action="open-doc"`，与 `openTaskDetail` 同构）；挂载侧新增 canvas `click`：命中卡且有 `cardDoc` → **延迟 220ms 打开文档**；`dblclick` 取消待触发单击后再开任务详情；`dispose` 清 timer 与监听；副标题改为「单击打开任务卡文档 · 双击打开任务详情」 |
| `tests/dag-view.test.ts` | 假 DOM 记录派发元素 + canvas 桩支持 `fire`；新增 4 用例（cardDoc 透传、单击延迟派发 open-doc、双击只派发 open-task、无 cardDoc 不派发） |

### 10.3 证据

- `npx vitest run dag-view` → **29 tests passed**（原 25，+4）。
- `npx vitest run dag-view node-panel client-view dag-styles dag-layout card-layer node-panel-styles` → **8 files / 158 tests passed**。
- 全量 `npx vitest run` → **85 failed / 2632 passed**；与上一轮失败文件集合**逐项相同**（零新增回归）。
- `npx tsc --noEmit -p tsconfig.json` → 全仓 **208 条（与改动前一致）**，本次涉及文件 **0 error**。
- `pnpm build` → 退出 0；`[verify-client] OK bundle=306787 bytes, 关键符号齐全`。

### 10.4 已知事项

双击→任务详情的委托仍只有看板页（board-mount）具备；会话面板里双击不发散——单击开文档才是面板的文档入口，与旧列表一致。
