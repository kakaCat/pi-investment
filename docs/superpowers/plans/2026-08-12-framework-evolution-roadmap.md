# 框架演进总规划：借鉴 OpenClaw / Hermes / TencentDB-Memory

> 创建：2026-08-12 · 主抓/审查：Claude（本机会话）· 执行：任意模型（按工作项领取）
> 架构图：`/Volumes/ORICO/doc/pi-framework-borrow-map.html`（PNG 同名）
> 参考代码：`/Volumes/ORICO/doc/github/{openclaw,hermes-agent,TencentDB-Agent-Memory}`

## 0. 这份文档怎么用

- **每个工作项（Wx.y）是自包含任务卡**：背景、改动面、验收标准、坑，全部写在卡里。执行模型不需要读过本对话。
- **领取规则**：一次只领一个工作项；开工前在「状态」栏标记 `进行中(by 谁/何时)`；完成标 `✅(日期)` 并附 commit 范围。
- **审查门禁**：每个工作项完成后必须由主抓会话过「§6 审查清单」才算完。测试不通过不得标记完成。
- **依赖**：卡上标了 `依赖:` 的，前置项不 ✅ 不得开工。

## 1. 背景与依据（执行模型需知道的上下文）

我们调研了三个 agent 框架（报告要点见 §7），核心结论：

1. **OpenClaw / Hermes 是"单 agent 个人助手"，我们是三层系统**（agent-ts 大脑 / quantsys-v2 中枢 / web-frontend 观测台）。借鉴件必须按层落位：运行时机制留 agent-ts，存储/调度/知识**服务化沉到 v2**，可视化与人工门禁放 web。
2. **记忆是本期的切入点**：现有记忆体系四处漏风——`.pi-invest/MEMORY.md` 为空、经验库为空、`KnowledgeService` 读路径是 mock（写进去=黑洞）、检索是伪向量 TF-IDF。
3. **腾讯 TencentDB-Agent-Memory 不直接采用**，vendor 三个零件：混合检索（BM25 jieba + 向量 + RRF）、写入去重、召回注入预算控制。其 core/adapter/gateway 三层解耦是 v2 记忆服务的结构参照。
4. **Hermes 的 MemoryProvider ABC 是 agent 侧协议蓝本**：`prefetch/queue_prefetch`（召回双缓冲）、`sync_turn`（异步写）、`on_pre_compress`（压缩前抢救）、`system_prompt_block`。
5. **OpenClaw 的两个安全设计必须内建**：provenance 会话门控（cron/wake 会话产出打标，不污染长期记忆）+ 防 recall 反馈循环（被注入过的内容不再二次抽取）。

## 2. 全局约束（所有执行模型必读，违反=返工）

1. **Worktree 隔离**：改代码必须 `EnterWorktree` 建隔离 worktree，完成合并后再删。主工作区 git 写有钩子硬阻断。合并回 main 走 update-ref+cp 模式（见记忆 `merge-back-without-main-workspace-writes`）。
2. **固定端口**（主分支不允许改）：v2 REST `127.0.0.1:5001`、WS `5003`、web `3001`、agent wake `3002`、PG `5432`。
3. **测试命令**：agent-ts 必须 `npm test`（裸 npx jest 误报 TS1378）；v2 用 `python -m pytest tests/`（自动切 quant_test 库，**严禁连生产库**）。
4. **基线失败**：jest 有 37 个预存在失败套件、pytest 有预存在失败清单（见记忆 `baseline-failing-tests`）。审查时区分"预存在"与"新回归"——执行模型必须提供改动前后的对比。
5. **数据访问**：v2 侧禁止直接 import akshare/tushare，走 DataProviderManager；agent 侧禁止直连 PG，走 v2 API。
6. **生产服务**：5001 是 FastAPI（nohup，无 supervisor，手动重启）；改 scheduler 代码要**同时重启 5001 和 daemon**；daemon 必须用 `venv/bin/python` 重启、禁止 `--reload`。
7. **部署纪律**：合并 main 后由主抓会话决定是否重启生产服务；执行模型不得自行重启生产。
8. **新功能只写 FastAPI 路由**，不再维护 Flask parity。

## 3. 分期总览

| 期 | 主题 | 工作项 | 状态 |
|---|---|---|---|
| P1 | 记忆服务化（本期重点） | W1.1 ~ W1.6 | ✅ 全部完成（2026-08-13） |
| P2 | 运行时治理 | W2.1 ~ W2.5 | ✅ 全部完成（2026-08-13） |
| P3 | v2 = Agent OS（服务协议化） | 仅方向，不排期 | — |
| P4 | 多 Agent 协作 | 仅方向，不排期 | — |

P2 各项彼此独立，可与 P1 后期并行；但同一文件域的改动不得并行（W2.1 动工具注册表，W1.4 也动工具层，需串行）。

---

## 4. P1 工作项：记忆服务化

### W1.1 修断链 + v13 案例三层写入（最小闭环，1天）

- **目标**：不动架构，先把"写了能找到"的最小链路跑通，并把 v13 复盘案例沉淀进去（这是本项目的缘起场景，兼作验收用例）。
- **改动面**：
  1. v2：`quantsys-v2/application/services/knowledge_service.py` 当前是 mock（写死返回空），接通现成的 `adapters/outbound/repositories/agent_knowledge_repository.py`。
  2. agent-ts：`agent-ts/src/services/scheduler/init-agent-tasks.ts` 的 `daily_ai_review` / `morning_ai_analysis` 任务 prompt 各加一句"决策/复盘前先 query_experience 或 memory_search 查询类似场景历史案例"。
  3. 案例写入（三层）：`.pi-invest/MEMORY.md` 手写 3 条蒸馏规则（机械止盈/崩盘日相对强度/三不管审计）；`memory_write` 写 v13 完整复盘叙事（关键词：v13、崩盘日调仓、机械止盈、三不管、相对强度、创业板反弹）；`experience_write` 写 2 条结构化经验（崩盘日买入抗跌股 buy / +10% 机械止盈 sell）。
- **验收**：
  - `knowledge_query`（agent 工具）能查出 `agent_knowledge` 表里已有的 8 条缠论知识（当前返回 0）。
  - 任务 prompt 改动通过 `npm run check:tool-refs`。
  - 用"止盈""崩盘"作关键词 memory_search 能命中 v13 案例。
- **坑**：v2 测试自动切 quant_test 库；knowledge 路由在 Flask+FastAPI 双侧都有（`adapters/inbound/api/routes/knowledge_management.py`），**只改 service 层**，两端自然生效。
- **状态**：✅ 2026-08-12（commit 7d33437；审查修复：案例数据误写 worktree 已迁回主工作区、JSONL 非法已重写、经验条目已对齐 Experience 契约、纠正 3 处股票名/归因幻觉；**待办：5001 重启后知识 API 才生效**）

### W1.2 MemoryEntry 统一模型 + /api/memory API（核心，2-3天）

- **目标**：v2 侧建立统一记忆存储，替代散落的 MEMORY.md/daily jsonl/experience-base.json/agent_knowledge 四套。
- **设计要点（已定稿，不得擅自更改）**：
  - 表 `quant.memory_entries`：`id, kind(rule|episode|experience|stock_note), scope(global|stock:X|strategy:Y|sector:Z), title, content, payload jsonb, evidence jsonb, status(testing|active|deprecated|archived), confidence, validation_count, success_count, provenance jsonb{session_kind,channel,session_id}, last_recalled_at, source, supersedes, embedding vector(1024), created_at, updated_at`。
  - `evidence` 非空才能 `status>=testing`（证据链门禁："No Execution, No Memory"）。
  - API（仅 FastAPI）：`POST /api/memory`（写）、`GET /api/memory/search`（q+scope+kind+status 过滤，本期先关键词，W1.3 上向量）、`POST /api/memory/{id}/validate`（验证计数+置信度爬坡）、`POST /api/memory/{id}/supersede`、`GET /api/memory/export`（全量导出 JSON，迁移保险）。
  - embedding 列本期允许 NULL（W1.3 填充），但表结构一次到位（pgvector 扩展一并装上）。
- **改动面**：v2 新 domain `domain/memory/`（模型+服务），repository，FastAPI 路由，PG 迁移脚本（参考 `scripts/migrations/` 现有惯例）。
- **验收**：CRUD+search+validate 的 pytest 覆盖；export 往返无损；旧 `agent_knowledge` 8 条数据迁移进新表（kind=experience, source=distiller, provenance 标记 chan_weekly）。
- **坑**：pgvector 安装 `CREATE EXTENSION vector`——生产库和 quant_test 都要装；迁移脚本必须幂等。**注意 scripts/ 被 gitignore，迁移脚本要 `git add -f`**。
- **依赖**：W1.1
- **状态**：✅ 2026-08-12（commit 4fa7259+审查修复 31f9227；生产库已迁移建表+013 数据迁移 8 条+v13 案例 6 条种子；**设计变更：embedding 用 TEXT 存 JSON 数组，弃用 pgvector**——brew pgvector 0.8.6 仅编 PG17/18 与 PG14 不兼容，且条目量级（数百）应用层算余弦足够，W1.3 相应调整；**待办：5001 重启后 API 生效**）

### W1.3 混合检索引擎 vendor（1-2天）

- **目标**：检索从关键词升级为 BM25(jieba) + 向量 + RRF。
- **做法**：参考 `/Volumes/ORICO/doc/github/TencentDB-Agent-Memory` main 分支 `src/core/tools/memory-search.ts` 与 `src/core/record/l1-dedup.ts`，**裁剪思想而非整包引入**——我们的后端是 Python，用 `jieba`（py）做 BM25，向量用 ollama 本地 `bge-m3`（`ollama pull bge-m3`，模型存 /Volumes/ORICO/ollama-models），RRF 融合 k=60。**embedding 存 memory_entries.embedding（TEXT 列放 JSON 数组），余弦相似度在应用层算**（条目量级数百，无需 pgvector；2026-08-12 设计变更，原 pgvector 方案弃用）。
- **写入侧**：写 memory 时同步算 embedding（ollama `/api/embeddings`）；ollama 不可用时降级为纯 BM25 并在响应里标注 `degraded: true`（参考腾讯 store 的 `isDegraded()` 设计）。
- **验收**：对 ≥20 条种子记忆（含 W1.1 的 v13 案例），"崩盘日买入"查询能把 v13 episode 排进 top3；ollama 停掉时搜索不报错走降级。
- **依赖**：W1.2
- **状态**：✅ 2026-08-12（c151e67 直接进 main 后由主抓补审通过+a1039b3 接缝修复：status 多值过滤；实测生产数据 top3 全中、降级正常、21/21 embedding 回填；流程备注：此单绕过审查门禁，下不为例）

### W1.4 agent 侧 MemoryProvider Port + 召回注入（2天）

- **目标**：agent-ts 的 memory 工具从"文件读写"切换为"v2 记忆服务客户端"，召回结果自动注入提示词。
- **设计要点**：
  - 新建 `agent-ts/src/services/memory/`：`port.ts`（接口参照 Hermes `agent/memory_provider.py`：`prefetch / sync_turn / search / validate / system_prompt_block`）+ `v2-client.ts`（HTTP 实现）。旧 `memory-store.ts` 保留为 fallback adapter。
  - `memory_write` / `memory_search` / `experience_write` / `query_experience` 四个工具改为走 port（工具名与参数契约不变，对 agent 透明）。
  - 召回注入：`system-prompt-builder.ts` 的 Memory 层扩展——每轮会话开始按当前上下文 prefetch top-3（含 scope 过滤），注入 `### Recalled Memory`；注入过的条目不写回（防 recall 循环：写入时排除 `source=recall` 上下文）。
  - provenance：所有写入携带 `{session_kind: user|cron|wake|distiller, channel, session_id}`——session_kind 从现有 session 元数据取。
- **验收**：jest 覆盖 port 双实现（v2 在线/降级文件）；v13 案例在模拟会话中被召回注入；cron 会话写入的条目带正确 provenance。
- **坑**：`npm test` 而非 npx jest；注入有字符预算（参照腾讯 `maxTotalRecallChars`，默认 2000 字符）。
- **依赖**：W1.2（W1.3 完成后接入向量检索获益，但不阻塞）
- **状态**：✅ 2026-08-12（首单打回后由主抓修补：77ea9ff 移植+1bea2b4 修复——write() 真实写入路径、召回注入移至 prompt 包装层保 cache、证据门禁粒度修订、三工具测试重建为 provider mock；tsc 零错、jest 232 全绿、pytest 52/52；**待办：5001 重启 + agent 重启后生效**）

### W1.5 周日蒸馏任务（1天）

- **目标**：每周日把一周 episode + agent_decisions 蒸馏成 rule 候选（status=testing），人工确认后 active。
- **做法**：复刻缠论周蒸馏模式（`application/services/chan_knowledge_distiller.py` 是成熟参照）；agent 侧新 cron 任务 `weekly_memory_distill`；蒸馏 prompt 必须要求引用证据（decision_id/trade_id），无证据条目直接丢弃；**recall 来源内容排除在蒸馏输入外**。
- **验收**：跑一次回填蒸馏（输入近两周数据），产出候选条目全部带 evidence；人工确认 API `POST /api/memory/{id}/validate {promote: true}` 能把 testing 升 active。
- **依赖**：W1.2、W1.4
- **状态**：✅ 2026-08-12（T1 a7fb822 v2 蒸馏服务+双端点、T2 f62f5f7 agent cron `weekly_memory_distill` 周日 21:00；审计通过，T2 E2E 生产污染 2 条已清除）

### W1.6 web 记忆面板 + 确认门禁（1-2天）

- **目标**：web-frontend 新增"记忆"页：四种 kind 浏览、scope 检索、证据链下钻、testing→active 人工确认按钮、调度观测（cron runs 简表）。
- **验收**：页面能对 W1.5 产出的 testing 条目执行确认/废弃；证据链点击跳到对应 decision 详情。
- **依赖**：W1.2（API 面稳定即可开工，可与 W1.3-1.5 并行）
- **状态**：✅ 2026-08-13（0e883b4 主抓直接实现；T4.1-T4.4 一页集成：kind tab/过滤/混合检索/详情抽屉+证据链决策下钻/testing 确认废弃门禁/scheduler_runs 观测；UI E2E 实证 promote 链路+混合检索 top3 命中 v13 案例；**设计补充**：新增 POST /api/memory/{id}/deprecate（supersede 需 new_id，无替代品的废弃走此端点）；顺带修复 5 个预存在 tsc 错误+esbuild devDep——T4.1 验收要求 build 通过而基线红）

---

## 5. P2 工作项：运行时治理（各自独立，可并行领取）

### W2.1 Tool Search 三段式（2-3天，收益最大）
- **目标**：110 工具不再全量塞 prompt。元工具三件套 `tool_search/tool_describe/tool_call`：目录只放名称+一行简述，schema 延迟到 describe。参照 `/Volumes/ORICO/doc/github/openclaw/docs/tools/tool-search.md`。
- **改动面**：`agent-ts/src/infrastructure/tools/index.ts` 注册表拆分（core 常驻 ~20 个 vs 目录化）；系统提示词 Tools 层重写。
- **验收**：核心场景（盘前/盘中/复盘/盯盘唤醒）全链路回归；prompt token 数对比（改动前后采样）；DeepSeek one-tool-at-a-time 怪癖下三段式不增加往返失败率。
- **坑**：这是高风险改动，影响所有会话；先在 worktree 用 3 个典型任务实测再合。
- **状态**：✅ 2026-08-13（主抓直接实现：catalog.ts + core 25 常驻 + 三元工具；schema 面 -74%、描述面 -65%，每请求省 ~20K token；**3 任务实测全过**：pool 查询 tool_search→describe→call×4 教科书链路、缠论分析 core 直连+search 混用、持仓 core 直调 21s；jest 26 新测试全过+全量回归与基线一致；kill-switch `PI_TOOL_SEARCH=off`；plan 子代理始终拿全量注册表；harness 留存 src/scripts/t8-live-test.ts）

### W2.2 Compaction 四件套（1-2天）
- 配对安全 split 点（toolCall/toolResult 不拆对）、压缩前静默记忆落盘（调 W1.4 的 sync_turn）、溢出错误模式库重试、工具结果 TTL 占位符（`[Old tool result content cleared]` + 按需回读落盘文件）。参照 openclaw `src/agents/embedded-agent-runner/tool-result-truncation.ts`、`docs/concepts/compaction.md`。
- **验收**：构造超长会话测试压缩不丢工具配对；落盘文件可回读。

### W2.3 Cron 硬化（1天）
- agent 侧 InMemorySchedulerStore 持久化（jobs 落 `.pi-invest/` 或 v2 PG，重启自动重注册）；过期任务**重排不补跑**；单任务 60min watchdog。参照 openclaw `src/cron/isolated-agent.ts`。
- **背景**：我们有合盖休眠丢任务的血泪史（记忆 `scheduler-sleep-misfire-fix`）。

### W2.4 Hook 三件套（1天）
- 工具调用 hook 机制：priority + per-hook timeout + 按触发源（cron/wake/user）门控。参照 openclaw `docs/plugins/hooks.md`。先把 LoopGuardian 的拦截逻辑迁移到统一 hook 面。

### W2.5 Prompt Cache 窄腰审计（0.5天，纯调查）
- 核查 8 层提示词构建是否每轮重建（Hermes 原则：每 session 只构建一次，压缩是唯一重建时机）。产出调查报告 + 修复建议，不直接改。
- **状态**：✅ 2026-08-13（docs/superpowers/specs/2026-08-13-prompt-cache-audit.md：173 轮实证——交互轮中位命中 98.8%，损失集中在召回注入旧行为+40K 冷启动信封；**审计超额发现 gateway beforePrompt 每轮重建系统提示词的缓存杀手**（W1.4 只修了 CLI 路径），已随 W2.1 同批修复：系统提示词仅 createSession 构建一次，召回改 addMessage 消息级注入保前缀）

---

## 6. 审查清单（主抓会话对每个工作项逐项过）

1. **测试**：新增代码有对应测试；`npm test` / `pytest` 全量跑过，新回归=0（对照基线清单）。
2. **契约**：工具参数/API 响应形状变更必须同步调用方与测试 mock（apiClient 信封解包教训：拦截器解包后的形状才是契约）。
3. **边界**：无跨层直连（agent 不直连 PG、v2 不调 LLM）；无新常驻进程（防静默死亡面）。
4. **端口/IP**：diff 中无端口/IP 漂移。
5. **数据安全**：不动生产库数据；迁移脚本幂等+有回滚路径；新表在 quant schema。
6. **证据链**：记忆相关写入必须带 evidence/provenance，无证据的 status 只能是 testing。
7. **文档**：涉及架构决策的工作项，完成后更新本文档状态栏 + 必要时写记忆。

## 7. 调研依据索引（执行模型查证用）

| 主题 | 参照位置（ORICO 本地） |
|---|---|
| OpenClaw 插件/slot/hook | `openclaw/docs/plugins/{architecture,hooks,manifest}.md`、`src/plugins/slots.ts` |
| OpenClaw 记忆架构 | `openclaw/docs/concepts/{memory-architecture,active-memory,dreaming}.md` |
| OpenClaw cron 硬化 | `openclaw/src/cron/isolated-agent.ts`、`docs/automation/cron-jobs.md` |
| OpenClaw Tool Search | `openclaw/docs/tools/tool-search.md` |
| OpenClaw compaction | `openclaw/docs/concepts/compaction.md`、`src/agents/embedded-agent-runner/tool-result-truncation.ts` |
| Hermes 记忆 provider | `hermes-agent/agent/memory_provider.py`、`memory_manager.py` |
| Hermes 自我成长 | `hermes-agent/agent/background_review.py`、`curator.py`、`tools/skill_manager_tool.py` |
| Hermes cron | `hermes-agent/cron/scheduler.py`、`cron/jobs.py` |
| 腾讯检索/存储 | `TencentDB-Agent-Memory/src/core/tools/memory-search.ts`（main 分支）、`src/core/store/types.ts` |

## 8. 变更日志

- 2026-08-12 初版（三框架调研完成，W1.1-W2.5 定义）
