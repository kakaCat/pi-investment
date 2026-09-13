---
id: design-dashboard-implementation-plan
title: 看板插件实现方案 · dashboard-holdings / dashboard-execution（双插件）
type: design
status: archived
updated: 2026-09-13
owners: [w-66dd4c29]
tags: [design]
---

# 看板插件实现方案 · dashboard-holdings / dashboard-execution（双插件）

> **状态：archived（已落地，2026-09-14 标注）**：本文是 2026-09-02 的方案稿，实现形态后来被用户纠正
> （标准**双半插件**，非独立 HTML 页面）——以文首「§0 最终落地状态」与附录 A 为准。落地现状见
> [holdings 包 README](../../packages/pages/holdings/README.md) 与 [execution 包 README](../../packages/pages/execution/README.md)。


> 日期：2026-09-02 · 作者：investor（w-66dd4c29）
> 设计稿：`page1-monitor-dashboard.html`（账户持仓看板）、`page2-execution-board.html`（双线执行确认看板）
> 架构图：`dsh-integration-arch.html`
> 状态：✅ 已落地（P1 execution 与 P2 holdings 均以双半插件上线 :13080）——正文 HTML 页面形态与路由表已被附录 A 与「§0 最终落地状态」取代，以新段为准

---

## 0. 最终落地状态与复盘（2026-09-04 追加 · investor w-1cee2467）

> 本段是**当前事实的唯一权威**；下方正文保留为历史设计（HTML 页面形态已被用户纠正废弃，见附录 A）。

| 项 | 计划（2026-09-02） | 实际落地（2026-09-04） |
|---|---|---|
| 页面形态 | HTML 独立页（/dashboard/holdings、/dashboard/execution） | 废弃——用户纠正为标准双半插件（附录 A）：JSON API + 浏览器侧 GUI |
| 路由 | /dashboard/holdings、/dashboard/execution | /dashboard/api/holdings、/dashboard/api/board（host 半 JSON 端点，client 半同源 fetch） |
| P1 execution | 独立插件 | 独立插件，唯一 owner /dashboard/api/board |
| P2 holdings | 独立插件 | 曾被并入 execution 插件（偏离双插件设计）→ 2026-09-04 按用户裁决 1B 恢复独立包，唯一 owner /dashboard/api/holdings；execution 内联合并副本已剥离 |
| profile 注册 | 未定 | 产品档（~/.dsh）与 dev 档（~/.dsh-agent-dh）cordis.patch.yml 均注册两插件；node_modules 均链接两包 |
| GUI 入口 | P3 按钮 | 侧栏 footer 双按钮：执行看板（execution order 100）+ 持仓看板（holdings order 200；dsh.client.inject=["slots"]） |

**复盘根因（交付与计划不一致）**：① 实现中途 HTML 页面方案崩溃，用户 09-04 纠正为双半插件标准，但计划正文未同步（附录先行）→ 正文误导；② holdings 被并入已验证的 execution 插件内联实现，违反「两个独立插件」设计且路由归属不清；③ 独立 holdings 包停留在带调试标记、未注册 slots、未提交状态，从未真正被 profile 加载（/tmp 标记缺席为实证）；④ 两档 profile 注册/链接漂移（dev 档缺 holdings）；⑤ 改动均未合并，文档/代码/配置三者互相不一致。

## 1. 目标

在 DSH Web GUI（:13080）内提供两个**纯只读监控页面**，由**两个独立插件**分别承载，共享 `/dashboard/` 域前缀：

| 插件 | 页面 | 路由 | 内容 |
|---|---|---|---|
| `@pi-investment/dashboard-holdings` | 账户持仓看板 | `/dashboard/holdings` | 多账户切换、券商式账户摘要、持仓明细（真实成本+未来买卖点）、今日自动交易（执行状态+🕊️通知）、价格触发盯盘任务 |
| `@pi-investment/dashboard-execution` | 双线执行确认看板 | `/dashboard/execution` | **系统健康监控（三端+PG+调度器+错误流）**、M0-M8×L1-L4 流程图、完整每日时间轴+周末流程、Agent 今日动态、分类型定时任务表 |

**拆分成两个插件的理由**：职责独立（持仓业务监控 vs 系统执行监控）、独立演进/独立禁用、单个插件故障不影响另一个；共享 `/dashboard/` 前缀保持同一域观感。两页顶栏带互相跳转链接；`/dashboard/` 根路径不设导航页（避免归属问题），入口=直接 URL + P3 的 GUI 入口按钮。

所有操作由 agent 自动完成，页面零操作按钮（仅查看/跳转）。

## 2. 总体架构

```
浏览器 :13080/dashboard/holdings        :13080/dashboard/execution
   │ fetch /dashboard/api/holdings        │ fetch /dashboard/api/board
   ▼                                     ▼
dashboard-holdings 插件              dashboard-execution 插件
（DSH 进程内 cordis 插件，互相独立、纯只读；源码位于 packages/pages/ 页面域，与其余包同属一个 workspace）
   ├── HTTP → quantsys-v2 :5001（scheduler/positions/signals/watch/health 等现有端点）
   ├── HTTP → Agent OS :8080（健康探测，execution 插件）
   ├── 只读 → PostgreSQL :5432（仅 v2 无端点时的补充，如 regime/theme 落库日期）
   ├── 读文件 → ~/.dsh-agent-dh/genome/genome.json + 日志 tail（ERROR 事件流）
   └── 同进程 → DSH 自身状态（进程信息 / native-scheduler 心跳）
```

**关键决策：不改 quantsys-v2、不改 Agent OS、不改任何现有插件。** 聚合逻辑全部收在两个新插件内；v2 缺端点的数据用 PG 只读兜底。

## 3. 插件包结构（页面域嵌套，两个包同构）

```
agent-dh/packages/pages/            # ← 页面域：agent-dh 自研的 DSH GUI 页面集合（嵌套特例，见注①）
├── holdings/                       #   项目1：账户持仓看板插件（@pi-investment/dashboard-holdings）
│   ├── package.json
│   ├── tsconfig.json
│   ├── src/
│   │   ├── index.ts     # apply(ctx) 注册路由
│   │   ├── config.ts    # Config schema
│   │   ├── routes.ts
│   │   ├── services/
│   │   │   └── portfolio.ts  # 多账户/持仓/买卖点/自动交易/盯盘
│   │   └── pages/
│   │       └── holdings.html # 内联全部 CSS/JS
│   └── test/
└── execution/                      #   项目2：双线执行确认看板插件（@pi-investment/dashboard-execution）
    ├── package.json
    ├── tsconfig.json
    ├── src/
    │   ├── index.ts     # apply(ctx) 注册路由
    │   ├── config.ts    # Config schema
    │   ├── routes.ts
    │   ├── services/
    │   │   ├── board.ts       # 聚合入口
    │   │   ├── health.ts      # 三端+PG 健康探测
    │   │   ├── checkpoints.ts # 检查点注册表+判定（§5）
    │   │   ├── errors.ts      # 日志 tail ERROR 流
    │   │   └── genome.ts      # genome.json 读取
    │   └── pages/
    │       └── execution.html # 内联全部 CSS/JS
    └── test/
```

> 注①（目录结构决策 2026-09-03）：页面插件统一收在 `packages/pages/` 域下（目录嵌套，包名仍为平级式 `@pi-investment/dashboard-*`，与现有 22 个包短名=目录名的约定解耦）。域内每个子目录是独立 workspace 包（含独立 package.json）。⚠️ pnpm-workspace.yaml 与根 package.json 的 workspaces 已加 `packages/pages/*` glob——嵌套包必须是 workspace 成员，否则 pnpm 静默忽略（不构建/不装依赖/不报错）。

**每个页面 HTML 内联全部 CSS/JS**——插件完全自包含，无共享静态资源，避免两个插件撞同一路由（webServer duplicate path 会抛错）。

**前端技术选型：纯静态 HTML + 原生 fetch 轮询（60s/30s），无 React、无构建链。** 理由：页面已在设计稿中定稿为静态 HTML，直接演进为真实页面，避免引入 DSH client bundle 构建管线，风险最小。client 半包（GUI 内「📊 看板」入口按钮）放 Phase 3 可选实现，届时两个插件各自注册自己的入口。

## 4. 路由设计

| 插件 | 路由 | 类型 | 说明 |
|---|---|---|---|
| holdings | `/dashboard/holdings` | exact → holdings.html | 页面1 |
| holdings | `/dashboard/api/holdings?account=` | JSON | 页面1 聚合数据 |
| execution | `/dashboard/execution` | exact → execution.html | 页面2 |
| execution | `/dashboard/api/board` | JSON | 页面2 聚合数据（含健康+检查点+任务） |

实现：`ctx.webServer.register({ kind: 'exact', path, handler(req,res) })`（⚠️ 2026-09-03 实测：真实签名**无 method 字段**、须带 kind，见 dashboard-implementation-detail.md §0-C1；duplicate (kind,path) 会抛错——两个插件路由不相交，也防止和其他插件撞路由）。所有 API 处理器套统一错误包装：单数据源失败只降级对应区块（`degraded: true` + 错误摘要），绝不整页 500。

> **数据访问模式（2026-09-03 curl 实测确认）：页面不在浏览器直接 fetch v2/os**——改由 DSH 插件处理器（服务端）统一做上游调用（fetch 到 `127.0.0.1:5001` / `127.0.0.1:8080`）再返回 `/dashboard/api/*` JSON。理由：CORS 虽已放开（v2 对 `Origin: http://127.0.0.1:13080` 返回 `access-control-allow-origin` + `allow-credentials: true`；os 同源无跨域问题），但服务端代理可做**超时/降级/统一错误包装/字段清洗**，避免把 v2/os 偶发故障直接暴露给页面并保持 `degraded` 语义一致。
>
> ⚠️ **上游真实端点（curl 实测，修正早期笔误——教训：字段假设必须真实验证）**：
> - 持仓汇总：`GET :5001/api/portfolio/summary?account_name=`（**非** `/api/trading/portfolio/summary`，无 trading 前缀；参数名 **account_name** 非 account）
> - 持仓明细：`GET :5001/api/portfolio/positions?account_name=`（参数同上）
> - 账户列表：`GET :5001/api/simulation/accounts`（可选 `?status=`）
> - 盯盘规则/触发：`GET :5001/api/watch/rules`（可选 symbol/enabled）、`GET :5001/api/watch/triggers`（可选 symbol/limit）
> - 定时任务：`GET :5001/api/scheduler/tasks`（可选 page/pageSize）
> - v2 健康：`GET :5001/api/health`（另有 /api/health/db 等细分）
> - Agent OS 健康：`GET :8080/health`（**根路径**，非 /api/health）
> - 完整清单以 `:5001/openapi.json`（422 条）为准；新增端点引用前先 curl 打样（见 §10 契约测试）

## 5. 核心：检查点注册表与状态判定（页面2 灵魂）

### 5.1 检查点注册表（代码内常量，后续可落库配置化）

```typescript
interface Checkpoint {
  id: string;                    // 'm1_regime_daily'
  line: 'engine' | 'autonomy';
  module: string;                // 'M1' | 'L2'
  name: string;                  // 'regime 落库'
  expect: { time: 'HH:mm'; days: '1-5' | '0-6' | '6,0' };  // 期望执行时间（本地时区）
  graceMinutes: number;          // 宽限期，默认 30
  verify: Verify;                // 见下
  blocksFlow?: string[];         // 失败时阻断的下游模块，如 ['M1','M3']
}

type Verify =
  | { type: 'scheduler_task'; taskName: string }              // /api/scheduler/tasks 查 last_run_at/last_status
  | { type: 'v2_endpoint'; path: string; dateField: string }  // v2 端点取最新业务日期
  | { type: 'pg_query'; sql: string }                         // 只读 SQL（regime/theme/experience 等）
  | { type: 'genome_file'; field: 'updated_at' | 'candidate' } // genome.json
  | { type: 'log_marker'; file: string; pattern: string };     // 日志中出现标记
```

### 5.2 状态判定算法

```
if 今日不满足 expect.days（非交易日/非周末任务日） → off_day（灰）
elif verify 通过（数据日期 == 最近应执行日）     → confirmed（绿）
elif scheduler_task.last_status == 'failed'      → failed（红，附 error 摘要）
elif now > expect.time + grace                   → late（黄："迟到 X 分钟"）
else                                              → pending（灰白：未到点）
```

特殊规则：
- **降级保护**：v2 不可达时，依赖 v2 的检查点全部标 `unknown`（紫灰），顶部健康区标红 v2——避免把"监控系统挂了"误报成"全部业务没跑"
- **阻断传播**：`blocksFlow` 非空的检查点 failed/late 时，健康区生成"阻断告警"卡，列出被堵住的下游模块；流程图对应节点边框标红
- **判定时间基准**：`expect.time` 一律本地时区（Asia/Shanghai），cron 里 UTC 存储的差异在注册表映射时一次性处理

### 5.3 初始检查点清单（映射真实任务/表）

| 模块 | 检查点 | verify |
|---|---|---|
| M0 | K线同步 21:00 | scheduler_task: gem-kline-update |
| M0 | 数据质量检查 16:00 | scheduler_task: 每日数据质量检查 |
| M1 | regime 落库 15:30 | pg: max(trade_date) from quant.market_regime |
| M1 | 主线落库 15:30 | pg: quant.market_theme |
| M2 | 股票池刷新 | scheduler_task: daily-pool-refresh |
| M3 | 信号生成+胜率回填 | scheduler_task: signal-perf-backfill-daily + signals 当日条数 |
| M4 | 熔断检查 16:30 | scheduler_task / strategy_circuit_breaker |
| M5 | 交易对账 15:35 | scheduler_task: daily_trade_verify |
| M6 | 盘后经验沉淀 | pg: memory_entries kind=experience 当日新增 |
| L1 | 学习追踪 | 同 M6 经验计数 |
| L2 | 每日蒸馏 16:00 | genome_file: candidates.json mtime / 蒸馏记录 |
| L3 | 周六变异/周日裁决 | genome_file: genome.json history 最新条目 |
| L4 | 周日元学习+周报 | pg: memory_entries scope=report:weekly |

## 6. 系统健康监控区（页面2 顶部，最高优先级）

```
┌──────────────────────────────────────────────────────────┐
│ 🟢 agent-dh :13080  运行 12 天 · 今日重启 0 · 调度器心跳 30s前 │
│ 🟢 quantsys-v2 :5001  API 正常 · APScheduler 运行中 · 34 任务 │
│ 🟡 Agent OS :8080    legacy · memory/通知通道正常           │
│ 🟢 PostgreSQL :5432  连接正常 · quant 库 104 表             │
├──────────────────────────────────────────────────────────┤
│ ⛔ 阻断告警：market_daily_snapshot failed → M1 regime 已 3   │
│    个交易日未更新（影响：M1 感知 / M4 仓位映射）               │
├──────────────────────────────────────────────────────────┤
│ 最近错误事件（三端日志 tail，最新 10 条，含来源标签）          │
└──────────────────────────────────────────────────────────┘
```

探测方式：
- **v2**：`GET :5001/api/health`（存在）+ 响应耗时；失败 → 端口探测兜底区分"进程死/端口堵/接口错"
- **Agent OS**：`:8080` 健康端点（沿用 agent_os_status 工具同款探测）
- **PG**：`SELECT 1` 只读连接（超时 3s）
- **agent-dh 自身**：同进程——process.uptime、memory 占用、native-scheduler 最近 tick（lifecycle 插件暴露的状态）；若页面能打开则 DSH 必然存活（自证），额外显示重启计数
- **错误事件流**：tail `~/v2-api.log`、`~/agent-dev.log`、`~/pg-server.log`，提取含 `ERROR|CRITICAL|Traceback|panic` 的最近 N 行，带时间戳和来源标签

## 7. 页面1 数据口径

| UI 元素 | 数据源 |
|---|---|
| 账户列表+切换 | v2 `GET /api/simulation/accounts` |
| 今日盈亏/持仓盈亏/总资产/市值/可用资金 | v2 `GET /api/portfolio/summary?account_name=`（实测 200：totalValue/totalPnl/totalPnlPct/cash 等） |
| 合规 chips（现金/单股/单行业/回撤） | 由 summary+positions 在聚合层计算，对照宪法阈值 |
| 持仓明细（代码/名称/市值/股数/现价/成本/盈亏） | v2 `GET /api/portfolio/positions?account_name=`（实测 200：positions[].quantity/sharesAvailable/avgCost/currentPrice/profitLossPct） |
| 未来买卖点 | 止损价=宪法分档（-8/-10/-12%）；买区/卖压=ZigZag（v2 swing 端点，若无则聚合层用 daily_klines 计算）；临近止损高亮 |
| 今日自动交易（委托价/数量/金额/执行状态/滑点/🕊️通知） | v2 `GET /api/simulation/trades` / `/api/simulation/accounts/{account}/trades` + notification 投递记录（聚合层清洗） |
| 盯盘任务（触发价/现价/距离/状态/动作） | v2 `GET /api/watch/rules`（可选 symbol/enabled）+ `GET /api/watch/triggers`（可选 symbol/limit） |

## 8. 注册与发布步骤

1. `agent-dh/packages/pages/holdings/` 与 `agent-dh/packages/pages/execution/` 按现有包同构创建（参照 trading 包的 package.json/tsconfig/tsdown；workspace glob `packages/pages/*` 已就位，`pnpm install` 后即为成员）
2. profile 注册：
   - `~/.dsh/profiles/investment/package.json` 加两条 link 依赖（指向嵌套路径，如 `file:../../../pi-investment/agent-dh/packages/pages/holdings` 与 `.../packages/pages/execution`；若 profile 依赖需 workspace:^ 解析，按 CLAUDE.md 手动 `ln -sfn` 建符号链接到 `node_modules/@pi-investment/*`）
   - `cordis.patch.yml` insert 两个插件条目（config 各自带 v2/os/pg 地址，互不影响）
3. `pnpm build` 构建 → `self_restart`（或 dsh 重启）→ 验证两个页面 URL
4. 验证清单：两页面渲染、API JSON 结构、停 v2 验证降级（标红不报错）、非交易日状态判定正确、禁用其中一个插件另一个不受影响

## 9. 分期实施

| Phase | 插件 | 内容 | 验收 |
|---|---|---|---|
| **P1** | dashboard-execution | 插件骨架 + 路由托管 + `/dashboard/api/board` + 页面2（健康区+流程图+时间轴+任务表） | 页面2 全绿/真实红黄状态与 DB 一致；停 v2 验证降级 |
| **P2** | dashboard-holdings | 插件骨架 + `/dashboard/api/holdings` + 页面1（多账户+持仓+买卖点+自动交易+盯盘） | 持仓数字与 v2 端点逐一核对一致；买卖点=止损档+ZigZag 真实计算 |
| **P3**（可选） | 两者各自 | client 半包：GUI 聊天页各自注入「📊」入口按钮；飞书联动（迟到/失败自动告警） | GUI 内一键打开；阻断事件 5 分钟内飞书可达 |

每个 Phase 完成按 R-010 发飞书通知。

## 10. 风险与对策

| 风险 | 对策 |
|---|---|
| DSH webServer 路由与现有插件冲突 | register 重复 path 会抛错→激活失败立即可见；选 `/dashboard/` 独立前缀 |
| v2 端点字段假设与真实不符（历史教训） | 先用 curl 对每个端点打样，契约测试固定响应形状 |
| PG 直读绕过了 v2 抽象 | 仅限只读、仅补 v2 无端点的 3-4 个查询；连接串走 config，失败降级标 unknown |
| 状态判定误报（非交易日标红） | 以 quant.trading_calendar 为准，周末/节假日 off_day |
| 插件崩溃拖垮 DSH | 所有处理器 try/catch 降级；插件纯只读无状态，可随时禁用 |

## 11. 工作量估算

P1 ≈ 1.5 天（插件骨架+聚合服务+页面2）；P2 ≈ 1 天；P3 ≈ 0.5 天。总计约 3 天。


---

## 附录 A · 实现方式修正（2026-09-04 · 双半插件标准）

> 用户纠正（2026-09-04，investor w-76653429）：「/Volumes/ORICO/doc/github/dsh-taskboard/dsh-taskboard 这个是标准实现方式，我看你用html做的这是错误的方法」。
> 即：独立 HTML 页面（webServer exact 路由吐整页）**不是** DSH GUI 插件的标准做法；标准是 dsh-taskboard 的**双半插件**：
> 包级声明 dsh.client（platform web）+ exports["./client"] → dsh web shell 的 client-modules host 把该包组合进 boot graph，
> 浏览器端执行 client bundle（wrapper id = 包名），在 **GUI 侧栏插入入口 + 中心栏挂载视图**（非 URL 页面）。

对 execution 插件的影响（已实施 2026-09-04）：

1. **host 半**只保留 GET /dashboard/api/board（JSON，同源免认证，供 client 半 fetch）；删除
   GET /dashboard/execution 页面路由与 src/page/execution.html（renderers 已移植为 client 半 TS）。
2. **client 半**新增 src/client/（index/dom/sidebar-entry/board-mount/view/styles/types，纯 DOM 零第三方依赖），
   tsdown 打包 → scripts/wrap-client.mjs 包 window.__ModuleLoader__.load → lib/client.js。
3. **GUI 呈现**：侧栏「执行看板」入口 + 中心栏看板视图（激活语义 dsh-panel-activate 事件 + html[data-dsh-exec-active]，
   与 taskboard/ssh 等面板互斥；MutationObserver 自愈入口）。
4. 依赖顺序铁律：**先 build:client（产出 lib/client.js）再重启**——host 在 clientPath 缺失时 MissingClientBundleError 启动即失败。

holdings 插件若后续做 GUI 呈现，同样按此双半方式（勿再走 HTML 页面路由）。

---

## 相关页面

- [页面插件契约](../architecture/page-plugin-contract.md)
- [holdings 包](../../packages/pages/holdings/README.md)
- [execution 包](../../packages/pages/execution/README.md)
- [page1 实施方案](page1-holdings-implementation-plan.md)
