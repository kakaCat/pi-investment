---
title: 盯盘引擎 V2 · 后端专项设计
status: draft
owner: 用户（PI Investment）
reviewers: agent
prd: docs/requirements/REQ-261022235419-2299/requirement.md
serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-11
created: 2026-10-23
updated: 2026-10-23
---

# 盯盘引擎 V2 · 后端专项设计  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-11

## 摘要  serves: FR-1, FR-2

- **问题**：后端引擎侧要把「宿主接入、取价性能、并发与事务、调度挂载」定死。
- **方案**：V2 引擎作为 FastAPI lifespan 的独立后台线程接入；取价按 symbol 去重 + 熔断隔离；仓储读写沿用 scoped_session + 只读事务收尾。
- **影响面**：adapters/inbound/fastapi_app  lifespan 一处接入点；v2 子包全新建。

## 背景与问题  serves: FR-1, FR-2

### 需求来源  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-11

| 需求编号 | 原始诉求 | 本设计如何回应 |
|---|---|---|
| FR-1 | 「查所有激活的盯盘规则数据」 | 引擎线程每拍 list_by_state('active') |
| FR-2 | 「查盯盘股票实时数据」 | 统一取价前置 + symbol 去重 |
| FR-3 | 「持仓一个文件、非持仓一个文件」 | 引擎内分流到两模块 |
| FR-4/FR-5 | 持仓/非持仓判定 | 两引擎模块职责 |
| FR-6 | 「作废范围」 | 失效扫描挂在取价后 |
| FR-7 | 「10次一个循环」 | 路由状态机由引擎驱动 |
| FR-11 | 「每日定时任务」 | 挂 DailyJobs 宿主线程 |

### 现状与代价  serves: FR-2

V1 曾因 daemon 未拉起导致盯盘静默消失一周（2026-08-02 事故）；引擎唯一宿主=FastAPI 5001 lifespan 是已立契约。

### 为什么是现在  serves: FR-1

V2 引擎的宿主要约必须在设计阶段定死，否则实施期会再引入新的宿主路径。

## 目标与非目标  serves: FR-1, FR-2

### 目标  serves: FR-1, FR-2

- V2 引擎唯一宿主 = FastAPI 5001 lifespan（与 V1 同契约）
- 取价性能：单拍取价耗时可控（symbol 去重 + 熔断隔离）
- 事务卫生：每拍 close_session 收尾，无 idle in transaction

### 非目标  serves: FR-1

- 不改调度架构（APSchedulerService / DailyJobs / launchd 不动）
- 不加新对外端口
- 不引入新数据库

## 方案总览  serves: FR-1, FR-2

**一句话方案**：V2 引擎类（WatchEngineV2）由 lifespan 起独立后台线程，与 V1 并存；每日重置任务挂 DailyJobs。

```text
FastAPI 5001 lifespan
  ├─ V1 WatchEngine 线程（保留至切换）
  ├─ V2 WatchEngineV2 线程（影子→主流程）
  └─ DailyJobs 线程组（+ v2_daily_cycle_reset 任务）
```

**关键概念**：影子模式——V2 线程判定只落日志不投递；WATCH_V2_ENABLED 开关切换。

## 架构与依赖  serves: FR-1, FR-2

- **模块划分**：`watch_bootstrap` 增加 V2 启动分支（开关控制）；引擎类独立
- **依赖方向**：lifespan → bootstrap → V2 引擎 → v2 子包模块
- **外部依赖**：quote 服务（复用）、PostgreSQL（复用）、通知 facade（复用）
- **与既有架构的差异**：无新宿主；线程模型与 V1 一致

## 旧代码黑盒复用与文件边界  serves: FR-1, FR-2, FR-3, FR-7

**原则**：不读懂 V1 代码，只用它的「接口」；新流程完全自立，对接不合并代码。

### 黑盒复用清单（只调接口，不读实现）  serves: FR-1, FR-2, FR-7

| 复用什么 | V2 怎么用 | 读懂程度 |
|---|---|---|
| watch_rules 表 + 三分支/路由字段 | 直接读写 | 字段语义已定，不读代码 |
| list_by_state('active') | 调它加载规则 | 不读 |
| get_realtime_quote() | 统一取价 | 不读 |
| position_state 字段 | 读持仓真值 | 不读 |
| 飞书通知 facade / agent 通道 | notify_feishu / notify_agent 最终调它发送 | 只看发送函数参数签名 |
| watch_triggers / watch_rule_changes 落库 | 复用仓储方法 | 不读 |
| FastAPI lifespan + launchd 宿主 | V2 线程照 V1 模式挂入 | 只看 watch_bootstrap.py |
| DailyJobs 框架 | 注册每日重置任务 | 只看 registry 注册格式 |
| conditions.evaluate（条件求值） | 判触发时调 | 只看输入输出，不读内部 |
| WATCH_ACCOUNT_AGENT_MAP | 账户路由 | 读配置 |

### 独立文件边界  serves: FR-3

V2 全部新代码写在 `watch_engine/v2/` 子包 + `tests/v2/`——**不改 V1 任何文件**。共享的是数据（同一张表）与函数调用（import），不是代码。

**例外仅 3 处接入点（只加不改）**：
1. `watch_bootstrap.py` 加 V2 启动分支（~5 行，开关控制）
2. `daily_jobs/registry.py` 注册每日循环重置任务（1 行 JobDef）
3. 新建迁移文件（不改旧迁移）

回滚 = 删 v2/ 目录 + 移除 3 处接入行，V1 原样。

### 落库标记  serves: FR-7

影子期 V1/V2 同写 watch_triggers——**V2 落库带 `engine='v2'` 标记**（新增列或 detail 字段内标记，迁移时定），影子对比对账按标记区分两边输出，切主后可审计。

## 数据模型  serves: FR-11

不适用：后端专项文档；字段契约见 data-model.md。每日重置任务读写 trigger_channel/process_state/cycle_count 三列。

## 接口设计  serves: FR-1, FR-2, FR-11

| 编号 | 接口 | 输入 | 输出 | 失败与错误 | 兼容性 |
|---|---|---|---|---|---|
| IF-1 | `watch_bootstrap.start_watch_engine_v2(skip)` | skip 标记 | (engine, thread) / None | 装配失败 → None + error（不阻断 API 启动） | 新增分支，旧路径不变 |
| IF-2 | `daily_jobs.v2_daily_cycle_reset()` | 无 | 重置条数 | 部分失败记日志继续 | 新增任务 |

#### IF-1 watch_bootstrap.start_watch_engine_v2  serves: FR-1

**语义**

lifespan 内启动 V2 引擎线程；pytest 下 skip=true 不启动；句柄存 app.state 供优雅停止。

**错误码**

装配失败 → 返回 None + error 日志（API 主体不受影响，盯盘缺失由探活告警暴露）。

**兼容性**

新增分支；`DISABLE_WATCH_ENGINE=true` 时 V1/V2 都不起（排障口径不变）。

## 备选方案  serves: FR-1

| 方案 | 一句话说明 | 优点 | 代价 | 为什么未选 |
|---|---|---|---|---|
| A（选用）lifespan 同宿主新线程 | 与 V1 契约一致 | 无新运维面 | 双线程并存期资源略增 | — |
| B 独立进程 | V2 单独 daemon | 隔离彻底 | 违反「盯盘引擎唯一宿主」契约（08-02 事故根源正是 daemon 未拉起） | 不能再制造一个会静默死亡的进程 |
| C：什么都不做 | 在 V1 引擎里改 | 无新线程 | V1/V2 逻辑缠绕，无法灰度 | 灰度需要两套并存 |

## 四风险与证据  serves: FR-2

| 风险类型 | 判断问题 | 现有证据 | 结论 |
|---|---|---|---|
| 价值 | 需要独立线程吗 | 影子灰度需要 V1/V2 同时跑 | 已验证 |
| 可用性 | 运维可理解吗 | 与 V1 宿主契约一致，无新概念 | 已验证 |
| 可行性 | 线程并跑得起来吗 | V1 引擎+sidecar+心跳已多线程并存运行 | 已验证 |
| 商业可行性 | 成本 | 单进程内多一线程 | 已验证 |

**未验证项的补课计划**：统一取价性能在影子期实测 tick 耗时（agent，M3 前）。

## 失败模式与回滚  serves: FR-1, FR-2

| 失败场景 | 触发条件 | 用户可见影响 | 检测手段 | 回滚动作 | 决策人 |
|---|---|---|---|---|---|
| V2 线程未起 | 装配失败 | V2 无判定 | 探活 + metrics 心跳 | 日志定位；开关回 V1 | agent |
| 取价拖慢 | 行情源慢 | tick 延迟 | tick 耗时日志 | 熔断隔离单票；回 V1 | agent |
| 连接泄漏 | 读事务未收尾 | idle in transaction 积锁 | pg_locks 监控 | _commit_if_readonly 已内置 | agent |

- **开关**：WATCH_V2_ENABLED（false=影子/true=主流程）；DISABLE_WATCH_ENGINE（排障）
- **回滚演练**：切换当天演练开关回滚
- **不可逆动作**：无

## 跨关注点  serves: FR-1, FR-2

| 关注点 | 结论 | 依据与措施 |
|---|---|---|
| 安全 | 无新增面 | 进程内线程 |
| 隐私与合规 | 无 | 无 |
| 成本 | 低 | 单线程 + 取价去重 |
| 可观测性 | 全覆盖 | 每拍日志 + metrics 心跳 + pg_locks 监控 |
| 性能与容量 | 取价去重后可控 | 实测于影子期 |
| 文档与支持 | 本文 + architecture.md | 运维手册随切换 |

## 交付拆分与里程碑  serves: FR-1, FR-2

| 里程碑 | 内容 | 出口判据 | 负责人 | 目标日期 |
|---|---|---|---|---|
| M1 | lifespan 接入 + V2 引擎骨架空转 | 服务重启后 V2 心跳可见；V1 不受影响 | agent | 拆分后第 1 天 |
| M3 | 影子→切换 | 影子对比一致；灰度无异常 | 用户 | M2 后 2 天 |

## 需求追溯  serves: FR-1, FR-2, FR-11

| 需求编号 | 设计节 | 测试用例 | 指标 |
|---|---|---|---|
| FR-1 | 接口设计 IF-1 | tests/api/test_watch_engine_v2_bootstrap.py | V2 心跳存在 |
| FR-2 | 架构与依赖 | tests/v2/test_quote_first.py | tick 耗时可控 |
| FR-11 | 接口设计 IF-2 | tests/v2/test_daily_reset.py | 每日清零生效 |

## 常见问题  serves: FR-1, FR-2

| 问题 | 回答 |
|---|---|
| 最可能被投诉什么 | 双引擎并存期通知可能双份——影子期 V2 只记录不投递，无这个问题 |
| 6 个月后会成为什么负担 | V1 代码留存——切换验收后归档删除 |
| 流量涨 10 倍先坏在哪里 | 行情源取价——去重+熔断兜住，超限需行情源扩容 |
| 谁半夜被叫起来、手上有什么 | 探活告警接收人；手上有关闭开关与 V1 回退 |
| 数据错了怎么修、修得回来吗 | 全部可逆（开关/删列/PATCH） |
| 这个决定错了多久能发现 | 影子对比当天；探活分钟级 |

## 开放问题  serves: FR-2

| 问题 | 选项 | 负责人 | 截止 |
|---|---|---|---|
| 影子期时长 | A 1 个交易日 / B 3 个交易日 | 用户 | 设计确认时 |

## 附录  serves: FR-1

- **相关文档**：[requirement.md](../requirement.md)、[architecture.md](architecture.md)、[data-model.md](data-model.md)
- **评审记录**：待设计确认门
- **变更历史**：v1.0 2026-10-23 初版
