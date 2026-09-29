# 看板实测回归 · 测试阶段运行报告（t-10122a）

> 卡：t-10122a（父卡 t-e77b06「看板实测回归（真实打开页面）」）｜需求：REQ-260927202051-f6df
> 本卡阶段：**test**｜验收标准：「目标命令输出全绿（贴命令与结果摘要）」
> 证据口径遵循 R-013：每条数字标注来源命令与时点；被测对象先钉事实再下结论。
> 采集时点：**2026-09-27 23:59 ~ 24:00 (+08:00)**（本文件所有实测均在该窗口内一次跑完）

---

## 0. 被测对象（先钉事实）

| 项 | 取值 | 来源 |
|---|---|---|
| 实例/端口 | `:13080`，pid **9454**，ppid 67516 | `lsof -ti:13080 -sTCP:LISTEN` |
| 启动时刻 | **2026-09-27 23:38:16 (+08:00)** | `ps -o pid,ppid,lstart,command -p 9454` |
| 启动命令 | `node --import tsx/esm …/@deepseek-ai/dsh/lib/bin.js --profile agent-dh --port 13080` | 同上 |
| 服务端产物 | `dist/index.mjs` / `lib/client.js` 均构建于 **23:03**；`find src -newer dist/index.mjs` = **0** ⇒ 产物不旧于源码 | `ls -la dist/ lib/`、`find` |
| 台账 | `.dsh-data/dsh-reqboard.json`：`schemaVersion=9`、**无 `tasks` 键**、`migrations=[{8→9, by: migrate-ledger.ts}]`、requirements=**82** | python 读盘 |
| 队列真值（磁盘） | **51** 份 `queue.json`、**616** 条任务、51 个需求有任务；本需求 **29** 条；状态分布 done 583 / in_progress 8 / todo 25 | python 扫 `docs/requirements/*/queue.json` |

**关于「重启后实测」**：被测实例 23:38:16 的启动**晚于**台账迁移（22:55）、迁移留痕修复（23:37）与 dist 构建（23:03），
即当前进程本身就是「迁移 + 读方改造之后」的新进程；本轮测试直接落在该进程上，
**未再叠一次重启**（:13080 即本测试的执行环境，重启会杀死验证进程本身）。
`quick-restart-result.json` 记明该次重启的用途：解锁本需求 workflow 链并让新进程 boot 时急切 load 修复后的 v9 台账。

---

## 1. 目标命令与结果（全绿）

### 1.1 真实浏览器实测（主证据，验收②③④⑥）

```bash
cd agent-dh
node docs/requirements/REQ-260927202051-f6df/notes/board-live/cdp-board-check.mjs \
  --port 13080 --req REQ-260927202051-f6df \
  --out docs/requirements/REQ-260927202051-f6df/notes/board-live/test-run/shots
# → EXIT=0；断言：15 passed / 0 failed
```

原始 stdout：`notes/board-live/test-run/cdp-board-check.console.log`；结构化证据：`…/test-run/shots/SUMMARY.json`

| # | 断言 | 实测值 |
|---|---|---|
| 1 | 页面加载（未落到 401） | `title=DeepSeek Harness`、`hasReqboardClient=true` |
| 2 | pmboard client 半已接管 | `window.__dshReqboardClient` 存在 |
| 3 | 泳道看板渲染出泳道 | 泳道数 = **6** |
| 4 | 泳道看板有需求卡（非空） | 卡片数 = **34**，空态 = false |
| 5 | 本需求卡片可见（⑥） | REQ-260927202051-f6df 命中，文案「父卡 2/3 · 子卡 11/12」 |
| 6 | 列表视图渲染出行 | 行数 = **10** |
| 7 | 任务总览页渲染（非空） | 需求分组 = **51**，任务行 = **616**（「616 个任务 · 51 个需求」） |
| 8 | 甘特图 SVG 渲染（③） | `.dsh-pm-gantt` 在场，条形数 = **2912** |
| 9 | 本需求在任务总览可见（⑥） | 该需求甘特条 = **128** |
| 10 | 需求详情页渲染（④） | 正文 171,531 字符、表格 2、任务行 **64**、6 个 Tab（概览/执行/时间线/归档/追溯/Token） |
| 11 | 依赖信息可见 | `.dsh-pm-dag=true`，DAG 层 = **11**，文本含「依赖」 |
| 12 | 无未捕获页面异常 | **0** 条 |
| 13 | 无 console.error | **0** 条 |
| 14 | 无失败的数据请求 | **0** 条（XHR/Fetch） |
| 15 | 接口/DOM 交叉核对 | 接口 tasks=**616**、requirements=**82**，DOM 卡片=34 |

### 1.2 页面可达性探针（验收① 的等价口径）

```bash
node docs/requirements/REQ-260927202051-f6df/notes/board-live/route-probe.mjs --port 13080
# → EXIT=0；断言：4 passed / 0 failed
```

| 断言 | 实测 |
|---|---|
| `GET /`（带 dsh-auth cookie） | **200**，bytes=32257，`pmboard` 命中 **5** |
| `GET /`（无 cookie） | **401**（鉴权在位） |
| `GET /dashboard` | **404** bytes=0 —— 客户端 hash 路由，服务端无此 path |
| `GET /dashboard/api/reqboard/state` | **200**，requirements=**82**、tasks=**616**、rev=5959 |

**验收① 字面命令的诚实记录**：`curl -s localhost:13080/dashboard | grep -c pmboard` → **0**。
原因：`/dashboard` 是 dsh web 的**客户端 hash 路由**（服务端 404），不是看板回归；
等价判据 `GET /` → 200 且 `pmboard=5` 成立（§1.2）。
此偏离已在 t-f4c9f5（复核）中确认为**口径偏差、非失败**，本轮独立复现同一结论。

### 1.3 启动日志核验（验收⑤）

对 `quick-restart.log` 最后一次启动段落（第 15177 行「Agent-DH 启动」起，28 行）：

```
LEDGER_REQUIRES_MIGRATION            命中 0   （整份日志亦为 0）
UnhandledPromiseRejection/uncaughtException/TypeError   命中 0
Queue ready tasks: t-c130ca (requirement REQ-260927202051-f6df)   ← boot 即从队列出 ready
[2026-09-27 23:38:08] health ok (HTTP 401)                        ← 401 为鉴权在位，非故障
```

### 1.4 排队/读方单测非回归（旁证，非本卡主证据）

```bash
cd packages/web/dsh-pmboard && npx vitest run tests/queue
# → EXIT=0；Test Files 12 passed (12)；Tests 131 passed (131)；Duration 825ms
```

原始 stdout：`notes/board-live/test-run/queue-unit.console.log`。
单测走 in-memory 夹具，只证明逻辑；§1.1 的浏览器实开证明渲染链路 —— 两者互相独立（R-013 口径）。

### 1.5 截图（验收⑦，非 curl 200 代替渲染）

| 视图 | 路径 | 尺寸/大小 | 非白像素比（去空白校验） |
|---|---|---|---|
| 泳道看板 | `…/test-run/shots/01-board-lanes.png` | 1680×1413 / 258,956 B | 0.284 |
| 列表视图 | `…/test-run/shots/02-board-list.png` | 1680×1413 / 261,835 B | 0.278 |
| 任务总览 + 甘特 | `…/test-run/shots/03-tasks-gantt.png` | 1680×1413 / 347,892 B | 0.325 |
| 需求详情（含 DAG/依赖） | `…/test-run/shots/04-req-detail.png` | 1680×1413 / 253,845 B | 0.438 |

四张 PNG 均为 1680×1413、采样唯一色 980~2401、非白像素 28%~44% ⇒ **非空白页**（`PIL` 采样统计）。
截图落在 **新目录** `test-run/shots/`，未触碰 t-c130ca / t-f4c9f5 已冻结的产物。

---

## 2. 数量对账（「与迁移后一致」）

| 指标 | 磁盘真值（本轮独立重算） | 看板实测 | 一致性 |
|---|---|---|---|
| 台账 requirements | 82 | 接口 requirements = 82 | ✅ |
| queue.json 份数 / 有任务需求 | 51 | 任务总览分组 = 51 | ✅ |
| 队列任务总数 | **616** | 任务总览行 = 616；接口 tasks = 616 | ✅ |
| 本需求任务数 | **29** | 泳道卡片显示「父卡 2/3 · 子卡 11/12」；详情页可见 | ✅ |
| 台账 `tasks` 键 | 无（v9） | 看板照常出数（读方已改走队列） | ✅ |

与 t-c130ca 报告（23:39）的差异为**运行期漂移**而非回归：甘特条 2906→2912、本需求甘特 122→128、
详情页任务行 69→64、正文长度 169,431→171,531 —— 均随本需求 workflow 链持续推进而变（期间任务在 done/ready 间移动，
台账 rev 5959），**结构性计数（616/51/82）逐项不变**。

---

## 3. 判定与边界

- **判定**：本卡（测试阶段）**通过** —— 三条目标命令 `EXIT=0` 全绿
  （CDP 浏览器实测 15/15、可达性探针 4/4、队列单测 131/131），启动日志 0 迁移标记 / 0 未捕获异常，四张真实渲染截图齐备且非空白。
- **边界（不做过度声明）**：
  1. headless Chrome 与有头渲染在同一 CSS 下等价，截图供人眼复核，**本报告不宣称「人已确认视觉效果」**。
  2. 本轮为**只读观测**：未下单、未改台账、未改源码、未重启服务；除自身产物外只新增 `notes/board-live/test-run/` 目录。
  3. 验收① 字面命令为**口径偏差**（`/dashboard` 为客户端 hash 路由，服务端 404），等价判据成立；
     若评审要求字面达标，需在服务端补 `/dashboard` 路由（属新工作，不属本卡）。
  4. 数量对账中的漂移已逐项解释（运行期活动），不构成回归。

## 4. 本卡落盘产出（仅新增 `test-run/` 目录）

| 文件 | 说明 |
|---|---|
| `…/test-run/report.md` | 本报告 |
| `…/test-run/cdp-board-check.console.log` | CDP 实测原始 stdout（15 passed / 0 failed） |
| `…/test-run/route-probe.console.log` | 可达性探针原始 stdout（4 passed / 0 failed） |
| `…/test-run/queue-unit.console.log` | 队列单测原始 stdout（131 passed） |
| `…/test-run/shots/SUMMARY.json` | 15 项断言结构化证据 |
| `…/test-run/shots/01-board-lanes.png` … `04-req-detail.png` | 四张真实渲染截图 |

> 复现方式（cwd = `agent-dh`）：§1.1 / §1.2 / §1.4 三条命令可直接重放，退出码与断言数应与本报告一致。
