# 记忆召回系统重设计 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 召回系统 DDD 重构：质量门 + XML 独立消息注入 + PG 审计闭环，彻底消除注入污染与噪音召回。

**Architecture:** 领域层纯逻辑（policy/quality-gate/XML 契约）→ 应用层 RecallService 编排 → SDK before_agent_start 扩展注入独立 CustomMessage；审计写 PG（v2 API），前端审计页 + agent 初标闭环。

**Tech Stack:** agent-ts (TypeScript/jest ESM) / quantsys-v2 (FastAPI/pytest/PG) / web-frontend (Vue3 Element Plus)

**Spec:** `docs/superpowers/specs/2026-08-13-memory-recall-redesign.md`（契约以此计划为准，计划比 spec 更细）

---

**全局执行顺序与并行图：[`2026-08-13-execution-order.md`](./2026-08-13-execution-order.md)**（双泳道：k3 + 单一执行模型；波次推进）

---

## 多模型执行使用说明（怎么把任务交给其他模型）

### 用法（每个任务一次）

1. 复制【通用执行规则】+ 对应任务的**完整内容**（Files/步骤/契约/验收全部），粘贴给一个**新开会话**的执行模型（Claude Code 切模型、或其他工具均可——提示词与工具无关，自带全部上下文）。
2. 执行模型干完会返回报告（分支名/文件清单/命令输出）。
3. 把报告交给 Claude（本会话）→ Claude 走【验收规程】→ 通过则合并，打回则带修改意见返工。

### 【通用执行规则】（每个提示词开头必附，逐字复制）

````
你在 /Users/yunpeng/pi-investment monorepo 工作。规则（违反=返工）：
1. 必须先建独立 worktree 再改代码：
   git worktree add .claude/worktrees/<任务编号> -b feat/<任务编号>
   cd 进去后立刻 git rebase main。禁止在主工作区直接改代码。
   agent-ts 测试前：ln -s /Users/yunpeng/pi-investment/agent-ts/node_modules agent-ts/node_modules
2. 只准创建/修改本任务【Files】列出的文件。发现必须改其他文件 → 停下来在报告里说明，不许自作主张。
3. 接口/schema/字段名/SQL 与本任务契约逐字一致。不许自创字段、不许"顺手改进"契约、不许重构无关代码。
4. 测试命令：agent-ts 必须 cd agent-ts && npm test -- <pattern>（裸 npx jest 会误报 TS1378）；
   v2 必须 cd quantsys-v2 && source venv/bin/activate && python -m pytest tests/<path> -x（自动切 quant_test 库，不会碰生产库）。
5. 涉及现有代码/生产数据/日志的断言，先读文件或查库验证再写。禁止凭印象描述代码行为。
6. 验收命令必须真跑，报告里贴完整输出（含通过数）。跑不过就停下来报告失败输出，不许跳过。
7. 完成后报告格式：分支名 / 改动文件清单 / 每条验收命令的输出 / 与契约的偏差（没有就写"无"）。
8. 不要执行 git push、不要合并回 main——验收由 Claude 做。
````

### 【Claude 验收规程】（每个其他模型任务回来后执行）

1. `git diff main...<分支> --stat` 核对只动了契约文件；
2. 接口/SQL/字段与计划逐字核对；
3. 亲自跑该任务全部验收命令；
4. 涉及生产事实的断言回查源头；
5. 通过 → merge-back 流程合并；不通过 → 列出具体偏差打回。

---

## 标记约定

**执行者标记**（每个任务标题内）：
- `【k3】` = Claude 亲做（架构判断/跨层契约/事实测量类，不委派）
- `【执行模型】` = 可委派其他模型执行（k3 按验收规程终审后合并）

**状态标记**（任务标题末尾，执行过程中更新）：
- `⬜` 未开始 ｜ `🔄` 进行中 ｜ `👀` 待 k3 验收 ｜ `✅` 验收通过已合并 ｜ `❌` 打回（附原因）

## 任务总览

| 任务 | 执行者 | 状态 | 依赖 |
|---|---|---|---|
| P0-T1 质量门（cosine_floor） | 执行模型 | ✅（r2 重发后通过 fb220b1） | 无 |
| P0-T2 floor 分布测量定值 | **k3** | ✅（floor=0.58，见 spec §6.1） | 无 |
| P0-T3 env 接线+重启验证 | 执行模型 | ⬜ | P0-T1 合并 + P0-T2 出值 |
| P1-T1 领域层四文件 | 执行模型 | ✅ | 无 |
| P1-T2 RecallService+端口 | **k3** | ✅ d74f212 | P1-T1 |
| P1-T3 审计适配器 | 执行模型 | ⬜ | P1-T2 |
| P1-T4 v2 审计 API+PG 表 | 执行模型 | ✅ | 无 |
| P1-T5 前端审计页 | 执行模型 | ✅（代码级；真机验收待批次3部署） | P1-T4（最终验收） |
| P2-T1 SDK 扩展接线 | **k3** | ⬜ | P1-T1~T3 合并 |
| P2-T2 删 wrapper 注入 | **k3** | ⬜ | P2-T1 |
| P2-T3 全通道验收 | **k3** | ⬜ | P2-T2 |

---

## 并行执行图

```
轨道A (其他模型, v2):    P0-T1 → P0-T3
轨道B (Claude, 测量):    P0-T2  ──────────────── 随时可做，产出 floor 终值 → 喂给 P0-T3
轨道C (其他模型→Claude): P1-T1 → P1-T2(Claude) → P1-T3
轨道D (其他模型, v2):    P1-T4
轨道E (其他模型, 前端):  P1-T5（契约已冻结可立即开工，最终验收依赖 P1-T4 部署）
轨道F (Claude, 接线):    P2-T1 → P2-T2 → P2-T3（等 C/D 完成）

A ∥ B ∥ C ∥ D ∥ E 全部可并行开工（文件不相交，见各任务 Files）。
并行安全约定：P0-T1 独占 domain/memory/service.py 改动权；P1-T4 禁止碰 service.py/hybrid_search.py。
```

---

## P0：v2 质量门

### P0-T1：hybrid_search 加 cosine_floor + 空结果语义【执行模型｜轨道A｜✅ fb220b1（r2）】

**Files:**
- Modify: `quantsys-v2/domain/memory/hybrid_search.py`
- Modify: `quantsys-v2/domain/memory/service.py`（仅 hybrid_search 方法签名与调用）
- Test: `quantsys-v2/tests/domain/memory/test_hybrid_search.py`（已存在则追加，不存在则创建）

**契约（逐字）：**
- `vector_rank(query_embedding, items, cosine_floor=0.0)` — 新增第三参数，只保留 `sim >= cosine_floor` 的条目；`cosine_floor=0.0` 时行为与现状完全一致（向后兼容）。
- `hybrid_rank(query, items, query_embedding, limit, cosine_floor=0.0)` — 新增第五参数透传给 vector_rank。
- `MemoryService.hybrid_search(..., limit=20)` — 内部调用 `hybrid_rank(..., cosine_floor=_load_cosine_floor())`；`_load_cosine_floor()` 读 `os.environ.get("MEMORY_RECALL_COSINE_FLOOR", "0.30")` 转 float，解析失败回退 0.30。
- 空结果语义现已存在（`strategy="none"` 分支），本任务不改。

- [ ] **Step 1: 写失败测试**

在 `tests/domain/memory/test_hybrid_search.py` 追加：

```python
from domain.memory.hybrid_search import vector_rank, hybrid_rank


def _item(i, emb):
    return {"id": i, "title": f"t{i}", "content": f"c{i}", "embedding": emb}


class TestCosineFloor:
    def test_below_floor_filtered(self):
        # 查询向量 [1,0]；item1 同向 sim=1.0，item2 正交 sim=0.0
        items = [_item(1, [1.0, 0.0]), _item(2, [0.0, 1.0])]
        ranked = vector_rank([1.0, 0.0], items, cosine_floor=0.30)
        assert [r["id"] for r in ranked] == [1]

    def test_floor_zero_backward_compatible(self):
        items = [_item(1, [1.0, 0.0]), _item(2, [0.0, 1.0])]
        ranked = vector_rank([1.0, 0.0], items, cosine_floor=0.0)
        assert len(ranked) == 2

    def test_default_floor_keeps_old_behavior(self):
        # 不传 cosine_floor = 0.0，与现状一致
        items = [_item(1, [1.0, 0.0]), _item(2, [0.0, 1.0])]
        assert len(vector_rank([1.0, 0.0], items)) == 2

    def test_hybrid_rank_threads_floor(self):
        # 向量无一过线且 BM25 零命中 → none
        items = [_item(1, [0.0, 1.0])]
        result = hybrid_rank("完全无关的词xyz", items, [1.0, 0.0], 5, cosine_floor=0.30)
        assert result["strategy"] == "none"
        assert result["items"] == []
```

注：embedding 字段格式以 `parse_embedding` 接受的为准（先读 `hybrid_search.py:61` 的 `parse_embedding` 确认是 list 还是 JSON 字符串，测试按实际格式构造——这是本任务唯一允许你读了再定的点）。

- [ ] **Step 2: 跑测试确认失败**

Run: `cd quantsys-v2 && source venv/bin/activate && python -m pytest tests/domain/memory/test_hybrid_search.py -x -q`
Expected: FAIL（`vector_rank() got an unexpected keyword argument 'cosine_floor'`）

- [ ] **Step 3: 实现**

`hybrid_search.py`：
- `vector_rank` 签名加 `cosine_floor: float = 0.0`，`ranked.append` 前加 `if sim < cosine_floor: continue`。
- `hybrid_rank` 签名加 `cosine_floor: float = 0.0`，调用 `vector_rank(query_embedding, items, cosine_floor)`。

`service.py` `hybrid_search` 方法内：

```python
import os  # 文件顶部如已有则跳过

def _load_cosine_floor() -> float:
    try:
        return float(os.environ.get("MEMORY_RECALL_COSINE_FLOOR", "0.30"))
    except ValueError:
        return 0.30
```

调用处改为 `hybrid_rank(q, candidates, query_embedding, limit, cosine_floor=_load_cosine_floor())`。

- [ ] **Step 4: 跑测试确认通过 + 全量回归**

Run: `python -m pytest tests/domain/memory/ -x -q`
Expected: 全过（含已有测试）
Run: `python -m pytest tests/ -q`（v2 全量，对照基线：已知预存在失败清单见 MEMORY「Baseline Failing Tests」，只允许基线失败）

- [ ] **Step 5: Commit（worktree 内，不 push）**

```bash
git add quantsys-v2/domain/memory/hybrid_search.py quantsys-v2/domain/memory/service.py quantsys-v2/tests/domain/memory/test_hybrid_search.py
git commit -m "feat(memory): vector_rank/hybrid_rank 增加 cosine_floor 质量门（默认0.30, env可调）"
```

---

### P0-T2：生产语料分数分布测量，定 floor 终值【k3｜轨道B｜✅ floor=0.58】

**Files:** 无代码改动（只读分析 + 结论回写 spec §6）

- [ ] **Step 1:** 写一次性脚本（/tmp，不进仓库）：从 PG `quant.memories` 取全部 active 条目的 embedding，用 50 条真实 query（从 SDK 会话日志 `~/.pi/agent/sessions/--Users-yunpeng-pi-investment-agent-ts--/*.jsonl` 提取近期用户消息）计算 cosine 分布。
- [ ] **Step 2:** 按"相关/不相关"人工标注 20 条样本对的分数分界，选 precision≥0.8 的 floor 候选。
- [ ] **Step 3:** 结论（分布数据 + 选定 floor + 理据）回写 spec §6 与 P0-T3 的 env 值。
验收：分析报告附数据；floor 不是拍的。

---

### P0-T3：env 接线与生产重启验证【执行模型｜轨道A｜⬜｜依赖 P0-T1+P0-T2】

- [ ] **Step 1:** `quantsys-v2/.env` 加 `MEMORY_RECALL_COSINE_FLOOR=0.58`（P0-T2 终值，见 spec §6.1；.env 不入库，只改本地；同时更新 `.env.example` 加注释行）。
- [ ] **Step 2:** 重启 5001：`launchctl kickstart -k gui/501/com.pi-investment.v2-api`（日志 `~/v2-api.log`）。
- [ ] **Step 3:** 实测：`curl -s "http://127.0.0.1:5001/api/memory/search?q=中国铝业股息" | python3 -m json.tool | head -30`，确认返回含 `strategy` 字段且低相关条目被过滤；再 `curl` 一个无关词确认 `strategy:"none"` 或空 items。
验收：两次 curl 输出贴报告。

---

## P1：agent-ts 领域层 + 应用层 + 审计

### P1-T1：领域层四文件（纯函数，零 IO）【执行模型｜轨道C｜✅ 9d706d6】

**Files:**
- Create: `agent-ts/src/domain/recall/types.ts`
- Create: `agent-ts/src/domain/recall/policy.ts`
- Create: `agent-ts/src/domain/recall/quality-gate.ts`
- Create: `agent-ts/src/domain/recall/recall-message.ts`
- Test: `agent-ts/src/domain/recall/__tests__/policy.test.ts`、`quality-gate.test.ts`、`recall-message.test.ts`

**契约（逐字——类型定义是后续所有任务的基准，一个字符都不许改）：**

```typescript
// types.ts
export type RecallFlow =
  | 'interactive-chat'
  | 'skill-invocation'
  | 'scheduled-task'
  | 'wake-event';

export interface RecallContext {
  flow: RecallFlow;
  rawText: string;        // 用户原文（skill 展开前）
  sessionId?: string;
}

export interface PolicyDecision {
  enabled: boolean;
  topK: number;
  charBudget: number;
  reason?: string;        // enabled=false 时必填
}

export interface RecallHit {
  id: number;
  score: number;
  source: 'bm25' | 'vector' | 'both';
  bm25Score?: number;
  vectorScore?: number;
  title?: string;
  content: string;
}

export type GateResult =
  | { gate: 'passed'; hits: RecallHit[] }
  | { gate: 'suppressed'; reason: 'policy-disabled' | 'empty-result' | 'below-floor' };

export interface RecallMessage {
  customType: 'recalled-memory';
  content: string;        // XML
  display: false;
  details: { flow: RecallFlow; count: number };
}
```

```typescript
// policy.ts — 策略表（声明式，唯一事实源）
import type { PolicyDecision, RecallFlow } from './types.js';

const POLICY_TABLE: Record<RecallFlow, { enabled: boolean; topK: number; charBudget: number }> = {
  'interactive-chat': { enabled: true, topK: 3, charBudget: 2000 },
  'skill-invocation': { enabled: true, topK: 2, charBudget: 1000 },
  'scheduled-task':   { enabled: true, topK: 3, charBudget: 2000 },
  'wake-event':       { enabled: true, topK: 2, charBudget: 1000 },
};

export function decidePolicy(flow: RecallFlow): PolicyDecision {
  const row = POLICY_TABLE[flow];
  if (!row) return { enabled: false, topK: 0, charBudget: 0, reason: 'unknown-flow' };
  return row.enabled
    ? { enabled: true, topK: row.topK, charBudget: row.charBudget }
    : { enabled: false, topK: 0, charBudget: 0, reason: 'policy-disabled' };
}
```

```typescript
// quality-gate.ts
import type { GateResult, RecallHit } from './types.js';

export function applyQualityGate(hits: RecallHit[]): GateResult {
  if (hits.length === 0) return { gate: 'suppressed', reason: 'empty-result' };
  return { gate: 'passed', hits };
}
// 注：分量阈值（BM25>0 / cosine floor）在 v2 检索侧已过滤；
// 本门负责"空则不注入"语义 + 未来扩展（如 source 加权）的单点。
```

```typescript
// recall-message.ts
import type { RecallFlow, RecallHit, RecallMessage } from './types.js';

function escapeXml(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

export function formatRecallMessage(flow: RecallFlow, hits: RecallHit[], charBudget: number): RecallMessage {
  const parts: string[] = [];
  let total = 0;
  const used: RecallHit[] = [];
  for (const h of hits) {
    const block = `  <memory id="${h.id}" relevance="${h.score.toFixed(2)}" source="${h.source}">${escapeXml(h.content)}</memory>`;
    if (total + block.length > charBudget) break;
    parts.push(block);
    total += block.length;
    used.push(h);
  }
  const content =
    `<recalled_memory source="auto-prefetch" flow="${flow}" count="${used.length}" gate="passed">\n` +
    parts.join('\n') +
    `\n</recalled_memory>`;
  return {
    customType: 'recalled-memory',
    content,
    display: false,
    details: { flow, count: used.length },
  };
}
```

- [ ] **Step 1:** 写三个测试文件（每个函数至少：正常例 + 边界例）。必须包含：
  - `decidePolicy`：四种 flow 各一条断言（topK/预算与策略表一致）；
  - `applyQualityGate`：空数组 → suppressed/empty-result；非空 → passed 且 hits 原样；
  - `formatRecallMessage`：① XML 结构断言（含 `count="2"`、`gate="passed"`、两个 `<memory`）；② 转义例（content 含 `<买卖> & "止损"` → 断言转义后无裸 `<`）；③ 预算截断例（charBudget=50 时只放第一条）。
- [ ] **Step 2:** `cd agent-ts && npm test -- domain/recall` 确认失败（模块不存在）。
- [ ] **Step 3:** 按上面契约实现四个文件（逐字，不许改名）。
- [ ] **Step 4:** `npm test -- domain/recall` 全过。
- [ ] **Step 5:** Commit：`feat(recall): 领域层——策略表/质量门/XML 消息契约（纯函数）`。

---

### P1-T2：RecallService 编排 + 端口接口【k3｜轨道C｜✅ d74f212】

**Files:**
- Create: `agent-ts/src/services/recall/ports.ts`
- Create: `agent-ts/src/services/recall/recall-service.ts`
- Test: `agent-ts/src/services/recall/recall-service.test.ts`

**端口契约：**

```typescript
// ports.ts
import type { GateResult, RecallContext, RecallHit, RecallMessage } from '../../domain/recall/types.js';

export interface RecallSearchPort {
  search(query: string, limit: number): Promise<RecallHit[]>;
}

export interface RecallAuditPort {
  record(decision: {
    ts: string; sessionId?: string; flow: string; queryText: string;
    strategy: string; degraded: boolean;
    gateResult: 'passed' | 'suppressed'; suppressReason?: string;
    hits: Array<{ memoryId: number; score: number; source: string; bm25Score?: number; vectorScore?: number }>;
  }): Promise<void>;  // 实现必须 fire-and-forget 友好（内部 catch，不抛）
}
```

- [ ] 编排：`RecallService.recall(ctx: RecallContext): Promise<RecallMessage | null>` — decidePolicy（disabled→审计+null）→ search → applyQualityGate（suppressed→审计+null）→ formatRecallMessage → 审计 passed → 返回消息。检索异常 → catch 后审计 `empty-result` + 返回 null（绝不阻塞对话）。
- [ ] 测试：mock 两个端口，覆盖五路径（policy-disabled / empty / passed / search 抛错 / 审计抛错不影响返回）。
- [ ] 验收：`npm test -- services/recall` 全过。

---

### P1-T3：审计适配器两个【执行模型｜轨道C｜⬜｜依赖 P1-T2】

**Files:**
- Create: `agent-ts/src/infrastructure/recall/audit-v2-client.ts`
- Create: `agent-ts/src/infrastructure/recall/audit-jsonl-fallback.ts`
- Test: `agent-ts/src/infrastructure/recall/audit-adapters.test.ts`

**契约：**
- `createRecallAuditPort(): RecallAuditPort` — 组合适配器：先 POST `${QUANTSYS_V2_API_URL}/api/memory/recall-audit`（fetch，3s timeout），失败降级追加 `{PI_INVEST_DIR 或 .pi-invest}/recall-audit.jsonl`；两者都失败只 `console.warn`，**永不抛出**。
- POST body 与 P1-T4 的 API 契约逐字一致（见 P1-T4）。
- [ ] 测试：mock fetch——① 成功直写；② fetch  reject → JSONL 有记录；③ JSONL 也失败 → 不抛。PI_INVEST_DIR 用临时目录（参照 evolution-test-hermetic-fix 的 env 覆盖模式）。
- [ ] 验收：`npm test -- infrastructure/recall` 全过。

---

### P1-T4：v2 审计 API + PG 表【执行模型｜轨道D｜✅ 23f55d6】

**Files:**
- Create: `quantsys-v2/infrastructure/persistence/migrations/create_memory_recall_audit_table.sql`
- Create: `quantsys-v2/adapters/outbound/repositories/memory_recall_audit_repository.py`
- Modify: `quantsys-v2/adapters/inbound/fastapi_app/routes/memory_async.py`（仅追加路由，禁止动既有路由和 service.py/hybrid_search.py）
- Test: `quantsys-v2/tests/domain/memory/test_recall_audit_routes.py`

**SQL 契约（逐字）：**

```sql
CREATE TABLE IF NOT EXISTS quant.memory_recall_audit (
  id BIGSERIAL PRIMARY KEY,
  ts TIMESTAMPTZ NOT NULL,
  session_id TEXT,
  flow TEXT NOT NULL,
  query_text TEXT,
  strategy TEXT,
  degraded BOOLEAN DEFAULT FALSE,
  gate_result TEXT NOT NULL,
  suppress_reason TEXT,
  hits JSONB NOT NULL DEFAULT '[]',
  created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_recall_audit_ts ON quant.memory_recall_audit (ts DESC);
CREATE INDEX IF NOT EXISTS idx_recall_audit_flow ON quant.memory_recall_audit (flow);
```

**API 契约（逐字）：**

```
POST /api/memory/recall-audit
  Body: {"ts","session_id","flow","query_text","strategy","degraded","gate_result","suppress_reason","hits":[...]}
  → 201 {"id": N}；校验：flow/gate_result 非空，缺 → 422
GET  /api/memory/recall-audit?flow=&gate_result=&date_from=&date_to=&suppressed_only=&page=&page_size=
  → {"items":[...], "total": N}（按 ts DESC 分页）
GET  /api/memory/recall-audit/stats?date_from=&date_to=
  → {"total": N, "injected": N, "suppressed": N, "injection_rate": 0.xx,
     "by_flow": {flow: {"total","injected","suppressed"}},
     "suppress_reasons": {reason: N},
     "score_histogram": [{"bucket":"0.0-0.1","count":N}, ...]}  -- 统计 hits[].score 分布，桶宽 0.1
POST /api/memory/recall-audit/{audit_id}/feedback
  Body: {"memory_id": N, "feedback": "relevant"|"irrelevant", "feedback_by": "human"|"agent"}
  → 更新 hits 数组中对应 memory_id 的元素，补 feedback/feedback_by/feedback_at=now()；
    human 覆盖 agent 允许，agent 覆盖 human 拒绝（409）
```

- [ ] **Step 1:** pytest 先写（TestClient）：POST 201/422、GET 分页筛选、stats 聚合数对、feedback 四条（human/agent/覆盖/409）。参照 `tests/domain/memory/test_routes.py` 现有模式。
- [ ] **Step 2:** 跑确认 404/失败。
- [ ] **Step 3:** 实现 migration + repository（JSONB hits 更新用 `jsonb_set` 或读改写均可，测试锁住行为即可）+ 4 条路由。
- [ ] **Step 4:** `python -m pytest tests/domain/memory/ -x -q` 全过。
- [ ] **Step 5:** 手动跑 migration 到 quant_investment（生产）与 quant_test：`psql -d quant_investment -f .../create_memory_recall_audit_table.sql`（测试库 pytest 会自建？——不，migration 需手动对两个库各跑一次，报告贴 \d 输出）。
- [ ] **Step 6:** Commit：`feat(memory): 召回审计 PG 表 + v2 API（写入/分页/聚合/标注）`。

---

### P1-T5：前端「召回审计」tab【执行模型｜轨道E｜✅ fae330d（主工作区打捞）｜真机验收待批次3】

**Files:**
- Modify: `web-frontend/src/services/api/memory.ts`（追加 audit API 函数）
- Create: `web-frontend/src/views/Memory/RecallAudit.vue`
- Modify: `web-frontend/src/views/Memory/index.vue`（加 tab）

**契约：**
- api 层（注意 apiClient 拦截器已解包 `{success,data}` 信封——函数直接返回解包后数据，参照该文件现有函数）：

```typescript
// 追加到 services/api/memory.ts
export interface RecallAuditItem { /* id, ts, session_id, flow, query_text, strategy,
  degraded, gate_result, suppress_reason, hits: Array<{memory_id, score, source,
  bm25_score?, vector_score?, feedback?, feedback_by?}> */ }
export function getRecallAudit(params: {...}): Promise<{items: RecallAuditItem[]; total: number}>
export function getRecallAuditStats(params: {date_from?: string; date_to?: string}): Promise<{...stats 契约见 P1-T4}>
export function postRecallAuditFeedback(auditId: number, body: {memory_id: number; feedback: 'relevant'|'irrelevant'; feedback_by: 'human'}): Promise<any>
```

- 页面 RecallAudit.vue：① 统计卡片（总数/注入率/抑制率 + suppress_reasons 列表）；② el-table 审计列表（时间/flow/query 摘要/gate_result/命中数，suppressed 行 class=灰色）；③ 行展开显示 hits（score/source/内容摘要/👍👎按钮调 feedback API，feedback_by='human'）；④ 筛选栏（flow 下拉/gate_result 下拉/日期范围/仅抑制 switch）。
- [ ] 验收（Claude 执行 gstack 或手动）：`cd web-frontend && npm run dev` 起页面真实截图；feedback 按钮点击后 PG 里 hits 对应元素有 `feedback_by:"human"`。**禁止用 mock 数据充验收**。

---

## P2：SDK 扩展接线（全部 Claude 亲做）

### P2-T1：sdk-recall-extension【k3｜轨道F｜⬜｜依赖 P1-T1~T3 合并】

**Files:**
- Create: `agent-ts/src/api/extensions/recall-extension.ts`
- Modify: `agent-ts/src/api/extensions/model-command.ts`（extensionFactories 数组追加 recallExtension）
- Test: `agent-ts/src/api/extensions/recall-extension.test.ts`

**契约：**
- `recallExtension: ExtensionFactory`：
  - `input` 事件 handler：暂存 `event.text`（skill 展开前原文）到闭包变量；
  - `before_agent_start` handler：用暂存原文构建 RecallContext（flow 判定：`input` 来源 + 暂存文本是否 `/skill:` 开头 → skill-invocation；options.skipSkillRouting 类机器消息 → scheduled-task/wake-event，**实施时先打日志实测各通道的 InputSource 值再定判定表，写进代码注释**）→ `RecallService.recall` → 非 null 则返回 `{ message: { customType: 'recalled-memory', content, display: false, details } }`；
  - 全程 try/catch，异常只 console.warn 返回 void（绝不阻塞对话）。
- [ ] 测试：fake pi 对象注册 handler，模拟 input→before_agent_start 序列：① 普通对话产出 message；② `/skill:x` 文本 → query 不含 skill 前缀；③ 检索空 → 返回 void。
- [ ] 真机验证：重启 agent，TUI 发一条普通消息 → PG 审计表有 `interactive-chat` 记录；`/provider pro` → 无新审计记录（结构免疫实证）；会话日志里召回以独立消息存在而非拼接。

### P2-T2：删除 wrapper 注入代码【k3｜轨道F｜⬜】

**Files:** Modify `agent-ts/src/infrastructure/session/session-factory.ts`（删 W1.4 注入块；路由基于原文的判定保留）+ 同步更新 `session-factory.test.ts`（注入相关 3 个测试迁移到 recall-extension.test.ts 形态）。
- [ ] 验收：`npm test -- session-factory` + `npm test` 全量（对照基线）。

### P2-T3：全通道验收【k3｜轨道F｜⬜】
- [ ] 调度任务真触发一次（或 scheduler_manage 手动 trigger）→ 审计表 `scheduled-task` 记录；
- [ ] wake 事件真触发一次 → `wake-event` 记录；
- [ ] 三通道记录截图/查询结果归档到 PR 描述。

---

## Self-Review 记录

- Spec 覆盖：§4 策略表→P1-T1；§5 XML→P1-T1+P2-T1；§6 质量门→P0；§8.1 表→P1-T4；§8.2 API→P1-T4；§8.3 前端→P1-T5；§8.4 agent 协助→依赖三 Agent 计划的 A1（本计划不含，接口已对齐 `recall_audit` 工具读 API）。
- 已知留白（有意）：P2-T1 的 flow 判定表需实测定 InputSource——已在任务内标注为"先实测再定"，非占位符。
- 类型一致性：RecallHit/GateResult/RecallMessage 在 T1/T2/T3/T5 间逐字一致。
