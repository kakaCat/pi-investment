---
title: 看板实测回归 · 独立复核报告（父卡 t-e77b06）
type: review
requirement: REQ-260927202051-f6df
task: t-f4c9f5
generated: 2026-09-27
---

# 独立复核报告 · 看板实测回归（t-f4c9f5）

> 本文件是子卡 `t-f4c9f5`（复核阶段）结论的**落盘副本** —— workflow 执行路径把复核产出留在 run 记录里
> （`reqboard_task_status(t-f4c9f5)` 可读原文），验收文档门禁要求 `reviews/` 非空，故按原文落盘，不改写结论。
> 复核时点：2026-09-27 23:53~23:58 (+08:00)。口径遵循 R-013：每个数字带命令来源。

## 0. 复核对象

| 面 | 内容 |
|---|---|
| 比对面（设计） | `design/test-cases.md` TC-10.1~10.5 + 纪律、`design/use-cases.md` UC-6、`decomposition.md` t16 验收①~⑦、`design/architecture.md` 风险登记（:13080 实测） |
| 实现面 | `t-c130ca` 研发（`notes/board-live/run-report-after-restart.md` + `SUMMARY.json` + 4 张 PNG + `route-probe.mjs`）、`t-6df9a0` 联调（`integration-record.md` + `integration-probe.mjs`） |

> 所有结论均经本复核**独立复跑/读源**，未直接采信他卡叙述。

## 1. 独立复跑（本卡自己的证据）

| 项 | 命令 | 结果 |
|---|---|---|
| 主证据 | `node docs/requirements/REQ-260927202051-f6df/notes/board-live/cdp-board-check.mjs --port 13080 --out /tmp/board-review-shots --cdp-port 9377 --req REQ-260927202051-f6df` | **EXIT=0；15 passed / 0 failed** |
| 可达性 | `node docs/requirements/REQ-260927202051-f6df/notes/board-live/route-probe.mjs --port 13080` | **EXIT=0；4 passed / 0 failed**（`GET /` 200 bytes=32257 pmboard=5；无 cookie 401；`/dashboard` 404 bytes=0；`/state` 200 requirements=82 tasks=616 rev=5957） |
| 联调 | `node docs/requirements/REQ-260927202051-f6df/notes/board-live/integration-probe.mjs --port 13080` | **EXIT=0；36 passed / 0 failed**；零写证明 queue.json 指纹 before=after（51 份）、台账 rev 5957→5957 |
| 单测 | `npx vitest run packages/web/dsh-pmboard/tests/t16-http-queue-integration.test.ts` | **1 file / 2 passed**（666ms） |
| 依赖维度（自建探针 `/tmp/dep-probe.mjs`，只读） | 枚举 `.dsh-pm-gantt` 全部子元素 | `line.grid=5 / text.axis=5 / line.mile=6 / text.rowlabel=29 / rect.track=29 / rect.bar=126 / line.now=1` —— **无任何 edge/连线图元** |

## 2. 偏离清单（共 4 处）

### 偏离 1 · 验收① 字面命令 —— 判为**口径偏差**，非失败
`curl -s localhost:13080/dashboard | grep -c pmboard` 命中 **0**：`/dashboard` 是 dsh web 的**客户端 hash 路由**，
服务端无此 path。等价判据成立（`GET /` → 200 且 `pmboard=5`）。
**建议**：修订卡内验收①文本为 `GET /` 口径，或（属新工作）服务端补 `/dashboard` 路由 —— 二者择一，否则字面永远不达标。

### 偏离 2 · 方案要求「本卡叠加重启」 —— 判为**过程偏离、验收意图满足**
实测 `pid 9454 lstart=Sun Sep 27 23:38:16`（晚于台账迁移 22:55 与 dist 构建 23:03）⇒ 被测实例本身即
「迁移 + 读方改造之后」的新进程；且 23:19 `shots-before-restart` 与 23:39 `shots-after-restart` **跨越该重启边界**，
结构性计数逐项相同。**残余**：重启脚本自身可用性不属本卡证据范围。

### 偏离 3 · TC-10.2 字面「依赖连线」 —— 判为**设计文本与 scope 自相矛盾**，非实现缺陷
甘特 SVG **无 edge 图元**（见 §1 探针）。依赖/批次实际由两处承载：
(a) 任务表依赖列 `.dsh-pm-tdeps` 实测 **616 格、非空 492 格**、值为真实依赖 id（如 `t-0e7fac→t-87f0da`）；
(b) 需求详情 DAG 分层视图 `.dsh-pm-dag` **11 层**（= 批次）。
`decomposition.md`「本轮不做」明确列出「队列 DAG 图形 UI」，父卡验收②已收敛为「无空白无 500」
⇒ 实现侧取「依赖信息可见」口径与范围声明自洽。**建议改文本，不改实现。**

### 偏离 4 · TC-10.3「字段完整」 —— **部分覆盖**，残余风险低
DOM 层只做行数/表格/Tab 计数（69 行 → 本复核 71 行），未逐字段断言；字段级完整性由联调层 `/state` 616 条
与磁盘 `queue.json`「去 layer 键集 + 值」逐字段全等承担（复跑 36/36，含 id 顺序逐项相同、出口无 layer）。
**残余风险**：DOM 渲染掉的字段不会被这条链发现，但接口层已封住数据完整性。

## 3. 非偏离项（必须同样记录）

| 项 | 判定 | 依据 |
|---|---|---|
| 偏离 5 · 计数漂移（616/2906/122/69 → 616/2910/126/71） | **非偏离，时点漂移** | 差异来自运行期活动（本父卡子卡/评论/产物写入）；结构性维度（泳道 6、卡片 34、列表 10、分组 51）逐项不变。判定以「结构计数一致 + 断言全绿」为准 |
| 偏离 6 · 本复核自身副作用 | **如实披露** | 复跑 `integration-probe.mjs` 使其重写 `integration-summary.json`（23:53→23:57，结论一致 36/36）；除该文件外零写生产、零改进程，未触碰他人凭证 |
| 纪律「TC-10.x 必须真实打开页面、禁止以 `curl 200` 代替渲染验证」 | **无偏离** | 主证据为 headless Chrome + CDP 真实加载，断言取自渲染后 DOM（`document.querySelector` 计数）而非接口 JSON，另落 4 张截图；curl/route-probe 仅作可达性佐证 |
| TC-10.1 任务页渲染与数量 | **无偏离** | 独立复跑：泳道 6 / 需求卡 34 / 列表 10 / 任务总览 51 组 616 行；磁盘独立复算 51 份 queue.json 共 616 任务、台账 requirements=82 且无 `tasks` 键 |
| TC-10.4 启动日志 | **无偏离** | `quick-restart.log` 最后一次启动段（28 行）：`LEDGER_REQUIRES_MIGRATION=0`、`UnhandledPromiseRejection=0`、`uncaughtException=0`、`TypeError=0` |
| TC-10.5 本需求自身任务可见 | **无偏离** | 泳道卡命中 REQ-260927202051-f6df；任务总览该需求分组命中（甘特条 122→本复核 126）；queue.json 本需求 29 任务 / 11 层 / 42 边 |
| 验收⑦ 截图证据 | **无偏离（仅余「人眼视觉确认」非我方可判）** | 4 张 PNG 真实渲染（1680×1413，原始像素流 7,122,933 B，分块去重 11,399/10,173/15,004/20,430 块 ⇒ 非空白）；**本复核模型无图像输入，未做人眼视觉确认**，如实保留为残余项 |

## 4. 总体判定与边界

- **总体判定**：设计 vs 实现共 **4 处偏离**（1 处口径偏差、1 处过程偏离、1 处设计文本自相矛盾、1 处部分覆盖），
  其余逐项「无偏离」。**未发现实现层缺陷、未发现伪造证据、未发现生产零写声明被破坏。**
- **边界（不越权）**：本卡只出结论，未修改任何 `src/`、测试或凭证文件；父卡 `t-e77b06` 与需求状态由链上裁决，不在本卡结论内。
- **交验收的待裁决项**：偏离 1（改验收①文本 / 补服务端路由）与偏离 3（改 TC-10.2 文本）需**人工裁决**，见 `verification-addendum.md` §四。
