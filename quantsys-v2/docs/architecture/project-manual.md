---
id: project-manual
title: QuantSys V2 项目说明书（L1）
summary: 这个项目是什么、关键认知在哪、每次变更在「最近更新」留一行。
type: architecture
status: living
updated: 2026-10-06
owners: [project]
tags: [manual, l1, index]
---

# QuantSys V2 项目说明书（L1）

> 本文件是**金字塔的顶层**：读完它应当知道「这个项目是什么、现在有哪些关键认知、去哪找」。
> 领域结论放 L2（`docs/architecture/` 等），过程与证据放 L3（`docs/requirements/REQ-*`）。

## 1. 这个项目是什么

PI Investment 的**后端服务系统**：为自主 AI 投研代理提供 HTTP/WebSocket API、
数据持久化（审计留痕）与量化计算（回测、因子、ML、风控）。

三层协作：`agent-ts`（决策者）→ **本仓 quantsys-v2（基础设施）** → `web-frontend`（监控看板）。

## 2. 关键架构与运行入口（一眼索引）

| 关注点 | 入口 / 文档 |
|---|---|
| HTTP API（5001） | `adapters/inbound/fastapi_app/main.py` |
| WebSocket（5003） | `adapters/inbound/fastapi_app/websocket_server.py` |
| CLI | `adapters/inbound/cli/main.py` |
| 调度（三条线程：APScheduler / DailyJobs / WatchEngine） | `docs/architecture/scheduler-architecture.md` |
| 数据访问（唯一入口） | `DataProviderManager`（`adapters/outbound/datasources/manager.py`）+ `CLAUDE.md`「Data Access Rules」 |
| DI 入口 | `infrastructure/services/service_factory.py` |
| 模拟交易账本完整性 | `docs/architecture/simulation-trading-integrity.md` |
| 交易日/新鲜度口径 | `docs/architecture/trading-day-freshness.md` |
| 通知测试守卫 | `docs/architecture/notification-test-guard.md` |
| **每日任务通知如实性契约** | `docs/architecture/notification-truthfulness.md` |
| **数据质量：异常检测三态语义 + 两个口径坑** | `docs/architecture/data-quality-anomaly-semantics.md` |
| 需求档案（L3） | `docs/requirements/REQ-*`（索引见 `docs/requirements/INDEX.md`，如存在） |

## 3. 关键认知（读到就少踩一次）

1. **"跑了" ≠ "有产出" ≠ "该发"**：两层——**发不发**由 `daily_jobs/notify_policy.py::is_no_op`
   判（无事 = `no_output is True` 或 `status ∈ {no_event, no_op}` → 开始与完成两条都不发，
   失败与人工触发除外）；**发出去怎么说得清**看 `notification-truthfulness.md`。
   台账 `success` 与"有产出"是两件事，不要用判 failed 代替如实描述，也不要用发消息代替留痕。
   2026-10-06 · REQ-261006165125-23a9。
2. **失败判定会下钻**：`find_result_failure` 只看含 `success`/`status` 标记键的子字典；
   子字典里别乱放这两个键，也别把缺口计数写成 `no_data`。
3. **打桩点 = 被调函数所在模块**：`runtime._run_job` 的桩必须打在 `runtime` 上，否则静默失效。
4. **交易日口径只有一个来源**：`application/services/trading_day_resolver.last_closed_trading_day`；
   调度侧的历史近似（只看 weekday）正在被补齐（REQ-261005203907-2b8c）。
5. **两套调度路径并存**：`quant.scheduler_tasks`（APScheduler）与 DailyJobs 宿主线程；
   改任务行为前先确认它走哪条路。**两边的交易日门已统一到同一份判据**
   （`application/services/trading_day_gate.py`，2026-10-06 · REQ-261006093620-a315）；
   差异只在载体：③ 用 `JobDef.trading_days_only`，② 用 `trading_day_policy` 三值列。
6. **测试期不得真实外发**：`tests/notify_guard.py` 默认 fail。
7. **策略侧的三态映射 ≠ 调度路径的记账**：`strategy_service` 会把 `skipped` 如实标出，
   但调度走的是 `application/jobs/job_protocol.result_from_dict` —— 那段只把 `failed` 判失败，
   **`skipped` 会落成 success**（2026-10-05 休市日实测）。改策略状态前先确认走哪条路
   （`v13-chain-reliability-audit.md`）。
8. **「设计写了回滚」不等于回滚可用**：归档前先确认载体在版本控制内 ——
   a7cd 的实现与文档整目录未跟踪、`tools/check_*.py` 被 `.gitignore:85` 排除，
   `git revert` 无提交可 revert（`v13-chain-reliability-audit.md` §2.2）。
9. **调度台账里 `skipped` 与 `missed` 极性相反**：`skipped`＝按日历本就不该跑（正常，**不告警**、
   不算"真执行"）；`missed`＝该跑没跑（异常，**告警**）。判漏跑用两套写出常量
   （`HANDLED_STATUSES` / `REAL_RUN_STATUSES`），**别写 `status != 'missed'`** ——
   靠副作用会在休市日把正常跳过读成"跑过"、或反过来刷出漏跑假警
   （2026-10-06 · REQ-261006093620-a315；`trading-day-freshness.md`）。
10. **「检测没跑成」不得写成「数据干净」**：异常检测（`DataValidator.detect_anomalies`）返回三态
    `ok` / `has_anomalies(True|False|None)` / `unknown_reason`；`has_anomalies is False` 只表示
    "真的检测过且没有异常"，**禁止真值判断**（`None` 也是假值）。两个必踩的坑：
    ① 迭代 `get_daily_klines()` 的返回（**polars DataFrame**）得到的是 Series，须先 `to_dicts()`；
    ② `logs/api.log` 的中文是 `\uXXXX`，**grep 中文恒为 0（假绿）**，统计要走 JSON 扫描
    （2026-10-06 · REQ-261006133733-1fdf；`data-quality-anomaly-semantics.md`）。
    现状读数：`Z-score>3` 使 **81.3%** 股票被判"有异常"，阈值重定属未决议题。
11. **常驻线程的日级判据在调用点，不在窗口函数**：编排 tick / 盘中监控两条线程的
    `_in_*_window` 只表达"时段"（含 `weekday()`），日级一律走
    `orchestrator_bootstrap._should_run_today()`（fail-open）与 `IntradayMonitor.check()` 首部的权威门；
    旁路直调 `check()` 在休市日返回 `non-trading-day`。两个运维细节：**进程重启会多一条跳过日志**
    （去噪键是内存态），**循环按线程启动对齐 60 秒节拍**（`:30` 槽位实际在 `:30:4x` 判定）。
    已知残留：`resume_from_breakpoint` 仍 fail-closed，日历覆盖断档时休市日仍会跑；
    `scheduler_tasks_runtime.handle_intraday_monitor` 会把 `skipped` 包成 `success`（接线前须先改）
    （2026-10-06 · REQ-261006130750-0654；`trading-day-freshness.md`「常驻线程侧」）。

12. **告警的分母必须先说清**：D级"806 只"、评分"86.28"、回填失败率"71.4%"可以**全是口径造的**——
    `count_by_grade_on` 数的是**行数**（同日多跑即翻倍），检查域混进了 403 只退市/长停标的
    （窗口内 0 数据）。三条纪律：**分母 = 可交易域**（判据取数据事实
    `gap = 最后一条 K 线的交易日名次 − 1`，不取失修的退市/停牌标记）、
    **计数按 distinct 标的**、**分母口径变更必须同步重定阈值**（旧 95.0 与旧口径上限 95.02 只差 0.02 分＝永久红灯）。
    另需「本期掉出可交易域」哨兵，否则新口径会把采集漏批静默豁免；取交易日要取够 5 个，
    否则 `gap 2–4` 被静默当存量（`application/services/kline_domain.py`）
    （2026-10-06 · REQ-261006163444-8e4f；`data-quality-anomaly-semantics.md` §5）。
13. **净值序列只认交易日；而交易日历是「白名单」**：`quant.simulation_equity_snapshot` 里落在
    周末/节假日的行，会**同时**污染三处——被当成交易日点算进波动率/IR/回撤/归因窗口、
    被 adjacent 配对成"假日日收益"、并让缺口判断报出假缺口（实测旧口径在同一段序列上报
    **21 个"缺失工作日"**，含国庆 10-01/10-02，进而触发无意义补跑）。
    口径唯一来源 `application/services/trading_day_gate.py`；口径实现
    `application/services/nav_series.py`（纯函数、不做 IO，交易日集合由调用方注入）；
    写入唯一闸门 `SimulationORMRepository.upsert_equity_snapshot`（非交易日不落库、返回 `None`）。
    ⚠️ **日历表只列交易日**：生产 23373 行 `is_trading_day` **全是 true、零条 false**——
    所以"非交易日"必须读成「**覆盖范围内 且 不在清单里**」，写 `is_trading_day = false`
    会匹配 **0 行**（本需求的设计初稿正是这么写的，被 dry-run 当场证伪）。
    "日历不可得"必须返回 `None` 并在返回体里显式声明（`verified=False`），**绝不用空集表达失败**
    ——那会把净值序列清空、让指标静默退化
    （2026-10-06 · REQ-261006190953-fc43；`equity-nav-trading-day-caliber.md`）。
14. **盯盘通知有四条硬契约**：① **非交易日零事件**——`tick()` 与 `run_forever` 共用
    `WatchEngine._resolve_trading_day`（默认 `TradingDayGuard`，含节假日），旁路调用也被护住，
    跳过必须留痕（否则"没开市"与"引擎没跑"不可区分）；② **名称缺失写「名称缺失」**，
    绝不回落成裸代码（`name or symbol` 是错的）；③ **级别与闭环解耦**——级别（P0..P3）决定
    卡片形态、**恒解析**，而「处置入口/回执位」等闭环承诺由 `closed_loop` 单独门控
    （旧实现把两者绑死，闭环未开时所有卡只剩一句「现价 X ≤ 阈值 Y（下破）」）；
    ④ **每次外发可归因**：`quant.notification_audit` 一通知一行 + 卡面尾注
    `v2-watch@<host>#<pid>`——因为 v2 与 agent-ts **共用同一个飞书机器人**，
    不写来源就永远分不清谁发的（`watch-notification-contract.md`）。
    （2026-10-07 · REQ-261007101318-c392）

## 4. 最近更新（每次 L1 变更追加一行）

| 日期 | 更新点 | 来源 REQ |
|---|---|---|
| 2026-10-07 | 新增认知 14「盯盘通知四条硬契约」（非交易日零事件 / 名称缺失不回落 / 级别与闭环解耦 / 外发可归因）；新建 L2 页 `watch-notification-contract.md`；补 `docs/README.md` 的架构入口段（此前 L2 页面无入口）；`quant.notification_audit` 上线（一通知一行 + 来源标识） | REQ-261007101318-c392 |
| 2026-10-05 | 新建本说明书；登记「每日任务通知如实性契约」为关键认知，并挂上架构/调度/数据访问等指针 | REQ-261005210015-1603 |
| 2026-10-06 | 登记两条关键认知（策略三态映射 ≠ 调度记账、回滚载体须在版本控制内）并挂上 L2 页 `v13-chain-reliability-audit.md` | REQ-261006010812-cd19 |
| 2026-10-06 | 交易日门统一到两条调度路径（判据 `application/services/trading_day_gate.py`）；新增认知 9「台账 `skipped` 与 `missed` 极性相反」；L2 页 `trading-day-freshness.md` 增「库表调度侧」一节 | REQ-261006093620-a315 |
| 2026-10-06 | 新增认知 10「检测没跑成 ≠ 数据干净」（异常检测三态 + polars 迭代坑 + 日志中文 grep 假绿）；L2 页 `data-quality-anomaly-semantics.md`；异常检测 100% 假阴性修复后读数变真（报错 7995→0、质量分 95.01→86.28、问题股 748→4623） | REQ-261006133733-1fdf |
| 2026-10-06 | 交易日门补齐**第 ④ 条路径**（常驻编排 tick / 盘中监控线程）：A 层循环预过滤 + B 层 `check()` 权威门，判据仍指 `trading_day_gate.py`；新增认知 11；`trading-day-freshness.md` 增「常驻线程侧」一节（含重启多一条日志、60s 节拍对齐、两条已知残留） | REQ-261006130750-0654 |

| 2026-10-06 | 新增认知 12「告警的分母必须先说清」（可交易域 / distinct 标的 / 阈值随口径重定 + 掉出域哨兵）；L2 页 `data-quality-anomaly-semantics.md` 增 §5「检查域与告警口径」；三项误报去伪：D级 806→404 只、评分 86.28→90.87、回填目标不再含退市标的 | REQ-261006163444-8e4f |
| 2026-10-06 | 每日任务通知改为「**有事才说**」：无事（`no_output=True` / `status∈{no_event,no_op}`）时开始与完成两条都不发，判据唯一入口 `daily_jobs/notify_policy.py`；开始消息改为超阈值「⏳ 仍在运行」提示；失败与人工触发不受影响；两个 env（`DAILY_JOBS_NOTIFY_NOOP` / `DAILY_JOBS_RUNNING_NOTICE_SECONDS`）可回滚。认知 1 升为两层、认知 6 补桩点陷阱；L2 页 `notification-truthfulness.md` 四条规则 → 五条 + 失败例外 + 回滚表 + 证据口径陷阱 | REQ-261006165125-23a9 |
| 2026-10-06 | 净值序列统一**交易日口径**（写入闸门 / 读取过滤 / 缺口判断 / 存量清理四层）：非交易日行写不进、读不到、不算缺口；缺口判断从 agent-dh 搬到 v2；新增认知 13「日历是白名单，缺行即非交易日」并建 L2 页 `equity-nav-trading-day-caliber.md`（含清理迁移与常驻巡检用法）。实施期被 dry-run 证伪一次设计谓词（D-6） | REQ-261006190953-fc43 |

## 5. 待写页（尚未落笔的主题）

- 数据管道（`DataPipelineService` 存在但生产未接线）的口径与接线方案；
- 盘中实时信号扫描能力缺口；
- 周度风险/组合分析链路的归属（审计已确认 `risk_check_job` 调不存在的方法且未排班，见
  `v13-chain-reliability-audit.md` §3；仍待定「修实 or 显式下线」）。
