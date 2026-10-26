# 拆分计划（REQ-261021222905-6dff）

> 目标 + 做法：新增 qs_plan 独立包——交易计划实体 + 幂等编译器（计划→watch_rules，执行仍归 WatchEngine）+
> 成交归因回写 + 定时反思（四输入五问）+ 反思驱动修改通道；agent 侧经 trading_plan 工具双端调用。
> 本计划须**人批准**后才能落任务卡（reqboard_decompose）。

## 编号口径

| 编号 | 出自 | 指什么 |
|---|---|---|
| FR-x | requirement.md 功能点表 | 需求条款 |
| D-x | requirement.md「讨论与裁定记录（D-x）」 | 需求阶段裁定（D-1~D-9） |
| IF-x | design/interfaces.md 接口清单 | 接口（IF-1~IF-17） |
| S-x | design/backend.md 服务表 | 服务/模块（S-1~S-15） |
| TC-x | design/test-cases.md | 测试用例（TC-1~TC-22） |
| UC-x | design/use-cases.md | 用户场景（UC-1~UC-6） |
| t-x | 本文档任务表 | 任务 |

## 任务表

| 计划 key | 任务 id | 标题 | 覆盖条款 | 落点（编号+文件） | 原型锚点 | 关联 D-x | 阶段 | 端侧 | 依赖 | 工作量 | 验收标准 | 子卡段 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| t1 | 回填 | 搭建 qs_plan 包骨架并落五表迁移 | FR-1 | S-10 + packages/qs_plan/pyproject.toml + infrastructure/persistence/migrations/20261105_trading_plan.py | — | D-6 | implement | backend | — | S | 迁移 dry-run 输出 5 表 2 列增量；`--apply` 后重跑报告 0 变更；`pytest tests/plan/ -q` 可收集 | dev,review |
| t2 | 回填 | 实现五表 ORM 与 TradingPlanRepository（含缺列预检降级） | FR-1 | S-10 + infrastructure/persistence/orm/models/trading_plan.py + adapters/outbound/repositories/trading_plan_repository.py | — | — | implement | backend | t1 | M | `pytest tests/plan/test_plan_repository.py -q` 绿：五表增删查改/唯一键幂等/缺列库读写不炸且 state 读 None | dev,review |
| t3 | 回填 | 实现计划领域模型与状态机守卫 | FR-1 | S-5 + packages/qs_plan/qs_plan/domain/plan/ | — | — | implement | backend | t2 | M | `pytest tests/plan/test_plan_state_machine.py -q` 绿：全部合法边通过、≥3 条非法边拒绝且状态不变（TC-1~3） | dev,review |
| t4 | 回填 | 实现 PlanService（CRUD/两步提交/纪律门/审计号强制） | FR-1, FR-6 | S-1 + packages/qs_plan/qs_plan/application/plan_service.py | — | D-2 | implement | backend | t3 | M | `pytest tests/plan/test_plan_service.py -q` 绿：版本 CAS 409、观察窗锁定与横跳拒绝 4xx、agent 缺审计号 400（TC-15~17） | dev,review |
| t5 | 回填 | 实现 PlanCompiler 幂等编译（spec→watch_rules diff/apply/退役） | FR-2 | S-2 + packages/qs_plan/qs_plan/application/plan_compiler.py | — | D-8 | implement | backend | t2 | M | 激活计划后 watch_rules 出现 plan_id 正确的托管规则；重复激活规则数不变；阈值修改后规则读数=新值（TC-4~6）；编译中途失败整体回滚（TC-7） | dev,review |
| t6 | 回填 | 实现计划生命周期路由与编译预览 | FR-1, FR-2, FR-6 | S-11 + adapters/inbound/fastapi_app/routes/plan_async.py + main.py 注册 | — | — | implement | backend | t4, t5 | M | 冒烟：IF-1~IF-9、IF-11 逐端点返回预期状态码；非法迁移 422、版本冲突 409；`pytest tests/plan/test_plan_routes.py -q` 绿 | dev,review |
| t7 | 回填 | 实现今日计划聚合视图 | FR-3 | S-3 + IF-10 + plan_async.py today 端点 | — | D-9 | implement | backend | t4 | S | `GET /api/plans/today` 有计划返回 targets/env_gate verdict/待办数；无计划 200+empty；冒烟 P95<500ms（TC-8） | dev,review |
| t8 | 回填 | 接通成交回执：execute_trade 发 FillEvent + FillSync 推进计划状态 | FR-4 | S-6/S-7 + qs_trading/application/services/account_trading_service.py + qs_watch/fill_sync_service.py | — | D-1 | implement | backend | t5 | M | 模拟带 plan_id 卖出成交 → 待办 handled + position_state 翻转 + 计划状态推进（TC-9）；部分成交只收敛批次（TC-10）；回执重放幂等（TC-11） | dev,review |
| t9 | 回填 | 实现计划统计归因与被拦信号统计 | FR-7 | S-12 + IF-14/IF-16 + watch_async.py 扩展 | — | — | implement | backend | t8 | S | 计划内/外成交分组计数正确（TC-19）；被拦归档触发给出 N 日涨跌幅（TC-18）；`pytest tests/plan/test_plan_stats.py -q` 绿 | dev,review |
| t10 | 回填 | 实现反思材料包组装与反思写回 | FR-5, FR-7 | S-4 + IF-12/13 + packages/qs_plan/qs_plan/application/reflection_pack_service.py | — | D-4 | implement | backend | t4 | M | 四输入齐全且缺段标 missing（TC-12）；五问缺项 400、合规落库、同周期重写 version+1（TC-13） | dev,review |
| t11 | 回填 | 实现反思定时任务与 overdue 兜底 | FR-5 | S-8 + qs_ops 调度任务 plan_reflect_daily/plan_reflect_weekly | — | D-5 | implement | backend | t10 | S | 定时触发后 plan_reflections 新增报告；agent 超时 overdue_count+1、连续 3 日告警（TC-14）；非交易日不触发 | dev,review |
| t12 | 回填 | 实现 trading_plan 工具双端（agent-dh 投资脑 + agent-ts fin-agent） | FR-3, FR-5, FR-6 | S-14/S-15 + IF-17 + agent-dh packages/tools + agent-ts src/infrastructure/tools | — | D-7, D-9 | implement | backend | t6 | M | 双端工具 action 覆盖 IF-1~15；账户取 agents.json 不写死；后端 4xx 原样透传；缺账户 AGENT_ACCOUNT_MISSING（TC-22） | dev,review |
| t13 | 回填 | 接通进化层消费反思知识段（只写知识不碰计划） | FR-8 | S-9 + qs_agenthub/application/services/evolution/lesson_generator.py | — | D-3 | implement | backend | t10 | S | 含 knowledge_updates 的反思 → agent_knowledge 落条目且 evidence 完整（TC-20）；结构检查脚本 grep 进化层对 plans 表写调用=0（退出码 0） | dev,review |
| t14 | 回填 | 实现 core_plan 批次适配器（P2） | FR-9 | S-13 + IF-15 | — | — | implement | backend | t4 | S | 批次 4 标的生成 4 个 draft 且预算一致；重复调用 0 新增；core_plan 缺失 422（TC-21） | dev,review |
| t15 | 回填 | 收口测试与端到端冒烟 | FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8, FR-9 | TC-1~TC-22 + tests/plan/ | — | — | test | backend | t6, t7, t8, t9, t11, t12, t13, t14 | M | `pytest tests/plan/ -q` 全绿；`pytest tests -k watch -q` 不新增红；UC-1（模拟成交全链）与 UC-2（反思→改计划→重编译）走通 | dev,review,test |

> 工作量：S=半天内 / M=1~2 天 / L=3 天以上（本计划无 L 卡）。
> 阶段说明：t15 为 test 卡（验证收口）；其余为 implement。

## 依赖理由（零交集边）

- t7 → t4：today 视图读 PlanService 聚合接口，文件虽不同（routes vs service），但接口未定前无法组装。
- t8 → t5：回执回调按 plan_id 推进计划状态，依赖编译器写入的托管规则与状态字段。
- t10 → t4：材料包读计划版本/事件（PlanService 产出的版本行），无版本行则「修改评估」无基线。
- t11 → t10：定时任务调材料包组装器，无组装器则任务空转。
- t12 → t6：工具封装的是 IF-1~15 路由，路由未落地则工具无 endpoint 可调。
- t13 → t10：进化层读 reflections 行的 knowledge_updates 段，无反思落库则无输入。
- t15 → t6..t14：收口卡只跑测试与冒烟，与实现卡零文件交集，但必须等全部实现卡完成。

## 接口清单 ↔ 接收卡 key（对照表）

| 接口 | 接收卡 key |
|---|---|
| IF-1 POST /api/plans | t6 |
| IF-2 GET /api/plans | t6 |
| IF-3 GET /api/plans/{id} | t6 |
| IF-4 PATCH /api/plans/{id} | t6 |
| IF-5 POST /api/plans/{id}/apply | t6 |
| IF-6 POST /api/plans/{id}/activate | t6 |
| IF-7 POST /api/plans/{id}/pause | t6 |
| IF-8 POST /api/plans/{id}/resume | t6 |
| IF-9 POST /api/plans/{id}/close | t6 |
| IF-10 GET /api/plans/today | t7 |
| IF-11 GET /api/plans/{id}/compile-preview | t6 |
| IF-12 POST /api/plans/{id}/reflections | t10 |
| IF-13 GET /api/plans/{id}/reflections | t10 |
| IF-14 GET /api/plans/{id}/stats | t9 |
| IF-15 POST /api/plans/from-core-plan | t14 |
| IF-16 GET /api/watch/outcomes/blocked-stats | t9 |
| IF-17 tool: trading_plan（双端） | t12 |

## 覆盖完整性（FR → 卡）

| 条款 | 承接卡 |
|---|---|
| FR-1 | t1, t2, t3, t4, t6, t15 |
| FR-2 | t5, t6, t15 |
| FR-3 | t7, t12, t15 |
| FR-4 | t8, t15 |
| FR-5 | t10, t11, t12, t15 |
| FR-6 | t4, t6, t12, t15 |
| FR-7 | t9, t10, t15 |
| FR-8 | t13, t15 |
| FR-9 | t14, t15 |

## 裁定承接（D-x → 卡）

| 裁定 | 承接卡 |
|---|---|
| D-1 不自动下单（agent 终判） | t8 |
| D-2 agent 主导演进（假设必填/纪律门） | t4 |
| D-3 三层分离（反思/进化不碰在跑计划） | t13 |
| D-4 反思四输入 + 反思驱动修改 | t10 |
| D-5 定时器驱动反思 | t11 |
| D-6 qs_plan 独立包 | t1 |
| D-7 agent 经工具调用 | t12 |
| D-8 qs_plan 零执行（执行=WatchEngine） | t5 |
| D-9 投资脑=agent-dh，双端工具 | t12 |

## 风险与回滚

- 面最大的是 t8（改 execute_trade）：事件发送失败只记日志不阻断成交（既有 11b 旁路先例），回滚=注释挂点即恢复现状；
- t5/t6 编译与路由：全部 additive，回滚=关 PLAN_ENABLED 开关（只读降级）；
- 迁移：dry-run 先行，回滚=列保留/DROP 新表（无既有数据依赖）。
