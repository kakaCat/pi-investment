# 工具验证测试报告 Round 4（复测 + 修复确认）

- **验证日期**：2026-08-30（周日，非交易时段）
- **复测窗口**：PI 投资顾问·投资脑（角色 ID: investor，窗口: **w-61513086**）
- **原报告**：Round 1-3 由窗口 w-dbc62ffa 出具（同文件，2026-08-30）
- **背景**：用户指示"问题修复了，重新测试之前失败的工具，测试完后更新数据"。本报告为对旧报告失败/待验证项的**复测结论 + 本轮新修复记录**。
- **验证方法**：
  1. **新鲜进程 harness**（21 项）：用 tsx 直接 import 各工具源码（agent-dh packages）+ 重建后的 quantsys-v2-client dist，走 `execute → snapshotJsonValue → validateJsonSchemaValue → render` 完整链路（dsh-session/dsh-tools 官方校验），验证的是**落盘代码**而非当前会话内存。
  2. **Live SDK 写路径 roundtrip**：通过 run_code 真实调用当前会话 SDK 工具（watch 创建/删除、memory、experience、signal_track、交易类拒绝路径）。
  3. 高危系统操作（self_restart / self_finalize / agent_os_restart / quantsys_v2_restart）**未执行**；genome_* 6 个因 SDK 未暴露**无法调用**。
- **数据源**：Agent OS (localhost:8080) + quantsys-v2 后端 (localhost:5001)

## 一、Round 4 复测总览

| 分类 | 数量 | 说明 |
|---|---|---|
| ✅ 通过 | **20/21** | 新鲜进程 harness：execute+snapshot+schema 校验+render 全链路通过 |
| ⚠️ 外部依赖 | **1** | kline_daily_sync：baostock 登录被拒（黑名单 10001011），数据源级故障，非代码 bug |
| ✅ 写路径 | **7/7** | watch_manage 创建/删除、memory_write/search、experience_write、signal_track.record、portfolio_trade 周末拒绝、algo_execute 拆单计划、rotation_execute 校验拒绝 |
| ⛔ 未执行 | **10** | 4 个高危系统操作 + 6 个 genome_*（SDK 未暴露） |

**结论：复测 21 项中 20 项通过（95%）；唯一未通过项为外部数据源故障。旧报告 10 个 ❌ 中 9 个确认已修复，1 个（kline_daily_sync）转 ⚠️ 外部依赖。本轮另发现并修复 4 个新 bug。**

## 二、逐项复测结果（21 项 harness）

| 工具 | 旧状态 | 复测结果 | 说明 |
|---|---|---|---|
| risk_controller.position_size | ✅(R2 修复) | ✅ | accountValue 100000 / recommendedSize 20000，snapshot+schema OK |
| risk_controller.stop_loss | ✅(R2 修复) | ✅ | entryPrice 1292.3，snapshot+schema OK |
| risk_controller.portfolio_risk | ✅(R2 修复) | ✅ | **本轮修复**：此前输出含 `symbol: undefined` 顶层键 → DSH snapshotJsonValue 拒绝整个值（"value must be an object"）。修复后 total_holdings 3 / checks 3 项 / risk_level low，snapshot viol=0 |
| factor_calculate | ❌(因子过期) | ✅ | 600519 贵州茅台 current_price 1292.3，因子完整返回 |
| factor_analyze | ✅(已修复) | ✅ | icMean -0.024，sampleSize 50，status ok |
| data_quality_report | ⚠️待验证 | ✅ | overall_score 92.5，missing_data/delayed_data 为空 |
| rotation_proposal | ❌(语法错误) | ✅ | market_style growth，style_confidence 0.47，正常返回 |
| rotation_simulate | ❌(依赖挂) | ✅ | simulation feasible=true，expected_positions=[]，cash_required=0 |
| agent_os_logs | ❌(日志文件不存在) | ✅ | 返回真实日志行（主服务日志） |
| strategy_list | ✅(R3 修复) | ✅ | total 152，id=178 value-macd-cross-v1 |
| data_fetch_financial | ✅ | ✅ | 600519：营收 922.78 亿 / 净利 445.17 亿 / ROE 17.72% / 毛利率 89.56% |
| competition_analysis | ❌(userRender) | ✅ | 公司名/行业/竞争对手结构完整，snapshot OK |
| learning_distill | ❌(非 lossless) | ✅ | success=true，rules=[]，snapshot OK（lossless 问题已消） |
| learning_apply | ❌(工具执行失败) | ✅ | 规则缺失被干净拒绝："规则 R-001 不存在"（dry_run 路径正常） |
| risk_barra_decomposition | ✅(已修复) | ✅ | total_risk 0 / 因子结构正常返回 |
| self_status | ❌(isClean) | ✅ | running，repo_clean true（lifecycle git.ts isClean 修复已生效） |
| quantsys_v2_status | ❌(userRender) | ✅ | running / db_connected / holdings_count 3 |
| memory_search | ❌(非 lossless) | ✅ | results=[] total=0，snapshot OK |
| data_fetch_macro | ✅(已修复) | ✅ | indicator=pmi 正常返回；**本轮追加修复**：akshare.get_macro_data NaN 清洗（见四-5） |
| evolution_run.propose | ❌(id 类型) | ✅ | 返回 uuid + strategy_id 178，schema 校验通过 |
| kline_daily_sync | ⚠️待验证 | ⚠️ | **外部依赖故障**：baostock 登录返回 `10001011 黑名单用户`（数据源封禁，非代码问题）。工具修复已生效：能精确上报"0/0 成功，1 失败（失败标的: 600519）+ 后端消息"而非笼统报错 |

## 三、写路径 roundtrip（7/7 通过）

| 项目 | 结果 | 说明 |
|---|---|---|
| watch_manage create→delete | ✅ | **本轮修复**：fresh 进程验证 create 返回 rule_id=75 → delete "规则已删除"。残留测试规则 72/73/74 已清理 |
| memory_write + memory_search | ✅ | 写入成功，search total=1 |
| experience_write | ✅ | success=true |
| signal_track.record | ✅ | 信号 ID 16（600519 C 级）已记录 |
| portfolio_trade BUY（周末） | ✅ 合规拒绝 | "非交易日（周末）禁止下单"——交易宪法时段约束正确执行 |
| algo_execute（TWAP 拆单） | ✅ | **本轮修复**：返回 algo_order_id=algo_20260830_xxx / total_quantity=100 / 3 个拆分子单，snapshot OK |
| rotation_execute | ✅ 校验拒绝 | 空 proposals 被正确拒绝（"proposals 必须是非空数组"），未真实调仓 |

## 四、本轮新修复（4 个，均经新鲜进程验证）

| # | 文件 | 问题 | 修复 |
|---|---|---|---|
| 1 | packages/risk/src/tools/RiskControllerTool/RiskControllerTool.ts | portfolio_risk 输出顶层含 `symbol: undefined` 键 → DSH snapshotJsonValue 拒绝整个输出（"value must be an object"），表现为偶发"读取 slice 失败"（实为 JSON.stringify(undefined)） | 整个 out 再过 sanitizeLossless，删除 undefined 键 |
| 2 | packages/core-tool/src/lossless.ts | sanitizeLossless 漏处理：`-0` 原样通过、Array.map 保留稀疏数组空洞 → snapshotJsonValue 拒绝（lossless 边界：拒绝 negative-zero / sparse） | `-0`→0；稀疏数组显式压实（`i in value` 判断） |
| 3 | packages/intelligence/src/tools/WatchManageTool/WatchManageTool.ts | ① 输出含 undefined 键（rule_id/data 可能缺失）→ lossless 拒绝；② rule_id 未从后端 `{rule:{id}}` 包装取出（unwrap 只剥一层 data） | 整体 sanitizeLossless + `rid = result?.rule?.id ?? result?.id ?? result?.rule_id` |
| 4 | quantsys-v2-client/src/client.ts + src/types.ts（dist 已重建） | algo_execute 契约断裂：请求传 duration 但后端读 duration_minutes；运行版后端返回 camelCase（orderId/parentQuantity/childOrders/executionStats）而契约声明 snake_case（algo_order_id/total_quantity/slices）→ AlgoExecuteTool.wrap 永远报"缺少必需字段" | 请求透传 duration_minutes；响应做 camelCase/snake_case 双向兼容映射 |

### 附 5：data_fetch_macro 后端 NaN 修复（本轮）

quantsys-v2/adapters/outbound/datasources/providers/market/akshare.py `get_macro_data`：新增 `_sanitize_records()`（NaN float → None），应用于 gdp/cpi/pmi 的 to_dict 输出。修复前 FastAPI 序列化报 "Out of range float values are not JSON compliant: nan"（路由 500）。已重启后端验证：`GET /api/market/macro` → success:true。

## 五、遗留问题

1. **kline_daily_sync 外部依赖**：baostock 登录被数据源封禁（黑名单 10001011，非代码问题）。路由/事件循环/错误透传修复均已生效；待数据源解封或更换数据源后重测。
2. **当前会话需重启生效**：TS 侧修复（risk/watch/algo/lossless）已落盘并通过新鲜进程验证，但**当前 GUI 会话加载的是会话启动时的构建**，live registry 中 watch_manage 仍报旧 lossless 错误；重启会话后生效（Python 后端修复已即时重启生效；quantsys-v2-client dist 已重建）。未在本会话执行 self_restart（⛔ 高危）。
3. **后端 algo 模拟器不拦截交易时段**：`POST /api/orders/algo-execute` 直接生成拆单计划，无交易时段校验（工具层 portfolio_trade 有拦截）。建议后端补充与 portfolio_trade 一致的时段/仓位校验（待办）。
4. **evolution_run 输出**：propose 模式返回 uuid（id 字段），schema 校验通过；full 模式未测（耗时长）。
5. **data_manager** 未纳入本轮 21 项清单（上轮代码审计确认正确），建议会话重启后补一次真实调用。

## 六、测试副作用（残留数据，请清理）

| 数据 | 位置 | 状态 |
|---|---|---|
| 测试记忆 1 条（"工具验证临时记录 20260830"） | Agent OS 记忆库（namespace=default） | 已写入，待清理 |
| 测试经验 1 条（600519 neutral 验证条目） | Agent OS 记忆库（experience） | 已写入，待清理 |
| 测试信号 1 条（signal ID 16，600519 C 级） | signal_track | 已记录，待清理 |
| 测试盯盘规则（fresh 验证 id 75） | watch_list | **已自清理** ✅（create→delete 闭环） |
| 测试盯盘规则 id 72/73/74（上轮+本轮 curl 残留） | watch_list | **已删除** ✅ |
| 测试通知（飞书 reports 渠道） | feishu | 复测结束后发送（见七） |

## 七、结论

- 旧报告 **10 个 ❌**：9 个确认已修复（rotation_proposal/rotation_simulate/evolution_run/learning_distill/learning_apply/self_status/memory_search/factor_calculate/quantsys_v2_status/competition_analysis 中的 9 项），kline_daily_sync 转 ⚠️ 外部依赖。
- 旧报告 **5 个 ⚠️待验证**：data_quality_report/kline_daily_sync/agent_os_logs 已实测；quantsys_v2_logs/agent_os_status nullable 上轮已确认非 bug。
- 本轮新发现并修复 **4 个真 bug**（portfolio_risk lossless、sanitizeLossless 加固、watch_manage 契约、algo_execute 契约映射）+ 1 个后端 NaN 序列化（data_fetch_macro）。
- **复测通过率 20/21（95%）**；唯一未通过为外部数据源（baostock 黑名单），无工具代码层面失败。

---

*报告窗口：w-61513086（Round 4 复测）；原报告：w-dbc62ffa（Round 1-3）。*


---

# 附录：Round 5 复测（核心工具基座恢复 + 全量 23 项冒烟）

- **验证日期**：2026-08-30（周日，非交易时段）
- **复测窗口**：PI 投资顾问·投资脑（角色 ID: investor，窗口: **w-b41f1ff0**）
- **背景**：Round 4 之后，core-tool 基座增强（render 默认注入、错误提取、lossless 导出）在会话丢失中一度回退（BaseTool.ts/index.ts 恢复为 HEAD，ToolDependencies/ToolRegistry 文件遗失），9 个已修工具因 `import { sanitizeLossless } from '@pi-investment/core-tool'` 缺失导出而无法加载。本轮**恢复基座并全量复测**，同时补齐 Round 4 未覆盖的 6 项（opportunity_scan / slippage_report / watch_list / data_manager_status / data_fetch_market_sentiment / data_fetch_north_flow）。
- **验证方法**：23 项新鲜进程 harness（`scripts/verify-smoke-20260830-r5.ts`），tsx 直接 import 工具源码，走 `tool.call() → toDSHToolDefinition().execute() → snapshotJsonValue(lossless) → validateJsonSchemaValue(schema) → output.render()` 全链路；慢工具（macro/sentiment/north_flow/evolution）单次执行 + 独立进程预算保护。

## Round 5 结果总览

| 指标 | 结果 |
|---|---|
| ✅ 通过 | **23/23（100%）** |
| ❌ 失败 | 0 |
| ⚠️ 外部依赖 | 0（本轮清单内全部通过；kline_daily_sync 仍为 baostock 外部故障，见 Round 4） |

## 本轮恢复/修复（2 项，均经 23 项 harness 验证）

| # | 文件 | 问题 | 修复 |
|---|---|---|---|
| 1 | packages/core-tool/src/index.ts | 会话恢复后丢失 `sanitizeLossless/toSnake` 导出 → 9 个工具（risk/learning/intelligence/factor/investment/competition/evolution）import 即崩溃 | 恢复 `export { sanitizeLossless, toSnake } from './lossless'` |
| 2 | packages/core-tool/src/BaseTool.ts | `toDSHToolDefinition()` 丢失 render 默认注入与错误提取 → 7 个无 render 的 prompt（quantsys_v2_logs/agent_os_status/data_quality_report/factor_analyze/data_manager/factor_calculate/agent_os_logs）在 DSH render 阶段失败 | 恢复：output.render 缺失时默认 `[{type:'text',text:JSON.stringify(data,null,2)}]`；错误提取兼容 string/{issue}/{error:{issue}} |

**说明**：ToolDependencies.ts / ToolRegistry.ts / SharedDependencyFactory.ts（DI 容器半成品）在会话丢失中遗失；全仓 grep 确认**无任何工具引用**（依赖注入仍为可选阶段），暂不重建，已在 TOOLS_REFACTOR_TRACKER.md 记录待办。

## 逐项结果（23/23 PASS，含 Round 4 未覆盖项）

| 工具 | 结果 | 说明 |
|---|---|---|
| strategy_list | ✅ | total 152，id=178 value-macd-cross-v1 |
| opportunity_scan | ✅ | **Round 4 未覆盖**：2.5s 返回 opportunities+scan_summary，结构完整 |
| risk_controller.position_size | ✅ | accountValue 100000 / recommendedSize 20000 |
| learning_analyze | ✅ | stub 返回混合类型 suggestions（'建议一'/123/null/对象）→ 全部字符串化，无 lossless 崩溃 |
| quantsys_v2_logs | ✅ | 真实日志行（AkShare 连接错误等） |
| agent_os_status | ✅ | **确认健康端点 /health → 200**（探测 /api/health 等为 404，配置默认值正确） |
| memory_search | ✅ | results+total=3 结构完整（搜索词命中 3 条） |
| slippage_report | ✅ | **Round 4 未覆盖**：total_fills 0 / avg/max 0 / by_symbol []，snapshot OK |
| watch_list | ✅ | **Round 4 未覆盖**：返回 id=71 规则（600519 price_break 2000） |
| data_quality_report | ✅ | overall_score 92.5，missing/delayed 为空 |
| rotation_proposal | ✅ | market_style growth / style_confidence 0.47 |
| factor_analyze | ✅ | rsi icMean -0.024 / sampleSize 50 |
| risk_barra_decomposition | ✅ | total_risk 0 / 因子结构完整 |
| data_manager_status | ✅ | **Round 4 未覆盖**：后端 running / 数据库已连接 / 持仓数 3 |
| data_fetch_financial | ✅ | 600519：营收 922.78 亿 / 净利 445.17 亿 / ROE 17.72% |
| factor_calculate | ✅ | 600519 贵州茅台 current_price 1292.3 |
| agent_os_logs | ✅ | 主服务真实日志行 |
| learning_apply | ✅ | stub 含 undefined 键 → sanitizeLossless 正确删除（impact 仅保留 count） |
| data_fetch_macro | ✅ | indicator=pmi 14.5s 正常返回（后端 NaN 修复持续生效） |
| data_fetch_market_sentiment | ✅ | **Round 4 未覆盖**：extreme_greed / fear_greed_index 100 |
| data_fetch_north_flow | ✅ | **Round 4 未覆盖**：days=5 结构完整（当日无数据，数据源问题非代码） |
| rotation_simulate | ✅ | feasible=true / expected_positions=[]（合法空方案） |
| evolution_run.propose | ✅ | 48ms 返回 uuid + strategy_id 178 + status completed |

## 结论

- **23/23 通过（100%）**，为当前所有冒烟清单项的最完整通过记录。
- 恢复基座后 9 个依赖 lossless 的工具全部可加载；7 个无 render 的 prompt 全部可渲染。
- 会话丢失教训已落实：**本次所有改动立即 git 提交**，防止再次回退。


---

# 附录：Round 6（重启工具实测 + quantsys_v2_restart launchd 兼容修复）

- **验证日期**：2026-08-30（周日，非交易时段）
- **验证窗口**：PI 投资顾问·投资脑（角色 ID: investor，窗口: **w-b41f1ff0**）
- **背景**：用户授权实测两个此前标为 🔴 未实测（高危）的重启工具。实测发现 quantsys_v2_restart 存在真实 bug 并修复。
- **验证方法**：新鲜进程 harness（`scripts/verify-restart-tools-r6.ts`），直接 import 工具源码，真实执行重启（非 dry-run），走 `tool.call() → toDSHToolDefinition().execute() → snapshotJsonValue → validateJsonSchemaValue → output.render()` 全链路；结束后 curl 健康端点 + lsof 确认服务恢复。

## 发现并修复的 bug（1 项）

| 项 | 详情 |
|---|---|
| **quantsys_v2_restart 误报失败** | v2-api 由 launchd 托管（com.pi-investment.v2-api，KeepAlive 自动拉起）。旧 kill+spawn 流程在 kill 后等待端口释放，但 launchd 立即拉起新进程 → 端口「永不释放」→ 工具误判 `Port 5001 still occupied after stop` 返回失败（实测 PID 63128→5783 即被 launchd 拉起）。**修复**：改为 launchctl kickstart -k 权威重启（原子 kill+重拉），launchd 不可用才回退旧 kill+spawn 流程；QuantsysV2Config 与插件 Config 新增 `launchdLabel`（默认 com.pi-investment.v2-api）。agent_os_restart 已于 2026-08-28 采用同款 kickstart 模式，无需改动 |

## Round 6 结果总览

| 指标 | 结果 |
|---|---|
| ✅ 通过 | **3/3（100%）** |
| 重启工具 | quantsys_v2_restart（12.7s）、agent_os_restart（11.2s）均走 launchd_kickstart 路径 |
| 服务恢复 | :5001 PID 6951→8507、:8080 PID 7594→9159，健康检查均 OK（db_connected true / agent-os /health 200） |
| 当前会话链路 | 重启后 agent_os_status / quantsys_v2_status / memory_search 均正常（agent-os 重启不影响 agent 进程） |

## 逐项结果（3/3 PASS）

| 项 | 结果 | 说明 |
|---|---|---|
| quantsys_v2_restart | ✅ | steps: launchd_kickstart(com.pi-investment.v2-api) → health_check ready after 2s；final_status running pid 8507 / port_listening / health_ok |
| agent_os_restart | ✅ | steps: launchd_kickstart(com.pi-investment.agent-os) → health_check ready after 1s；final_status running pid 9159 / port_listening / health_ok |
| post_restart_health | ✅ | :5001 /api/health {"status":"ok","db_connected":true}；:8080 /health {"status":"ok"} |

## 遗留

- 本轮为真实重启实测：**两次重启均真实发生并恢复**；当前会话工具链（agent-os/quantsys 客户端）在重启后立即可用。
- tracker 中 quantsys_v2_restart / agent_os_restart 已由 🔴 未实测（高危）更新为 🟢 全链路（R6）。仍剩 🔴：self_restart / self_finalize（会退出当前 agent 进程，无法自测）、strategy_optimize、learning_track、notification_send、genome_*（SDK 未暴露）。

---

## Round 7：self_restart「重启后 session 丢失」根因修复（2026-08-31）

### 背景
用户反馈：self_restart 需要重新打包插件（改 src 后必须 pnpm build，插件从 dist 加载），但真实重启后会话丢失。排查确认两条根因 + 一个前提缺口。

### 根因 1：重启后整实例起不来（dist 打包 dead）——「session 全丢」的直接原因
- 上次真实重启（2026-08-30T05:33:54Z）restart-result.json 状态 dead；启动日志：
  Cannot find package '@pi-investment/core-tool' imported from .../packages/lifecycle/dist/index.mjs（ERR_MODULE_NOT_FOUND，rollback 也失败）。
- 机制：lifecycle 等插件 dist 产物保留了 import from "@pi-investment/core-tool"（tsdown 默认 external），而 profile 的 node_modules 里 21/22 个 @pi-investment 包都有 link，唯独 core-tool 缺失（profile package.json dependencies 漏声明）→ 启动即 dead，agent 永不恢复 → 用户视角「session 全部丢失」。
- 修复：profile package.json（运行时 ~/.dsh/profiles/investment/package.json + 源模板 agent-dh/profiles/investment/package.json）补充 "@pi-investment/core-tool": "link:.../packages/core-tool" 并 pnpm install 建立链接（core-tool 入口为 TS 源码，tsx 加载器可直接加载）。

### 根因 2：续跑消息无法回投发起会话（即使启动成功，发起窗口也接不到恢复消息）
- SelfRestartTool.execute(args, _context) 丢弃了 DSH 传入的 exec 上下文（caller agent / session id）；BaseTool.toDSHToolDefinition 的 execute 第二参 _exec 被忽略。
- scheduleRestart 写 pending-resume.json 时不写 origin_agent_id（只有 reason/base_branch/resume_task/attempt）→ 重启后 setupResume 永远走兜底分支（投 investor 根 agent），发起窗口无法接收续跑消息。
- 修复（3 处，commit dd3e7b46）：
  1. core-tool/src/BaseTool.ts：call(args, external?) 合并外部上下文；DSH execute 把 exec 透传进 ToolContext（exec.agent.id === session id，dsh-agent 语义确认）；
  2. lifecycle/.../SelfRestartTool.ts：execute 从 context.exec?.agent?.id 取发起会话 id 传入 scheduleRestart；
  3. lifecycle/src/index.ts：scheduleRestart(reason, preserveContext, originAgentId?) 将 origin_agent_id 写入 pending → setupResume 分支①/② 可精确回投发起会话（30 分钟窗口内等 agent/created 匹配，超时兜底 investor root）。

### 验证
| 项 | 结果 | 说明 |
|---|---|---|
| pnpm build 全量 | 通过 | agent-dh 全包构建成功（lifecycle dist 含 origin_agent_id ×2、exec?.agent?.id） |
| core-tool 链接 | 通过 | ~/.dsh/profiles/investment/node_modules/@pi-investment/core-tool → agent-dh/packages/core-tool |
| 临时实例启动（:13099 + 隔离 DSH_HOME） | 通过 | HTTP 200、进程存活、日志无 ERR_MODULE_NOT_FOUND / failed to import；验证后已清理 |
| dist 含新逻辑 | 通过 | lifecycle/dist/index.mjs 含 origin_agent_id 写入与 exec 透传 |

### 遗留
- 真实 self_restart E2E 仍不宜本会话自测（会杀死当前 :13080 进程）；且 :13080 当前无 launchd/supervisor 兜底（dsh-doctor 是否覆盖 13080 未确认），重启后需要 restart-with-build.sh 或人工拉起。本轮修复保证两个前提成立：① 重启后能正常启动（不再 dead）；② 启动后 setupResume 能把续跑消息回投发起会话。
- 建议后续：为 :13080 配置 launchd KeepAlive（或确认 dsh-doctor 覆盖），再安排真实 self_restart 全链路验证。
