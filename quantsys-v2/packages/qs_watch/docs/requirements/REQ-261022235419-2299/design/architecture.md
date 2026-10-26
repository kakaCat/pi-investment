---
title: 盯盘引擎 V2 · 架构设计
status: draft
owner: 用户（PI Investment）
reviewers: agent
prd: docs/requirements/REQ-261022235419-2299/requirement.md
serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8, FR-9, FR-10, FR-11
created: 2026-10-23
updated: 2026-10-23
---

# 盯盘引擎 V2 · 架构设计  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8, FR-9, FR-10, FR-11

## 摘要  serves: FR-1, FR-2, FR-3, FR-7
- **问题**：V1 盯盘主流程是「意图驱动」——规则带固定 intent、持仓门在取价前过滤，导致建仓要接棒建新规则、未持仓票没有作废范围、曾出现程序写死过滤吞信号。
- **方案**：按持仓驱动重写主流程——统一取价前置 → 按持仓分两个判定模块 → 失效判定独立覆盖全票 → 触发按 10 次循环路由 → 发 agent 与发飞书两个独立通道文件。
- **影响面**：新增 v2/ 子包 6 个文件；复用规则表与取数服务；V1 管道保留至灰度切换；agent 侧接 agent_prompts 提示词协议。

## 背景与问题  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7
### 需求来源  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8, FR-9, FR-10, FR-11
| 需求编号 | 原始诉求 | 本设计如何回应 |
|---|---|---|
| FR-1 | 「查所有激活的盯盘规则数据」 | 每拍加载 rule_state='active' 全集 |
| FR-2 | 「查盯盘股票实时数据……再和规则对比」 | 统一取价前置，不在取价前过滤 |
| FR-3 | 「判断盯盘是持仓还是非持仓，持仓写一个文件，非持仓写一个文件」 | position_engine / unpositioned_engine 两独立模块 |
| FR-4 | 「持仓的看止盈止损减仓增仓」 | 持仓模块四操作判定 |
| FR-5 | 「未持仓看到买入范围等级」 | 非持仓模块买入范围+观察判定 |
| FR-6 | 「盯盘要设定涨多少或跌多少这个规矩就作废」「未持仓看作废范围」 | 失效判定独立覆盖全部激活票 |
| FR-7 | 「第一次触发都要发给agent判断……重复发10次内agent不处理直接发群里」「10次一个循环」 | 触发路由 10 次循环状态机 |
| FR-8 | 「失效投递给agent，让agent判断是否修改规则还是删除」 | 失效投递 agent 裁决闭环 |
| FR-9 | 「盯盘还要和账户绑定，那个账户要发对应的agent」 | 账户映射路由 |
| FR-10 | 「提示词和模板是单独的2个文件」「持仓和非持仓方案提示词和模板不一样」 | agent_prompts / feishu_templates 两独立文案文件，按「持仓×判定类型」组织 |
| FR-11 | 「盯盘添加一个字段是否触发agent」「每日定时任务是另外一个运行方式」 | 触发字段 + 10 次循环 + 每日收盘重置双机制 |

### 现状与代价  serves: FR-2, FR-6, FR-7
V1 实测（2026-10-22）：39 次触发仅 1 条送达；环境闸拿 51 只样本的假涨跌比吞掉 6 条信号；未持仓票的失效规则永远僵在 active（作废范围走不到）；建仓后要 reconcile 次日「接棒」建新规则，建仓当天无止损盯盘。

### 为什么是现在  serves: FR-2, FR-6
V1 顺序错误导致补丁越叠越多（接棒、环境闸、多套分级已删其一），继续修补成本高于重写；用户已明确完整模型（D-1~D-21 全部裁定落账）。

## 目标与非目标  serves: FR-1, FR-2, FR-3, FR-6, FR-7
### 目标  serves: FR-1, FR-2, FR-3, FR-6, FR-7
- 所有激活票每拍都有实时价可用（含被持仓/到期门跳过的票），取价输入集合 = 激活规则 symbol 集合
- 持仓/非持仓判定分别在两个独立模块文件，互不内嵌
- 失效判定覆盖全部激活票（含未持仓、未触发、未到期），止损豁免
- 触发路由 10 次循环 + 每日重置语义可单测（循环第 1/2~9/10 次行为确定）
- 发 agent 与发飞书两个文件各自可 import 且互不 import 对方

### 非目标  serves: FR-3, FR-4
- 不改条件 DSL 求值器（price_break 等判定保留复用）——求值逻辑已验证，重写无收益
- 不做持仓双面规则（一条规则同时买入面+卖出面）——本期只做顺序与分类，双面规则属后续（开放问题）
- 不做前端 UI——纯后端引擎，无页面
- 不改通知渠道本身（飞书 webhook / agent 通道复用现有基础设施）

## 方案总览  serves: FR-1, FR-2, FR-3
**一句话方案**：每拍取全部激活规则的实时价（前置不过滤），按持仓状态分流到两个判定模块各自判定，失效判定独立覆盖全部激活票，触发按 10 次循环路由到 notify_agent 或 notify_feishu 两个独立通道。

```text
激活规则 → 统一取价 → 持仓分类 ─┬─ position_engine（增仓/止盈/止损/减仓）
                               └─ unpositioned_engine（买入范围/观察）
        失效判定（全票覆盖）→ invalid → notify_agent（裁决）
        命中 → 10次循环路由 ─┬─ notify_agent（agent_prompts）
                            └─ notify_feishu（feishu_templates）
```

**关键概念**：
- **触发线 / 失效线**：规则的触发条件（conditions）与失效偏离阈值（invalidation_threshold_pct，agent 必填）
- **10 次循环**：每规则独立计数，循环第 1 次发 agent、2~9 不处理、第 10 次直通群并归零
- **双通道**：notify_agent（判断层）与 notify_feishu（用户通知层）文件级分离

## 架构与依赖  serves: FR-3, FR-4, FR-5, FR-9
- **模块划分**：
  - `position_engine.py` — 持仓类判定（增仓/止盈/止损/减仓）
  - `unpositioned_engine.py` — 非持仓类判定（买入范围/观察）
  - `notify_agent.py` — agent 投递通道（首发、失效投递、账户路由）
  - `notify_feishu.py` — 飞书盯盘群通道（agent 判断后发群、循环第 10 次直通）
  - `agent_prompts.py` — agent 提示词注册表（按 持仓×判定类型）
  - `feishu_templates.py` — 飞书模板注册表（按 持仓×判定类型）
- **依赖方向**：主循环 → 判定模块 → 通道模块 → 文案注册表；单向无环；两个通道互不 import
- **外部依赖**：实时取数服务（复用 DataProviderManager）、持仓真值（fill 实时 + 日频对账，复用）、通知基础设施（飞书 webhook / agent 通道，复用）。取数失败 → 该票本轮失明（隔离）；熔断冷却 → 本轮整体跳过且不计停牌
- **与既有架构的差异**：V1 主流程（15 阶段管道）在切换前并行保留；V2 不复用 V1 管道，只共享规则表与取数服务

## 数据模型  serves: FR-6, FR-11
详见 [data-model.md](data-model.md)。要点：规则新增 `trigger_channel`（是否触发 agent，默认 agent）、`process_state`（处理状态）、`cycle_count`（循环计数 0..9）三列；复用今日已落的 rule_state / invalidation_threshold_pct / confirm_count。迁移为幂等加列，可回滚（删列）。

## 接口设计  serves: FR-1, FR-2, FR-4, FR-5, FR-7, FR-8, FR-9
| 编号 | 接口 | 输入 | 输出 | 失败与错误 | 兼容性 |
|---|---|---|---|---|---|
| IF-1 | load_active_rules() | 无 | List[Rule]（rule_state='active'） | 仓储异常 → 本轮空集 + error 日志 | 新增，无旧调用方 |
| IF-2 | fetch_quotes(symbols) | symbol 列表（去重） | Dict[symbol, Quote] | 单 symbol 失败 → 该键缺失（本轮失明）；全部熔断 → 返回空 + cooling 标记 | 复用现有 quote 服务 |
| IF-3 | check_invalidation(rule, quote) | 规则 + 实时价 | 命中 → 标 invalid 并返回 InvalidEvent；否则 None | 无报价/缺阈值 → 跳过不判 | 新增 |
| IF-4 | position_engine.evaluate(rule, quote, position) | 规则 + 价 + 持仓 | Judgment（增仓/止盈/止损/减仓/none） | 持仓不可知 → fail-open 求值 | 新增 |
| IF-5 | unpositioned_engine.evaluate(rule, quote) | 规则 + 价 | Judgment（买入/观察/none） | 同上 | 新增 |
| IF-6 | route_trigger(rule, trigger) | 规则 + 触发 | RouteDecision（agent / skip / direct） | 计数读写失败 → 本轮按首发处理 | 新增 |
| IF-7 | notify_agent.send(rule, trigger) | 规则 + 触发 | bool（送达） | 失败 → False + 重试由调用方 | 新增 |
| IF-8 | notify_feishu.send(rule, trigger) | 规则 + 触发 | bool（送达） | 同上 | 新增 |

#### IF-1 load_active_rules  serves: FR-1
**语义**

每拍判定的输入集：加载 `rule_state='active'` 的全部规则。invalid/archived 不进集合；异常返回空集而不是半截数据。

**错误码**

仓储异常 → 本轮空集 + error 日志（本轮不判，下拍重试）。

**兼容性**

新增内部接口，无旧调用方。

#### IF-2 fetch_quotes  serves: FR-2
**语义**

对激活规则覆盖的 symbol（去重）统一取实时价；任何过滤（失效/到期/持仓）都发生在取价之后。

**错误码**

单 symbol 失败 → 该键缺失（本轮该票失明，其余不受影响）；全部熔断 → 空表 + cooling 标记（不计停牌）。

**兼容性**

复用现有 quote 服务，无破坏性变更。

#### IF-3 check_invalidation  serves: FR-6
**语义**

作废范围判定：`|现价−触发价|/触发价 > rule.invalidation_threshold_pct`（agent 设定）→ 标 invalid + 留痕 + 投递 agent。独立于持仓与触发；止损豁免（保护线穿越是触发非失效）。

**错误码**

无报价或条件缺阈值 → 跳过不判（不误标）。

**兼容性**

新增；与 V1 stale_residency 里的失效判定合并（V2 为唯一入口）。

#### IF-4 position_engine.evaluate  serves: FR-4
**语义**

持仓票的判定入口：增仓/止盈/止损/减仓四操作。止损宪法级 fail-open（持仓状态滞后显示空仓时照常判定并留痕）。

**错误码**

持仓真值读不出 → fail-open 照常求值 + state_mismatch 事件留痕。

**兼容性**

新增模块文件，无旧调用方。

#### IF-5 unpositioned_engine.evaluate  serves: FR-5
**语义**

非持仓票的判定入口：买入范围（entry 买点触发）与观察（trend_observe）。

**错误码**

同 IF-4（状态不可知 fail-open）。

**兼容性**

新增模块文件，无旧调用方。

#### IF-6 route_trigger  serves: FR-7
**语义**

每规则独立 10 次循环路由：计数+1 后 ==1 → agent；2~9 → skip；==10 → direct（直通群）并归零。止损不豁免循环。

**错误码**

计数读写失败 → 按首发处理（宁可多发一次 agent，不漏判断）。

**兼容性**

新增内部接口，无兼容负担。

#### IF-7 notify_agent.send / IF-8 notify_feishu.send  serves: FR-7, FR-9
**语义**

两个通道文件各自独立实现、互不 import；notify_agent 负责首发与失效投递（读 agent_prompts、按账户映射路由），notify_feishu 负责盯盘群（读 feishu_templates）。

**错误码**

发送失败返回 False；trigger 落库 notified=false，下拍补发（at-least-once）。

**兼容性**

新增；与 V1 notifier 并存至切换。

## 备选方案  serves: FR-1, FR-2, FR-3
| 方案 | 一句话说明 | 优点 | 代价 | 为什么未选 |
|---|---|---|---|---|
| A（选用）：持仓驱动重写 V2 | 取价前置+两模块+失效独立+循环路由 | 顺序正确、作废范围全覆盖、无接棒补丁 | 重写工程量；双跑灰度期维护两套 | — |
| B：在 V1 上继续补丁 | 前移取价、持仓门改对比维度 | 改动小 | 意图驱动骨架不变，接棒/分面问题依旧，越补越绕 | 补丁无法消除「intent 随持仓翻转失效」的结构性矛盾 |
| C：什么都不做 | 维持 V1 现状 | 零工作量 | 未持仓票无作废范围、建仓当天无止损、顺序问题持续 | 今天已实测吞信号/盲区，不能接受 |

## 四风险与证据  serves: FR-2, FR-7
| 风险类型 | 判断问题 | 现有证据 | 结论 |
|---|---|---|---|
| 价值 | 用户真的想要吗 | 用户全程逐条裁定（D-1~D-21）并主动纠正实现方向 | 已验证 |
| 可用性 | 用户会用吗 | 触发→agent→盯盘群路径与现有使用习惯一致；模板沿用现有卡片风格 | 部分 |
| 可行性 | 我们建得出来吗 | 取数/仓储/通知通道全部复用现有已验证组件；失效判定核心逻辑已在 V1 单测验证（六边界） | 部分 |
| 商业可行性 | 成本能接受吗 | 自用系统；统一取价增加少量 symbol 取价（去重后可控） | 已验证 |

**未验证项的补课计划**：可行性中的「统一取价性能」与「V1/V2 判定一致性」→ 影子模式并行跑一天对比（见 testing.md）→ agent + 用户 → 切换前出结论。

## 失败模式与回滚  serves: FR-2, FR-7, FR-11
| 失败场景 | 触发条件 | 用户可见影响 | 检测手段 | 回滚动作 | 决策人 |
|---|---|---|---|---|---|
| 统一取价拖慢 tick | 激活票过多/行情源慢 | 判定延迟 | tick 耗时指标 | 开关回 V1 主流程 | 用户 |
| V2 判定与 V1 不一致 | 影子对比漂移 | 通知口径变化 | 影子模式日对比报告 | 保持 V1，修 V2 | 用户 |
| 循环计数错乱 | 计数读写失败 | 重复/漏发 agent | 触发日志对账 | 计数清零重来 | agent |
| 通道发送失败 | 飞书/agent 通道故障 | 通知未达 | notified=false 对账 | 补发短路重发 | 引擎自动 |

- **开关**：`WATCH_V2_ENABLED`（默认 false 影子模式，true 切主流程）
- **回滚演练**：切换当天保留 V1 一键开关；影子对比通过后切换
- **不可逆动作**：无（新列可删、开关可回、V1 代码保留）

## 跨关注点  serves: FR-2, FR-7
| 关注点 | 结论 | 依据与措施 |
|---|---|---|
| 安全 | 无新增外部面 | 复用现有通知与仓储；无新鉴权面 |
| 隐私与合规 | 无新增采集 | 交易数据本机库，不外发 |
| 成本 | 低 | 统一取价按 symbol 去重；agent token 由 10 次循环控制（循环内不重复消耗） |
| 可观测性 | 全覆盖 | 每拍激活数/取价数/分类数/失效数/路由决策落日志；trigger 落库可溯源 |
| 性能与容量 | 可控 | 取价去重；失效判定为纯算术；上限=激活规则数×条件数 |
| 文档与支持 | 本设计文档集 + 需求文档 | 切换值班手册随测试策略文档 |

## 交付拆分与里程碑  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8, FR-9, FR-10, FR-11
| 里程碑 | 内容 | 出口判据 | 负责人 | 目标日期 |
|---|---|---|---|---|
| M1 | 骨架：模块文件 + 接口契约 + 数据列迁移 | 接口冻结；迁移双库 VERIFY OK | agent | 拆分后第 1 天 |
| M2 | 主流程：取价前置 + 分类 + 判定 + 失效 + 路由 + 双通道 | 全部 FR 单测绿（pytest 退出码 0） | agent | M1 后 2 天 |
| M3 | 影子模式对比 + 切换 | 影子对比一致；灰度一天无异常；V1 下线 | 用户 | M2 后 2 天 |

## 需求追溯  serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8, FR-9, FR-10, FR-11
| 需求编号 | 设计节 | 测试用例 | 指标 |
|---|---|---|---|
| FR-1 | 方案总览 / 接口设计 IF-1 | tests/v2/test_loader.py | 激活数=库一致 |
| FR-2 | 方案总览 / 接口设计 IF-2 | tests/v2/test_quote_first.py | 取价集合=symbol 集合 |
| FR-3 | 架构与依赖 | tests/v2/test_split.py | 两模块分流正确 |
| FR-4 | 架构与依赖 | tests/v2/test_position_engine.py | 四操作各自产出 |
| FR-5 | 架构与依赖 | tests/v2/test_unpositioned_engine.py | 买点触发/不触发 |
| FR-6 | 数据模型 / 接口设计 IF-3 | tests/v2/test_invalidation.py | invalid 标记+投递 |
| FR-7 | 触发路由状态机 / IF-6~8 | tests/v2/test_trigger_routing.py | 循环行为确定 |
| FR-8 | 接口设计 IF-7 | tests/v2/test_invalidation.py | 裁决回写语义 |
| FR-9 | 双通道投递 | tests/v2/test_account_routing.py | 账户路由正确 |
| FR-10 | 双通道投递 | tests/v2/test_message_templates.py | 模板/提示词分键 |
| FR-11 | 触发路由状态机 | tests/v2/test_daily_reset.py | 每日重置生效 |

## 常见问题  serves: FR-7, FR-11
| 问题 | 回答 |
|---|---|
| 最可能被投诉什么 | 某天 agent 没处理导致第 10 次才看到群通知——设计上每日重置+循环首发 agent 优先把新鲜触发给 agent |
| 6 个月后会成为什么负担 | 文案注册表膨胀——按「持仓×判定类型」分键约束它只增不滥 |
| 流量涨 10 倍先坏在哪里 | 统一取价的行情源压力——symbol 去重 + 熔断隔离已兜住，再加需行情源扩容 |
| 谁半夜被叫起来、手上有什么 | 没人——引擎故障有 launchd 守护 + 探活告警；通知故障有 notified 对账补发 |
| 数据错了怎么修、修得回来吗 | 规则状态可 PATCH 回 active；计数可清零；invalid 可裁决恢复——全部可逆 |
| 这个决定错了多久能发现 | 影子模式当天出对比报告；切换后触发日志与通知量对账可见 |

## 开放问题  serves: FR-3, FR-7
| 问题 | 选项 | 负责人 | 截止 |
|---|---|---|---|
| V1 下线方式 | A 影子灰度后切换（本设计推荐）/ B 直接切换 | 用户 | 设计确认时 |
| 观察类 15 分钟聚合缓冲是否保留到 V2 | A 保留 / B 观察类即时单发 | 用户 | 设计确认时 |
| 持仓双面规则是否进 V2 | A 进 / B 后续单独立项（本设计推荐） | 用户 | 设计确认时 |

## 附录  serves: FR-1
- **需求文档**：[requirement.md](../requirement.md)（R-1~R-12、D-1~D-21 裁定记录）
- **相关文档**：V1 今日改造（三分支/一股票一规则/hold 四态/失效实时判定/环境闸移除）——V2 继承其数据面与 agent 设定原则
- **评审记录**：待设计确认门
- **变更历史**：v1.0 2026-10-23 初版
