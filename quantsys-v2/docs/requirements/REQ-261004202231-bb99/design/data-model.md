---
req_id: REQ-261004202231-bb99
title: 记忆数据与表的处置
doc: design/data-model
serves: FR-3
---

# 数据模型：记忆相关对象的处置（REQ-261004202231-bb99）

## 处置前（实测）

| 对象 | 状态 |
|---|---|
| `quant.memory_entries` | 生产 **16 行**，全部为「测试记忆写入 - W3 冒烟测试」（kind=experience / status=testing / source=NULL） |
| `quant_test.memory_entries` | 表存在、**0 行** |
| `quant.memory_recall_audit` | 生产**不存在**（端点却长期返回 200 + 空数组 → R-008 一直在测空气） |
| 迁移脚本 | `scripts/migrations/012_*`（建表）、`013_*`（从 agent_knowledge 迁 8 条缠论知识）、`infrastructure/persistence/migrations/create_memory_recall_audit_table.sql` |

## 处置（已执行）

1. **先备份**：`pg_dump -t quant.memory_entries quant_investment > /tmp/memory_entries_pre_drop.sql`（5,693 字节，含 1 个 COPY 块 / 16 行）。
2. **再删除**：两个库各执行 `DROP TABLE IF EXISTS quant.memory_entries`；删后查询均报 `relation "quant.memory_entries" does not exist`。
3. **脚本标注**：4 个迁移脚本文件头加「已作废（2026-10-05 · REQ-261004202231-bb99）…请勿再执行」，保留作历史与回滚依据。
4. **回归**：`pytest tests/test_orm_db_drift.py` → **6 passed**（删表未引入模型↔库漂移）。

## 不变式

- `agent_knowledge` 表**不动**（迁移 013 的源表，历史数据保留）。
- 记忆的新家是 agent-os 的 `memories` 表（独立库 `agent_os`），与 v2 的量化库分离。
