# 实施期与设计文档的偏离登记（REQ-261006190953-fc43）

规则：设计文档已确认，**不回头私改**；实施中出现的偏离一律记在这里，并在验收材料里逐条引用。
判据：偏离是否改变**对外契约**。不改契约的偏离照做并记账；改契约的必须退回设计重新批准。

---

## DEV-1 · `filter_trading_days` 的日期取值器命名（不改变契约）

- **卡**：t-7c5daa（子卡 t-8c1870 复核段发现）
- **设计原文**（`design/interfaces.md` §2）：`date_of: Callable[[Any], date] = _snapshot_date`
- **实现**：`date_of: Callable[[Any], Optional[date]] = _row_date`
- **差异**：占位名不同；返回值从 `date` 放宽为 `Optional[date]`（认不出日期的行按"不可判定"保留）
- **为什么不改回**：`date` 断言会让"日期不可解析"的行直接崩掉，而净值表理论上允许脏日期；
  保留语义（认不出 → 保留一行）比崩掉安全。
- **契约影响**：无。调用方只传 `rows` / `trading_days`，`date_of` 是可选覆盖点。

## DEV-2 · `nav_coverage.trading_day_source` 的取值来源（不改变契约，语义更准）

- **卡**：t-7c5daa（子卡 t-8c1870 复核段发现）
- **设计原文**（`design/interfaces.md` §2）：`trading_day_source` 「来自 verdict_info 的 source」
- **实现**：引用 `trading_day_guard.SOURCE_CALENDAR` / `SOURCE_UNAVAILABLE` 常量
- **差异**：`verdict_info()` 描述的是**今天**这一天的判定来源（它内部就调 `TradingDayGuard.check(now)`）；
  而 `nav_coverage` 覆盖的是**历史区间**，用当日 verdict 填区间口径等于把两个语义混起来。
- **实现取值**：有日历时 `'trading-calendar'`；无日历（None）时 `'unavailable'`。
  **与设计的词表完全一致**（都是 `TradingDayGuard` 的既有来源常量），未发明新值。
- **契约影响**：无。字段名、类型、可能取值集合都不变；只是不再由"当日判定"冒充"区间来源"。

---

## DEV-3 · 既有测试 `test_equity_snapshot_upsert` 隐含假设"今天一定是交易日"（测试侧，已修）

- **卡**：t-8c7962（子卡研发段实测发现）
- **现象**：闸门一上线，`tests/test_multi_account_domain.py::TestRepository::test_equity_snapshot_upsert`
  当场变红（`assert 0 == 1`）。日志给出原因：
  `skip_daily_write_non_trading_day ... day=2026-10-06 source=trading-calendar-holiday`。
- **根因不在闸门**：该用例调 `upsert_equity_snapshot(...)` **不传 `snapshot_date`**（取"今天"），
  于是它的结果随日历漂移——**每逢周末/节假日必红**，此前只是没人在休市日跑它。
- **处置**：扩该文件**既有的** autouse 夹具 `_fixed_trading_clock`（它本就声明"交易判定不是本文件
  测试目标，统一注入常真日历"），补一格把按日落库的门也注入"常真"。
  **没有**改成 `force=True` 散落在用例里（那会把"绕过门"混进正常测试代码），也**没有**动生产代码。
- **未改**：用例断言的语义（同日 upsert 不产生第二条）逐字不变。
- **排查范围**：把所有写快照的测试面跑了一遍（`test_multi_account_domain` / `test_oversell_guard` /
  `test_account_trading_service_v2` / `test_simulation_repo_status` / `test_pending_orders` /
  `test_trade_cash_race` / `test_equity_snapshot_daily_return` / 两个新文件 / `test_risk_metrics_service`
  = **160 passed, 1 skipped**），**只有这一处**受新契约影响。

## DEV-4 · `calculate_daily_return` 内部新增了对 `nav_series` 的懒加载依赖（签名不变）

- **卡**：t-8c7962（子卡 t-d41793 复核段发现）
- **设计原文**（`design/interfaces.md` §3）：「`calculate_daily_return` / `recompute_account_max_drawdown`
  **签名不变**，内部改走交易日口径（`previous_valid_snapshot(trading_days=...)`）」。
- **实现**：签名确实未变（仍是 `(account_name, day, total_value)`），但在方法体内
  `from application.services.nav_series import trading_day_set` 取日历，再透传给基准。
- **为什么会这样**：设计要"签名不变"又要"内部走交易日口径"，那日历只能由方法自己解析。
  替代方案（让四个调用方各自传 `trading_days`）与卡约束「不对计划外的调用方做破坏性改动」冲突。
- **代价（已登记，不是没看见）**：仓储层因此**运行时**依赖 application 层。
  缓解：模块级不 import（懒加载），与 `strategy_repository.py:592` 的既有做法一致；
  真要在架构上消除，需要把日历集合提升为仓储的构造注入——那是一次跨四调用方的改造，不属本需求。
- **契约影响**：无（对外签名与返回类型不变）。

## DEV-5 · `trading_day_set` 从 nav_series 迁到日历仓储（口径不变，位置变了）

- **卡**：t-0ae23e 联调段（子代理报回分层棘轮红灯后定位）
- **设计原文**（`design/interfaces.md` §2）：`trading_day_set` 是 `nav_series` 的四个导出之一。
- **实现**：搬到 `adapters/outbound/repositories/trading_calendar_repository.py`
  （与 `list_trading_days` 同处，adapters 层），`nav_series` 变成**纯口径模块**（零 IO、不 import 任何上层）。
- **为什么必须改**：`nav_series`（application）import 仓储（adapters）是**方向倒置**，
  被 `tests/test_layer_purity.py` 的棘轮计为新增违规；而"日历读取"本来就是读一张表，
  本该留在仓储层。改完顺带把该文件从违规名单里摘掉（棘轮 −1）。
- **契约影响**：函数名、签名、返回语义（不可得→None）逐字不变；只是 import 路径变了。
  卡 A 的验收 ① 仍成立（测试已同步改 import 位置）。
- **连带**：`simulation_repository.calculate_daily_return` 改为从**同层**的日历仓储取集合，
  该处违规随之消失。

## DEV-6 · 回填计数虚高：闸门拒写的日子被算成「已写」（卡 C 范围内一并修）

- **卡**：t-0ae23e（子代理复核时报出，属卡 B 引入的回归）
- **现象**：`DailySnapshotService.backfill_account` 无条件 `written += 1`，
  而仓储在非交易日会**拒写并返回 None** → 回填回执把被拒的日子算作"已写"，数字虚高。
- **处置**：只在实际落库（返回值非 None）时计入 `written`，被拒计入新增的 `refused`，
  并写进返回值与日志。行为可观察、可复核。
- **为什么在本卡修**：它是"写入入口接线"的直接后果（卡 B 加了门，卡 C 负责把门的结论带出来），
  留成"另开卡"会让运维回填长期给出假回执。

## DEV-7 · 卡 D 多改一个文件：`adapters/inbound/fastapi_app/shared.py`（纯新增）

- **卡**：t-39a044
- **设计原文**：只列了两个路由文件（`design/interfaces.md` §5/§6）。
- **实现**：在 inbound 共享层新增纯函数 `nav_window_and_coverage(...)`，两个端点共用。
- **为什么**：`window` 五字段 + `nav_coverage` 的组装必须两端点一致，放两处拷贝必然漂移。
  口径本身仍 100% 来自未改动的 `nav_series`（该函数只做拼装，不含任何判定）。
- **契约影响**：无（新增内部函数，不改任何对外行为）。

## DEV-8 · 新键用 snake_case，与既有驼峰键在同一 payload 内并存（**设计选择，已刻意**）

- **卡**：t-39a044
- **现象**：`api_response` 会把 `data` 递归驼峰化，而设计文档 §5/§6 字面写的是
  `window.trading_days` / `nav_coverage.missing_trading_days` 等蛇形键。
- **实现**：两块按**设计字面**用 snake_case 注入（既有键 `returnsSource`/`navPoints`/… 不受影响，逐键回归已过）。
- **代价**：同一响应里两种命名风格并存——这是"与已批准的设计文档字面对齐"
  优先于"与既有驼峰风格一致"的结果。
- **影响下游**：卡 E（agent-dh）按**蛇形**消费这两块，与设计文档一致。
- **若要改回驼峰**：改动点只在注入的两行 + `shared.py` 的键名 + 卡 E 的字段名，属可控变更，
  但需要走设计变更（当前设计文档是蛇形）。

## DEV-9 · `filtered_non_trading` 的精确口径（设计只给了字段名，卡 D 定死并注释）

- **卡**：t-39a044
- **口径**：**同一 `limit` 的未过滤快照行中、因落在非交易日而被剔除的行数**；
  日历不可得时**恒为 0**（没过滤过，不是"没有脏行"）。
- **为什么需要定死**：同一名字至少有三种可能读法（窗口内被剔除数 / 全表脏行数 / 本次查询剔除数），
  不定死就会各写各的。
- **契约影响**：字段语义明确化；卡 E 与验收单引用此口径。

## DEV-10 · 卡 D 修掉一个新增代码引入的缺陷（正面发现）

- **现象**：`POST /api/risk/metrics` 在**显式 `returns` 口径**下，`window`/`nav_coverage` 变量未赋值
  → `UnboundLocalError` → 端点 500。被既有回归 `tests/migration/test_analysis_parity.py` 当场抓住。
- **归因**：该初始化缺失由卡 D 的新增代码引入（非存量），已修并补
  `test_explicit_returns_path_unchanged` 锁死该路径。
- **教训**：新增字段时要先处理"这条口径下字段根本不存在"的分支——否则新增即 500。

## DEV-11 · 删除谓词从「显式 false」改为「白名单语义」（**裁定 D-6**，改的是设计本身）

- **卡**：t-5c9a67（子代理按设计实现后，实测发现设计前提错误）
- **设计原文**（`design/data-model.md` §3，**已按 D-6 修订**）：删除只用 `is_trading_day = false`，`null` 一律不动。
- **实测推翻**：生产 `quant.trading_calendar` **23373 行全是 true、零条 false**——
  它是白名单（只列交易日，缺行即非交易日）。旧谓词匹配 **0 行**，`--expect 35` 永不成立 →
  按设计实现**一行脏数据都清不掉**（子代理如实报出并拒绝自行改口径，处置正确）。
- **现行口径**（用户裁定 D-6）：非交易日 = **覆盖范围内**（`min~max(trade_date)`）**且不在清单里**；
  防误删由覆盖范围承担（范围外一律不动）。
- **落点**：迁移脚本 `_non_trading()` 为唯一谓词实现（五处 SQL 共用）；
  `requirement.md` 记 D-6（含"确认戳无法覆盖"的说明）；`design/data-model.md` §3 带修订标记。
- **效果**：生产 dry-run 命中 **35 行**（原为 0）、库内零改动；`--apply` 后判据归零才成立。
- **连带**：卡 F 的测试夹具随之改写（哨兵从"2030 + 显式 false 日历行"改为"自造覆盖窗口 + 窗口内缺行"），
  验收 ② 由"缺行不动"反转为"**窗口外**不动"。

## DEV-12 · 巡检器的「违规 / warn」两分按 D-6 重定义（卡 G 的 ③ 被反转）

- **卡**：t-6f1c29
- **卡面原文**：违规 = `is_trading_day is false` 的行；「日历缺行的日期按 warn 单列、不计入违规」。
- **D-6 之后**：白名单语义下**日历缺行恰恰就是违规**，③ 的原语义**整条反转**。现定义：
  - **违规** = 覆盖范围 `min~max(trade_date)` **内** 且不在交易日清单里 → 退出码 2；
  - **warn** = 覆盖范围**外**的行（日历没铺到）→ 单列提示、不计违规（承担"防误判"）；
  - **判不了**（日历空表/连不上/查询异常）→ 退出码 3，**绝不报成"干净"**。
- **同源保证**：巡检器与迁移脚本用的是**同一份**白名单谓词，避免"清理用一套、巡检用另一套"。
- **活性证据（造脏行才认）**：`tests/test_check_nontrading_equity_snapshots.py` 6 passed；
  生产实跑 = 35 行违规 / 退出码 2；测试库（日历空表）= 退出码 3。

## DEV-13 · 失真注释的订正文字里**不能出现**那个标记名（卡面判据是 grep == 0）

- **卡**：t-6f1c29 验收 ⑤：`grep -c is_synthetic application/services/trading_day_guard.py == 0`。
- **第一版订正**为说清"删了什么"，把原字面量引在注释里 → 自己把判据绊红。
- **处置**：**改文字、不放松判据**（判据的意图是对的：文件里不得再出现该失真声明）。
  现订正文字表述为「已标记某个合成标记列、并从统计口径排除」+ 实测既无该列也无引用，
  事实完整保留、字面量归零。

## DEV-14 · 卡 E 在 agent-dh 侧的四处实现选择（均为可测性/兼容，不改变对外语义）

- **卡**：t-1974b4
- ① **把 `buildNavCoverage` 抽成纯函数并导出**：原 `probeNavCoverage` 是 private + 内联 `fetch`，
  不引网络桩就无法断言"原样透出"。纯函数与线上探测走同一条代码路径（探测只负责取 body）。
- ② **`probeNavCoverage` 去掉 `navPoints` 形参**：该参数只服务于被删掉的"尾部切片自算"链路；
  窗口端点/点数一律取 v2 的 `points/from/to`，避免又出现"两侧各切一次"。
- ③ **保留并重算 `impact` 字段**：它不在 v2 返回里，但旧输出有该键，删掉会让下游读不到；
  以 `{...nc, impact}` 附加，**不覆盖** v2 的任何键。
- ④ **v2 非 2xx / 请求失败也返回 `verified:false`**（旧实现返回 `null`）：与"缺字段"同一诚实口径，
  basis 分别写明原因。卡面只规定了"未返回该字段"，这条是**同向扩展**（绝不能回退 weekday 自算）。

## R-5 · 端到端「透出」分支要等 v2 重启才成立（**部署动作，需人放行**）

- **实测**：线上 5001 此刻跑的是**未重启的旧版**——`GET /api/simulation/performance?account_name=agent_virtual`
  的 `data` 只有 `equity_curve/initial_capital/current_value/cumulative_return/max_drawdown`，
  **没有** `window` / `nav_coverage`（卡 D 的源码在工作区，但进程没换）。
- **含义**：卡 E 的"① 原样透出"目前只能桩测（已与 v2 源码契约对齐）；
  线上现在走的是"② v2 未提供 nav_coverage → 如实声明未做交易日校验"这条分支（**行为正确、不误报**）。
- **为什么不由本窗口顺手重启**：本工作区里还有**其他需求在飞**的未提交改动
  （例如 `should_have_run.py` / `trading_day_resolver.py`）。重启 API 会把它们一并投上生产，
  那是**跨需求的部署决定**，必须由人放行。→ 已列入验收材料待办。

## R-6 · 旧口径的误报规模（量出来了，作为缺陷严重性的存档）

- 用线上 60 点序列（2026-06-22→2026-10-02）跑**旧** agent-dh 口径：报 **21 个"缺失工作日"**，
  其中包含 2026-10-01/10-02 这类国庆休市日 —— 即"报告里的缺口"有相当一部分根本不是缺口。

## DEV-15 · 跨仓卡的任务汇报：改动文件必须写成 `../<兄弟仓>/...`

- **卡**：t-1974b4（子卡 t-d1ea93 关任务时被凭证门拦下）
- **现象**：`reqboard_task_report(files_changed=['agent-dh/packages/...'])` 回报成功，但
  `reqboard_task_move(to=done)` 被拒：`REQBOARD_SUBTASK_GATE：改动文件不存在或 mtime 早于链出身`。
- **根因**：凭证门按**工作区根（quantsys-v2）相对路径**校验文件存在性与 mtime，而卡 E 改的全在
  兄弟仓 `agent-dh`，`agent-dh/...` 在 quantsys-v2 下不存在。
- **解法（已验证）**：写成 **`../agent-dh/packages/...`** —— 解析后指向真实文件，门通过。
- **给后续跨仓卡的结论**：改动文件一律用 `../<兄弟仓>/...` 登记，别用"仓名开头"的相对路径。

## R-7 · agent-dh 的两处**预存**失败/错误（与卡 E 无关，已用 stash 对照取证）

- `apps/web/tests/plugin-schema.smoke.test.ts`：插件构造 5000ms 超时 → 该文件 1 failed / 20 passed。
  把卡 E 的 3 个文件 `git stash` 后重跑**同样失败** → 预存问题。
- `packages/tools/risk/src/tools/RiskMetricsTool/prompt.ts` 的 output schema 里
  `additionalProperties` 写了两次 → TS1117；`git show HEAD` 确认基线即如此。
  全仓 `npx tsc --noEmit` 本就大量红，本卡**未新增**任何类型错误。

## R-1 · `source='future'` 也会被闸门拒写（当前无实际触发路径，登记备查）

- **实测**：`TradingDayGuard.check()` 对**任何未来日期**返回
  `is_trading_day=False, source='future', degraded=False`（含 2026-10-13~12-31 这些日历里明确
  标为交易日的日期）。
- **后果**：闸门 `skip_non_trading_day` 因此会拒写"快照日期在未来"的写入。
- **为什么现在不构成故障**：净值快照的四个写入方**都写"今天"**——
  `take_daily_snapshot()` / `_snapshot_one(target_date=今天)` / 成交事务 / 补跑脚本，
  实测无一传递未来日期。
- **为什么仍要登记**：将来若有人写"为次日预置快照"或"补跑次日"，会被**静默跳过**（只留一行日志）。
  真出现时，本风险条目是第一条线索。**不要**把 `source='future'` 改判为降级来"修"它——
  未来日期本来就无法标记市值，拒写是对的；要修的是那个写入方。

## R-2 · `tools/snapshot_daily.py` 仍自带第二套交易日判据（卡外小径，登记备查）

- **实测**：该脚本用"当日 `600519` 有没有 K 线"当交易日代理判据（早于卡 A 就存在）。
- **现状不构成故障**：它与门**同向**（都拦非交易日），且它放行时门仍会兜住（服务返回
  `written=0/refused=n`，退出码 0，不会误报失败）。
- **为什么要登记**：本需求的口径是"交易日历唯一真源、禁止第二套判据"，这条属未清理的残留。
  它的正确修法是改成调日历（或直接删掉这一层防护，交给门），但那会牵动 `tools/` 下的
  运维入口语义——**不属本需求的验收面**，留给后续卡。

## R-3 · `take_daily_snapshot` 新增了一种返回形状（下游契约待 agent 侧确认）

- **变化**：非交易日不再返回绩效 dict，而是返回 `{'skipped': True, 'reason', 'trading_day_source', 'trading_day'}`。
- **Python 侧已核对**：`daily_orchestrator._phase_post_market` 只把它透传进 `daily_review` 事件，
  Python 侧不取键，orchestrator 自身不读 → 未见破缺。
- **未确认**：agent 侧（提示词/工具）对 `daily_snapshot` 新形状的容错程度。**硬取 `nav` 的下游需容错**。

## R-4 · 分层棘轮（`tests/test_layer_purity.py`）当前是红的 —— 归因已逐文件查实（**不是本需求单独造成**）

- **实测**：`total=320 > TOTAL_BASELINE=318`（新增 2 处）。
- **逐文件归因**（方法：对工作区每个改动文件，分别扫描"工作区内容"与"HEAD 内容"的违规数并求差）：

| 文件 | 工作区 − HEAD | 归属 |
|---|---|---|
| `application/services/should_have_run.py` | **+3** | **不是本需求**（同族需求 `REQ-261006093620-a315` 的在飞改动） |
| `application/services/trading_day_resolver.py` | **+2** | **不是本需求**（同上） |
| `adapters/outbound/repositories/simulation_repository.py` | **+1**（原 +2，经 DEV-5 后降为 +1） | 本需求（卡 B） |
| `application/services/nav_series.py` | 0（原 +1，经 DEV-5 归零） | 本需求（卡 A，已修） |

- **净账**：在飞合计 +8、同期清理 −4 ⇒ 相对基线 +4；本需求占 **+1**，其余 +1 由他人在飞改动贡献。
- **本需求这 1 处的性质**：`adapters/outbound → application.services.trading_day_gate`。
  它是**结构性代价**，不是疏忽：FR-2 要求"闸门设在被调函数层、不可绕过"，
  而 outbound 层调 application 在本仓方向规则下必被计为倒置。
  替代方案（由组合根注入回调、仓储默认 None）会**重新打开"漏加门"的洞**——
  正是本需求要修的缺陷，故明确否决。
- **处置**：**不动基线**。理由：① 本仓规则「不做看到红就调基线」；
  ② 即便把基线调到 319，总数仍是 320，红灯不会消失（另 +1 属他人）；
  ③ 调基线等于替他人未完成的工作背书。**移交**：`should_have_run.py` / `trading_day_resolver.py`
  两条属 `REQ-261006093620-a315` 的范围，应由该窗口一并核对/入账。
