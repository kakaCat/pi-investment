# REQ-261004202231-bb99: quantsys-v2 记忆子系统下线

**需求ID**: REQ-261004202231-bb99
**类型**: refactor（子系统下线 / 跨仓清理）
**作用域**: `quantsys-v2/`（主）+ 三个相邻消费方（`quantsys-v2-client`、`web-frontend`、`agent-dh` 的 1 个工具）
**档位**: 轻档（L3 依据见文末；出现"要保留记忆能力 / 要迁移数据 / 要让 v2 继续供记忆"信号即单向升级重档）

## TL;DR

**用户裁定：quantsys-v2 侧不应再承载「记忆」，相关代码应当删除（记忆归 agent 侧）。**

实测这个子系统**已经是半死的**，删除不是在拆有用的东西：

- 端点在跑、但**最关键的 recall-audit 表在生产根本不存在**，而它稳定返回 `200 + {"items":[],"total":0}`
  —— 那个"R-008 效果可测"的能力**一直在测空气**（与 REQ-261001145152-3982 在追的 ORM↔生产库漂移同形）；
- 库里 `memory_entries` 只有 16 行，**全部是同一句「测试记忆写入 - W3 冒烟测试」**（10-03~10-04，status=testing），
  **没有任何真实知识**；
- 迁移 013 本意是把 `agent_knowledge` 的 8 条缠论知识迁进来，实测**没有一行 `source=distiller`**（该迁移在生产未真正生效）；
- 而 agent 真正在用的那 4 个记忆工具（`memory_search` / `memory_write` / `experience_write` / `experience_stats`）
  **早已改走 agent-os**，只有 `memory_recall_audit` 一个还挂在 v2。

## 边界

### 做什么

- **FR-1: v2 内下线记忆实现** —— 删除记忆端点、领域服务、仓储、注册点、测试（清单见下）。
- **FR-2: 摘除三个外部消费方** —— `quantsys-v2-client` 的 2 个方法、`web-frontend` 的「记忆」页与路由、
   `agent-dh` 的 `memory_recall_audit` 工具。
- **FR-3: 数据与迁移处置** —— `quant.memory_entries` 的 16 行测试数据、`memory_recall_audit`（生产本就不存在）
   与三个建表/迁移脚本；**DROP 单独一步、需人点头**。
- **FR-4: 叙述落档** —— 把「v2 不再承载记忆」写进 v2 项目文档（refactor 的归档去向 = architecture / work-logs）。

### 不做什么

- **不动 agent-os**：agent-dh 那 4 个记忆工具仍走 `:8080`，本需求不改变它们的后端（那是另一条线）。
- **不动 `agent_knowledge` 表**：迁移 013 的源表保留原样（其自身注释即写明"原表保留不动"）。
- **不删 `20261002_create_missing_orm_tables.py`**：它同时补了 7 张表，只有 1 张是记忆的；只处理其中记忆那一行。
- **不顺手重构其它模块**：本需求只做"下线"，不做 `domain/memory` 之外的结构调整。

### 边界理由

- **为什么不是"把它修好"**：用户已裁定 v2 不该承载记忆；且真要修，得先补 `memory_recall_audit` 表、
  重做向量通路（ollama 不在）、再谈与 agent-os 的能力对齐——成本远高于删。
- **为什么要连 v2 外的消费方一起**：只删 v2 会让 `quantsys-v2-client` 的两个方法、web-frontend 的记忆页
  变成**指向 404 的活代码**（构建能过、点开才炸）——那正是本仓最反感的"静默失败"。
- **为什么删代码与删数据分两步**：代码可 revert，**DROP TABLE 不可回滚**；16 行虽无价值，但应由人点头。

## 现状

> 2026-10-04 补节名：refactor 档的 G2 必填节为「现状 / 目标结构 / 行为不变式」，本节即其一
> （原标题「现状实测」）。以下全部可复核。

| 维度 | 实测 | 证据 |
|---|---|---|
| 删除面（v2 内） | **24 文件 / 3,574 行** | `find . -path ./venv -prune -o -type f -name '*memory*' -print \| wc -l` |
| 端点存活 | `GET /api/memory/health` → 200 ok；`/api/memory/search` → 200 | `curl 127.0.0.1:5001/api/memory/health` |
| **recall-audit 表** | **`quant.memory_recall_audit` 生产不存在**，端点却返回 200+空数组 | `psql -c "select count(*) from quant.memory_recall_audit"` → relation does not exist |
| 数据 | `memory_entries` 16 行，全是测试串 | `select kind,status,source,count(*) … group by` → 16 / testing / NULL |
| 迁移 013 效果 | 无 `source=distiller` 行 | 同上分组查询 |
| v2 外消费方① | `quantsys-v2-client/src/client.ts:2067-2084`（2 方法） | grep `api/memory` |
| v2 外消费方② | `web-frontend`：`views/Memory/index.vue`、`RecallAudit.vue`、`services/api/memory.ts`（**1,070 行**）+ `router/index.ts:213` `/memory` 路由 | `find web-frontend/src -ipath '*memory*'` |
| v2 外消费方③ | `agent-dh` 的 `RecallAuditTool`（其 prompt 明文标注数据源） | `packages/tools/memory/src/tools/RecallAuditTool/*` |
| 删除后为何"静默" | `main.py` 用**宽容导入**（`except → optional_failed`），端点消失不报错 | `main.py:1067-1083` |
| 历史因果 | `POST /api/memory` 曾恒 500（缺表），日志出现 272/137 次 | `infrastructure/persistence/migrations/20261002_create_missing_orm_tables.py:20` |

## 目标结构

删除完成后的结构性事实（即"v2 有哪些能力"的清单变化）：

- v2 **不再有**记忆能力：无 `/api/memory*` 路由、无 `domain/memory/`、无记忆仓储、无对应测试；
- 记忆的**唯一承载方是 agent 侧**：agent-dh 的 `memory_search`/`memory_write`/`experience_write`/
  `experience_stats` 4 个工具走 agent-os `:8080`（本需求不改它）；而"效果可测"工具 `memory_recall_audit`
  随 v2 端点一起删除；
- `quant.memory_entries` 表在**步骤 1（删代码）之后仍在**，步骤 2 才 DROP（代码与数据分两步）；
- v2 的分层纯净性基线因删掉 `application→adapters` 方向的违规而**下降**，不得上升。

## 行为不变式

删除期间**必须成立**的不变量（任一破坏即判失败，不是"观察项"）：

1. **非记忆能力等价**：`/api/health`、`/api/stock/{symbol}/klines`、`/api/simulation/accounts` 的
   状态码与响应形状，删除前后一致。
2. **无活代码指向被删端点**：v2 / quantsys-v2-client / web-frontend / agent-dh 的源码中
   `grep 'api/memory'` → **0 命中**。
3. **无残留符号引用**：`domain/ application/ adapters/ infrastructure/` 中
   `grep 'MemoryService\|MemoryRepository\|memory_async'` → **0 命中**。
4. **"容忍失败"不得被冒用**：v2 启动日志的 `optional_failed` 不因本次删除新增条目——
   `main.py` 是宽容导入，这条防的是"删出导入错误却被静默吞掉"。
5. **agent 侧其余 4 个记忆工具不受影响**：它们走 agent-os，删 v2 端点不应改变其可用性。

## 删除面清单（按仓分列）

**A. quantsys-v2（主）**
- 端点：`adapters/inbound/fastapi_app/routes/memory_async.py`、`memory_distill_async.py`
- 领域：`domain/memory/`：`service.py` `hybrid_search.py` `embedding.py` `distiller.py` `models.py` `__init__.py`
- 仓储：`adapters/outbound/repositories/memory_repository.py`、`memory_recall_audit_repository.py`
- 注册点：`route_registrar.py:278-279`、`main.py:1067-1083`
- 测试：`tests/domain/memory/`（10 文件）
- 迁移脚本：`infrastructure/persistence/migrations/create_memory_recall_audit_table.sql`、
  `scripts/migrations/012_create_memory_entries_table(.no_vector).sql`、`013_migrate_agent_knowledge_to_memory_entries.sql`

**B. quantsys-v2-client**：`src/client.ts:2067-2084` 两个方法

**C. web-frontend**：`src/views/Memory/`（2 文件）、`src/services/api/memory.ts`、`src/router/index.ts:213-215` 路由
（+ 菜单项若另有登记处，一并摘除）

**D. agent-dh**：`packages/tools/memory/src/tools/RecallAuditTool/`（含注册行 `index.ts:84`）；
**仅此一个工具**——另外 4 个走 agent-os，不动。

## 处置顺序（前置依赖，不可颠倒）

```
t1 清消费方（B/C/D）→ t2 摘 v2 注册点 → t3 删 v2 实现与测试 → t4 数据处置（需人确认）→ t5 文档落档
```

- **必须先清消费方**：否则 `t2/t3` 一落地，B/C/D 就变成指向 404 的活代码。
- **t4 单独一步**：DROP 不可回滚，需人点头；建议先只删代码、表留原样，确认后再 DROP。

## 验收方向（可证伪）

1. `curl -s -o /dev/null -w '%{http_code}' 127.0.0.1:5001/api/memory/search` → **404**（现状 200）
2. v2 启动日志不再出现 `Registered: memory` / `Registered: memory_distill`，且 `optional_failed` 无新增
3. `python -m pytest tests/ -q --collect-only | grep -c 'domain/memory'` → **0**
4. `grep -rn 'api/memory' --include='*.py' --include='*.ts' --include='*.vue' quantsys-v2 quantsys-v2-client web-frontend agent-dh`
   → **0 命中**（历史文档/work-log 除外）
5. `web-frontend` 构建通过（无缺失 import）、`/memory` 路由不再注册
6. 既有判据不退化：`./scripts/restart-with-build.sh --verify-only` 四层全过；
   `pytest tests/test_layer_purity.py` 基线**不上升**（记忆模块本身含 application→adapters 违规，删后应**下降**）

## 风险

| 风险 | 处置 |
|---|---|
| 删表不可回滚 | 代码与数据分两步；DROP 前先 `pg_dump` 那 16 行 |
| 漏掉消费方（构建能过、点开才炸） | 验收第 4 条用**全仓 grep 断言 0 命中**兜底 |
| `quantsys-v2-client` 是 npm 包，删方法可能影响别的消费者 | 删除前 `grep` 全仓调用点（当前只有 agent-dh 的 RecallAuditTool） |
| 与 REQ-261001145152-3982 的收尾冲突（仍在改 v2） | 只在 `quantsys-v2/` 内动记忆相关文件，不碰其它 |

## L3 依据（为什么是轻档）

改动是**删除**为主、无新接口、无数据模型演进；作用域虽跨 4 个仓但边界清晰（grep 可穷举）。
升级条件：一旦出现"要保留记忆能力/要先迁移数据/要让 v2 继续对外供记忆"任一信号，
即升级为重档（需要设计与灰度）。

## 范围变更（2026-10-04 追加 · 用户裁定 · 本节 FR-5/FR-6 为新增条款）

**背景**：实施 t1 时实测发现两处卡面未覆盖的 v2 记忆消费方，用户当场裁定处置方向。

- **FR-5: 看板记忆探针改指 agent-os** —— agent-dh 仪表盘 M6「盘后经验沉淀」探针
  （`packages/web/execution` 的 `fetchMemoryToday`，现走 v2 `/api/memory/search`）改为查 agent-os 记忆接口；
  **不删除该看板指标**。
- **FR-6: agent-ts 记忆消费迁 agent-os** —— agent-ts（旧 agent，**用户确认仍在使用**）的 4 处 v2 记忆消费
  迁移到 agent-os：`services/memory/v2-client.ts`（V2MemoryProvider，现为 provider 链首选）、
  `infrastructure/tools/agent/recall-audit-tool.ts`（3 个端点）、
  `infrastructure/recall/audit-v2-client.ts`（写审计）、
  `infrastructure/adapters/quant/quant-v2-client.ts` 的 `memory_distill_*` 映射与周度蒸馏任务。

**裁定原文**：问「看板 M6 探针怎么处置」→ 答「应该把功能转移到agent-os里」；
问「agent-ts 的 4 处消费要不要并进来」→ 答「agent-ts依旧使用」。

**同一口径**：记忆能力归 agent 侧（agent-os），v2 只做数据与量化。FR-5/FR-6 都是**迁移**，
不是"保留 v2 记忆"；迁移完成后 v2 侧照原计划删干净。

### ⚠️ 阻塞事实（必须与上面的裁定一起看）

**agent-os 服务当前不可用**：`curl http://127.0.0.1:8080/health` → 连接失败（health=000），无运行进程；
`agent-os/` 下无构建产物与 launchd plist（只有 `agent-os.sh`/`agent-os-daemon.sh`/Dockerfile/Makefile）。
接口契约在 `agent-os-client/src/memory-client.ts`（`GET /api/v1/memory/search`、`GET /api/v1/memory`、
`POST /api/v1/memory`、`PATCH/DELETE/GET /api/v1/memory/{id}`）。

因此 FR-5/FR-6 的「端到端可用」在本需求内**无法验证**，只能验证到**契约对齐 + 不可用时显式降级**。
把 agent-os 记忆后端跑起来属另一件事（影响面含 agent-dh 现有 4 个记忆工具），本需求不擅自扩到这里。

### 档位说明（诚实登记）

上面 L3 依据自己写的升级条件（"要保留记忆能力/要迁移"）**已触发**。处置：不重走一遍 design 阶段，
而是把 FR-5/FR-6 作为**附卡**补进拆分计划并各带一节设计（等价于重档实质要求的设计 + 灰度），
交你在计划批准门一并裁决。

<!-- reqboard:marks:begin 机器维护，请勿手改 -->

#### 条款接收状态（随卡的生命周期自动更新）

| 编号 | 接收状态 | 承载任务 |
|------|---------|---------|
| FR-1 | ✅ 已接收 | t2、t3、t4 |
| FR-2 | 🔴 **未被接收** | — |
| FR-3 | 🔴 **未被接收** | — |
| FR-4 | 🔴 **未被接收** | — |

> 🔴 **未被接收（3 条）**：FR-2、FR-3、FR-4

<!-- reqboard:marks:end -->
