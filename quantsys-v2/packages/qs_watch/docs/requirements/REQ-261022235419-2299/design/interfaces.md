---
title: 盯盘引擎 V2 · 接口设计
status: draft
owner: 用户（PI Investment）
reviewers: agent
prd: docs/requirements/REQ-261022235419-2299/requirement.md
serves: FR-1, FR-2, FR-4, FR-5, FR-6, FR-7, FR-8, FR-9, FR-10, FR-11
created: 2026-10-23
updated: 2026-10-23
---

# 盯盘引擎 V2 · 接口设计  serves: FR-1, FR-2, FR-4, FR-5, FR-6, FR-7, FR-8, FR-9, FR-10, FR-11

## 摘要  serves: FR-1, FR-2, FR-7

- **问题**：V2 的模块间契约需要定死，拆分与联调才有依据。
- **方案**：9 条内部接口（IF-1~IF-9）+ 文案注册表契约；对外 API 不新增。
- **影响面**：v2/ 子包内部；对外无破坏。

## 背景与问题  serves: FR-7

### 需求来源  serves: FR-1, FR-2, FR-4, FR-5, FR-6, FR-7, FR-8, FR-9, FR-10, FR-11

| 需求编号 | 原始诉求 | 本设计如何回应 |
|---|---|---|
| FR-1 | 「查所有激活的盯盘规则数据」 | IF-1 load_active_rules |
| FR-2 | 「查盯盘股票实时数据」 | IF-2 fetch_quotes |
| FR-4 | 「持仓的看止盈止损减仓增仓」 | IF-4 position_engine.evaluate |
| FR-5 | 「未持仓看到买入范围」 | IF-5 unpositioned_engine.evaluate |
| FR-6 | 「作废范围」 | IF-3 check_invalidation |
| FR-7 | 「10次一个循环」「发agent」 | IF-6 route_trigger / IF-7 notify_agent.send |
| FR-8 | 「失效投递给agent」 | IF-7 notify_agent.send（失效裁决入口） |
| FR-9 | 「发对应的agent」 | IF-7 内账户映射路由 |
| FR-10 | 「提示词和模板是单独的2个文件」 | 文案注册表契约 |
| FR-11 | 「每日定时任务是另外一个运行方式」 | IF-9 reset_daily_cycles |

### 现状与代价  serves: FR-7

V1 的通知与路由耦合在 notifier 单文件，无法分开演进；无契约文档，拆分凭读代码。

### 为什么是现在  serves: FR-1

设计阶段必须把契约定死，否则拆分阶段无法落卡。

## 目标与非目标  serves: FR-7

### 目标  serves: FR-7, FR-9, FR-10

- 9 条接口签名、错误语义、兼容性全部定死
- 文案注册表按键「持仓状态 × 判定类型」可查
- 两通道文件互不 import（结构约束可验证）

### 非目标  serves: FR-1

- 不新增对外 REST API
- 不改既有 /api/watch/* 语义
- 不定 agent 内部协议（属 agent-ts 侧）

## 方案总览  serves: FR-7

**一句话方案**：主循环 → 判定模块 → 路由 → 双通道，全部经定死契约调用。

```text
tick → load_active_rules → fetch_quotes → check_invalidation
     → position_engine/unpositioned_engine.evaluate
     → route_trigger → notify_agent.send / notify_feishu.send
     （每日）reset_daily_cycles
```

**关键概念**：RouteDecision（agent/skip/direct）；Judgment（判定结果值对象）。

## 架构与依赖  serves: FR-7, FR-9

- **模块划分**：契约见接口清单；实现在 v2/ 子包
- **依赖方向**：主循环 → 判定 → 路由 → 通道；notify_agent 与 notify_feishu 互不 import
- **外部依赖**：quote 服务、通知 facade、仓储
- **与既有架构的差异**：通道从 V1 notifier 单文件拆为两文件

## 数据模型  serves: FR-7

不适用：接口契约文档，数据字段见 data-model.md。

## 接口设计  serves: FR-1, FR-2, FR-4, FR-5, FR-6, FR-7, FR-8, FR-9, FR-10, FR-11

### 接口清单  serves: FR-1, FR-2, FR-7

| 接口 id | 接口 | 输入 | 输出 | 失败与错误 | 兼容性 |
|---|---|---|---|---|---|
| IF-1 | `load_active_rules()` | 无 | List[Rule] | 仓储异常 → 空集 + error | 新增 |
| IF-2 | `fetch_quotes(symbols)` | symbol 去重列表 | Dict[str, Quote] | 单票失败缺键；全熔断 → 空+cooling | 复用现有 |
| IF-3 | `check_invalidation(rule, quote)` | Rule, Quote | Optional[InvalidEvent] | 无报价/缺阈值 → None | 新增 |
| IF-4 | `position_engine.evaluate(rule, quote, position)` | Rule, Quote, Position | Judgment | 持仓不可知 → fail-open | 新增 |
| IF-5 | `unpositioned_engine.evaluate(rule, quote)` | Rule, Quote | Judgment | 同上 | 新增 |
| IF-6 | `route_trigger(rule, trigger)` | Rule, Trigger | RouteDecision | 计数失败 → 按首发处理 | 新增 |
| IF-7 | `notify_agent.send(rule, trigger)` | Rule, Trigger | bool | False + 下拍补发 | 新增 |
| IF-8 | `notify_feishu.send(rule, trigger)` | Rule, Trigger | bool | False + 下拍补发 | 新增 |
| IF-9 | `reset_daily_cycles()` | 无 | 重置条数 | 部分失败记日志继续 | 新增 |

#### IF-1 load_active_rules  serves: FR-1

**语义**

每拍输入集：rule_state='active' 的全部规则；异常返回空集不返回半截。

**错误码**

仓储异常 → 本轮空集 + error 日志（下拍重试）。

**兼容性**

新增内部接口。

#### IF-6 route_trigger  serves: FR-7

**语义**

每规则独立 10 次循环：计数+1==1 → agent；2~9 → skip；==10 → direct 并归零。

**错误码**

计数读写失败 → 按首发处理（宁可多发不漏判）。

**兼容性**

新增内部接口。

**幂等与重试**

计数更新为读改写；并发同规则触发按先后序递增，允许偶发超发（不漏）。

## 备选方案  serves: FR-7

| 方案 | 一句话说明 | 优点 | 代价 | 为什么未选 |
|---|---|---|---|---|
| A（选用）函数契约 | Python 函数签名 + 文档语义 | 与现状一致、无序列化层 | 无类型级强制 | — |
| B Pydantic 模型契约 | 全量值对象 | 强类型校验 | 引入新依赖与转换层 | 当前规模下转换层是纯成本 |
| C：什么都不做 | 不写契约文档 | 零工作量 | 拆分凭读代码，接口漂移无约束 | 契约不定死不许进拆分（本仓纪律） |

## 四风险与证据  serves: FR-7

| 风险类型 | 判断问题 | 现有证据 | 结论 |
|---|---|---|---|
| 价值 | 契约要这么细吗 | 拆分阶段凭契约落卡（本仓纪律） | 已验证 |
| 可用性 | 执行者读得懂吗 | 签名+错误码+兼容性三段式 | 已验证 |
| 可行性 | 写得出来吗 | 全部为新增内部接口，无外部约束 | 已验证 |
| 商业可行性 | 成本 | 无 | 已验证 |

**未验证项的补课计划**：无。

## 失败模式与回滚  serves: FR-7

| 失败场景 | 触发条件 | 用户可见影响 | 检测手段 | 回滚动作 | 决策人 |
|---|---|---|---|---|---|
| 契约实现偏差 | 实现与签名不符 | 联调失败 | 接口测试 | 修实现对齐契约 | agent |

- **开关**：无
- **回滚演练**：契约是文档，回滚=改文档+改实现
- **不可逆动作**：无

## 跨关注点  serves: FR-7

| 关注点 | 结论 | 依据与措施 |
|---|---|---|
| 安全 | 无新增面 | 内部接口 |
| 隐私与合规 | 无新增采集 | 无 |
| 成本 | 无 | 无 |
| 可观测性 | 调用日志 | 各接口入口 log |
| 性能与容量 | 无特殊 | 内存调用 |
| 文档与支持 | 本文 | 本文即契约 |

## 交付拆分与里程碑  serves: FR-1, FR-2, FR-7

| 里程碑 | 内容 | 出口判据 | 负责人 | 目标日期 |
|---|---|---|---|---|
| M1 | 接口冻结 | 本文确认 | 用户 | 设计确认时 |

## 需求追溯  serves: FR-1, FR-2, FR-7

| 需求编号 | 设计节 | 测试用例 | 指标 |
|---|---|---|---|
| FR-1 | IF-1 | tests/v2/test_loader.py | 激活数一致 |
| FR-2 | IF-2 | tests/v2/test_quote_first.py | 取价集合一致 |
| FR-7 | IF-6/IF-7/IF-8 | tests/v2/test_trigger_routing.py | 循环行为确定 |

## 常见问题  serves: FR-7

| 问题 | 回答 |
|---|---|
| 最可能被投诉什么 | 契约太细——但拆分凭它落卡 |
| 6 个月后会成为什么负担 | 接口演化需同步本文——serves 追溯兜底 |
| 流量涨 10 倍先坏在哪里 | 不适用（内部契约） |
| 谁半夜被叫起来 | 无人 |
| 数据错了怎么修 | 契约为文档，改实现即可 |
| 这个决定错了多久能发现 | 接口测试当日可见 |

## 开放问题  serves: FR-7

| 问题 | 选项 | 负责人 | 截止 |
|---|---|---|---|
| route_trigger 计数读写并发策略 | A 读改写（允许偶发超发）/ B 行锁 | agent | 拆分阶段定 |

## 附录  serves: FR-1

- **相关文档**：[requirement.md](../requirement.md)、[architecture.md](architecture.md)、[data-model.md](data-model.md)
- **评审记录**：待设计确认门
- **变更历史**：v1.0 2026-10-23 初版
