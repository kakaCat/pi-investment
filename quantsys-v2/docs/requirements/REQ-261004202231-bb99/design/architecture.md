---
req_id: REQ-261004202231-bb99
title: 记忆子系统下线的边界、分批与验证
doc: design/architecture
serves: FR-1, FR-2, FR-3, FR-4
---

# 架构设计（REQ-261004202231-bb99）

**前提**：本需求**不改运行时架构**——不新增服务、不新增表、不新增接口，只**删除**一个已经半死的子系统
及其三个消费方。所以设计的重点不是新结构，而是两件事：**删除顺序**（谁先谁后）与**怎么证明**
（既没删漏、也没删坏）。

## 目标与判定（serves: FR-1, FR-2, FR-3, FR-4）

**目标**：v2 不再对外提供任何记忆能力，且**没有任何活代码指向被删的端点**。

可证伪判定（任一不成立即未达成）：

1. `curl -s -o /dev/null -w '%{http_code}' 127.0.0.1:5001/api/memory/search` → **404**（现状 200）；
2. v2 启动日志不再出现 `Registered: memory` / `Registered: memory_distill`，且宽容导入的
   `optional_failed` **无新增项**（不能把"删掉导致导入失败"混进"容忍失败"）；
3. `python -m pytest tests/ -q --collect-only 2>/dev/null | grep -c 'domain/memory'` → **0**；
4. 全仓 grep：`api/memory` 在 `quantsys-v2` / `quantsys-v2-client` / `web-frontend` / `agent-dh`
   的**源码**中 **0 命中**（历史文档/work-log 除外）。

## 依赖与调用方清单（serves: FR-1, FR-2）

删除的判据是"**谁在调用它**"——下表是穷举口径，逐行都可用 grep 复核（这是"没删漏"的唯一证据）：

| 方向 | 调用方（精确位置） | 调用什么 | 处置 |
|---|---|---|---|
| v2 内 | `adapters/inbound/fastapi_app/route_registrar.py:278-279` | 注册两个 memory 路由 | 删两行 |
| v2 内 | `adapters/inbound/fastapi_app/main.py:1067-1083` | `include_router`（**宽容导入**） | 删两段（连同 warning 分支） |
| v2 内 | `routes/memory_distill_async.py:9` | `domain.memory.distiller` | 随端点一起删 |
| v2 内 | `routes/memory_async.py:15-16` | `MemoryRecallAuditRepository` / `MemoryService` | 随端点一起删 |
| 外部① | `quantsys-v2-client/src/client.ts:2067-2084` | `GET /api/memory/recall-audit`(+stats) | 删 2 个方法 |
| 外部② | `web-frontend/src/services/api/memory.ts` + `views/Memory/{index,RecallAudit}.vue` + `router/index.ts:213-215` | 记忆页与路由（**1,070 行**） | 删页面与路由；菜单若另有登记处一并摘（删前 grep 复核） |
| 外部③ | `agent-dh/packages/tools/memory/src/tools/RecallAuditTool/`（注册行 `packages/tools/memory/src/index.ts:84`） | 经 v2 客户端调 recall-audit | 删该工具（**仅此一个**；同包另外 4 个工具走 agent-os，不动） |

**依赖方向核对**：被删的 `domain/memory` 自身含 `application → adapters` 方向的违规（`service.py` 经仓储取数），
删除后 `tests/test_layer_purity.py` 的基线应当**下降而非上升**——这也是一条独立的正确性旁证。

## 分批设计：一类改动一批（serves: FR-1, FR-2, FR-4）

按 refactor 档要求，**一次只改一类东西**，每批都能独立验证、独立回滚：

- **批 A（FR-2）消费方摘除**：外部① ② ③。
  验证：前端/客户端构建通过；`grep -rn 'api/memory'` 在三个仓源码中 0 命中；
  agent-dh 侧删掉注册行后重启，工具列表中不再出现 `memory_recall_audit`。
  ⚠️ 顺序上 A 必须**先于** B：否则 B 一落地，A 的三个消费方立刻变成指向 404 的活代码。
- **批 B（FR-1）v2 内删除**：注册点两处 → 端点两个 → 领域 `domain/memory/` → 仓储两个 → 测试 10 个。
  验证：判定 1~3 条（404 / 日志 / 收集 0）。
- **批 C（FR-4）叙述落档**：v2 侧文档注明"记忆不再由 v2 承载"（refactor 的归档去向 = architecture / work-logs）。
  验证：`wiki_probe.py` 无新增死链/孤儿。

三批之间**没有共享代码的新增**，因此任何一批卡住都不影响其余两批的完整性。

## 行为等价验证设计（serves: FR-1, FR-2）

删除**不是等价替换**，所以口径改造为「**非记忆能力等价**」——证明"除了记忆，别的没被碰坏"：

1. **删前取基线**：`GET /api/health`、`/api/stock/600519/klines`、`/api/simulation/accounts` 三个无关端点的
   状态码与响应形状；`pytest --collect-only | tail -1` 的用例总数；`restart-with-build.sh --verify-only` 四层结论。
2. **删后逐项比对**：三个端点状态码与形状不变；用例总数 = 基线 − `tests/domain/memory` 的用例数（差值可解释）；
   四层体检仍全过。
3. **反向断言**（防"删多了"）：`grep -rn 'MemoryService\|MemoryRepository\|memory_async' --include='*.py'`
   在 `domain/ application/ adapters/ infrastructure/` 中 0 命中——确保没有任何地方**仍在引用**被判死的符号。

## 验收口径（serves: FR-1, FR-2, FR-3, FR-4）

- 判定 1~4（见"目标与判定"）逐条可跑；
- 规范对照：[层边界只许向内](../../../../../agent-dh/docs/architecture/conventions.md#c-01)（`kb-conventions-c01`）
  —— 批 B 删掉的正是 `application→adapters` 方向违规；删后基线**只允许下降**，
  若上升说明删漏或引入了新违规，按失败处理；
- `./scripts/restart-with-build.sh --verify-only` 四层全过；
- `python3 agent-dh/scripts/wiki_probe.py` 无新增死链（批 C 的文档改动）。

## 风险与回滚（serves: FR-1, FR-3）

| 风险 | 处置 |
|---|---|
| 删多了（误伤同目录其它能力） | 批 B 的"反向断言"（0 命中即无残留引用）；删除按文件粒度提交，可 `git revert` 单批 |
| 删少了（有消费方没找到） | 判定 4 用**全仓 grep 断言 0 命中**兜底；"构建能过、点开才炸"正是本仓最反感的静默失败 |
| 与 REQ-261001145152-3982 的收尾相撞 | 只动记忆相关文件；`git status` 复核未触碰其文件 |
| 数据不可回滚 | 见 `migration.md`：**代码与数据分两步**，DROP 前先 dump |

## 范围变更设计：消费方迁移到 agent-os（serves: FR-5, FR-6）

**统一口径**：记忆能力归 agent 侧（agent-os `:8080`，契约见 `agent-os-client/src/memory-client.ts`）；
v2 只保留数据与量化。两处迁移都**只换数据源**，不新增能力。

### FR-5 · 看板 M6 探针（agent-dh）（serves: FR-5）

| 现状 | 改成 |
|---|---|
| `data-aggregation.ts` 的 `fetchMemoryToday()` 调 v2 `/api/memory/search?namespace=experience&limit=100` | 调 agent-os `GET /api/v1/memory?limit=100`，按 `created_at` 计当日新增 |
| 校验类型 `v2_memory_kind`（`types/index.ts:23`、`data-aggregation.ts:649`）与 `checkpoint-registry.ts:142` 的 M6 定义 | 改述为 agent-os 口径（**M6 指标保留**，不再指向 v2） |

**灰度/不变式**：agent-os 不可用时该探针必须**显式 degraded**（沿用既有 `errors.memory` 字段），
不得静默返回 0 —— 这正是本需求的教训（R-008 曾长期"测空气"）。

### FR-6 · agent-ts 记忆链路（4 处）（serves: FR-6）

| # | 现状 | 改成 |
|---|---|---|
| 1 | `provider-manager.ts:40` 首选 `V2MemoryProvider`，失败降 `FileFallbackProvider` | 首选 `AgentOSMemoryProvider`（同类下已存在），失败仍降 `FileFallbackProvider`；删 `v2-client.ts` 与其测试 |
| 2 | `infrastructure/tools/agent/recall-audit-tool.ts` 调 v2 3 个端点（list/stats/feedback） | 改走 agent-os（`infrastructure/agent-os/cli.ts:175` 的 `agentOSMemoryRecallAudit` 已在，可直接接） |
| 3 | `infrastructure/recall/audit-v2-client.ts` 写 v2 审计（带 JSONL 回退） | 写 agent-os；JSONL 回退保留（不可用时仍不丢审计） |
| 4 | `quant-v2-client.ts:487-489` 的 `memory_distill_inputs/candidates` + 周度 `weekly_memory_distill` | 蒸馏属**能力**：agent-os 若无对应端点则该任务**显式停用并留痕**（不静默失败），并在验证材料登记 |

**不变式**：agent-ts 对外行为（工具可用性、审计不丢）不退化；4 处改完后
`grep -rn 'api/memory' agent-ts/src` 必须为 0。
