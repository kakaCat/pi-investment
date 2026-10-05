---
req_id: REQ-261004202231-bb99
title: 被删除的接口面（15 个端点）
doc: design/interfaces
serves: FR-1, FR-2
---

# 接口面：删掉了什么（REQ-261004202231-bb99）

## 删除的端点（15 个，删后全量 curl 全 404）

| 文件 | 方法 + 路径 |
|---|---|
| `routes/memory_async.py` | POST `/api/memory`、GET `/api/memory/search`、GET `/api/memory/export`、GET `/api/memory/health`、POST `/api/memory/recall-audit`、GET `/api/memory/recall-audit`、GET `/api/memory/recall-audit/stats`、POST `/api/memory/recall-audit/{audit_id}/feedback`、GET `/api/memory/{entry_id}`、POST `/api/memory/{entry_id}/validate`、POST `/api/memory/{entry_id}/supersede`、POST `/api/memory/{entry_id}/deprecate`、POST `/api/memory/import` |
| `routes/memory_distill_async.py` | GET `/api/memory/distill/inputs`、POST `/api/memory/distill/candidates` |

## 删掉的消费方接口

| 消费方 | 删掉的东西 |
|---|---|
| `quantsys-v2-client`（TS 客户端） | `getRecallAudit` / `getRecallAuditStats` 两个方法 |
| `web-frontend` | 记忆页两个组件 + `services/api/memory.ts` + `/memory` 路由 + 「记忆面板」菜单项 |
| `agent-dh` | `memory_recall_audit` 工具（RecallAuditTool 三文件 + 注册行 + 再导出） |
| `agent-ts` | V2MemoryProvider、v2 召回审计工具与审计写入客户端、2 条蒸馏端点映射 |

## 新的接口面（agent 侧，不属本仓）

- `GET /api/v1/memory`、`GET /api/v1/memory/search`、`POST /api/v1/memory`（agent-os `:8080`）。
- 看板 M6 探针改查 `GET /api/v1/memory?category=experience&limit=100`（不可用时显式 degraded）。
