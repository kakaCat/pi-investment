---
id: memory-subsystem-retired
title: 记忆子系统已下线（v2 不再承载记忆）
type: architecture
status: living
tags: [memory, retirement, agent-os, decision]
updated: 2026-10-05
summary: v2 不再承载记忆——15 个端点全 404、领域/仓储/测试/端口全删，记忆归 agent-os；附「删干净」的三条判据。
---

# 记忆子系统已下线（QuantSys V2）

**来源**：[REQ-261004202231-bb99](../requirements/REQ-261004202231-bb99/requirement.md)（2026-10-04 立项 / 2026-10-05 落地）

## 一句话

**v2 不再提供任何记忆能力**：15 个 `/api/memory*` 端点全部 404，
`domain/memory/`、记忆仓储、记忆测试、路由注册点全部删除；记忆由 **agent 侧（agent-os `:8080`）** 承载。

## 为什么是删、不是修

- 用户裁定：**记忆归 agent 侧**，v2 只做数据与量化。
- 这个子系统本来就是**半死的**：`quant.memory_recall_audit` 表在生产**从来不存在**，
  而端点稳定返回 `200 + {"items":[],"total":0}` —— R-008 的「效果可测」一直在**测空气**；
  `quant.memory_entries` 只有 16 行测试串；迁移 013 的蒸馏链路在生产没有一行落库。
- agent 真正在用的 4 个记忆工具（`memory_search` / `memory_write` / `experience_write` /
  `experience_stats`）**早已改走 agent-os**。

## 删了什么（可复核）

| 类别 | 内容 |
|---|---|
| 端点 | **15 个**（`memory_async.py` 13 + `memory_distill_async.py` 2）——删除后全量 curl **全 404** |
| 注册点 | `route_registrar.py` 两条路由表项（方法随改名 `register_memory_routes` → `register_knowledge_routes`）；`main.py` 两段 `include_router`（**不留宽容导入分支**） |
| 领域 | `domain/memory/`（6 文件） |
| 仓储 | `memory_repository.py`、`memory_recall_audit_repository.py` |
| 端口 | `domain/ports/repository_ports_extended.py::IMemoryRepository`（实现删后成空壳） |
| 测试 | `tests/domain/memory/`（10 文件）+ `tests/test_api_smoke.py` 的 2 个记忆用例 |
| 外部消费方 | quantsys-v2-client 的 2 个 recall-audit 方法；web-frontend 的记忆页与路由；agent-dh 的 `memory_recall_audit` 工具；agent-dh 看板 M6 探针（改指 agent-os） |

**证据**：删除前基线见需求目录 `baseline.md`；逐文件清单与实施结果见 `deletion-checklist.md`。

## 怎么确认「删干净」（三条判据）

1. **端点**：15 个 `/api/memory*` 全 404（含 `export` / `import` / `distill` 等冷门路径）；
2. **符号**：`grep -rn 'MemoryService|MemoryRepository|domain\.memory|IMemoryRepository'` 于
   `domain/ application/ adapters/ infrastructure/ tests/` → **0**；
3. **启动**：最近一次重启的日志里**没有** `Registered: memory`，也没有 `Failed to import memory`
   —— 这正是**故意不放宽容导入分支**的原因：「删干净」要能被日志直接证伪。

## 仍然存在的（别误删）

- `scripts/migrations/012_create_memory_entries_table(.no_vector).sql`、`013_migrate_agent_knowledge_to_memory_entries.sql`、
  `infrastructure/persistence/migrations/create_memory_recall_audit_table.sql` —— 保留作历史与回滚依据；
- `quant.memory_entries`（16 行测试数据）与 `quant.memory_recall_audit`（生产本就不存在）——
  **表结构尚未 DROP**，属该需求的 t7，需人点头后单独执行（先 `pg_dump`）。

## 与 agent 侧的分工

- **记忆读写与经验沉淀**：agent-os `:8080`（`GET/POST /api/v1/memory`、`/api/v1/memory/search`），
  由 agent-dh 的 4 个记忆工具调用；
- **v2 侧只保留决策与账本**（`agent_decisions` / `strategy_performance` 等），不再有「记忆」这一层。

## 已知遗留（不属本次范围）

- agent-os 自身的 `schema.sql` / `migrations/002` / HTTP 层三方漂移（`memories` 两套形状），
  本机是**手工按并集补齐**的，正式修法应由 agent-os 出一版对账迁移 —— 见
  [agent-os 本机重建](../../../agent-dh/docs/work-logs/2026-10/agent-os-restore.md)；
- `event_calendar_repository.py` / `simulation_repository.py` 的注释仍以 `memory_repository` 作写法范例（指向已删文件），
  属注释级历史指向，未改。
