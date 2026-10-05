---
req_id: REQ-261004202231-bb99
title: 记忆数据与迁移脚本的处置
doc: design/migration
serves: FR-3
---

# 数据与迁移处置（REQ-261004202231-bb99）

## 现状（serves: FR-3）

| 对象 | 实测 | 判断 |
|---|---|---|
| `quant.memory_entries` | **16 行**，全部 `kind=experience, status=testing, source=NULL`，内容均为「测试记忆写入 - W3 冒烟测试」（10-03~10-04） | **无真实知识**，删除不丢信息 |
| `quant.memory_recall_audit` | **表在生产不存在**，而端点返回 `200 + {"items":[],"total":0}` | 从来就是空跑；无需处置 |
| 迁移 `scripts/migrations/012_create_memory_entries_table(.no_vector).sql` | 建表脚本 | **保留为历史**，标注作废 |
| 迁移 `scripts/migrations/013_migrate_agent_knowledge_to_memory_entries.sql` | 迁 `agent_knowledge` 的 8 条缠论知识 → `memory_entries` | 实测**无 `source=distiller` 行**＝该迁移在生产未真正生效；**保留脚本、标注未生效**，源表 `agent_knowledge` 不动 |
| 迁移 `infrastructure/persistence/migrations/create_memory_recall_audit_table.sql` | 建 recall-audit 表 | 保留脚本、标注"生产从未建表" |
| 迁移 `infrastructure/persistence/migrations/20261002_create_missing_orm_tables.py` | **7 张表**一起补（含 `memory_entries`） | **不删、不改**：它管 7 张表，只有 1 张是记忆的 |

## 处置方案（serves: FR-3）

**分两步，先代码、后数据**（这是本设计对"可回滚"的全部主张）：

- **步骤 1（随批 B 一起）**：只删代码与测试；**表与脚本一律不动**。
  此时 v2 已不提供记忆能力，但数据仍在——可回滚（`git revert` 即恢复能力）。
- **步骤 2（单独一次，需人明确点头）**：
  ```bash
  pg_dump -t quant.memory_entries quant_investment > /tmp/memory_entries_pre_drop.sql
  psql -d quant_investment -c 'DROP TABLE IF EXISTS quant.memory_entries'
  ```
  先 dump 再 DROP；`memory_recall_audit` 不存在则跳过。
  测试库（`quant_test`）同样处理（否则 `test_orm_db_drift.py` 会红——它比对的是测试库）。

## 回滚（serves: FR-3）

- 步骤 1 之后：`git revert` 批 B 的提交即恢复端点与实现；数据一直没动。
- 步骤 2 之后：用步骤 2 产出的 dump 恢复（`psql -f /tmp/memory_entries_pre_drop.sql`）。
- 迁移脚本始终保留 → 若将来要重建，`012` 可直接复用。

## 不做（serves: FR-3）

- 不迁移 `memory_entries` 里那 16 行（测试串，无价值）；
- 不删 `agent_knowledge`（迁移 013 的源表，与本需求无关）；
- 不改 `20261002_create_missing_orm_tables.py`（7 表共用的迁移）。
