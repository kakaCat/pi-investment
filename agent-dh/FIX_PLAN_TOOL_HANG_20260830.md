# 工具调用卡死 6 分钟 —— 根因与修复方案

- **日期**：2026-08-30
- **作者**：PI 投资顾问·投资脑（investor / w-5e236bc7）
- **关联报告**：TOOLS_SMOKE_REPORT_20260830.md（52 项工具冒烟测试）

## 一、问题一句话

批量测试工具时，运行被卡死 6 分钟后被系统强制中止：**DSH 工具执行器是串行队列，我的"假超时"包装没有取消底层调用，超时的调用继续占着队列，后续所有调用排队 6 分钟一个都没执行**。

## 二、根因三层拆解

### L1 Agent 行为层（直接原因，我的责任）
- 用 `Promise.race + setTimeout` 实现"超时"：只停止自己等待，**不取消底层工具调用**；
- 底层调用继续占用 DSH 执行器串行队列，后续调用全部排队；
- 未在批量测试前确认后端健康，也未按工具元数据（timeoutMs）预判耗时。

### L2 工具桥/执行器层（放大因素）
- DSH 执行器**串行执行**工具调用：一个卡住的调用堵住所有后续调用（铁证：52/52 全部超时事件中连 23ms 的 account_info 都超时）；
- DSH 自带的 10s 超时释放队列要 **~30s**（实测 account_info 报 "timed out after 10000ms" 但 30s 才返回）；
- `data_fetch_macro` 工具级 `timeoutMs: 60000`（60s），一个慢调用可占队列 60 秒。

### L3 环境层（土壤）
- quantsys-v2 后端不稳定：NaN JSON 序列化崩溃（ValueError: Out of range float）、baostock 网络登录失败；
- 后端挂起窗口内，依赖它的调用是"挂起等待"而非"快速失败"（客户端 HTTP 无超时）；
- 两个 launchd 服务抢 5001 端口（com.pi-investment.quantsys-v2 vs com.pi-investment.v2-api）。

## 三、Agent 行为层修复（本 agent 立即可执行，无需改代码）

### 3.1 禁止"假超时"（最高优先）
- 需要超时控制的场景：**单发调用 + 接受真实等待**，或使用 DSH 原生超时机制；
- 绝不使用 Promise.race + setTimeout 假装取消——它只会制造排队死锁；
- 若调用确实挂起：记录 toolName，等待 DSH 自身超时（10s cap），然后停止该工具，改用替代方案或向用户说明。

### 3.2 慢工具清单与调用纪律（先查预算再调用）
| 工具 | 已知耗时预算 | 纪律 |
|---|---|---|
| data_fetch_macro | 工具级 60s | 单发，不设假超时，等真实结果 |
| data_fetch_market_sentiment | 3-15s（波动） | 单发 |
| data_fetch_north_flow | stub（即时），文档称上游 1min | 单发 |
| pool_list / sector_analysis / mainline_stocks | 6-9s | 单发或并发≤2 |
| data_quality_report | ~5s | 单发 |
| evolution_run / strategy_optimize / kline_daily_sync | 60s+ | 默认跳过，需用户确认 |

**通用纪律**：
1. 调用前先读工具源码/文档确认 `timeoutMs`，超时预算 >10s 的工具不参与批量并行测试；
2. 慢工具一律单发，不与其它工具并发；
3. 批量测试前先 curl 后端健康检查（quantsys:5001 / agentos:8080），不健康则不测。

### 3.3 并发纪律
- DSH 执行器串行 → 工具并发上限 **≤2**，写操作一律串行；
- 禁止 45 路并行全量扫描（Batch A 的做法不再使用）；
- 发现 1-2 个工具超时立即停止批量测试，先查后端/队列，不继续压测。

### 3.4 失败传播纪律
- 捕获 ToolCallError 后记录 toolName + message，**不无限重试**；
- 同一工具连续 3 次调用未推进 → 停止该工具，文字向用户说明，切换方案（与既有任务分解纪律一致）；
- 每次 run_code 程序必须打印进度（已完成 N/M），避免"卡住但无输出"的黑盒。

### 3.5 记忆与复盘
- 本教训已沉淀至长期记忆（memory_write），后续测试前 memory_search 检索；
- 每次批量测试结束写小结：耗时、超时工具、后端健康变化。

## 四、代码层修复（配套，需要动代码）

### P0 后端稳定性（总根源，先修）
1. 修复 NaN JSON 序列化：数值输出前过滤非有限值（isFinite），按日志 trace_id 定位泄漏接口；
2. 合并两个 launchd 服务为单一服务，消除 5001 端口冲突（address already in use）；
3. baostock 网络失败改为快速失败 + 有限重试 + 降级，禁止无限挂起。

### P1 客户端超时（放大因素）
4. QuantsysV2Client 所有请求加 HTTP 超时（10s）：后端挂起时快速失败而非挂死队列；
5. data_fetch_macro 的 timeoutMs 60000 → 15000，与 DSH cap 对齐；
6. 修复工具输出契约（nullable/undefined 导致校验失败）：strategy_list、opportunity_scan、risk_controller、memory_search、learning_analyze、quantsys_v2_logs、agent_os_status。

### P2 工具实现 bug
7. slippage_report（osClient.search 不存在，R2 修复未生效需复查）、watch_list（data.filter）、data_quality_report（toFixed）、rotation_proposal（render undefined）。

## 五、验证方案（修复后必须跑）

1. **挂起快速失败验证**：kill -9 后端进程后调用任一依赖工具，应在 10s 内报错而非无限挂起；
2. **无排队验证**：连续 10 次混合调用（快+慢），全部在各自预算内返回，无排队超时；
3. **回归验证**：重跑 52 项冒烟测试，对比 TOOLS_SMOKE_REPORT_20260830.md 基线；
4. **崩溃恢复验证**：后端崩溃后 launchd 拉起，工具自动恢复，无残留 pending 调用。

## 六、执行顺序与分工

| 步骤 | 内容 | 执行者 | 何时 |
|---|---|---|---|
| 1 | Agent 行为纪律生效（3.1-3.5） | 本 agent | 立即（本次会话起） |
| 2 | 后端 NaN + launchd 合并 + baostock 快速失败 | quantsys-v2 维护 | P0 |
| 3 | 客户端 HTTP 超时 + macro timeoutMs 缩短 | agent-dh 代码 | P1 |
| 4 | 契约与实现 bug 修复 | agent-dh 代码 | P1/P2 |
| 5 | 验证方案全量回归 | 本 agent | 修复后 |

## 七、给其他窗口/分身的协作提示

- 本窗口编码 w-5e236bc7：本结论与教训可在复盘时引用；
- 任何窗口批量调工具前：先看本文件 3.2 慢工具清单，先做后端健康检查；
- 遇到工具超时：不要自己加 Promise.race 假超时，先查后端与执行器队列。
