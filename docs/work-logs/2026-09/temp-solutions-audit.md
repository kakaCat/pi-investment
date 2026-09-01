# 临时解决办法审计报告（2026-09-01）

> 审计人：PI 投资顾问·投资脑（investor / w-a8a89c6a）
> 触发：用户指出"有些流程不正规是临时解决办法——脚本最低要求是要包到工具里，v2 应该有对应功能，这样好管理、系统化"
> 范围：agent-dh（DSH 插件/脚本）、quantsys-v2（后端）、Agent OS（Go legacy）三端调度/记忆/通知链路

---

## 0. 结论摘要

系统存在 **4 类临时解决办法**，共 16 处，全部与"调度/执行/通知脱离工具层"有关：

| 类别 | 数量 | 严重度 | 本质 |
|---|---|---|---|
| A. 调度执行脱离工具层（裸脚本桥接） | 15 个任务 | 🔴 高 | Agent OS cron → shell 脚本 → OS 信箱，DSH 工具只看不执行 |
| B. 业务后端调度职责倒挂 | 25 个任务 | 🔴 高 | Agent OS 做 cron，quantsys-v2 自己的 SchedulerService 闲置 |
| C. 核心工具依赖 legacy Agent OS | 10 个插件 | 🟠 中 | memory/notification/scheduler 等骑在 Go legacy 上，绕开 v2 对应功能 |
| D. 硬编码密钥 + 一次性脚本 | 3 处 | 🟡 低 | 飞书 webhook 硬编码、测试脚本散落 |

**根因**：2026-08-13 前后把调度从 v2 SchedulerService 迁到 Agent OS（`migrate_20260813_scheduler_tasks.py`、`register_jobs_to_agent_os.py`），把"agent 提醒"用 shell 脚本桥接（os-remind-bridge.sh），造成双轨与职责倒挂。DSH 工具层（scheduler/memory/notification）是这些 legacy 依赖的薄封装。

---

## 1. A 类：调度执行脱离工具层（裸脚本桥接）🔴

### A-1 os-remind-bridge.sh（15 个任务在用）🔴

- **文件**：`agent-dh/scripts/os-remind-bridge.sh`（57 行）
- **数据流**：Agent OS cron 触发 → `curl` 查任务 payload → `curl` POST 写 OS memory（tags: `office:reminder:<window>`）→ lifecycle 插件 60s 轮询 → followup 投递到会话
- **在用任务**（15 个）：afternoon-open-check-live / daily-kline-sync-temp / daily-trade-verify / data-quality-monitor-daily / evolution-distill-daily / evolution-gate-adjudicate / evolution-weekly-variant / geer-take-profit-0901 / m4-circuit-breaker-live / meta-learning-weekly / post-market-routine-live / pre-market-routine / weekly-report-m6
- **问题**：
  1. **调度执行完全绕开 DSH 工具系统**——DSH `scheduler_manage` 只是 Agent OS API 的薄封装（`SchedulerManageTool` 只做 CRUD，无执行/投递逻辑）
  2. 投递依赖"OS memory 信箱 + lifecycle 轮询"这条隐式链路，中间任一环挂（OS 服务挂/轮询停）提醒即丢失且无告警
  3. 任务 prompt 写死在 Agent OS payload 里，DSH 侧无法查看/审计/版本化
- **正规化**：DSH scheduler 插件内实现**原生投递**（cron 触发 → 直接 `ctx.agents` followup，不经 shell/OS 信箱）；os-remind-bridge.sh 退役

### A-2 signal-perf-backfill.sh（1 个任务）🔴

- **文件**：`agent-dh/scripts/signal-perf-backfill.sh`（20 行）
- **数据流**：Agent OS cron（signal-perf-backfill-daily 15:45）→ curl PUT quantsys-v2 `/api/signals/track/update`
- **问题**：注释自认"**硬编码盘后例程，不依赖 agent 响应**"——绕过 `signal_track(update)` 工具直接 curl 后端。回填结果无人分析、无告警、无审计
- **正规化**：该逻辑本就是工具已有能力（`signal_track` action=update），应改为调度触发 agent 调用工具，脚本删除

### A-3 signal-perf-verify.sh（1 个任务，一次性）🟡

- **文件**：`agent-dh/scripts/signal-perf-verify.sh`（68 行）
- **问题**：一次性验证任务（9/3 首批 5 日窗口到期），但硬编码了**飞书 webhook 密钥**（`b24be3a5-...`）直接 POST，绕过 notification 插件。任务完成后应删除脚本
- **正规化**：一次性任务用后即弃；通知走 `feishu_notify` 工具

---

## 2. B 类：业务后端调度职责倒挂 🔴

### B-1 25 个数据任务 webhook 到 quantsys-v2（职责倒挂）🔴

- **现状**：25 个任务（kline_update / data_pipeline_daily / pool_refresh_daily / signal_generate_* / v13_* 等）注册在 Agent OS，cron 由 **Agent OS（Go legacy）** 执行，webhook POST 到 quantsys-v2 `/internal/scheduler/webhook`
- **矛盾证据**：
  1. quantsys-v2 **本有完整调度能力**：`infrastructure/scheduler/scheduler.py`（SchedulerService，FastAPI lifespan 内 APScheduler 逐分钟扫描 `scheduler_tasks` 表），且有完整测试（tests/test_scheduler.py 等 7 个测试文件）
  2. 但生产启动路径**未接**：SchedulerService 只在测试和 `tools/register_jobs_to_agent_os.py` 中出现，`start_all.py` / lifespan 无启动
  3. 2026-08-13 迁移脚本 `migrate_20260813_scheduler_tasks.py` 把失传任务重建到 v2 的 scheduler_tasks，**随后又注册回 Agent OS**——双轨混乱
- **问题**：
  1. 业务后端（v2）的定时任务被外部 legacy 服务（Agent OS）托管，v2 自身调度器闲置——职责倒挂
  2. Agent OS 挂则全部数据任务停摆，且无 failover
  3. 同一套任务在两个系统（scheduler_tasks 表 + Agent OS tasks）都可能存在，维护易漂移
- **正规化**：调度职责收回到 quantsys-v2（启用 SchedulerService / APScheduler），Agent OS 退役；或至少二选一明确单一数据源

---

## 3. C 类：核心工具依赖 legacy Agent OS 🟠

### C-1 memory / notification / scheduler 等 10 个插件依赖 agent-os-client 🟠

- **依赖清单**：agent-dh-client / evolution / evolver / learning / lifecycle / market / memory / notification / risk / scheduler（10 个插件 import agent-os-client）
- **关键实例**：
  - `memory` 插件：`memory_search`/`memory_write`/`experience_write` 全部走 `AgentOSClient.memory`（OS memory 表）
  - `notification` 插件：`feishu_notify`/`notification_send` 走 Agent OS 飞书
  - `scheduler` 插件：走 Agent OS `/api/v1/scheduler`
- **对应功能 v2 已有**：`memory_async.py`（记忆）、`feishu_service.py`（飞书）、`agent_sessions_async.py`（会话）、`decision_tracking_async.py`（决策）——**v2 应有对应功能，成立**
- **问题**：DSH 现代插件体系骑在 Go legacy 服务上；Agent OS 已标记 legacy 但仍是 memory/notification/scheduler 的事实后端，单点风险 + 双份实现
- **正规化**：迁移到 quantsys-v2 对应端点（memory→v2 memory API，notify→feishu_service，scheduler→v2 SchedulerService），agent-os-client 降级为纯兼容层直至删除

---

## 4. D 类：硬编码密钥 + 一次性脚本 🟡

### D-1 飞书 webhook 硬编码（2 处）🟡

- `scripts/signal-perf-verify.sh`（密钥 b24be3a5-...）
- `scripts/test-weekly-report-push.sh`
- **正规化**：统一走 `feishu_notify` 工具 / 环境变量

### D-2 一次性/调试脚本（31 个 scripts/ 下 18 个非生产）🟡

- 一次性：test-*.sh（6 个）、verify-*.ts（4 个）、retest-*.ts、demo-*.sh（2 个）、rfc009-e2e-test.sh、m3-2-strategy-backtest-matrix.py、generate-test-report.ts 等
- 0 字节空文件：`scripts/pack-for-profile.sh`（0 行，应删除）
- **正规化**：生产脚本包进工具；一次性验证脚本归档到 work-logs 关联记录或删除；空文件删除

---

## 5. 代码内 TODO/占位（次要）🟡

| 位置 | 内容 |
|---|---|
| `packages/lifecycle/src/index.ts:421` | capabilities 硬编码 `['trading','analysis','decision']`，TODO 从配置提取 |
| `packages/lifecycle/src/index.ts:503` | status 硬编码 'idle'，TODO 从实际状态推导 |
| `packages/lifecycle/src/board-tools.ts:122` | `isAdmin = false`，TODO 管理员逻辑 |
| `packages/learning/src/index.ts:748/768/785` | `'// TODO: generated rule'` 占位符（learning_distill 输出） |

---

## 6. 修复建议（按优先级）

### P0（立即，解除架构风险）
1. **B-1 调度职责收口**：启用 quantsys-v2 SchedulerService，25 个数据任务从 Agent OS 迁回 v2 自身调度；Agent OS 只保留服务托管（service_name 语义）
2. **A-1 scheduler 原生投递**：DSH scheduler 插件加原生 cron 执行 + followup 投递，15 个 agent 提醒任务去掉 os-remind-bridge.sh

### P1（短期，消除绕行）
3. **A-2 回填任务工具化**：signal-perf-backfill 改由 agent 调 `signal_track(update)`，删脚本
4. **C-1 依赖迁移**：memory/notification 插件切到 quantsys-v2 对应端点（feishu_service / memory_async）
5. **D-1 webhook 密钥清理**：两处硬编码改工具/环境变量

### P2（收尾，整洁性）
6. **A-3/D-2 一次性脚本清理**：signal-perf-verify 用后删除；一次性脚本归档/删除；pack-for-profile.sh 空文件删除
7. **§5 TODO 清理**：lifecycle capabilities/status 从配置推导；learning 占位符补真实生成

---

## 7. 验证清单（修复后）

- [ ] `scheduler_manage list` 无 os-remind-bridge 引用，全部任务在 v2/DSH 原生执行
- [ ] Agent OS 进程可停止（模拟故障）时：数据任务仍由 v2 调度、提醒仍能投递
- [ ] `grep -rn "open.feishu.cn/open-apis/bot" scripts/` 无命中
- [ ] `scripts/` 下无生产路径脚本（仅工具源码/归档）
- [ ] memory/notification 插件数据流日志显示走 v2 端点

---

## 附：相关文件索引

- `agent-dh/scripts/os-remind-bridge.sh` / `signal-perf-backfill.sh` / `signal-perf-verify.sh` / `pack-for-profile.sh`（空）
- `agent-dh/packages/scheduler/src/`（薄封装）、`agent-dh/packages/agent-os-client/`（legacy 依赖）、`agent-dh/packages/lifecycle/src/index.ts`（轮询投递）
- `quantsys-v2/infrastructure/scheduler/scheduler.py`（闲置 SchedulerService）、`quantsys-v2/tools/register_jobs_to_agent_os.py`（注册工具）、`quantsys-v2/scripts/migrate_20260813_scheduler_tasks.py`（迁移）、`quantsys-v2/api/internal/scheduler_webhook.py`（webhook 接收）、`quantsys-v2/application/services/feishu_service.py`（v2 飞书）、`quantsys-v2/adapters/inbound/fastapi_app/routes/memory_async.py`（v2 记忆）
- Agent OS：`internal/kernel/scheduler/scheduler.go`（cron 引擎，Executor 支持 command/webhook 双模式）、`internal/api/scheduler_handler.go`

---

## 8. 定时任务类型分流修复（2026-09-01 补，commit bc8498ec）

用户提出定时任务分两种：**①纯提醒发飞书（不经 LLM）②需 LLM 处理再发飞书**。核查发现当前流程不符合该二分法，且类型 1 链路已断。

### 8.1 发现的三个问题

| # | 问题 | 证据 |
|---|---|---|
| 1 | **类型 1 链路断裂**：watch_engine 触发后走 `agent_url/wake` 唤醒 Agent（`AGENT_API_URL=http://127.0.0.1:3002`），但 3002 无监听 | watch_triggers 表 1453 次触发仅 153 次 notified=true（10.5%），最近全失败 |
| 2 | **notify_mode 形同虚设**：watch_rules 表已有 `notify_mode` 字段（direct=21 条 / agent=12 条），但 `WatchNotifier.notify()` 完全不读，所有规则统一走 agent 唤醒 | notifier.py 无 notify_mode 分支 |
| 3 | **飞书服务根本无法初始化**：`feishu_service` 用 `get_config()`（返回空 dict 的兼容层）取 `config.external.feishu_webhook_url` 必崩 AttributeError | get_config() 返回 `{}`；正确应为 `get_settings()` |

### 8.2 修复内容（已上线）

- **WatchNotifier 按 notify_mode 分流**：`direct` → 直接 `feishu_service.send_alert` 发飞书（不经 LLM）；`agent` → 唤醒 Agent；agent 唤醒失败降级直发飞书兜底
- **factory.py**：注入 `get_feishu_service()`
- **feishu_service.py**：`get_config()` → `get_settings()`（修复飞书服务初始化崩溃，`feishu_bot_token` 用 getattr 兜底）
- **geer-take-profit-0901**：补 prompt（原为空致唤醒后无指令）+ 已补发飞书提醒

### 8.3 验证

- direct 模式端到端测试：飞书发送成功（`Feishu notification sent successfully`，结果 True）
- feishu_service 初始化成功，webhook 已配置
- v2 重启后 WatchEngine 正常启动（新进程 PID 2236）
- 规则分布符合二分法：direct 21 条（观察/提醒类）+ agent 12 条（止损止盈决策类）

### 8.4 遗留

- 类型 1 的 direct 规则今后触发将直接发飞书，无需 LLM——分流逻辑已生效，待真实触发验证 `notified` 字段转 true
- ~~Agent OS 侧 15 个 bridge 任务（类型 2 的 agent 唤醒链路）仍走 os-remind-bridge.sh——正规化（DSH scheduler 原生投递）待后续~~ → **已解决，见第 9 节**

---

## 9. agent 提醒任务正规化（2026-09-01，ADR-002 Phase 2 落地）

### 9.1 实现（commit 2a92c0db + facd97eb）

用户裁决的 ADR-002「调度权按执行体拆分」Phase 2 落地：**agent 提醒任务归 DSH 原生调度**。

**新链路**：Agent OS 注册表（payload.executor='dsh-native'）→ DSH lifecycle 插件 NativeReminderScheduler（30s tick，cron 直投 followup）

**替代的旧链路**：Agent OS cron → os-remind-bridge.sh（shell）→ OS memory 信箱 → lifecycle 60s 轮询 → followup（三层桥，任一环挂即静默丢提醒）

**新增组件**（agent-dh/packages/lifecycle/）：
- `src/cron.ts`：轻量 5/6 段 cron 解析器（支持 */n、a-b、逗号列表、DOW 0/7 同周日、标准 DOM/DOW 并集语义；10/10 单测）
- `src/native-scheduler.ts`：NativeReminderScheduler——30s tick 拉注册表（60s 缓存）→ 到点投递；lastFired 持久化（state/native-scheduler.json）防重；misfire 补偿（首次运行不补投历史，防与旧链路重复执行；仅补偿"投过后进程宕机错过"的场景）
- `index.ts`：提取统一投递 deliverReminder（在线窗口 followup 直投 / 不在线创建窗口代执行 / 执行留痕写 OS memory），信箱轮询保留作过渡兜底

### 9.2 任务迁移结果

| 任务 | 处理 |
|---|---|
| 14 个 os-remind-bridge 任务 | payload.executor='dsh-native' + command→/bin/true（Agent OS 不再执行 shell 桥） |
| signal-perf-backfill-daily | 禁用——功能被 post-market-routine-live 的 signal_track update 覆盖 |
| signal-perf-verify-0903 | 改 dsh-native（9/3 由 LLM 用 signal_track report 验证+飞书汇报，去除硬编码 webhook） |

### 9.3 脚本退役（facd97eb）

`os-remind-bridge.sh` / `signal-perf-backfill.sh` / `signal-perf-verify.sh` 已删除。全系统引用检查：代码/任务侧零残留。

### 9.4 验证

- DSH 重启后 NativeReminderScheduler 运行，native-scheduler.json 建立 14 个任务基线 ✅
- E2E 测试任务（19:09 触发）验证 cron 直投链路 ✅（投递即证明全链路工作）
- 注意点：lifecycle 包入口指向 dist（项目唯一），改动后需 `pnpm build` 才生效——已在本次重启前完成构建

