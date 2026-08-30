# 工具全量冒烟测试报告（52 项实测）

- **测试时间**：2026-08-30 20:20-20:31
- **测试人**：PI 投资顾问·投资脑（investor / w-5e236bc7）
- **方法**：run_code 真实调用 SDK 工具；每调用独立超时（10-15s，超时即中断）；并发 2；写操作只走参数校验路径（不真实成交、不发送真实消息）
- **测试环境**：Agent OS :8080 正常；quantsys-v2 :5001（测试期间崩溃过 1 次，launchd 已自动拉起）

## 一、总览

| 结论 | 数量 |
|---|---|
| 稳定可用 | 27 |
| 预期正确拒绝（校验正常，非 bug） | 3 |
| 有 bug / 不可用 | 18 |
| 超时不稳（曾通过，复测挂起） | 3 |
| 未测试（高危/重/写操作/框架工具） | 另列 |

## 二、稳定可用（27 个）

account_info、position_list、trade_monitor、trade_verify、m4_circuit_breaker_check、data_fetch_quote、data_fetch_kline、pool_list、screening、market_style_detect、sector_analysis、chip_analysis、mainline_stocks、risk_metrics、regime_position_limit、evolution_leaderboard、market_alert、signal_track(report)、quantsys_v2_status、self_status、competition_analysis、notification_channels、scheduler_manage(list)、board_read、regime_daily、mainline_scan、strategy_execute

**使用注意**：
- trade_verify 报 2 条持仓勾稽异常（601288/002241 账面≠成交净额）——数据一致性问题，非工具 bug
- chip_analysis 返回全 0（avg_cost/profit_ratio 等）——疑似数据降级，不可直接用于决策
- screening 结果含退市股等脏数据（如"退市观典"）
- competition_analysis 返回"待实现" stub，无实际分析能力
- mainline_stocks 字段多为 null；pool_list 较慢（约 8.7s）

## 三、预期正确拒绝（3 个，校验逻辑正常）

| 工具 | 入参 | 返回 |
|---|---|---|
| portfolio_trade | quantity=50 | 拒绝"必须是100的整数倍" |
| algo_execute | quantity=0 | 拒绝"必填参数" |
| rotation_execute | proposals=[] | 拒绝"必须是非空数组" |

## 四、有 bug / 不可用（18 个）

### A 类：SDK 输出契约 / schema 校验失败（7）
| 工具 | 错误 |
|---|---|
| strategy_list | items[8/10].description 必须为 string（后端返回 null） |
| opportunity_scan | 输出必须为 object（返回非对象） |
| risk_controller | 输出非 lossless JSON（含 undefined） |
| learning_analyze | suggestions 元素必须为 string |
| quantsys_v2_logs | _metadata.warning 必须为 string（null） |
| agent_os_status | health_error 必须为 string（null） |
| memory_search | 输出非 lossless JSON（含 undefined） |

### B 类：工具实现 bug（4）
| 工具 | 错误 |
|---|---|
| slippage_report | this.osClient.search is not a function（修复未生效/回归） |
| watch_list | data.filter is not a function |
| data_quality_report | Cannot read properties of undefined (reading 'toFixed') |
| rotation_proposal | render 读 total_buy 时 undefined |

### C 类：后端 bug / 接口失败（3）
| 工具 | 错误 |
|---|---|
| factor_analyze | HTTP 500: StockORMRepository 无 get_all_stocks |
| risk_barra_decomposition | API request failed: getBarraDecomposition |
| data_manager(status) | 工具执行失败 |

### D 类：数据 / 环境（4）
| 工具 | 错误 |
|---|---|
| data_fetch_financial | 未获取到财务数据（曾正常，疑数据源/参数） |
| factor_calculate | momentum_6m 因子过期 12 天，拒绝服务（需回补） |
| agent_os_logs | 日志文件不存在（实际日志为 agent-os.log） |
| learning_apply(dry_run) | 工具执行失败（规则缺失或 bug，未定性） |

## 五、超时不稳（3 个，曾通过）

| 工具 | 首轮 | 本轮 | 判断 |
|---|---|---|---|
| data_fetch_macro(pmi) | 报参数错（未传参） | 10s 超时 | 接口慢/后端不稳 |
| data_fetch_market_sentiment | 3.6s 通过 | 15s 超时 | 后端性能问题 |
| data_fetch_north_flow | 3.6s 通过 | 15s 超时 | 后端性能问题（上游本身慢） |

补充复测因后端挂起卡死 6 分钟被中断——需后端稳定后复测定性。

## 六、未测试项及原因

| 类别 | 工具 | 原因 |
|---|---|---|
| 高危操作 | self_restart / self_finalize / agent_os_restart / quantsys_v2_restart | 会中断会话或共享服务，禁止测试 |
| 重/长操作 | evolution_run / strategy_optimize / kline_daily_sync | 60s+/全市场同步 |
| 写操作 | memory_write / experience_write / learning_track / feishu_notify / notification_send / board_post / board_update / signal_track(record/update) / scheduler_manage(非 list) / data_manager(非 status) | 会真实写入/发消息 |
| 写路径待完成 | watch_manage | 补充测试中 create 调用卡死中断，结果未知 |
| SDK 未暴露 | genome_*（6 个） | 当前 agent 未挂载 genome 插件 |
| 框架内建工具 | bash/read/write/edit/glob/grep/str_replace_editor/read_image/web_search/ask_user_question/create_goal/get_goal/update_goal/exit_plan_mode/interrupt_agent/job_kill/job_list/job_output/send_message/subagent/subagent_fork/list_agents/ralph/workflow/skill/todo_write（25 个） | Harness 自带，本会话正常使用 |

## 七、测试过程中的重大发现

1. **quantsys-v2 后端崩溃**：测试期间 :5001 崩溃，launchd 自动拉起。日志根因：ValueError: Out of range float values are not JSON compliant: nan（某接口返回 NaN）+ baostock 网络登录失败。**这是"工具总不好使"的最大外部原因——后端不稳定，前端工具全跟着超时**。
2. **两个 launchd 服务并存**：com.pi-investment.quantsys-v2 与 com.pi-investment.v2-api 同时存在，日志有 address already in use 冲突，建议合并。
3. **工具桥卡死连锁**：后端一挂，所有依赖它的工具（含部分 Agent OS 工具）排队超时；bash 等本地工具不受影响。恢复后端即可恢复。

## 八、修复优先级建议

1. **P0（后端稳定性）**：修复 NaN JSON 序列化；合并重复 launchd 服务；恢复因子数据管道（factor_calculate 过期 12 天）
2. **P1（契约/实现 bug，13 个）**：strategy_list、opportunity_scan、risk_controller、learning_analyze、quantsys_v2_logs、agent_os_status、memory_search、slippage_report、watch_list、data_quality_report、rotation_proposal、factor_analyze、risk_barra_decomposition
3. **P2（数据/环境，4 个）**：data_fetch_financial、agent_os_logs 路径、learning_apply 定性、trade_verify 勾稽异常
4. **P3（复测）**：data_fetch_macro / market_sentiment / north_flow 待后端稳定后复测；watch_manage 写路径补测

---

## 九、2026-08-30 21:00 重测结果（服务重启后）

**方法**：串行逐个调用，不用假超时；后端 quantsys:200 / agentos:200（uvicorn PID 45084→72126，20:48 重启确认）。

### 修复进展：3/23 有改善，19 个代码 bug 全部未修

| 工具 | 修复前 | 重测 | 状态 |
|---|---|---|---|
| data_fetch_market_sentiment | 15s 超时 | OK 2.6s | **已恢复**（原为队列阻塞假象） |
| data_fetch_north_flow | 15s 超时 | OK 2ms（stub） | **已恢复**（原为队列阻塞假象） |
| data_fetch_macro | 10s 超时 | FAIL 28s，HTTP 500 ValueError | 超时→明确后端 bug（有进展但未修） |
| strategy_list / opportunity_scan / risk_controller×2 / learning_analyze / quantsys_v2_logs / agent_os_status / memory_search | 契约错 | 同样的契约错 | **未修** |
| slippage_report / watch_list / data_quality_report / rotation_proposal | 实现错 | 同样的实现错 | **未修** |
| factor_analyze / risk_barra_decomposition / data_manager(status) | 后端错 | 同样的后端错 | **未修** |
| data_fetch_financial / factor_calculate / agent_os_logs / learning_apply | 数据/环境 | 同样 | **未修** |
| watch_manage create/delete | 未测（卡死） | FAIL 输出非 lossless JSON | **新确认：写路径也挂** |

### 重测结论

1. **后端重启只恢复了稳定性**（sentiment/north_flow 恢复、无排队卡死），**代码层 19 个 bug 一个未修**——失败清单当前全部仍然失败；
2. **新暴露**：GET /api/market/macro 后端 500（ValueError，ExceptionGroup 包装）——data_fetch_macro 从"超时"变成可定位的后端错误；
3. **新确认**：watch_manage 写路径（create）输出非 lossless JSON，契约问题；
4. **DSH 超时机制澄清**：DSH 尊重工具声明的 timeoutMs（macro=60s 可跑 28s），"tool call timed out after 10000ms" 出现在工具声明 10s 或队列阻塞时——修复方案中"缩短 macro timeoutMs"依然成立。

### 待修清单（未变，见第四节）

A 类契约 7 + B 类实现 4 + C 类后端 3 + D 类数据/环境 4 + macro 后端 500 + watch_manage 契约 = **20 个待修点**。

