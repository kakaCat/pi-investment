# dashboard 页面插件 · 详细实施方案（数据链路实测版）

> 日期：2026-09-03 · 作者：investor（w-76653429）
> 上游文档：docs/design/dashboard-implementation-plan.md（结构/路由/分期决策，本方案不重复其内容）
> 本文档定位：在 plan 之上，针对"页面调 v2/os API 取数"约束的【数据链路实测细化】——文中所有端点、参数、返回字段均经 2026-09-03 真实 curl 打样验证。实施以本文档为准。

---

## 0. 相对 plan 的关键纠错与决策（先读）

| # | 主题 | plan 原稿（错误/未定） | 实测结论（本方案采用） |
|---|---|---|---|
| C1 | webServer 注册 API | register({path, method, handler}) | 真实签名：register({kind: "exact"|"prefix", path, handler(req,res)})——【无 method 字段】；handler 直接持有 node:http 的 req/res，自行 writeHead+end。返回 disposer，包在 ctx.effect 里注册 |
| C2 | 持仓汇总/明细端点 | /api/trading/portfolio/summary?account= 与 /api/portfolio/positions?account= | 真实：GET /api/portfolio/summary?account_name= 与 GET /api/portfolio/positions?account_name=（无 trading 前缀；参数名是 account_name，不是 account）|
| C3 | agent-os 健康端点 | /api/health | 真实：根路径 GET :8080/health → {"status":"ok",...}。agent-os 其余探测路径均 404，只信 /health |
| C4 | 检查点引用的调度任务 | gem-kline-update、strategy_circuit_breaker 等 | 【不存在】。真实调度任务共 22 个（见 §5.2 清单）。M0 K线更新对应「每日数据更新」（cron 22:30 工作日），数据质量对应「每日数据质量检查」（cron 22:00 每日）|
| C5 | ERROR 事件流日志路径 | ~/v2-api.log、~/agent-dev.log | 已停更（v2-api.log 停留在 08-31）。真实写入：v2 → /Users/yunpeng/pi-investment/quantsys-v2/logs/launchd-stdout.log；agent-os → /Users/yunpeng/pi-investment/agent-os/logs/launchd-stdout.log；DSH → ~/.dsh-agent-dh/profile-13080.log；PG → ~/pg-server.log（仍在写）。均用 tail 提取 |
| C6 | regime/theme 数据来源 | PG 直读 quant.market_regime/theme | 【免 PG 直读】：v2 现成端点 GET /api/market/perception/regime（20 日序列，字段 trade_date/regime/sentiment_score/ad_ratio/reason）与 GET /api/market/perception/themes（trade_date + themes[] 含 rank/theme/limit_up_count/stocks）。memory/experience 用 GET /api/memory/search。PG 直读降为 0 |
| C7 | CORS | 未明示 | 实测 v2 已放开：带 Origin: http://127.0.0.1:13080 请求返回 access-control-allow-origin + allow-credentials:true。但架构仍锁【服务端代理】（浏览器不直连 5001/8080），理由见 §4 |
| C8 | v2 账户聚合快捷源 | — | 新增：GET /api/health/platform/status 一屏即含 holdings_count=2、cash、market_value、total_assets、max_drawdown、balance_date、db_connected、model_loaded——页面2 健康区与页面1 摘要可共用 |

架构结论（锁定）：浏览器(:13080) → fetch 自身同源 /dashboard/api/* → 插件服务端聚合器 → 上游 v2(:5001)/os(:8080) HTTP + 本机文件 tail。浏览器永不直连 5001/8080。

---

## 1. 交付范围

两个独立只读页面插件（分阶段，每阶段独立验收，见 §9）：

| 插件 | 路由 | 内容 | 上游 |
|---|---|---|---|
| @pi-investment/dashboard-execution（P1 先行） | GET /dashboard/execution（HTML）+ GET /dashboard/api/board（JSON） | 系统健康区 / M0-M8×L1-L4 检查点 / 每日时间轴 / 定时任务表 / 最近错误事件 | v2 health×3；os /health；scheduler tasks+runs；genome.json+candidates.json；三处日志 tail；同进程 DSH 状态 |
| @pi-investment/dashboard-holdings（P2） | GET /dashboard/holdings（HTML）+ GET /dashboard/api/holdings（JSON） | 多账户切换 / 账户摘要 / 持仓明细+买卖点 / 今日自动交易 / 盯盘任务 | v2 accounts、portfolio/summary、portfolio/positions、watch/rules+triggers、simulation/trades、executions/daily、market/perception/regime（买卖点辅助）|
| P3（可选） | — | GUI 入口按钮 / 飞书告警联动 | — |

---

## 2. 服务端路由实现（C1 落地的代码模式）

### 2.1 模板：复用 lifecycle /wake 的注入模式（已验证在运行）

lifecycle 插件 wake-webhook.ts 已于 2026-09-02 用同一机制注册 exact /wake 路由，本次 curl POST /wake 返回 405（路由存活、仅限 POST）——证明该模式可运行。核心代码形态：

  import { Context } from "@deepseek-ai/cordis";
  (ctx as any).inject?.(["webServer"], (webCtx: any) => {
    webCtx.effect(() => webCtx.webServer.register({
      kind: "exact",
      path: "/dashboard/execution",
      handler: async (req: any, res: any) => { /* 见 2.2 */ }
    }), "dashboard-execution: page");
  });

要点：
- 注入用惰性 inject(["webServer"])，webServer 服务就绪前不阻塞插件启动（照抄 wake-webhook 注释里的理由）；
- kind 必须是 "exact"（页面/API 都是全路径匹配；本插件不用 prefix，避免误吞 DSH 自身路由）；
- duplicate (kind,path) 会抛错 → 路由表互斥是天然契约，新增前先查已注册路径（见 §10 自查清单）；
- register 返回 disposer，必须包在 webCtx.effect 内以便插件停用时自动注销。

### 2.2 handler 职责（HTML 与 JSON 两种）

HTML 路由（页面）：读取包内静态 HTML（相对插件目录，用 import.meta.url 定位，勿用 __dirname——tsx/ESM 下不可靠），writeHead(200, text/html; charset=utf-8) + end(html)。插件自包含：HTML 内联全部 CSS/JS，无共享静态资源。

JSON API 路由（聚合数据）：统一 try/catch 包装：

  成功：200 + {"success":true, data:{...}}
  局部降级：200 + {"success":true, data:{..., degraded:[{source:"v2", error:"..."}]}}（单源失败只标红对应区块，绝不整页 500）
  整体异常：500 + {"success":false, error:"..."}

fetch 全部走服务端封装 http.ts：AbortController 超时（默认 4s，可配）+ 解析 {success,data} 信封 + 中文错误包装（参照 quantsys-v2-client 拦截器文案风格，但不依赖该包——理由见 §3）。

---

## 3. 与 quantsys-v2-client 的取舍

新插件【不依赖 @pi-investment/quantsys-v2-client】。理由（2026-09-03 源码核对）：
1. 其 getPortfolioSummary / getPositions 走 GET /api/simulation/accounts/{name}（返回单账户状态对象），与 §0-C2 实测的 /api/portfolio/summary|positions（返回 {positions:[...]}/多字段汇总）口径不同——client 是交易工具语义（agent 用），页面要的是看板语义，强行复用要适配字段；
2. client 挂 axios + axios-retry（失败自动重试 3 次），页面轮询场景不需要重试放大延迟，反而需要快速失败+区块降级；
3. 页面聚合层只读、端点固定（约 10 个），自包含轻量 fetch 封装（40 行内）比引一个大 client 干净，且避免 profile 侧再链一个新 workspace 依赖。

依赖最小化：@deepseek-ai/cordis（必需）+ 可选 @deepseek-ai/schemastery（Config schema）。

---

## 4. 数据访问模式与上游契约（先打样再写代码）

### 4.1 服务端代理（决策）

虽然 CORS 已放开（v2 实测允许 13080），浏览器仍不直连 5001/8080，理由：
1. 统一超时/错误处理：页面 fetch 只面对 /dashboard/api/* 一种信封，v2/os 的偶发超时/5xx/格式漂移在服务端被折叠为 degraded 区块；
2. 字段清洗与聚合：多源拼装（如 summary + positions + regime）在服务端一次完成，HTML 零业务逻辑；
3. 端点变化只改服务端，页面 HTML 不动；
4. 安全性：浏览器不暴露内部端口面。

### 4.2 上游端点契约（2026-09-03 实测）

全部外层信封 {success:true, data:...}（os /health 例外，裸 {"status":"ok"}）。

| 用途 | 端点 | 实测返回要点 |
|---|---|---|
| v2 存活 | GET :5001/api/health | 200 裸 {"status":"ok",...}（0.01s 级）|
| v2 DB | GET :5001/api/health/db | {"status":"healthy","pool_status":{...}} |
| v2 平台+账户聚合 | GET :5001/api/health/platform/status | data: {status, holdings_count, balance:{cash,market_value,total_assets,position_count,total_return,max_drawdown,balance_date}, db_connected, model_loaded, timestamp} |
| v2 调度任务 | GET :5001/api/scheduler/tasks?pageSize=200 | data.tasks[]: {id,name,enabled,scheduleKind,scheduleExpr,payload:{command},lastRun,nextRunAt,createdAt}（实测 22 个）|
| v2 任务运行记录 | GET :5001/api/scheduler/runs?pageSize=50 | data.runs[]: {id,taskId,taskName,status(failed/…),triggeredAt,finishedAt,durationMs,payload:{error?}} |
| v2 失败运行 | GET :5001/api/scheduler/runs/failed?pageSize=50 | 同上（84 条历史）|
| v2 regime | GET :5001/api/market/perception/regime | data[]（按日期降序，20 条）: {trade_date, regime(range/…), sentiment_score, ad_ratio, reason, created_at} |
| v2 主线主题 | GET :5001/api/market/perception/themes | data: {trade_date, themes:[{id,rank,theme,limit_up_count,stocks:[{symbol,name,change_pct}]}]} |
| v2 memory | GET :5001/api/memory/search?q=&namespace= | 需要时打样（实施时确认参数名）；另有 /api/memory/health → {"status":"ok"} |
| v2 持仓汇总 | GET :5001/api/portfolio/summary?account_name=agent_virtual | data: {accountName,totalValue,totalCost,totalMarketValue,totalPnl,totalPnlPct,dailyChange,positions,cash,profitCount,lossCount,lastUpdated} |
| v2 持仓明细 | GET :5001/api/portfolio/positions?account_name=agent_virtual | data: {positions:[{symbol,quantity,sharesAvailable,avgCost,currentPrice,totalCost,currentValue,profitLoss,profitLossPct}], count} |
| v2 账户列表 | GET :5001/api/simulation/accounts | data: [{account_name/…, status}]（实施时确认字段名）|
| v2 盯盘规则 | GET :5001/api/watch/rules | data: 规则列表（含 id/name/symbol/condition/enabled/triggered_count）|
| v2 盯盘触发 | GET :5001/api/watch/triggers?limit=50 | data: 触发记录 |
| v2 今日交易 | GET :5001/api/executions/daily?start_date=&end_date=（必填参数）| 打样 400，实施时带日期；另 /api/executions/stats 当前返回 {} |
| v2 今日信号 | GET :5001/api/signals?date= | 实施时打样（signal_track 后端落库）|
| os 存活 | GET :8080/health | 裸 {"status":"ok","time":…} |

### 4.3 各区块数据源映射（页面 → API）

页面2 /dashboard/api/board：
- 健康区：v2 /api/health + /api/health/db + /api/health/platform/status（并行，4s 超时）；os /health；PG 由 platform/status.db_connected 代替 SELECT 1；DSH 同进程 process.uptime() + memoryUsage()；
- 检查点：§5（scheduler tasks/runs + regime + genome）；
- 定时任务表：scheduler/tasks 全量（22 个，含 enabled/schedule/nextRunAt/lastRun）；
- 错误事件流：§6（三处日志 tail）。

页面1 /dashboard/api/holdings：
- 账户列表/切换：simulation/accounts + portfolio/summary（默认 agent_virtual，可切换传 account_name）；
- 摘要数字：portfolio/summary（totalValue/totalPnl/totalPnlPct/cash/…）；
- 持仓明细：portfolio/positions（symbol/quantity/sharesAvailable/avgCost/currentPrice/profitLoss/profitLossPct）；
- 合规 chips：聚合层按宪法阈值算现金/单股/单行业/回撤占比（持仓市值占 totalValue 等）；
- 今日自动交易：executions/daily + simulation/trades（实施时打样选型）；
- 盯盘任务：watch/rules + watch/triggers（规则现价/距离由聚合层取 quote 或规则自带字段）；
- 买卖点：positions + swing_points 分析（POST /api/analysis/swing-points 已存在于 openapi，plan 的 ZigZag 口径）。


---

## 5. 检查点注册表（真实任务映射，替代 plan §5.3 的臆测任务名）

### 5.1 注册表数据结构（服务端常量，后续可配置化）

  interface Checkpoint {
    id: string;              // 如 "m0_kline_sync"
    line: "engine" | "autonomy";
    module: string;          // 展示用："M0" / "L1" ...
    name: string;
    verify: Verify;
    expectDays: string;      // "1-5" 工作日 / "0" 周日 / "0-6" 每日
    expectTime: string;      // "HH:mm" 本地时区
    graceMinutes: number;    // 默认 30
    blocksFlow?: string[];   // 失败阻断的下游模块 id
  }
  type Verify =
    | { type: "scheduler_task"; taskName: string; statusField?: "lastRun" | "todaySuccess" }
    | { type: "v2_regime" }                    // market/perception/regime 最新 trade_date
    | { type: "v2_themes" }                    // market/perception/themes 最新 trade_date
    | { type: "v2_memory_kind"; kind: string } // memory/search 当日新增计数
    | { type: "genome_file"; file: "genome.json" | "candidates.json" }
    | { type: "log_marker"; file: string; pattern: string };

### 5.2 真实调度任务清单（2026-09-03 scheduler/tasks 实测，22 个，全部 enabled）

| id | 任务名 | cron | 对应检查点 |
|---|---|---|---|
| 233 | 每日数据更新 | 22:30 周一-五 | M0 K线同步 |
| 232 | 每日数据质量检查 | 22:00 每日 | M0 数据质量 |
| 238 | 每周财务数据更新 | 周六 18:30 | M0 财务（周度） |
| 258 | daily-pool-refresh | 23:00 周日至四 | M2 股票池刷新 |
| 236 | 每日信号生成 | 08:30 周一-五 | M3 信号生成 |
| 242 | 每日信号执行 | 07:30 周一-五 | M3 信号执行 |
| 311 | signal-perf-backfill-daily | 15:45 周一-五 | M3 胜率回填 |
| 307 | daily_trade_verify | 15:35 周一-五 | M5 交易对账 |
| 301 | market_daily_snapshot | 22:00 周一-五 | M1 感知快照（regime/themes 落库驱动） |
| 268 | v13-risk-check | 08:00 周一-五 | M4 风控 |
| 271 | v13-weekly-report | 周日 01:00 | L4 周报 |
| 262 | chan-knowledge-distill-weekly | 周日 12:00 | L2/L3 周蒸馏 |
| 252 | daily-strategy-validation | 13:00 周一-五 | L1 策略验证 |
| 250 | pre-market-scan | 01:25 周一-五 | M3 盘前扫描 |
| 249 | v13-simulation-trading | 06:30 周一-五 | M3 模拟交易 |
| 269 | v13-verification | 07:30 周一-五 | L1 验证 |
| 312 | market-style-update | 23:30 周一-五 | M1 风格 |
| 308 | fund_flow_update | 23:00 周一-五 | M1 资金流 |
| 237 | 每周报告生成 | 周五 10:00 | L4 周度（跨周视角） |
| 253 | weekly-strategy-discovery | 周六 02:00 | L1 发现 |
| 318 | 每日财报时效性检查 | 09:00 每日 | M0 财报时效 |
| 261 | chan-scan-daily | 22:30 周一-五 | M0/M1 缠论扫描 |

### 5.3 初始检查点定义（M0-M8 × L1-L4，映射真实 verify）

注意：plan §5.3 曾把 M1 的 regime/theme 映射到 PG 查询——现在改为 v2 端点（§0-C6），且"数据日期"口径统一为最近一个交易日 trade_date。

| 模块 | id | 检查点名称 | verify（真实） | 期望 | blocksFlow |
|---|---|---|---|---|---|
| M0 | m0_kline_sync | 日K同步 | scheduler_task: 每日数据更新 | 22:30 周一-五 | M1,M2,M3 |
| M0 | m0_data_quality | 数据质量检查 | scheduler_task: 每日数据质量检查 | 22:00 每日 | M1 |
| M0 | m0_fin_weekly | 周度财务更新 | scheduler_task: 每周财务数据更新 | 周六 18:30 | M2 |
| M1 | m1_regime | regime 落库 | v2_regime（trade_date==最近交易日）| 22:10 周一-五（随 snapshot）| M4 |
| M1 | m1_themes | 主线主题落库 | v2_themes（trade_date==最近交易日）| 22:10 周一-五 | M2,M3 |
| M2 | m2_pool_refresh | 股票池刷新 | scheduler_task: daily-pool-refresh | 23:00 周日-四 | M3 |
| M3 | m3_signal_gen | 信号生成 | scheduler_task: 每日信号生成 | 08:30 周一-五 | — |
| M3 | m3_signal_exec | 信号执行 | scheduler_task: 每日信号执行 | 07:30 周一-五 | — |
| M3 | m3_perf_backfill | 胜率回填 | scheduler_task: signal-perf-backfill-daily | 15:45 周一-五 | L1 |
| M4 | m4_risk_check | 风控/熔断 | scheduler_task: v13-risk-check | 08:00 周一-五 | M5 |
| M5 | m5_trade_verify | 交易对账 | scheduler_task: daily_trade_verify | 15:35 周一-五 | — |
| M6 | m6_experience | 盘后经验沉淀 | v2_memory_kind: experience（当日新增>0）| 16:00+ 周一-五 | L1,L2 |
| L1 | l1_strategy_validate | 策略验证 | scheduler_task: daily-strategy-validation | 13:00 周一-五 | — |
| L2 | l2_distill | 经验蒸馏 | genome_file: candidates.json（created_at 当日）或 scheduler_task 周蒸馏 | 16:00 周一-五 | — |
| L3 | l3_gate | 验证门裁决 | genome_file: genome.json history（最新条目当日）| 每日（周日重点）| — |
| L4 | l4_weekly_report | 周报 | scheduler_task: v13-weekly-report | 周日 01:00 | — |

实现说明：
- scheduler_task 判定数据来自 GET /api/scheduler/tasks?pageSize=200 一次拉全 + 最近一次 /runs 结果匹配（lastRun + 最近 run.status）；失败优先取 runs 里该 task 最近一条 failed 的 error 摘要；
- 判定基准"最近应执行日"用 trading_calendar 语义（周末非交易日→m3 系 off_day 灰；周日任务 l4 等按 0 处理）；
- regime/themes 的 trade_date 取最近交易日（09-02 是最近交易日 → 今天 09-03 晚间未落库属 pending 而非 failed，宽限到 22:30+）。

### 5.4 状态判定算法（沿用 plan §5.2）

  off_day（灰）: 今日不满足 expectDays 或今日非交易日且任务是交易日的
  confirmed（绿）: verify 通过（数据日期==最近应执行日，或 scheduler lastRun 当日成功）
  failed（红）: scheduler run.status==failed（附 payload.error 摘要，截断 200 字）
  late（黄）: now > expectTime + grace 且非 failed/confirmed
  pending（灰白）: 未到 expectTime
  unknown（紫灰）: v2 不可达时全部依赖 v2 的检查点标 unknown（降级保护，防误报"业务没跑"）

---

## 6. 健康区与错误事件流实现

### 6.1 健康探测（/dashboard/api/board 的 health 区块）

并行探测（Promise.allSettled，各 4s 超时，任何单源失败只降级对应行）：
1. quantsys-v2：GET :5001/api/health → ok 时再取 /api/health/db（pool_status）与 /api/health/platform/status（holdings_count、balance、db_connected、model_loaded）；总耗时计入展示；
2. Agent OS：GET :8080/health（根路径）；
3. PostgreSQL：不再直连——用 platform/status.db_connected 字段；db_connected=false 时该行标红并提示查 v2 /api/health/db；
4. agent-dh 自身：同进程 process.uptime() + process.memoryUsage().rss/heapUsed + 最近调度心跳（如可取 lifecycle 状态；取不到就显示 uptime，页面能打开即自证存活）；
5. 启动计数：读 ~/.dsh/profiles/investment/state/restart-counter.json（若存在），或日志中 "restart" 计数。

展示形态（沿用设计稿）：每行 图标+名称+端口+关键指标+耗时；v2 行下方若 failed 给出 platform/status 摘要。

### 6.2 错误事件流（三端日志 tail）

真实日志位置（C5 修正后）：
- v2: /Users/yunpeng/pi-investment/quantsys-v2/logs/launchd-stdout.log（进程 51866 打开句柄确认）+ launchd-stderr.log
- os: /Users/yunpeng/pi-investment/agent-os/logs/launchd-stdout.log + launchd-stderr.log
- dsh: /Users/yunpeng/.dsh-agent-dh/profile-13080.log（实时在写，本次读到 QuantsysV2Client retry 行）
- pg: /Users/yunpeng/pg-server.log（可选，仍在写）

实现：tail 最后 300 行（fs 读 + 取尾，日志 < 30MB 直接全读截尾亦可），按行过滤 /ERROR|CRITICAL|Traceback|panic|FATAL/i，取最近 10 条，输出 {file, line, ts}，ts 从行首时间戳尝试解析（如 [2026-09-03T…]），解析失败标 no_ts。

轮询窗口：日志区 60s 刷新，健康区 30s。

---


---

## 7. 页面2（execution）规格与每日时间轴

### 7.1 时间轴数据源

不用臆造理想日程——直接以 v2 真实调度任务的 cron 为时间轴底本（§5.2 清单），叠加当日 runs 状态：
- 按 cron 换算本地时间（cron 字段为服务器本地/UTC——2026-09-03 实测任务 318 显示 09:00，与业务语义一致，判定为本地时区；实施时先抽样换算验证，若有 UTC 偏移在注册表映射时一次校正，plan §5.2 已注明此坑）；
- 每行：任务名 + 期望 HH:mm + 当日 run 结果（成功/失败/未到点）；
- 用 /api/scheduler/runs 匹配当日 taskId，失败行红标 + error 摘要。

### 7.2 页面布局（静态规格，HTML 内联实现）

1. 顶部健康区（30s 轮询）：四行服务（v2/os/PG/agent-dh）+ 每行右侧关键指标 + 总体耗时；
2. 阻断告警卡：任一检查点 failed/late 且 blocksFlow 非空 → 列出下游；
3. M0-M8 × L1-L4 检查点看板（60s）：网格卡片，色标 灰白/绿/红/黄/紫灰（§5.4），卡片含 verify 摘要；
4. 最近错误事件（60s）：三端日志 tail 合流，10 条，来源标签 v2/os/dsh，时间戳倒序；
5. 底部任务明细表（30s 或手动刷新）：22 个真实任务 id/name/enabled/schedule/nextRunAt/lastRun/last status；可展开失败 run 的 error。

页面自身状态：document.visibilityState 变化时暂停/恢复轮询；每次 fetch 失败显示上一次缓存 + 顶部"数据陈旧"提示。

---

## 8. P1 落地与注册（实施阶段执行，非本方案范围）

1. 目录：agent-dh/packages/pages/execution/（package.json 按 §2，依赖 cordis ^4 + schemastery ^3.18）；
2. agent-dh 根 pnpm install（使嵌套 workspace 生效）→ 单包无需独立 install；
3. 按 §2 树实现 src（routes/services/pages）+ test；接入 tests/plugin-schema.smoke.test.ts（仅当注册工具——若只注册 webServer 路由无工具，跳过 schema 但插件本身仍要在冒烟里加载验证 apply 不抛错）；
4. 注册进 profile：
   - ~/.dsh/profiles/investment/package.json dependencies 加 file: 指向 packages/pages/execution（嵌套 file: 路径，见 plan §8）；
   - cordis.patch.yml insert execution 插件段；
   - ln -sfn 链接（profile 不在 agent-dh workspace，workspace: 协议会失败，必须手动符号链接，agent-dh/CLAUDE.md 有样例）；
   - agent-dh 根 vitest 冒烟全绿；
5. 重启 :13080（用其自身 stop.sh/start.sh——多实例铁律）；验证 /dashboard/execution 200 + /dashboard/api/board JSON；
6. 页面逐区块对照 §4.3 契约验收（§9）；
7. R-010 飞书通知完成。

P2（holdings）同流程，页面路由 /dashboard/holdings + /dashboard/api/holdings。

---

## 9. 验收清单（P1 execution 页面）

功能：
- [ ] GET /dashboard/execution 返回 200 + text/html，浏览器渲染无 console 错误；
- [ ] GET /dashboard/api/board 返回 {success:true, data:{health, checkpoints, tasks, errors, timeline}}，单区块字段与 §4.2 契约一致；
- [ ] 健康区四行正确显示 v2（含 db/platform 摘要）/os/PG(db_connected)/agent-dh（uptime+rss）；
- [ ] 检查点按 §5.4 正确着色：当前为 pending/late 而非 failed 的边界（如 09-03 晚间 regime 未落库应 pending，不误报 failed）；
- [ ] 22 个任务在时间轴与任务表中齐全，runs 失败行带 error 摘要（如 daily-pool-refresh 现存的 list_pools 报错应显示）；
- [ ] 错误事件流能抓到真实日志行（profile-13080.log 现有 QuantsysV2Client retry 行）；
- [ ] 降级：kill v2（不 kill 其他）→ 页面健康区 v2 红、依赖 v2 的检查点紫灰 unknown、错误流出现连接失败行、页面不 500；恢复 v2 后 60s 内自愈；
- [ ] 60s/30s 轮询窗口生效，tab 隐藏时暂停。

工程：
- [ ] schema 冒烟测试加载插件不抛错（UNSUPPORTED_SCHEMA 门禁）；
- [ ] 代码走 wake-webhook 注入模式 + effect 包裹 disposer；
- [ ] 未改动其他插件/配置文件（git status 干净只含本插件文件）。

---

## 10. 风险与实施前自查清单

1. 路由冲突：注册前先查 webServer 已注册路径（grep packages/*/src 中 .register({kind,path}），勿撞 /wake、勿撞 DSH 内建（如 SPA fallback 的 catch-all——页面与 API 用 exact 匹配天然避开 prefix fallback）；
2. execution HTML 的 URL 编码与 query 解析：handler 里自己 parse req.url（node:url），注意中文 account_name 需 encodeURIComponent；
3. 日志文件轮转：logrotate/重建时 inode 变化，用"打开句柄的当前路径重新打开"而非缓存 fd（每次请求重新 fs.open 或 stat 长度即可，日志 < 30MB 无压力）；
4. scheduler cron 时区若为 UTC：cron 字段换算须在注册表一次校正（§7.1），验证法：比对任务 318「每日财报 09:00」本地 09:00 出现 run；
5. 端口探测保底：HTTP 探测失败时区分 进程死/端口堵/超时（fetch error 类型：ECONNREFUSED vs timeout）输出不同文案；
6. /api/executions/daily 需要日期参数（实测 400），前端必须带上；executions/stats 空 {} 不用；
7. 每个新端点在写解析代码前 curl 打样一次（含字段名大小写、嵌套层），遵守"字段假设必须用真实数据验证"教训；
8. 若 P1 验收时发现 v2 scheduler 任务名变动（未来），检查点 verify 用 taskName 匹配 + 找不到时该检查点标 unknown 并附"任务不存在"提示，不让页面崩溃。

---

## 附：本方案实测数据快照（2026-09-03 晚）

- v2 平台：holdings_count=2，balance{cash:97462.91, market_value:7823.0, total_assets:105285.91, total_return:0.0529, max_drawdown:0.0031, balance_date:2026-09-03}，db_connected:true，model_loaded:false；
- 持仓明细 2 条（portfolio/positions?account_name=agent_virtual）；
- regime 最近 09-02 = range（情绪60/量能9.52/涨家占比26.8%），themes 09-02 主线：汽车零部（5 涨停）等；
- 调度 22 任务全 enabled；runs 历史 failed 84 条，最近一例 run 3388 daily-pool-refresh 报 "function object has no attribute list_pools"（v2 侧缺陷，非本插件问题，页面应如实展示）；
- DSH /wake 路由存活（405=仅 POST），证明 webServer exact 注册机制在运行；
- CORS 实测放开但架构仍走服务端代理。