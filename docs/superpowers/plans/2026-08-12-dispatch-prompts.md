# 派单 Prompt 集（框架演进 W1.1-W2.5）

> 配套：[2026-08-12-framework-evolution-roadmap.md](2026-08-12-framework-evolution-roadmap.md)（下称"总纲"）
> 用法：整段复制对应工作项的 prompt 发给执行模型。每个 prompt 自包含，无需对话上下文。
> 通用要求已内置在每段中；执行模型的报告由 Claude 主会话按总纲 §6 审查。

---

## 通用前缀（所有派单共用，已并入各段，单独派发时勿漏）

无。（每段已自包含）

---

## W1.1 修断链 + v13 案例三层写入

```
你在 pi-investment 仓库（/Users/yunpeng/pi-investment）执行框架演进工作项 W1.1。

【必读】docs/superpowers/plans/2026-08-12-framework-evolution-roadmap.md 的 §2 全局约束与 W1.1 任务卡。违反全局约束=返工。

【任务】三部分：
1. v2 修断链：quantsys-v2/application/services/knowledge_service.py 当前是 mock（所有方法写死返回空）。接通 adapters/outbound/repositories/agent_knowledge_repository.py，让 get_active_knowledge/apply_knowledge/get_knowledge_summary/validate_knowledge 走真实 PG 数据。只改 service 层，Flask/FastAPI 路由不动。
2. agent-ts 触发钩子：agent-ts/src/services/scheduler/init-agent-tasks.ts 的 daily_ai_review 与 morning_ai_analysis 两个任务 prompt 各加一句："决策/复盘前先用 query_experience 或 memory_search 查询类似场景的历史案例与教训"。改完跑 npm run check:tool-refs 必须过。
3. v13 案例三层写入（数据操作，直接执行）：
   a. 在 agent-ts/.pi-invest/MEMORY.md 写入 3 条规则（该文件当前不存在，新建）：
      - 无人值守的策略账户必须注册机械止盈/止损盯盘规则——2026-07 v13 案例：补注册 +10% 止盈后锁定 3 笔利润，同期无规则的 v14 亏 -53%
      - 崩盘日显著抗跌的股票在 V 型反弹中领涨（相对强度=资金护盘信号），2026-07-28 创业板 -7.35% 当日 v13 持仓 5 只全部抗跌随后全部盈利
      - 新策略/新账户上线先审计"三不管"：是否注册策略、是否有盯盘规则、是否在巡检范围
   b. 通过 agent 的 memory_write 机制（或直接写 agent-ts/.pi-invest/memory/daily/2026-08-12.jsonl，格式 {"ts","category","content"}）写入 v13 完整复盘叙事一篇，须含关键词：v13、崩盘日调仓、机械止盈、三不管、相对强度、创业板反弹、时机运气与纪律。
   c. 通过 experience_write（或直接写 agent-ts/.pi-invest/experience/experience-base.json，先读现有 schema 对齐）写入 2 条经验：①场景"指数崩盘日+策略调仓"，conditions=[崩盘日抗跌,相对强度,成长风格切换]，action=buy；②场景"浮盈触及+10%且盘中回落"，action=sell（机械止盈），注明边界：300561 逃顶成功 vs 300469 少赚 5-9%。

【验收】①knowledge_query 工具（或 GET /api/knowledge/active）能查出 agent_knowledge 表已有 8 条知识（修前返回 0）；②npm run check:tool-refs 通过；③用"止盈""崩盘"检索能命中 v13 案例；④pytest（quantsys-v2）与 npm test（agent-ts，禁止裸 npx jest）无新增失败（基线失败清单见总纲 §2.4）。

【报告格式】改动文件清单 / 测试输出前后对比 / 验收四条逐条自证。
```

---

## W1.2 MemoryEntry 统一模型 + /api/memory API

```
你在 pi-investment 仓库执行框架演进工作项 W1.2（P1 核心单）。

【必读】docs/superpowers/plans/2026-08-12-framework-evolution-roadmap.md 的 §2、W1.2 卡。依赖 W1.1 已完成（查状态栏）。

【任务】在 quantsys-v2 建立统一记忆存储与 API：
1. PG 迁移（quant schema，脚本幂等，参考 scripts/migrations/ 惯例）：
   - CREATE EXTENSION IF NOT EXISTS vector（生产库 quant_investment 与 quant_test 都要）
   - 新表 quant.memory_entries：id bigserial PK, kind text (rule|episode|experience|stock_note), scope text (global|stock:X|strategy:Y|sector:Z), title text, content text, payload jsonb, evidence jsonb, status text (testing|active|deprecated|archived), confidence float8, validation_count int, success_count int, provenance jsonb {session_kind,channel,session_id}, last_recalled_at timestamptz, source text, supersedes bigint 自引用, embedding vector(1024) 可空, created_at, updated_at。索引：scope、kind、status、embedding(ivfflat 或 hnsw，数据量小可先跳过)。
   - 约束：status != 'testing' 以下略——证据链门禁放 service 层校验：写入/升级时 evidence 必须非空（"No Execution, No Memory"）。
2. domain 层：quantsys-v2/domain/memory/（模型+服务），repository 走现有 Repository 模式。
3. FastAPI 路由（只写 FastAPI，不维护 Flask parity）：
   POST /api/memory（写）、GET /api/memory/search（q+scope+kind+status，本期关键词 ILIKE 即可）、POST /api/memory/{id}/validate（验证计数与置信度爬坡：<10 样本 0.3 / 10-30 0.5 / >30 0.7）、POST /api/memory/{id}/supersede、GET /api/memory/export（全量 JSON）。
4. 数据迁移：quant.agent_knowledge 现有 8 条迁入 memory_entries（kind=experience, source=distiller, provenance={"session_kind":"distiller","channel":"chan_weekly"}），原表保留不动。

【验收】pytest 覆盖 CRUD/search/validate/supersede/export；export→import 往返无损；迁移后 8 条可查；证据链门禁：evidence 为空的写入 status 只能是 testing 或被拒。

【报告格式】改动文件清单 / 迁移脚本 dry-run 输出 / pytest 输出 / 验收逐条自证。
```

---

## W1.3 混合检索引擎 vendor

```
你在 pi-investment 仓库执行框架演进工作项 W1.3。依赖 W1.2。

【必读】总纲 §2 + W1.3 卡。参照代码（本地，MIT）：/Volumes/ORICO/doc/github/TencentDB-Agent-Memory（main 分支）src/core/tools/memory-search.ts、src/core/record/l1-dedup.ts——读思想，不整包引入。

【任务】把 W1.2 的 search 升级为混合检索：
1. BM25：Python 侧用 jieba 分词 + rank_bm25（或自实现），对 title+content 建索引。
2. 向量：ollama 本地 bge-m3（ollama pull bge-m3；模型目录 /Volumes/ORICO/ollama-models）。写入/更新 memory_entries 时同步算 embedding（POST http://127.0.0.1:11434/api/embeddings）。
3. RRF 融合（k=60），search API 返回带 score 与命中来源（bm25|vector|both）。
4. 降级：ollama 不可达时自动降级纯 BM25，响应标 degraded:true，不报错。

【验收】构造 ≥20 条种子记忆（含 W1.1 v13 案例），"崩盘日买入"查询 v13 episode 进 top3；停 ollama 后搜索返回 degraded 结果不 5xx；pytest 覆盖。

【报告格式】改动文件清单 / 检索质量演示（查询→top5 截图或文本）/ pytest 输出。
```

---

## W1.4 agent 侧 MemoryProvider Port + 召回注入

```
你在 pi-investment 仓库执行框架演进工作项 W1.4。依赖 W1.2（W1.3 不阻塞）。

【必读】总纲 §2 + W1.4 卡。协议蓝本（本地）：/Volumes/ORICO/doc/github/hermes-agent/agent/memory_provider.py。

【任务】
1. 新建 agent-ts/src/services/memory/：port.ts 定义 MemoryProvider 接口（prefetch/query、sync_turn、search、validate、systemPromptBlock）；v2-client.ts 实现（走 QUANTSYS_V2_API_URL 的 /api/memory/*）；file-fallback.ts 包装现有 memory-store.ts 作降级。
2. 四个工具改走 port，工具名/参数契约不变（对 agent 透明）：memory_write、memory_search、experience_write、query_experience。
3. 召回注入：system-prompt-builder.ts 的 Memory 层新增 ### Recalled Memory——会话开始按最近用户消息/任务上下文 prefetch top-3，字符预算 2000；注入过的条目调 validate 更新 last_recalled_at。
4. 防 recall 循环：sync_turn 写入时排除本轮被召回注入的内容（只沉淀原始产出）。
5. provenance：所有写入携带 {session_kind: user|cron|wake|distiller, channel, session_id}，session_kind 从现有 session 元数据映射。

【验收】jest（必须 npm test）覆盖 port 两实现与降级；模拟会话验证召回注入与预算截断；cron 会话写入带正确 provenance。

【报告格式】改动文件清单 / 测试输出 / 验收逐条自证。
```

---

## W1.5 周日蒸馏任务

```
你在 pi-investment 仓库执行框架演进工作项 W1.5。依赖 W1.2、W1.4。

【必读】总纲 §2 + W1.5 卡。成熟参照：quantsys-v2/application/services/chan_knowledge_distiller.py（缠论周蒸馏）。

【任务】
1. agent-ts 新 cron 任务 weekly_memory_distill（每周日，注册进 init-agent-tasks.ts）：收集近 7 天 memory_entries 中 kind=episode/stock_note 条目 + agent_decisions 记录，调 LLM 蒸馏为 rule 候选。
2. 蒸馏规则：每条候选 rule 必须引用证据（decision_id/trade_id/entry id 列表）；无证据的产出丢弃；被召回注入过的内容（last_recalled_at 非空且为唯一来源）排除在输入外；产出 status=testing, source=distiller。
3. 人工确认链：testing → 调 POST /api/memory/{id}/validate {promote:true} 升 active（web 按钮在 W1.6，本期 API 可用即可）。

【验收】用近两周数据回填跑一次：产出候选全部带 evidence； promote API 状态机正确；npm run check:tool-refs 过。

【报告格式】改动文件清单 / 回填蒸馏产出样本（≥3 条）/ 测试输出。
```

---

## W1.6 web 记忆面板 + 确认门禁

```
你在 pi-investment 仓库执行框架演进工作项 W1.6。依赖 W1.2（API 面稳定即可开工，可与 W1.3/W1.4/W1.5 并行）。

【必读】总纲 §2 + W1.6 卡。前端栈：Vue 3 + Element Plus，web-frontend/，dev 端口 3001 代理 /api→5001。

【任务】新增"记忆"页：
1. 列表：按 kind（rule/episode/experience/stock_note）tab 浏览，scope/status 过滤，关键词搜索（调 GET /api/memory/search）。
2. 详情：content 全文 + evidence 证据链展示（可点击跳决策详情）+ provenance + 验证计数/置信度。
3. 门禁操作：testing 条目提供"确认生效/废弃"按钮（调 validate / supersede API），操作需二次确认。
4. 调度观测简表：scheduler_runs 近 50 条（任务名/状态/耗时/错误），已有 API 则复用。

【注意】apiClient 拦截器解包 {success,data}——调用方和 mock 都用解包后形状（历史 bug 教训）。

【验收】页面全流程可操作；vitest 或手动验证截图；不破坏现有页面构建（npm run build 过）。

【报告格式】改动文件清单 / 页面截图 / 构建与测试输出。
```

---

## W2.1 Tool Search 三段式（高风险）

```
你在 pi-investment 仓库执行框架演进工作项 W2.1（P2 最高收益+最高风险）。

【必读】总纲 §2 + W2.1 卡。参照：/Volumes/ORICO/doc/github/openclaw/docs/tools/tool-search.md。

【任务】把 110 个工具的全量 schema 从系统提示词中卸下：
1. 工具注册表（agent-ts/src/infrastructure/tools/index.ts）拆分：core 常驻 ~20 个（portfolio/trade/data_fetch/memory/task 等高频）保留全量 schema；其余进目录（名称+一行简述）。
2. 三个元工具：tool_search（关键词查目录）→ tool_describe（取完整 schema）→ tool_call（按名调用，参数经 describe 的 schema 校验）。
3. 系统提示词 Tools 层重写：只放 core 工具 + 三件套 + 目录使用说明。
4. 注意 DeepSeek one-tool-at-a-time 特性：三段式会增加往返，目录检索质量必须保证一次命中率高（简述要写得好）。

【验收】worktree 内先实测 3 个典型任务（盘前分析/盯盘唤醒决策/盘后复盘）全链路通过；prompt token 数改动前后采样对比；npm test 全量无新回归。实测不过不得合 main。

【报告格式】改动文件清单 / 三任务实测记录 / token 对比数据 / 测试输出。
```

---

## W2.2 Compaction 四件套

```
你在 pi-investment 仓库执行框架演进工作项 W2.2。

【必读】总纲 §2 + W2.2 卡。参照：/Volumes/ORICO/doc/github/openclaw/docs/concepts/compaction.md、src/agents/embedded-agent-runner/tool-result-truncation.ts。

【任务】增强 agent-ts compaction（src/services/ 下现有压缩服务）：
1. split 点保证 toolCall/toolResult 配对不拆。
2. 压缩前执行一轮静默"记忆落盘"（调 memory port 的 sync_turn，W1.4 完成后接入，未完成则留接口）。
3. 上下文溢出：识别 provider 溢出错误模式 → 触发压缩重试而非直接失败。
4. 旧工具结果 TTL 降级为占位符（如 [Old tool result content cleared, ref: <path>]），配合现有 tool-response-handler 落盘实现按需回读；聚合预算 ≤0.5×上下文窗口。

【验收】构造超长会话 jest 用例：压缩后无孤儿 toolResult；占位符可回读原文；npm test 过。

【报告格式】改动文件清单 / 测试输出 / 验收自证。
```

---

## W2.3 Cron 硬化

```
你在 pi-investment 仓库执行框架演进工作项 W2.3。

【必读】总纲 §2 + W2.3 卡 + 记忆教训：本系统有合盖休眠丢任务、misfire 静默丢失史。参照：/Volumes/ORICO/doc/github/openclaw/src/cron/isolated-agent.ts、docs/automation/cron-jobs.md。

【任务】agent-ts 调度器（src/services/scheduler/，当前 InMemorySchedulerStore 重启丢任务）：
1. 任务定义持久化（.pi-invest/ JSON 或 v2 PG 二选一，说明理由），重启自动恢复注册。
2. 过期任务策略：重排到下一周期，不补跑（防休眠后集中轰炸）。
3. 单任务执行 60min watchdog，超时标记失败并通知。
4. 执行历史可查（对接 scheduler_manage 工具）。

【验收】模拟重启任务不丢；模拟过期不补跑；npm test 过。

【报告格式】改动文件清单 / 测试输出 / 验收自证。
```

---

## W2.4 Hook 三件套

```
你在 pi-investment 仓库执行框架演进工作项 W2.4。

【必读】总纲 §2 + W2.4 卡。参照：/Volumes/ORICO/doc/github/openclaw/docs/plugins/hooks.md。

【任务】agent-ts 建统一工具调用 hook 机制：
1. 三要素：priority（执行顺序）、per-hook timeout（超时仅停等待不取消）、按触发源门控（cron/wake/user）。
2. hook 可返回拦截/修改/放行；把现有 LoopGuardian（轮次纠偏/no_tool 拦截）迁移为注册在统一 hook 面的首批 hook。
3. hook 执行有日志，可审计。

【验收】jest 覆盖顺序/超时/门控/拦截；LoopGuardian 行为回归一致；npm test 过。

【报告格式】改动文件清单 / 测试输出 / 验收自证。
```

---

## W2.5 Prompt Cache 窄腰审计（纯调查）

```
你在 pi-investment 仓库执行框架演进工作项 W2.5（纯调查，不改代码）。

【必读】总纲 §2 + W2.5 卡。原则（Hermes AGENTS.md）：系统提示词每 session 只构建一次，压缩是唯一合法重建时机；cache 前缀稳定神圣。

【任务】审查 agent-ts 8 层提示词（src/services/intelligence/system-prompt-builder.ts）：
1. 提示词是否每轮重建？哪些层是动态的（Memory/Bootstrap/Runtime/Channel）？动态层放在前缀还是后缀？
2. DeepSeek/Kimi 的 prompt cache 机制下，当前结构的缓存命中率如何（可查 usage 字段或日志估算）？
3. 产出调查报告：现状 / 缓存损失点 / 重构建议（动态内容后置、静态前缀稳定）+ 预估收益。

【验收】报告落 docs/superpowers/specs/2026-08-xx-prompt-cache-audit.md（日期填实际），含数据支撑。

【报告格式】直接交付报告文件路径。
```
