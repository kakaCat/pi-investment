# v2 记忆删除清单（REQ-261004202231-bb99）

> **用途**：t2~t5 的逐文件执行清单，由 2026-10-04 的全仓普查得到；解锁后照此一次做干净。
> 普查口径：`grep -rn 'api/memory|MemoryService|MemoryRepository|memory_entries' `
> 排除 `venv/ node_modules/ dist/ .git/ __pycache__/`。

## 一、端点清单（**15 个**，删除后应全部 404）

`adapters/inbound/fastapi_app/routes/memory_async.py`（13 个）：

| # | 方法 + 路径 | 行 |
|---|---|---|
| 1 | POST `/api/memory` | 28 |
| 2 | GET `/api/memory/search` | 60 |
| 3 | GET `/api/memory/export` | 98 |
| 4 | GET `/api/memory/health` | 110 |
| 5 | POST `/api/memory/recall-audit` | 119 |
| 6 | GET `/api/memory/recall-audit` | 155 |
| 7 | GET `/api/memory/recall-audit/stats` | 192 |
| 8 | POST `/api/memory/recall-audit/{audit_id}/feedback` | 219 |
| 9 | GET `/api/memory/{entry_id}` | 272 |
| 10 | POST `/api/memory/{entry_id}/validate` | 288 |
| 11 | POST `/api/memory/{entry_id}/supersede` | 320 |
| 12 | POST `/api/memory/{entry_id}/deprecate` | 347 |
| 13 | POST `/api/memory/import` | 365 |

`adapters/inbound/fastapi_app/routes/memory_distill_async.py`（2 个）：

| # | 方法 + 路径 | 行 |
|---|---|---|
| 14 | GET `/api/memory/distill/inputs` | 44 |
| 15 | POST `/api/memory/distill/candidates` | 72 |

> ⚠️ **计数更正**：`requirement.md` 正文写的是「v2 接口面减少 12 个端点」——实测 **15 个**。
> 以本清单为准（需求文档已确认，不回改；差异在此如实登记）。

## 二、文件级清单（按卡）

**t2 · 摘注册点**
- `adapters/inbound/fastapi_app/route_registrar.py:278-279`
- `adapters/inbound/fastapi_app/main.py:1067-1083`（宽容导入，删后端点消失是**静默**的 → 必须同时核 `optional_failed`）

**t3 · 端点与仓储**
- `routes/memory_async.py`、`routes/memory_distill_async.py`
- `adapters/outbound/repositories/memory_repository.py`、`memory_recall_audit_repository.py`

**t4 · 领域实现**
- `domain/memory/`：`service.py` `hybrid_search.py` `embedding.py` `distiller.py` `models.py` `__init__.py`

**t5 · 测试**
- `tests/domain/memory/`（10 文件）
- ⚠️ **普查新增（超出原卡面）**：`tests/test_api_smoke.py` —— 它是**活体 API 冒烟测试**，
  含 `test_memory_search`（断言 200）与 `test_memory_write`（断言非 500）；
  端点一删这两条必红。处置：**删这两个用例 + 头注释里的端点列表**（其余用例保留）。
- 复核结论：`tests/` 下**再无**其它文件引用记忆（`domain/memory` 与 `test_api_smoke.py` 之外为 0）。

**t6 · 文档收口**
- v2 侧新增/追加「v2 不再承载记忆」一节；
- 可选：`tools/check_orm_drift_vs_production.py` 的 docstring 用 `POST /api/memory → 500` 作**漂移示例**
  （历史事实，建议加一句「该端点已于 REQ-bb99 下线」而不删例子）。

## 三、明确**不删**的（普查中命中但保留）

| 对象 | 为什么留 |
|---|---|
| `scripts/migrations/012_create_memory_entries_table(.no_vector).sql`、`013_*.sql`、`infrastructure/persistence/migrations/create_memory_recall_audit_table.sql` | 保留作历史与回滚依据（t7 只在头部标注作废） |
| `docs/requirements/REQ-261001145152-3982/**`（audit-report / optimization-backlog / self-review） | 别的需求的**历史**文档，提到记忆是当时的取证，不属本次范围 |
| `quant.memory_entries` / `quant.memory_recall_audit` 表 | t7 的处置对象，需人点头后 DROP |

## 四、删后逐条验证（t3/t5 的验收）

```bash
# ① 15 个端点全部 404（抽样：最常用 + 最冷门各一个）
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:5001/api/memory/search        # 期望 404
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:5001/api/memory/distill/inputs # 期望 404
# ② 反向断言：无残留符号引用
grep -rn 'MemoryService\|MemoryRepository\|domain\.memory\|memory_async' domain/ application/ adapters/ infrastructure/ --include='*.py'   # 期望 0
# ③ 测试收集与总数
./venv/bin/python -m pytest tests/ -q --collect-only | tail -1     # 与 baseline.md 的 6565 − 被删数一致
./venv/bin/python -m pytest tests/test_api_smoke.py -q --collect-only | grep -c memory   # 期望 0
# ④ 非记忆端点不变（对照 baseline.md）
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:5001/api/health               # 期望 200
```

---

## 五、实施结果（2026-10-05 实测 · t2 + t3 已落地）

| 验证项 | 结果 |
|---|---|
| 15 个端点（全量 curl） | **全部 404**（`/api/memory`、search、export、health、recall-audit ×3、`{entry_id}` ×4、import、distill ×2） |
| 非记忆端点 | `/api/health` **200 / 163B**（与基线同）；`/api/simulation/accounts` **200 / 1398B**（同）；`/api/stock/600519/klines` **200**，形状不变（`symbol/count/klines`）——`count` 由基线 65 → **64**（滚动窗口随日期平移，非删除所致） |
| 最近一次重启的注册序列 | 无 `Registered: memory` / `memory_distill`；无 `Failed to import memory` 告警（`optional_failed` 未新增） |
| 代码改动 | `route_registrar.py`：删两条路由表项 + 方法改名 `register_memory_routes` → `register_knowledge_routes`（定义与唯一调用点同步）；`main.py`：删两段 `include_router`，**不留宽容导入分支**（"删干净"由 `optional_failed` 直接可证） |
| 已删 4 文件 | `routes/memory_async.py`、`routes/memory_distill_async.py`、`repositories/memory_repository.py`、`memory_recall_audit_repository.py` |
| 语法与启动 | 两个改动文件 `ast.parse` 通过；v2 重启后 `/api/health` 200 |

**遗留（不属本卡）**：`event_calendar_repository.py` / `simulation_repository.py` 注释里以 `memory_repository` 作**写法范例**
（"except 里先 `_safe_rollback()`"），该文件已删 → 范例成了历史指向。未改（改别的仓储注释属噪音），登记供 t6 文档收口时斟酌。

## 六、实施结果（t4 + t5）

| 验证项 | 结果 |
|---|---|
| 残留符号（`MemoryService\|MemoryRepository\|domain.memory\|IMemoryRepository`） | **0**（domain/application/adapters/infrastructure/tests 全口径） |
| 已删 | `domain/memory/`（6 文件）、`tests/domain/memory/`（10 文件） |
| 顺带清掉的悬空件 | `domain/ports/repository_ports_extended.py` 的 `IMemoryRepository`（实现类删后成空壳端口）+ `domain/ports/__init__.py` 的导入与 `__all__` 条目；`tests/test_api_smoke.py` 的 2 个记忆用例、头注释端点列表、随之未使用的 `import pytest` |
| v2 运行态 | 重启后 `/api/health` **200**；`/api/memory/search` **404** |
| 测试收集 | **6488**（基线 6565 → 删 77 条；方向与数量一致） |
| 分层纯净性 | **322 → 319**（-3），删掉的正是 `domain/memory/*` 造成的违规；**剩余违规中 memory 相关 = 0 条** |
| 分层门禁现状 | 仍 `319 > 318` **失败**——差的那 1 条属**其它需求在飞改动**（`weekly_report_service` / `v13_config` / `paper_trading_engine` 等），不由本需求负责 |


## 七、实施结果（t6 · 文档落档）

- 新增 [docs/architecture/memory-subsystem-retired.md](../../architecture/memory-subsystem-retired.md)：
  front-matter（title/type/tags/updated）+ 一句话结论 + 为什么删（含"测空气"事实）+
  删了什么（可复核表）+ **三条"删干净"判据** + 仍存在别误删的 + 与 agent 侧分工 + 已知遗留；
- 已登记进 [docs/architecture/README.md](../../architecture/README.md) 的「已写」索引（避免孤儿页）；
- agent-dh 侧同步收口：`docs/architecture/memory-and-recall.md` 第 4 条（原教人用 `memory_recall_audit`）已改写为下线说明。


## 八、t7 前半段已完成（非破坏部分 · 2026-10-05）

| 项 | 结果 |
|---|---|
| 备份 | `pg_dump -t quant.memory_entries quant_investment > /tmp/memory_entries_pre_drop.sql` → **5,693 字节**，含 1 个 `COPY quant.memory_entries` 块、**16 行数据**（验收①达成） |
| 生产表 | `quant.memory_entries` = **16 行**（全部 `kind=experience / status=testing / 内容「测试记忆写入 - W3 冒烟测试」`） |
| 测试库 | `quant_test.memory_entries` = **0 行**（表存在但空） |
| `memory_recall_audit` | 生产 **不存在**（`pg_tables` 计数 0）→ 无表可 DROP，与需求分析一致 |
| 迁移脚本 | `012_create_memory_entries_table.sql`、`012_..._no_vector.sql`、`013_migrate_agent_knowledge_to_memory_entries.sql`、`create_memory_recall_audit_table.sql` **四个文件头均已标注「已作废…请勿再执行」**（验收⑤达成） |

**仍待执行（需人点头）**：两个库的 `DROP TABLE IF EXISTS quant.memory_entries`
——不可回滚，但已具备 dump 回滚路径。


## 九、t7 完成（2026-10-05）

**人工确认留痕**：用户在弹框中的裁决原文 = 「**执行 DROP（两个库）**」（选项一）。
（本条落在此处是因为卡片台账当时无法落库——见文末「台账状态」。）

| 验收项（卡面要求） | 结果 |
|---|---|
| ① dump 文件存在且非空 | **达成**：`/tmp/memory_entries_pre_drop.sql` 5,693 B，含 16 行 COPY 数据 |
| ② 人确认记录存在 | **达成**：见本节的裁决原文 |
| ③ DROP 后查询报 relation does not exist | **达成**：`quant_investment` 与 `quant_test` 双库 `DROP TABLE` → 均报 `relation "quant.memory_entries" does not exist` |
| ④ `pytest tests/test_orm_db_drift.py` 通过 | **达成**：`6 passed in 1.12s`（notify-guard `intercepted=0 egress=0`） |
| ⑤ 迁移脚本含作废标注 | **达成**：4 个脚本文件头均已标注 |

**顺带复核**：DROP 后 v2 `/api/health` 仍 **200**、`/api/memory/search` 仍 **404**。

## 十、本需求 v2 侧完成度（截至 2026-10-05）

| 卡 | 状态 |
|---|---|
| t1 摘外部消费方 | ✅ 完成（client / web-frontend / agent-dh RecallAuditTool；web 构建 exit 0；重启后工具清单无 `memory_recall_audit`，其余 4 个仍在） |
| t2 摘注册点 | ✅ |
| t3 删端点与仓储 | ✅（15 端点全 404） |
| t4 删 domain/memory | ✅（含悬空端口） |
| t5 删记忆测试 | ✅（6565 → 6488） |
| t6 文档落档 | ✅（架构页 + 索引 + agent-dh 侧收口） |
| t7 数据与迁移处置 | ✅（本文） |
| t8 看板探针改指 agent-os | ✅ 完成（代码 + 文档 + 不可用时的 degraded 断言；agent-os 现已可用，实测口径「今日新增 1」） |
| t9 agent-ts 迁移 | ⛔ **未做**：仓库索引有 4 处未合并路径（3 个 agent-ts 文件 + `quantsys-v2/.env`），按用户指示不碰 agent-ts |

**台账状态**：需求下仍有 9 张未取消的遗留卡（7 张 `[重做]` + 2 张残留子卡），
导致新批准的 9 卡计划无法落库、t1~t8 的完工记录无法写入；且索引里的未合并条目使 `git commit` 被拒。
两组数据（代码/文档）其实都已在盘上并逐项验证过。

