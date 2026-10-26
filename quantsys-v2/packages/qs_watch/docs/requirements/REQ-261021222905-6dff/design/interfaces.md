---
title: 交易计划与反思闭环 · 接口设计
status: draft
owner: 本窗口（lead）
reviewers: 用户（最终决策人）
prd: 要创建一个qs_plan里创建/REQ-261021222905-6dff/requirement.md
serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-9
created: 2026-10-21
updated: 2026-10-21
---

# 交易计划与反思闭环 · 接口设计  serves: FR-1

## 摘要 `serves: FR-1`

- **问题**：计划系统的对外契约需要一次定死——拆分阶段按清单造卡，不许凭空增减。
- **方案**：REST API 16 条（plan_async.py）+ 1 条 watch 侧统计扩展；错误码 8 个统一定义；全部新增、无旧调用方。
- **影响面**：新增 routes/plan_async.py；watch_async 扩展 1 端点；agent-ts quant-v2-client 路由表同步。

## 背景与问题 `serves: FR-1`

### 需求来源 `serves: FR-1`

| 需求编号 | 原始诉求 | 本设计如何回应 |
|---|---|---|
| FR-1/FR-2 | 计划实体与编译 | IF-1~IF-9、IF-11 |
| FR-3 | 盘前一屏计划 | IF-10 |
| FR-4 | 成交归因（内部事件） | 见 architecture.md「架构与依赖」（IFillListener 端口，非 HTTP） |
| FR-5/FR-6 | 反思与修改通道 | IF-12/IF-13/IF-5 |
| FR-7 | 被拦信号统计 | IF-16 |
| FR-9 | core_plan 适配 | IF-15（P2，本轮可后置） |

### 现状与代价 `serves: FR-1`

现状：watch 系 API 分散在 watch_async/watch_todo_async；无计划面；agent-ts 路由表对 core-plan 零引用。
代价：agent 无任何计划可读，计划能力无从消费。

### 为什么是现在 `serves: FR-1`

契约不定死不许进拆分（设计纪律）；下游 agent-ts 接线依赖本清单。

## 目标与非目标 `serves: FR-1`

### 目标 `serves: FR-1`

- 16 条接口签名（参数/返回/错误码）一次定死；全部有错误语义与幂等口径；
- 「接口清单」表作为拆分阶段「一接口一卡」的对照输入。

### 非目标 `serves: FR-1`

- 不做 GraphQL/WebSocket 面（REST 足够；推送走既有 watch 通知链）；
- 不做跨账户聚合接口（单计划单账户，D-3 边界）；
- 不提供托管规则的直改端点（单一写点=编译器；人工 force 走既有 watch PATCH+force，见 architecture.md 开放问题）。

## 方案总览 `serves: FR-1`

**一句话方案**：plan_async.py 承载 15 条计划面接口，watch 侧扩 1 条统计接口；错误码统一 `PLAN_*` 族。

```text
agent/人 --> FastAPI plan_async --> plan_service / plan_compiler / plan_aggregator / reflection_pack
                                      |
                                      +--> 错误语义统一 PLAN_*（400/404/409/422）
```

**关键概念**：编译预览（PATCH 暂存 draft_spec → apply 生效的两步提交）；managed rule（托管规则，接口层只读）。

## 架构与依赖 `serves: FR-1`

- **模块划分**：routes/plan_async.py（薄壳，参数校验+调服务）→ qs_plan application 服务层 → L1 仓储。
- **依赖方向**：路由 → qs_plan → 仓储；路由不直连 ORM（沿用本仓分层）。
- **外部依赖**：注册进 main.py（与 watch 路由同批）；无新中间件。
- **与既有架构的差异**：无（与 watch_async 同形态：async 路由 + 结构化错误响应）。

## 数据模型 `serves: FR-1`

请求/响应体字段以 data-model.md 的表结构为准；本文不重复字段级定义，只定契约语义。

## 接口设计 `serves: FR-1, FR-2, FR-3, FR-5, FR-6, FR-7, FR-9`

| 编号 | 接口 | 输入 | 输出 | 失败与错误 | 兼容性 |
|---|---|---|---|---|---|
| IF-1 | POST /api/plans | {account, name, horizon, spec} | 计划（draft, version=1） | 400 PLAN_SPEC_INVALID | 新增 |
| IF-2 | GET /api/plans | account, status? | 计划列表 | 无（空列表正常） | 新增 |
| IF-3 | GET /api/plans/{id} | — | 计划+version+stats | 404 PLAN_NOT_FOUND | 新增 |
| IF-4 | PATCH /api/plans/{id} | spec 片段, expected_version, reason, decision_audit_id? | 暂存回执+编译预览 diff | 409 VERSION_CONFLICT；400 DECISION_AUDIT_REQUIRED；400 PLAN_CHANGE_LOCKED | 新增 |
| IF-5 | POST /api/plans/{id}/apply | expected_version | 编译回执（create/update/retire 计数+审计行号） | 409 / 422 PLAN_STATE_ILLEGAL | 新增 |
| IF-6 | POST /api/plans/{id}/activate | expected_version | 编译回执 | 409 / 422（非 draft/paused） | 新增 |
| IF-7 | POST /api/plans/{id}/pause | reason | 状态回执 | 422（非 active/holding） | 新增 |
| IF-8 | POST /api/plans/{id}/resume | expected_version | 状态回执 | 422（非 paused） | 新增 |
| IF-9 | POST /api/plans/{id}/close | reason, close_disposition? | 状态回执+规则退役计数 | 422（有持仓且未给处置方案） | 新增 |
| IF-10 | GET /api/plans/today | account | 聚合视图（plans/targets/env_gate/delta/todos） | 200+empty（无计划） | 新增 |
| IF-11 | GET /api/plans/{id}/compile-preview | — | diff 预览（不落库） | 404 / 无变更时 empty diff | 新增 |
| IF-12 | POST /api/plans/{id}/reflections | 五问报告 | 落库回执（report_id） | 400 REFLECTION_INCOMPLETE | 新增 |
| IF-13 | GET /api/plans/{id}/reflections | limit? | 报告列表（新→旧） | 无 | 新增 |
| IF-14 | GET /api/plans/{id}/stats | — | 命中率/盈亏/执行时延/版本对照 | 404 | 新增 |
| IF-15 | POST /api/plans/from-core-plan | account, batch | 生成的 draft 计划 id 列表 | 422 CORE_PLAN_UNAVAILABLE | 新增（P2） |
| IF-16 | GET /api/watch/outcomes/blocked-stats | since?, horizon? | 被拦/抑制信号走势统计 | 无（空集正常） | watch 侧扩展 |
| IF-17 | tool: trading_plan（agent-dh + agent-ts 双端） | 计划操作集（today/list/create/activate/pause/resume/close/patch/apply/preview/reflect/stats） | 工具结果（后端响应透传+摘要） | 后端 4xx 原样透传（PLAN_* 族） | 双客户端新增（D-7/D-9） |

#### IF-1 POST /api/plans `serves: FR-1`

**语义**

创建 draft 计划；spec 必填段 targets/entry/exit/monitoring/schedule，exit 至少含 stop_loss 或 reduce_plan 其一。

**错误码**

400 PLAN_SPEC_INVALID（缺段/非法值，响应逐条列缺项）→ 补全重试；400 PLAN_ACCOUNT_UNKNOWN → 放弃。

**兼容性**

新增；spec JSONB 未知字段忽略并记 warning。

#### IF-2 GET /api/plans `serves: FR-1`

**语义**

按账户+状态过滤列计划；默认不含 archived。

**错误码**

无（空列表是正常响应）。

**兼容性**

新增；响应字段只增不改。

#### IF-3 GET /api/plans/{id} `serves: FR-1`

**语义**

计划详情：status/version/spec/当前版本基线/stats 摘要/最近事件 10 条。

**错误码**

404 PLAN_NOT_FOUND → 放弃。

**兼容性**

新增。

#### IF-4 PATCH /api/plans/{id} `serves: FR-1`

**语义**

修改 spec（暂存 draft_spec，不生效）；响应带编译预览 diff——两步提交的第一步。

**错误码**

409 VERSION_CONFLICT → 重读重试；400 DECISION_AUDIT_REQUIRED（agent 自主修改缺审计号）→ 补号；
400 PLAN_CHANGE_LOCKED（观察窗内同字段反向修改且无说明）→ 补说明或放弃。

**兼容性**

新增。

#### IF-5 POST /api/plans/{id}/apply `serves: FR-1`

**语义**

暂存修改生效：version++、编译 diff 落库、审计、冻结基线+观察窗。

**错误码**

409 VERSION_CONFLICT（天然幂等：重放即 409）；422 PLAN_STATE_ILLEGAL。

**兼容性**

新增。

**幂等与重试**

expected_version 即幂等键；重复 apply 不会二次编译。

#### IF-6 POST /api/plans/{id}/activate `serves: FR-1`

**语义**

draft/paused → active，触发首编译；重复激活幂等（规则数不变）。

**错误码**

422 PLAN_STATE_ILLEGAL（closed/archived 不可激活）。

**兼容性**

新增。

**幂等与重试**

编译按 (plan_id, role, symbol) 幂等键命中；重复 activate 不产生重复规则。

#### IF-7 POST /api/plans/{id}/pause `serves: FR-1`

**语义**

暂停：托管规则停用（enabled=false），不退役；留痕原因。

**错误码**

422（非 active/holding）。

**兼容性**

新增。

#### IF-8 POST /api/plans/{id}/resume `serves: FR-1`

**语义**

恢复：托管规则重新启用；interval 时钟按既有「重启首拍求值」口径恢复。

**错误码**

422（非 paused）。

**兼容性**

新增。

#### IF-9 POST /api/plans/{id}/close `serves: FR-1`

**语义**

关闭：退役全部托管规则、写 close_reason；有持仓时必须给 close_disposition（持仓处置方案）。

**错误码**

422（有持仓未给处置方案；已 closed）。

**兼容性**

新增。

#### IF-10 GET /api/plans/today `serves: FR-1`

**语义**

盘前聚合视图（FR-3）：激活计划 + 条件就绪度 + 环境闸 verdict + 持仓差额 + 未决待办。

**错误码**

无计划 → 200 + empty=true；环境闸缺数 → 维度 skipped。

**兼容性**

新增；P95<500ms（≤20 计划/账户）。

#### IF-11 GET /api/plans/{id}/compile-preview `serves: FR-1`

**语义**

只读预览当前 draft_spec 相对线上规则的 diff；永不落库。

**错误码**

404；无变更时返回 empty diff（正常）。

**兼容性**

新增。

#### IF-12 POST /api/plans/{id}/reflections `serves: FR-1`

**语义**

反思报告落库：五问必填、verdict=keep/observe 必须附理由、adjust/close 必须附提案；材料包快照随行。

**错误码**

400 REFLECTION_INCOMPLETE（逐项点名）；404。

**兼容性**

新增；同周期重写=新版本行，旧报告保留。

#### IF-13 GET /api/plans/{id}/reflections `serves: FR-1`

**语义**

报告列表（新→旧），供 today 视图「修改评估」段与人工回看。

**错误码**

无。

**兼容性**

新增。

#### IF-14 GET /api/plans/{id}/stats `serves: FR-1`

**语义**

计划统计：命中率（按版本分组）、计划内/外盈亏、执行时延 p50/p95、修改前后对照。

**错误码**

404。

**兼容性**

新增。

#### IF-15 POST /api/plans/from-core-plan `serves: FR-1`

**语义**

FR-9（P2）：把 core_plan 某批次标的生成 draft 计划；一律 draft 不自动激活；重复调用幂等。

**错误码**

422 CORE_PLAN_UNAVAILABLE（文件缺失/过期/账户不符）。

**兼容性**

新增（P2，本轮可后置实现）。

#### IF-17 tool: trading_plan（agent-dh + agent-ts）`serves: FR-3, FR-5, FR-6`

**语义**

agent 侧唯一调用面（D-7：不直接调 REST）。封装 IF-1~IF-15 全部计划操作；账户一律取
agents.json 的 instance.account（工具内不写死账户名，沿用 agent-dh 账户纪律 R-019）。
agent-dh 实现落 packages/tools（投资脑主消费方，D-9）；agent-ts 实现落 src/infrastructure/tools（同契约）。

**错误码**

后端 PLAN_* 族原样透传；工具自身仅补「账户未配置」前置错误（AGENT_ACCOUNT_MISSING）→ 放弃并修配置。

**兼容性**

双端新增；action 枚举与 IF 清单一一对应（新增后端端点时工具需同步，契约测试 TC-22 守门）。

#### IF-16 GET /api/watch/outcomes/blocked-stats `serves: FR-1`

**语义**

FR-7：被环境闸/市场门拦截与抑制的归档触发的后续走势统计（回答「拦错了没有」）；挂 watch 侧既有过回填数据，不动回填本体。

**错误码**

无（空集正常）。

**兼容性**

watch 统计面 additive 扩展。

## 接口清单 `serves: FR-1, FR-2, FR-3, FR-5, FR-6, FR-7, FR-9`

| 接口 id | 形态 | 职责 | serves |
|---|---|---|---|
| IF-1 | `POST /api/plans` | 创建 draft 计划 | FR-1 |
| IF-2 | `GET /api/plans` | 计划列表 | FR-1 |
| IF-3 | `GET /api/plans/{id}` | 计划详情 | FR-1 |
| IF-4 | `PATCH /api/plans/{id}` | 修改暂存+预览（CAS/审计/纪律门） | FR-6 |
| IF-5 | `POST /api/plans/{id}/apply` | 修改生效+重编译 | FR-2, FR-6 |
| IF-6 | `POST /api/plans/{id}/activate` | 激活+首编译 | FR-2 |
| IF-7 | `POST /api/plans/{id}/pause` | 暂停（规则停用） | FR-1 |
| IF-8 | `POST /api/plans/{id}/resume` | 恢复 | FR-1 |
| IF-9 | `POST /api/plans/{id}/close` | 关闭（规则退役） | FR-1 |
| IF-10 | `GET /api/plans/today` | 盘前聚合视图 | FR-3 |
| IF-11 | `GET /api/plans/{id}/compile-preview` | 编译预览（不落库） | FR-2, FR-6 |
| IF-12 | `POST /api/plans/{id}/reflections` | 反思报告写回 | FR-5 |
| IF-13 | `GET /api/plans/{id}/reflections` | 反思报告列表 | FR-5, FR-6 |
| IF-14 | `GET /api/plans/{id}/stats` | 计划统计（版本对照） | FR-6, FR-7 |
| IF-15 | `POST /api/plans/from-core-plan` | core_plan 批次→draft 计划（P2） | FR-9 |
| IF-16 | `GET /api/watch/outcomes/blocked-stats` | 被拦信号走势统计 | FR-7 |
| IF-17 | `tool: trading_plan`（agent-dh + agent-ts 双端） | agent 侧计划调用唯一入口（封装 IF-1~15） | FR-3, FR-5, FR-6 |

**错误码清单（PLAN_* 族）**：PLAN_SPEC_INVALID(400) / PLAN_ACCOUNT_UNKNOWN(400) / PLAN_NOT_FOUND(404) /
VERSION_CONFLICT(409) / PLAN_STATE_ILLEGAL(422) / PLAN_CHANGE_LOCKED(400) /
DECISION_AUDIT_REQUIRED(400) / REFLECTION_INCOMPLETE(400) / CORE_PLAN_UNAVAILABLE(422)。

## 备选方案 `serves: FR-1`

| 方案 | 一句话说明 | 优点 | 代价 | 为什么未选 |
|---|---|---|---|---|
| A（选用） | REST 16 条 + PLAN_* 错误族 | 与 watch 系同形态、agent-ts 客户端表驱动易接 | 端点数多 | — |
| B | 合并为 3-4 个大端点（action 参数路由） | 端点少 | 契约含糊、拆分无法一接口一卡 | 拆分对照要求清单粒度 |
| C：什么都不做 | 让 agent 直接读写表 | 零接口成本 | 无校验无审计无纪律门 | 违反本仓分层与审计纪律 |

## 四风险与证据 `serves: FR-1`

| 风险类型 | 判断问题 | 现有证据 | 结论 |
|---|---|---|---|
| 价值 | 调用方需要这些接口吗 | FR 逐条映射（需求来源表） | 已验证 |
| 可用性 | agent 会正确使用两步提交吗 | 未验证（接线后观察 VERSION_CONFLICT 率） | 部分 |
| 可行性 | 16 条能按时交付吗 | 全部薄壳路由+既有服务层模式 | 已验证 |
| 商业可行性 | 维护成本 | 无新依赖 | 已验证 |

**未验证项的补课计划**：两步提交可用性 → 实施期 agent 真实 PATCH→apply 一次即证。

## 失败模式与回滚 `serves: FR-1`

| 失败场景 | 触发条件 | 用户可见影响 | 检测手段 | 回滚动作 | 决策人 |
|---|---|---|---|---|---|
| 路由注册遗漏 | main.py 未挂 | 全 404 | 冒烟脚本逐端点探测 | 补注册重启 | agent |
| 错误码语义漂移 | 实现与本文档分叉 | 调用方误处理 | 契约测试逐错误码断言 | 按文档修正 | agent |
| PATCH/apply 竞态 | 两人同改 | 后到者 409 | VERSION_CONFLICT 日志 | 重读重试（正常流） | 调用方 |

- **开关**：`PLAN_ENABLED=false` 时全部接口只读（GET 可用，写接口 503）；
- **回滚演练**：quant_test 库逐端点冒烟；
- **不可逆动作**：无。

## 跨关注点 `serves: FR-1`

| 关注点 | 结论 | 依据与措施 |
|---|---|---|
| 安全 | 内网 API；agent 写操作必须 decision_audit_id | DECISION_AUDIT_REQUIRED 强制 |
| 隐私与合规 | 不适用：无个人信息 | — |
| 成本 | 无新资源 | — |
| 可观测性 | 写接口全留痕（plan_events/审计行）；4xx 带结构化原因 | 沿用 structlog |
| 性能与容量 | today 视图 P95<500ms；其余接口 O（单计划） | 冒烟计时 |
| 文档与支持 | 本文档即契约；OpenAPI 由 FastAPI 自动生成 | /docs 可读 |

## 交付拆分与里程碑 `serves: FR-1`

| 里程碑 | 内容 | 出口判据 | 负责人 | 目标日期 |
|---|---|---|---|---|
| M1 | IF-1~IF-9、IF-11（实体+编译面） | 契约测试绿；冒烟 200 | 本窗口 | 第 1 批 |
| M2 | IF-10、IF-14、IF-16（视图与统计） | P95 达标；统计断言 | 本窗口 | 第 2 批 |
| M3 | IF-12/13（反思面）；IF-15（P2 可后置） | 五问缺项 400；适配幂等 | 本窗口 | 第 3-4 批 |

## 需求追溯 `serves: FR-1`

| 需求编号 | 设计节 | 测试用例 | 指标 |
|---|---|---|---|
| FR-1 | IF-1/2/3/6/7/8/9 | TC-1~TC-3 | 契约测试数 |
| FR-2 | IF-5/6/11 | TC-4~TC-7 | 幂等断言 |
| FR-3 | IF-10 / IF-17 | TC-8 / TC-22 | P95<500ms |
| FR-4 | （事件端口，见 architecture.md） | TC-9~TC-11 | 收敛率 |
| FR-5 | IF-12/13 / IF-17 | TC-12~TC-14 / TC-22 | 五问齐全率 |
| FR-6 | IF-4/5 / IF-17 | TC-15~TC-17 / TC-22 | 横跳拒绝率 |
| FR-7 | IF-14/16 | TC-18/19 | 覆盖率 |
| FR-9 | IF-15 | TC-21 | 幂等 |

## 常见问题 `serves: FR-1`

| 问题 | 回答 |
|---|---|
| 最可能被投诉什么 | 端点太多——按 FR 分组，agent-ts 路由表驱动，不手敲 |
| 6 个月后会成为什么负担 | 错误码扩张——PLAN_* 族集中定义，新增需评审 |
| 流量涨 10 倍先坏在哪里 | today 视图聚合查询——P95 监控，超了加缓存 |
| 谁半夜被叫起来 | 无人——接口故障无资损路径；写接口有开关 |
| 数据错了怎么修 | 409 竞态是正常流；审计行可回放任一版本 |
| 这个决定错了多久能发现 | 契约测试 CI；冒烟脚本上线即跑 |

## 开放问题 `serves: FR-1`

| 问题 | 选项 | 负责人 | 截止 |
|---|---|---|---|
| compile-preview 是否并入 PATCH 响应而删 IF-11 | A 保留独立端点；B 并入 | 本窗口 | 拆分前：倾向 A（agent 可随时只读预览） |
| IF-15 是否本轮交付 | A 本轮；B 后置 P2 | 用户 | 设计确认时裁定 |

## 附录 `serves: FR-1`

- **相关文档**：architecture.md / data-model.md / test-cases.md / use-cases.md（同目录）；requirement.md
- **评审记录**：待设计确认门落章
- **变更历史**：v1 初稿（2026-10-21）
