# 拆分计划（REQ-261004202231-bb99）

> **目标**：让 v2 不再对外提供记忆能力，且没有任何活代码指向被删的端点。
> **做法**：按「消费方 → 注册点 → 实现 → 测试 → 文档 → 数据」的顺序**只删不加**；
> 数据处置单独一张卡、且执行前须人点头（DROP 不可回滚）。
> 本计划须**人批准**后才能落任务卡（reqboard_decompose）。

## 编号口径

| 编号 | 出自 | 指什么 |
|---|---|---|
| FR-x | requirement.md 功能点 | 需求条款（FR-1~FR-4） |
| M-x | migration.md 迁移步骤 | 迁移/数据处置步骤（M-1 / M-2） |
| t-x | 本文档任务表 | 任务 |

（本需求是 refactor 删除型：设计文档集为 architecture.md + migration.md，**无** interfaces/frontend/backend/data-model/test-cases
—— 覆盖对照里的接口与用例两列按「纯删除、无新增接口/用例」处理，逐行给出理由。）

## 任务表

| 计划 key | 任务 id | 标题 | 覆盖条款 | 落点（编号+文件） | 阶段 | 端侧 | 依赖 | 工作量 | 验收标准 | 子卡段 |
|---|---|---|---|---|---|---|---|---|---|---|
| t1 | （落库后回填） | 摘除外部三处记忆消费方 | FR-2 | quantsys-v2-client/src/client.ts:2067-2084；web-frontend/src/services/api/memory.ts；web-frontend/src/views/Memory/index.vue；web-frontend/src/views/Memory/RecallAudit.vue；web-frontend/src/router/index.ts:213-215；agent-dh/packages/tools/memory/src/index.ts:84；agent-dh/packages/tools/memory/src/tools/RecallAuditTool/{RecallAuditTool.ts,prompt.ts,index.ts} | implement | fullstack | — | M | ① grep -rn api/memory 于 quantsys-v2-client / web-frontend / agent-dh/packages 源码 → **0 命中**；② web-frontend 构建通过（无缺失 import）；③ agent-dh 重启后工具清单里**没有** memory_recall_audit，且其余 4 个记忆工具仍在 | dev,review |
| t2 | （落库后回填） | 摘除 v2 记忆路由注册点 | FR-1 | route_registrar.py:278-279；main.py:1067-1083 | implement | backend | t1 | S | ① 对 v2 启动日志 logs/launchd-api.log 执行 `grep -c 'Registered: memory'` → **返回 0**；② 同一日志 `grep 'optional_failed'` 的条目与删除前**一致**（不变）；③ 复核 adapters/inbound/fastapi_app/main.py 无残留 memory 字面量 | dev,review |
| t3 | （落库后回填） | 删除 v2 记忆端点与仓储 | FR-1 | routes/memory_async.py；routes/memory_distill_async.py；repositories/memory_repository.py；repositories/memory_recall_audit_repository.py | implement | backend | t2 | S | ① curl -o /dev/null -w %{http_code} 127.0.0.1:5001/api/memory/search → **404**（现状 200）；② /api/memory/health → 404 | dev,review |
| t4 | （落库后回填） | 删除 domain/memory 领域实现 | FR-1 | domain/memory/service.py；hybrid_search.py；embedding.py；distiller.py；models.py；__init__.py | implement | backend | t3 | S | ① grep MemoryService / MemoryRepository / domain.memory 于 domain+application+adapters+infrastructure → **0 命中**；② v2 启动无 ImportError | dev,review |
| t5 | （落库后回填） | 删除记忆测试（10 文件） | FR-1 | tests/domain/memory/（含 __init__.py 共 10 个文件） | test | backend | t4 | S | ① pytest --collect-only 后 grep -c domain/memory → **0**；② 用例总数 = 基线 − 被删用例数（差值可解释） | dev,review |
| t6 | （落库后回填） | 文档落档：v2 不再承载记忆 | FR-4 | docs/architecture/（新增或追加一节） | doc | doc | t5 | S | ① python3 agent-dh/scripts/wiki_probe.py 无新增死链/孤儿；② 落档文档里可查到「记忆由 agent 侧承载」+ 本需求 REQ id | dev,review |
| t7 | （落库后回填） | 处置记忆数据与迁移脚本（**执行前须人确认**） | FR-3 | M-1/M-2：scripts/migrations/012_*.sql、013_*.sql、infrastructure/persistence/migrations/create_memory_recall_audit_table.sql；pg_dump 产物 | implement | backend | t3 | S | ① `ls -l /tmp/memory_entries_pre_drop.sql` **返回**非空文件；② 需求评论里可查到**人确认**原文；③ `psql -d quant_investment -c "select count(*) from quant.memory_entries"` **返回** relation does not exist；④ 对 quant_test 同样处置后 `pytest tests/test_orm_db_drift.py` **通过**；⑤ scripts/migrations/013_*.sql 头部含作废标注 | dev,review |

- 一个任务只干一件事，标题动词开头。
- 工作量口径：S = 半天内 / M = 1~2 天；本需求**无 L 卡**。
- **顺序不可颠倒**：t1 必须最先（只删 v2 会让三个消费方变成指向 404 的活代码）；t7 在 t3 之后、且执行前须人点头。

## 覆盖对照

| 需求条款 | 接口（interfaces） | 页面/模块（frontend/backend） | 测试用例（test-cases） | 接收任务 | 完整性 |
|---|---|---|---|---|---|
| FR-1 v2 内下线记忆实现 | —（纯删除：v2 接口面**减少** 12 个端点，无新增） | domain/memory；routes/memory_async + memory_distill_async；2 个仓储（删除落点） | —（纯删除，验证由行内可执行断言承载） | t2, t3, t4, t5（4） | ✅ |
| FR-2 摘除三个外部消费方 | —（消费方接口被删而非新增） | quantsys-v2-client；web-frontend/views/Memory；agent-dh RecallAuditTool | —（纯删除） | t1（1） | ✅ |
| FR-3 数据与迁移处置 | —（无接口变更） | M-1 dump / M-2 DROP（见 migration.md） | —（数据处置，用 psql 断言代替用例） | t7（1） | ✅ |
| FR-4 叙述落档 | —（纯文档） | docs/architecture（文档落点） | —（纯文档） | t6（1） | ✅ |
| **合计** | 0 接口（删除型） | 4 组落点 | 0 用例（删除型） | **7** 任务 | **4/4 条款有主** |

## 覆盖完整性规则（本需求的适用说明）

1. 本需求是**删除型 refactor**：接口与用例两列为 0 是**本质属性**而非遗漏——v2 的接口面只减不增；
   删除动作的验证用**行内可执行断言**（404 / grep 0 命中 / 收集 0）承载，不新造接口或用例。
2. 反向核查：本计划不新增任何接口/页面/用例 → 不存在「超范围设计」。
3. 4 条 FR 全部有接收任务（见上表），无孤儿条款。

## 容量自检

单卡 `detailUnits = files×1 + anchors×0.5 + chars/2000`，逐卡估算：t1≈12.0、t2≈3.2、t3≈5.3、
t4≈7.3、t5≈11.2、t6≈4.2、t7≈2.7 —— **全部 ≤ 16**，无需分批标记。

## 计划变更 v2（2026-10-04 · 用户裁定后追加 t8 / t9）

**为什么改**：实施 t1 时实测发现两处卡面未覆盖的 v2 记忆消费方，用户当场裁定
「功能转移到 agent-os」+「agent-ts 依旧使用」→ 新增 FR-5 / FR-6 与两张卡。
**旧批准因此作废，需重新批准**（范围从"纯删除"扩为"两处迁移 + 删除"，卡数 7 → 9）。

| 计划 key | 标题 | 覆盖条款 | 落点 | 阶段 | 端侧 | 依赖 | 工作量 | 验收标准 | 子卡段 |
|---|---|---|---|---|---|---|---|---|---|
| t8 | 看板记忆探针改指 agent-os | FR-5 | agent-dh/packages/web/execution/src/services/data-aggregation.ts（fetchMemoryToday）、types/index.ts:23、services/checkpoint-registry.ts:142 | implement | fullstack | — | S | ① `grep -rn 'api/memory' agent-dh/packages` 的**代码**命中为 0（dsh-pmboard 的 ledger fixture 属历史数据，单列说明）；② agent-os 不可用时 M6 探针返回 degraded（errors.memory 非空）而非静默 0；③ 该包 `npx tsc --noEmit` 通过 | dev,review |
| t9 | agent-ts 记忆消费迁 agent-os | FR-6 | agent-ts/src/services/memory/{provider-manager,v2-client}.ts、infrastructure/tools/agent/recall-audit-tool.ts、infrastructure/recall/audit-v2-client.ts、infrastructure/adapters/quant/quant-v2-client.ts:487-489、services/scheduler/tasks/memory-distill-task.ts | implement | backend | — | M | ① `grep -rn 'api/memory' agent-ts/src` 返回 0 命中；② agent-ts 相关 vitest 用例通过（provider / recall-audit / audit-adapters）；③ 首选 provider 为 agent-os（日志或单测断言） | dev,review |

**覆盖对照增量**

| 需求条款 | 接口 | 页面/模块 | 测试用例 | 接收任务 | 完整性 |
|---|---|---|---|---|---|
| FR-5 看板探针迁移 | —（无新接口，换数据源） | data-aggregation / checkpoint-registry | —（用 M6 探针三态断言替代） | t8（1） | ✅ |
| FR-6 agent-ts 迁移 | —（同上） | provider-manager / recall-audit-tool / audit 适配器 | 既有 vitest（provider / recall-audit / audit-adapters） | t9（1） | ✅ |

**顺序（2026-10-04 实施期修正）**：t8 / t9 必须早于 **t3 与 t2**。
计划 v2 只把 t3 卡在 t8/t9 之后，实施时发现 **t2（摘注册点）一落地端点就没了**，
所以 t2 同样必须排在 t9 之后；实际执行次序按 `t1 → t8 → t9 → t2 → t3 → t4 → t5 → t6 → t7`。
（本条为事实性说明，不改已批准计划的依赖定义，故以注记形式落在这里。）
