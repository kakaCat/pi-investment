# 记忆召回系统重设计（Memory Recall Redesign）

- 日期：2026-08-13
- 状态：待评审
- 关联：`2026-08-13-agent-domain-split.md`（记忆 Agent 职责在此定义召回审计职责的归属）

---

## 1. 背景与事故史

W1.4 记忆召回注入（`session-factory.ts` wrapSessionWithLogger）上线后连续事故：

1. **2026-08-13 `/provider` 参数污染**（7c692a0 已修）：召回记忆以 `<recalled_memory>` 块字符串拼接到用户消息尾部，slash 命令 args 被污染，`/provider pro` 报"未知目标"。
2. **2026-08-13 技能路由误触发/误抑制**（1bba7e8 已修）：注入发生在路由判定之前，召回记忆里的交易关键词（止损/买入/加仓/股票代码）参与路由打分——"帮我分析一下贵州茅台600519的走势"被误路由到 portfolio-entry。
3. **召回内容质量差**（本设计的主攻问题）：生产日志实证，relevance 0.02~0.03 的噪音（K线契约/止损规则/策略体检）被硬塞进 top-3 注入；"中国铝业股息多少"召回出机器人产业分析。

两个 hotfix 是豁免清单式打地鼠。根本问题：召回的**何时（控制）、召回什么（检索）、够不够格（质量）、怎么进上下文（注入）、效果如何（验证）**五个职责纠缠在一个 wrapper 里，且只有 TUI 主会话有召回（调度/wake/飞书没有）。

## 2. 现状解剖

| 职责 | 现状位置 | 问题 |
|---|---|---|
| 何时召回 | `wrapSessionWithLogger`（仅 TUI 主会话） | 调度任务（start-headless 明确不经 wrapper）、wake、飞书无召回 |
| 召不召回 | 硬编码 `startsWith('/')`、`forcedSkill`、`skipSkillRouting` | 业务规则长在控制流里 |
| 检索 | v2 `domain/memory/hybrid_search.py`（BM25 jieba + bge-m3 + RRF） | `vector_rank` 无余弦下限；RRF 是名次分不是相关度分；`prefetch` 无门槛硬塞 top-3 |
| 注入 | 字符串拼接进用户消息 | 污染一切下游文本消费者 |
| 验证 | 无 | 召回决策零审计 |

另：`core/agent/system-prompt.ts:114` 留好了 `recalledMemory` 参数（原设计：会话开始召回进系统提示词 Memory 层双缓冲），从未接线——本设计不启用该路径（见 §7 决策记录）。

## 3. 目标架构（DDD 四层）

```
┌─ 控制流（SDK 事件层，只触发，不做业务判断）──────────────────┐
│  before_agent_start 扩展事件（slash 命令结构性不到这层）       │
│  input 事件（暂存 skill 展开前的用户原文，供 query 构建）      │
└──────────────────────┬──────────────────────────────────────┘
                       ↓ RecallContext{flow, rawText, sessionId}
┌─ 应用层 RecallService（编排，无业务规则本体）────────────────┐
│  流程识别 → Policy 判定 → query 构建 → 检索 → 质量门          │
│  → XML 格式化 → 注入 → 审计                                  │
└──────┬──────────────┬──────────────┬────────────────────────┘
       ↓              ↓              ↓
┌─ 领域层（纯逻辑，零 IO，100% 可测）──────────────────────────┐
│  RecallPolicy（策略表） QualityGate（过门判定+抑制原因）      │
│  RecallMessage + formatRecallXml（表示契约）                 │
└─────────────────────────────────────────────────────────────┘
       ↓ MemorySearchPort   ↓ RecallInjectionPort   ↓ RecallAuditPort
   （已存在 port.ts）     （新：带外消息投递）     （新：PG 主写 + JSONL 降级）
```

**解耦核心**：SDK 事件层只把 `{flow, rawText}` 交给 RecallService；该不该召回、召回多少、什么格式、够不够格全部是领域层声明式规则。新增流程 = 策略表加一行，不改控制流。

代码落位（agent-ts）：
```
src/domain/recall/            # 领域层（新）
  types.ts                    # RecallFlow / RecallContext / RecallDecision / RecallMessage
  policy.ts                   # 策略表 + 判定
  quality-gate.ts             # 过门判定
  recall-message.ts           # XML 格式化
src/services/recall/
  recall-service.ts           # 应用层编排
  ports.ts                    # Injection / Audit 端口接口
src/infrastructure/recall/    # 适配器（新）
  sdk-recall-extension.ts     # before_agent_start + input 事件扩展
  audit-v2-client.ts          # PG 主写适配器（POST /api/memory/recall-audit）
  audit-jsonl-fallback.ts     # 本地 JSONL 降级
```

## 4. 流程策略表（RecallPolicy）

| flow | 召回 | query 来源 | topK | 字符预算 | 注入 |
|---|---|---|---|---|---|
| `interactive-chat` | ✅ | 用户原文 | 3 | 2000 | 独立消息 |
| `skill-invocation`（显式+强制路由） | ✅ | 用户原文（剥 `/skill:` 前缀与 skill 正文） | 2 | 1000 | 独立消息 |
| `scheduled-task` | ✅ | 任务 prompt | 3 | 2000 | 独立消息 |
| `wake-event` | ✅ | 唤醒事件文本 | 2 | 1000 | 独立消息 |
| `slash-command` | ❌ 结构免疫 | — | — | — | — |

flow 识别规则（SDK 事件层事实，非猜测）：
- SDK `prompt()` 先尝试扩展命令（`/provider` 等 registered command）→ 直接返回，**不会**触发 `before_agent_start` → slash 命令结构免疫，无需豁免判断。
- `/skill:x args` 不是 registered command → 走到 skill 展开 → 进 agent 循环 → 触发 `before_agent_start`。query 必须用展开前原文：扩展内在 `input` 事件（展开前触发）暂存原文，`before_agent_start` 时使用。
- `skipSkillRouting` 的机器消息（调度/事件）→ flow=scheduled-task/wake-event，由调用方在 PromptOptions 传入或在扩展内按来源判定。**具体判定字段在 P1 实施时以 `InputSource`（interactive/rpc/extension）+ options 实测确定并写进代码注释**。

## 5. 注入契约（XML + 独立消息）

注入为 SDK CustomMessage（`before_agent_start` 返回 `message`），**不拼接进用户文本**：

```typescript
{
  role: "custom",              // convertToLlm 转为独立 user 消息
  customType: "recalled-memory",
  display: false,              // TUI 不渲染
  content: <XML 见下>,
  details: { flow, gate, hits } // 结构化数据，供调试
}
```

content XML 契约：

```xml
<recalled_memory source="auto-prefetch" flow="interactive-chat" count="2" gate="passed">
  <memory id="123" relevance="0.61" source="both">记忆内容</memory>
  <memory id="456" relevance="0.48" source="bm25">记忆内容</memory>
</recalled_memory>
```

契约约束（测试锁定）：
- `count` = 实际 `<memory>` 子元素数；`gate="passed"` 时才产生注入消息。
- 抑制时**不产生注入消息**，只落审计（`gate="suppressed:<reason>"`）。
- XML 转义：记忆内容含 `<>&"` 必须转义（用现成 escape 工具或手写四字符替换，测试覆盖）。

## 6. 质量门（QualityGate）

v2 侧（`quantsys-v2/domain/memory/hybrid_search.py`）：
1. `vector_rank` 增加余弦下限参数 `cosine_floor`：低于 floor 的条目不进入向量排名。
2. `hybrid_rank` 空结果语义：BM25 零命中且向量无一过线 → `strategy="none"`，返回空 items。
3. floor 来源：环境变量 `MEMORY_RECALL_COSINE_FLOOR`，默认 0.30；**最终值 0.58**（2026-08-13 生产语料分布测量确定，见下方测量记录 §6.1）。

agent-ts 侧（`domain/recall/quality-gate.ts`）：
- 输入：检索响应 items（含 score/source/bm25_score/vector_score）。
- 规则：策略允许 + 有 hits + gate 判定 passed → 注入；否则 suppressed 并给出原因（`policy-disabled` / `empty-result` / `below-floor`）。
- RRF 分是名次分，**不作为**阈值依据；阈值只在分量信号上（BM25>0 已有、cosine≥floor 新增）。

### 6.1 floor 终值测量记录（2026-08-13 P0-T2）

**测量对象**：43 条 active 记忆 × 50 条真实 query（从 SDK 会话日志 `~/.pi/agent/sessions/--Users-yunpeng-pi-investment-agent-ts--/*.jsonl` 提取近期用户消息，剥离 scheduled 提示词/skill 前缀/recalled_memory 注入），共 2150 个 cosine 对。

**全量 cosine 分布**（bge-m3，同域金融语料）：

| 分位 | 值 | | 阈值 | 通过对占比 |
|---|---|---|---|---|
| min | 0.208 | | ≥0.50 | 9.1% |
| p50 | 0.408 | | ≥0.55 | 2.4% |
| p90 | 0.497 | | ≥0.58 | 0.8% |
| p95 | 0.522 | | ≥0.60 | 0.4% |
| max | 0.650 | | | |

**关键事实**：spec §1 所述「relevance 0.02~0.03 的噪音」是 **RRF 名次分**（1/(60+rank)≈0.016~0.03），与 cosine 完全不同尺度。bge-m3 在同域金融语料下 cosine 基线高达 0.2~0.65，**默认 0.30 实为 no-op**（仅 8/2150 对 < 0.30，位于全分布 p1 以下）。

**人工标注 24 对（9 相关 / 15 不相关）**：相关对聚簇 0.584~0.650（中位 ~0.60，如「歌尔股份→盯盘规则 0.608」「今世缘→T+1 0.584」「机器人产业→机器人分析 0.650」）；噪音对聚簇 0.406~0.576（中位 ~0.46，如「三花智控→chan_3买 0.576」「招商银行→杭州银行交易 0.551」「移动→盯盘规则 0.552」）。

**precision@floor**：0.50→0.64；0.55→0.73；0.56→0.89；0.58→1.0。灰区 0.55~0.58 内仅一条边界噪音（chan 通用买点 0.576）与一条边界相关（今世缘 0.584）交错——相关/噪音 crossover 恰在 0.576~0.584 之间。

**结论：floor = 0.58**（满足 precision≥0.8，且落在 crossover 缝隙处，代价是牺牲 0.52~0.58 的弱语义命中如「行业机会→market style 0.516」，由 BM25 回补词法命中）。0.55 为 precision 不达标的低边界，仅作参考。P3 观察期凭真实标注集离线重放再调。

## 7. 决策记录

- **不启用 system-prompt 的 recalledMemory 路径**：逐消息召回用 before_agent_start 独立消息覆盖；会话开始的双缓冲召回留作后续优化（非本 spec 范围），`recalledMemory` 参数保留不动。
- **不删除路由判定基于原文的修复**（1bba7e8）：该逻辑正确，P2 删的仅是 wrapper 里的注入代码。
- **审计存 PG 不存 JSONL**：PG 是唯一事实源（前端/API/agent 三方消费）；JSONL 仅降级。

## 8. 审计闭环

### 8.1 表结构（PG，`quant.memory_recall_audit`）

```sql
id BIGSERIAL PRIMARY KEY
ts TIMESTAMPTZ NOT NULL           -- 召回时间
session_id TEXT                   -- 会话
flow TEXT NOT NULL                -- interactive-chat / skill-invocation / scheduled-task / wake-event
query_text TEXT                   -- 检索 query（截断 500）
strategy TEXT                     -- hybrid / bm25 / vector / none
degraded BOOLEAN                  -- embedding 不可用
gate_result TEXT NOT NULL         -- passed / suppressed
suppress_reason TEXT              -- policy-disabled / empty-result / below-floor
hits JSONB NOT NULL DEFAULT '[]'  -- [{memory_id, score, source, bm25_score, vector_score,
                                  --   feedback, feedback_by, feedback_at}]
created_at TIMESTAMPTZ DEFAULT now()
```

- `feedback`: `relevant` / `irrelevant` / NULL；`feedback_by`: `human` / `agent`。
- **bm25_score/vector_score 原始分必须存**——调 floor 时离线重放，无需重跑检索。

### 8.2 API（v2 FastAPI，`adapters/inbound/fastapi_app/routes/memory_async.py` 扩展）

```
POST /api/memory/recall-audit            写入一条审计（agent-ts 调用）
GET  /api/memory/recall-audit            分页+筛选：flow / gate_result / 日期范围 / 仅抑制 / 仅👎 / 仅人机冲突 / 仅待复核
GET  /api/memory/recall-audit/stats      聚合：注入率、抑制率（按原因）、分数分布直方图、按 flow 分组
POST /api/memory/recall-audit/{id}/feedback  标注：{memory_id, feedback, feedback_by}
```

### 8.3 前端（web-frontend Memory 页新 tab「召回审计」）

- 统计卡片区：召回次数、注入率、抑制率（按原因细分）、分数分布直方图
- 审计列表：时间 / 流程 / query 摘要 / 门结果 / 命中数；抑制行灰色显示原因
- 展开详情：每条命中的 memory id、分数、来源、内容摘要、跳转记忆详情
- 标注：每条命中 👍/👎；筛选：仅 agent 标👎 / 仅人机冲突 / 仅待复核
- 标注冲突规则：**human 优先**，人覆盖 agent 标注

### 8.4 Agent 协助审计（人机协同：agent 做苦力，人做裁决）

- 新工具 `recall_audit`（action: `list` / `stats` / `feedback`），归**记忆 Agent**（见姊妹 spec）。
- 每日审计任务（调度，初定每日 19:00，可并入 daily_ai_review）：
  1. 拉当日审计（stats + 全量样本）
  2. LLM 逐条初标相关性，写 feedback（`feedback_by="agent"`）
  3. 低置信度条目标 `needs_review` 留人复核
  4. 输出日报：注入率/噪音率/典型误召回/floor 建议；系统性问题主动通知
- floor 调优闭环：标注集积累 → agent 离线重放候选 floor 算 precision/recall → 提交建议 → **人确认后改 env**（autoExecute 默认关契约）→ stats 前后对比定稿。

## 9. 阶段计划与多模型执行策略

**分工原则**（用户 2026-08-13 指令）：执行模型能力有限，任务契约必须写死（文件路径/接口/命令/验收标准），Claude 负责最终验收。难度分级：L=机械可抄模式（其他模型）；M=需理解局部架构但契约可写死（其他模型+Claude 审查）；H=架构判断/跨层契约/调试（Claude 亲做）。

**Claude 验收规程**（每个非 Claude 任务完成后必做，W1.1 教训）：
1. 对契约：实现与本 spec 的接口/表结构/文件路径逐字核对；
2. 真跑：验收命令亲自跑一遍，看输出不信报告；
3. 回查事实源：涉及生产数据/日志的断言，亲自查源验证。

### P0 v2 质量门

| 任务 | 内容 | 难度 | 执行者 | 验收 |
|---|---|---|---|---|
| P0-T1 | `vector_rank`/`hybrid_rank` 加 cosine_floor + 空结果语义；pytest 覆盖（过线/不过线/全灭三例） | M | 其他模型 | `python -m pytest tests/domain/memory/ -x` 全过；新增 ≥3 测试 |
| P0-T2 | 用生产语料跑分数分布（脚本抽样 50 条真实 query 的 cosine 分布），定 floor 终值写回本节 | H | **Claude** | 分布数据附 PR；floor 值有理据 |
| P0-T3 | env 接线 `MEMORY_RECALL_COSINE_FLOOR`，重启 5001（launchctl kickstart） | L | 其他模型 | curl 实测一次检索返回结构含 strategy 字段 |

### P1 agent-ts 领域+应用层+审计端口

| 任务 | 内容 | 难度 | 执行者 | 验收 |
|---|---|---|---|---|
| P1-T1 | `src/domain/recall/` 四文件（types/policy/quality-gate/recall-message），纯函数 + jest 全覆盖 | M | 其他模型 | `npm test -- domain/recall` 全过；XML 转义/契约测试在列 |
| P1-T2 | `recall-service.ts` 编排 + ports.ts（不接线） | H | **Claude** | 编排单测（mock ports）全过 |
| P1-T3 | 审计适配器两个（v2 主写 fire-and-forget + JSONL 降级） | M | 其他模型 | 失败降级测试：v2 不可达时落 JSONL 不抛错 |
| P1-T4 | v2 审计 API + PG 表迁移 | M | 其他模型 | curl POST/GET/stats/feedback 全通；pytest 覆盖 |
| P1-T5 | 前端「召回审计」tab | M | 其他模型 | 页面真实渲染截图 + API 对接无 mock 残留 |

### P2 SDK 扩展接线（全通道切换）

| 任务 | 内容 | 难度 | 执行者 | 验收 |
|---|---|---|---|---|
| P2-T1 | `sdk-recall-extension.ts`（input 暂存原文 + before_agent_start 注入），挂入 createAppResourceLoader | H | **Claude** | 扩展单测 + 真起 agent 验证 `/provider pro`、skill 调用、普通对话三类消息 |
| P2-T2 | 删除 wrapper 注入代码，恢复 wrapper 只做日志/路由/压缩 | H | **Claude** | session-factory 全部测试过；生产 agent 重启后日志抽查 |
| P2-T3 | 全通道验证（TUI/调度/wake 各触发一次，审计表有对应 flow 记录） | M | Claude+其他模型 | 审计表三类 flow 各有 ≥1 条真实记录 |

### P3 观察期
- 记忆 Agent 每日审计任务上线（依赖姊妹 spec 的 A1）→ 一周后 floor 离线重放调优 → 前后对比定稿。

## 10. 风险与回滚

- P2 接线出问题：扩展从 extensionFactories 摘除即回滚（wrapper 注入代码删除前先在同一 commit 内完成扩展验证）。
- floor 过严导致长期零召回：stats 页注入率监控；env 可热调。
- PG 审计表写入失败：JSONL 降级保底，定期核对。
