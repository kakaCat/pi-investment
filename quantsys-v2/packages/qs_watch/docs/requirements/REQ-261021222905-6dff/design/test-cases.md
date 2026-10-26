---
title: 交易计划与反思闭环 · 测试用例设计
status: draft
owner: 本窗口（lead）
reviewers: 用户（最终决策人）
prd: 要创建一个qs_plan里创建/REQ-261021222905-6dff/requirement.md
serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8, FR-9
created: 2026-10-21
updated: 2026-10-21
---

# 交易计划与反思闭环 · 测试用例设计  serves: FR-1

## 摘要 `serves: FR-1`

- **问题**：21 条用例覆盖 9 条 FR 的可证伪判据，作为实施与验收的统一对照。
- **方案**：单元（domain 纯逻辑）+ 应用层（假件仓储/时钟/通知，与 watch 测试同风格）+ 契约（路由错误码）+ 结构检查脚本；全部落 tests/plan/。
- **影响面**：新增 tests/plan/；watch 既有套件不许新增红。

## 背景与问题 `serves: FR-1`

### 需求来源 `serves: FR-1`

| 需求编号 | 原始诉求 | 本设计如何回应 |
|---|---|---|
| FR-1~FR-9 | 每条 FR 的验收标准（requirement.md） | TC-1~TC-21 一一对应（见需求追溯表） |

### 现状与代价 `serves: FR-1`

现状：watch 测试体系成熟（764 例、假件模式、场景矩阵）；无 plan 测试。
代价：无契约测试时接口语义靠口头，验收凭印象。

### 为什么是现在 `serves: FR-1`

测试先行定判据——拆分阶段任务卡的验收列直接引用 TC 编号。

## 目标与非目标 `serves: FR-1`

### 目标 `serves: FR-1`

- TC-1~TC-21 全部可机械执行（pytest 收集即跑）；每条断言对应一个可证伪点；
- 假件只替换出口与取数，判定与编排全走生产代码（沿用 watch 测试铁律）。

### 非目标 `serves: FR-1`

- 不做真实 DB/真实行情源的集成测试（quant_test 冒烟由验收段人工跑）；
- 不做压测（性能只有 today 视图 P95 一条，冒烟计时覆盖）。

## 方案总览 `serves: FR-1`

**一句话方案**：四类用例——状态机/编译器（domain 纯逻辑）、服务层（假件仓储+时钟）、路由契约（错误码）、结构检查（grep 脚本）。

```text
tests/plan/
  test_plan_state_machine.py     TC-1~3
  test_plan_compiler.py          TC-4~7
  test_plan_today.py             TC-8
  test_plan_fill_loop.py         TC-9~11
  test_reflection_pack.py        TC-12~14
  test_plan_change_discipline.py TC-15~17
  test_plan_stats.py             TC-18~19
  test_evolution_boundary.py     TC-20（结构检查）
  test_core_plan_adapter.py      TC-21
```

**关键概念**：假件模式（FakeRepo/FakeNotifier/FakeClock 复用 tests.services.test_watch_engine 同款）。

## 架构与依赖 `serves: FR-1`

- **模块划分**：tests/plan/ 独立目录；conftest 复用 tests/ 根 conftest（quant_test 库守卫）。
- **依赖方向**：测试 → qs_plan 生产代码 + qs_watch/qs_trading 被接线点；不依赖 agent-ts。
- **外部依赖**：无网络、无真实 DB（除根 conftest 的库名守卫）。
- **与既有架构的差异**：无。

## 数据模型 `serves: FR-1`

测试数据以 data-model.md 五表为准；假件仓储实现同接口内存版（与 watch 测试的 FakeTodoRepo 同模式）。

## 接口设计 `serves: FR-1`

| 编号 | 接口 | 输入 | 输出 | 失败与错误 | 兼容性 |
|---|---|---|---|---|---|
| IF-1 | pytest tests/plan/ -q | 无 | 退出码 0=全过 | 任一断言失败 → 退出码 1 | — |

#### IF-1 pytest tests/plan/ -q `serves: FR-1`

**语义**

plan 全部用例入口；验收时与 `pytest tests -k watch -q`（既有套件不新增红）并跑。

**错误码**

退出码 1 → 按失败用例编号回 TC 对照表定位 FR。

**兼容性**

新增目录，不影响既有套件。

## 功能测试用例 `serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8, FR-9`

### TC-1 计划创建与首版本 `validates: FR-1` `serves: FR-1`

- 前置：spec 四段齐全（1 标的、止损 8%、监控全开）；
- 步骤：POST /api/plans；
- 预期：返回 status=draft、version=1；库内计划行+版本行+事件行同事务存在；
  缺 exit 段的 spec → 400 PLAN_SPEC_INVALID 且三表零写入。

### TC-2 状态机合法边全过 `validates: FR-1` `serves: FR-1`

- 步骤：draft→active（编译）→holding（模拟 fill）→closing（清仓 fill）→closed→archived；另 active→paused→active；
- 预期：每边 plan_events 有一行（from/to/actor/reason 齐全）。

### TC-3 非法迁移被拒 `validates: FR-1` `serves: FR-1`

- 步骤：draft 直接 close；closed 再 activate；closed 再 PATCH；
- 预期：各返回 422 PLAN_STATE_ILLEGAL，状态不变、事件零新增。

### TC-4 首编译产物正确 `validates: FR-2` `serves: FR-2`

- 前置：含 1 标的+止损+两批减仓的计划；
- 步骤：activate；
- 预期：watch_rules 新增 entry/stop_loss/reduce×2 共 4 条托管规则，plan_id/role 正确；
  trading_plan_rules 4 行；position_state 按持仓真值写入（非默认 none）。

### TC-5 编译幂等 `validates: FR-2` `serves: FR-2`

- 步骤：activate 两次 + 同 spec apply 两次；
- 预期：规则数恒 4，trading_plan_rules 无重复行（联合唯一键命中）。

### TC-6 修改重编译 diff `validates: FR-2, FR-6` `serves: FR-2, FR-6`

- 步骤：PATCH 止损 8%→10% → apply；
- 预期：预览 diff=update 1 条；apply 后规则阈值=新值、version=2、
  watch_rule_changes 有 change_kind=plan_compile 且 plan_id 溯源的审计行；
  版本行冻结基线+window_ends_at。

### TC-7 编译失败回滚+托管直改被拒 `validates: FR-2` `serves: FR-2`

- 步骤 A：注入仓储异常使编译第二条规则失败 → 全部回滚（0 条半编译规则）；
- 步骤 B：agent 通道直接 PATCH 托管规则 → 拒（PLAN_RULE_MANAGED 语义）；
  人工 force=true → 放行且 drift 事件落库。

### TC-8 今日计划聚合视图 `validates: FR-3` `serves: FR-3`

- 步骤 A：1 个 active 计划（含环境闸假件 verdict=blocked）调 GET /api/plans/today →
  返回该计划、targets、env_gate verdict、待办计数；
- 步骤 B：无计划账户 → 200 + empty=true；
- 步骤 C：冒烟计时 P95<500ms（20 计划假件）。

### TC-9 成交回执收敛 `validates: FR-4` `serves: FR-4`

- 步骤：模拟带 plan_id 卖出 FillEvent（清仓）；
- 预期：待办 handled、触发 disposition=handled、position_state→none、
  计划 active→closing→closed、执行时延落 detail、exit 族规则退役。

### TC-10 部分成交只收敛批次 `validates: FR-4` `serves: FR-4`

- 步骤：两批减仓计划，第一批卖出成交；
- 预期：该批 reduce 规则退役/标记已执行，计划不收摊（仍 holding），第二批规则存活。

### TC-11 回执幂等与计划外成交 `validates: FR-4` `serves: FR-4`

- 步骤 A：同一 FillEvent 重放 → 不产生二次收敛；
- 步骤 B：无 plan_id 成交 → 计划状态不动，归因视图记「计划外」。

### TC-12 材料包四输入齐全 `validates: FR-5, FR-7` `serves: FR-5, FR-7`

- 前置：假件备好修改历史 1 条、被拦信号 2 条、盈利成交 1 笔、亏损成交 1 笔；
- 步骤：reflection_pack_service 组装；
- 预期：四段齐全且各自含预期读数；某段缺数据 → 该段标 missing 而非空数组冒充。

### TC-13 反思落库与五问校验 `validates: FR-5` `serves: FR-5`

- 步骤 A：五问齐全+verdict=adjust 附提案 → 落库成功（report_id）；
- 步骤 B：缺一问 → 400 REFLECTION_INCOMPLETE（点名缺哪问）；
- 步骤 C：verdict=keep 无理由 → 400；
- 步骤 D：同周期重写 → version+1 新行，旧报告保留。

### TC-14 反思缺席 overdue `validates: FR-5` `serves: FR-5`

- 步骤：模拟定时器触发后 agent 超时未写回；
- 预期：reflection_overdue_count+1；连续 3 日（假时钟推进）→ 产出告警标记。

### TC-15 观察窗锁定 `validates: FR-6` `serves: FR-6`

- 前置：v2 版本 apply 于 3 日前（window=10）；
- 步骤：PATCH 同字段（止损）新值；
- 预期：标记「无对照组」——无加强证据（hypothesis.evidence ≥2 条）→ 400 PLAN_CHANGE_LOCKED。

### TC-16 防反复横跳 `validates: FR-6` `serves: FR-6`

- 前置：N 日内止损 8→10（v2）；
- 步骤：再改回 8（反向）且不写「上次为什么错」；
- 预期：400 且提示必填 change_reason；附完整说明 → 放行。

### TC-17 agent 修改审计号强制 `validates: FR-6, FR-8` `serves: FR-6, FR-8`

- 步骤：actor=agent 的 PATCH 缺 decision_audit_id；
- 预期：400 DECISION_AUDIT_REQUIRED；带号 → 落库且版本行/事件行均含该号。

### TC-18 被拦信号走势统计 `validates: FR-7` `serves: FR-7`

- 前置：假件构造 2 条 env_gate 归档触发（回填日收盘价已知）；
- 步骤：GET /api/watch/outcomes/blocked-stats；
- 预期：返回其后 5/10/20 日涨跌幅与「拦对/拦错」计数，口径与 outcome 回填一致。

### TC-19 计划内/外成交分组 `validates: FR-7` `serves: FR-7`

- 前置：plan_id 成交 2 笔 + 无 plan_id 成交 1 笔；
- 步骤：GET /api/plans/{id}/stats；
- 预期：计划内 2 笔计入盈亏，计划外单列不计入。

### TC-20 进化层零写计划（结构检查） `validates: FR-8` `serves: FR-8`

- 步骤：运行结构检查脚本（grep packages/qs_agenthub 对 trading_plan*/plans 表的写调用）；
- 预期：退出码 0（零写调用）；另：含 knowledge_updates 的反思 → agent_knowledge 落条目且 evidence 完整。

### TC-22 trading_plan 工具双端契约 `validates: FR-3, FR-5, FR-6` `serves: FR-3, FR-5, FR-6`

- 前置：假件 QuantsysV2Client（agent-dh 侧）与 quant-v2-client（agent-ts 侧）；
- 步骤 A：agent-dh TradingPlanTool 调 today/list/reflect/propose → 参数正确透传（账户取 agents.json，不写死）；
- 步骤 B：agent-ts trading-plan-tool 同样动作 → 请求形态与 A 一致（同契约）；
- 步骤 C：后端 400 PLAN_SPEC_INVALID → 双端原样透传错误码；
- 步骤 D：agents.json 缺账户 → AGENT_ACCOUNT_MISSING，不发请求。
- 预期：双端 action 枚举与 IF-1~15 一一对应（IF-17 契约断言）。

### TC-21 core_plan 适配幂等 `validates: FR-9` `serves: FR-9`

- 步骤：对假件 core_plan（批次 4 标的）调 from-core-plan 两次；
- 预期：第一次生成 4 个 draft；第二次 0 新增；core_plan 缺失 → 422 CORE_PLAN_UNAVAILABLE。

## 备选方案 `serves: FR-1`

| 方案 | 一句话说明 | 优点 | 代价 | 为什么未选 |
|---|---|---|---|---|
| A（选用） | 假件应用层测试为主（watch 同模式） | 快、稳、可断言内部路径 | 不覆盖真 DB | — |
| B | 全真集成测试（quant_test 库） | 覆盖真 SQL | 慢且脆，CI 不稳定 | watch 系已证明假件模式够用；真库冒烟放验收段 |
| C：什么都不做 | 靠人工验收 | 零成本 | 回归无保障 | 本仓纪律：核心模块测试覆盖 |

## 四风险与证据 `serves: FR-1`

| 风险类型 | 判断问题 | 现有证据 | 结论 |
|---|---|---|---|
| 价值 | 用例覆盖全部 FR 判据吗 | 需求追溯表逐条对 | 已验证 |
| 可用性 | 假件模式可复用吗 | watch 764 例同款模式在跑 | 已验证 |
| 可行性 | 21 条能落地吗 | 每条都是既有模式的变体 | 已验证 |
| 商业可行性 | 维护成本 | 目录独立，不碰既有套件 | 已验证 |

**未验证项的补课计划**：无未验证项。

## 失败模式与回滚 `serves: FR-1`

| 失败场景 | 触发条件 | 用户可见影响 | 检测手段 | 回滚动作 | 决策人 |
|---|---|---|---|---|---|
| 新用例误红既有套件 | 共享 fixture 冲突 | CI 红 | 并跑 watch 套件 | 隔离 conftest | agent |
| 用例判据与 FR 脱节 | 文档改了用例没改 | 假绿 | 需求追溯表对照（验收时逐条核） | 补/改用例 | agent |

- **开关**：无（测试无开关）；
- **回滚演练**：不适用；
- **不可逆动作**：无。

## 跨关注点 `serves: FR-1`

| 关注点 | 结论 | 依据与措施 |
|---|---|---|
| 安全 | 测试不触生产库 | 根 conftest 三层守卫（*_test 库名强制） |
| 隐私与合规 | 不适用 | — |
| 成本 | 21 例假件测试 <10s | — |
| 可观测性 | 用例编号=FR 对照 | 失败即定位 FR |
| 性能与容量 | 不适用 | — |
| 文档与支持 | 本文档即用例索引 | — |

## 交付拆分与里程碑 `serves: FR-1`

| 里程碑 | 内容 | 出口判据 | 负责人 | 目标日期 |
|---|---|---|---|---|
| M1 | TC-1~7（实体+编译） | 全绿 | 本窗口 | 第 1 批 |
| M2 | TC-8~11（视图+回执） | 全绿 | 本窗口 | 第 2 批 |
| M3 | TC-12~21（反思+纪律+边界） | 全绿 | 本窗口 | 第 3-4 批 |

## 需求追溯 `serves: FR-1`

| 需求编号 | 设计节 | 测试用例 | 指标 |
|---|---|---|---|
| FR-1 | TC-1~3 | TC-1/2/3 | 状态机边覆盖率 100% |
| FR-2 | TC-4~7 | TC-4/5/6/7 | 编译幂等+回滚断言 |
| FR-3 | TC-8 / TC-22 | TC-8/22 | P95<500ms |
| FR-4 | TC-9~11 | TC-9/10/11 | 收敛率/幂等 |
| FR-5 | TC-12~14 / TC-22 | TC-12/13/14/22 | 五问齐全率 |
| FR-6 | TC-15~17 / TC-22 | TC-15/16/17/22 | 横跳拒绝率 |
| FR-7 | TC-18/19 | TC-18/19 | 分组正确率 |
| FR-8 | TC-20 | TC-20 | 结构检查退出码 0 |
| FR-9 | TC-21 | TC-21 | 适配幂等 |

## 常见问题 `serves: FR-1`

| 问题 | 回答 |
|---|---|
| 最可能被投诉什么 | 用例多——每条对一个可证伪点，失败即定位 |
| 6 个月后会成为什么负担 | 假件与生产漂移——假件只替换出口（铁律同 watch） |
| 流量涨 10 倍先坏在哪里 | 不适用（测试无流量） |
| 谁半夜被叫起来 | CI 红=提交者本人 |
| 数据错了怎么修 | 假件内存态，无修复负担 |
| 这个决定错了多久能发现 | 每次 CI |

## 开放问题 `serves: FR-1`

| 问题 | 选项 | 负责人 | 截止 |
|---|---|---|---|
| 真库冒烟是否纳入 CI | A 仅验收段人工；B 纳入 nightly | 本窗口 | 实施期定：倾向 A（与 watch 现状一致） |

## 附录 `serves: FR-1`

- **相关文档**：architecture.md / interfaces.md / data-model.md / use-cases.md（同目录）；requirement.md
- **评审记录**：待设计确认门落章
- **变更历史**：v1 初稿（2026-10-21）
