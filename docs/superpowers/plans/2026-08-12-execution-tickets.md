# 微工单执行集（W1.5-W2.5 细粒度拆分 + 并行编排）

> 配套：总纲 + 派单集（§0 验收证据制全程适用）
> 用途：执行模型智能不足时的兜底——每个微工单（T 编号）是**纯操作序列**，不需要设计判断。
> 创建：2026-08-12（W1.1-W1.4 审查经验回流）

## 0. 执行排期与审计门禁（2026-08-12 定稿）

**节奏原则**：一次派发不超过一个工单；每单交付后由我（Claude 主会话）过审计点，通过才派下一单。同轮并行的多单也必须分别审计。

| 轮次 | 派发内容 | 并行? | 我的审计点（5分钟快查） |
|---|---|---|---|
| R1 | **T7**（纯调查，零风险试单） | 单发 | 报告文件存在+含数据表+结论可行动 |
| R2 | **T1**（v2 蒸馏服务）+ **T4.1**（web 骨架） | 双路并行 | T1: pytest 真实输出+路由注册实证（import 数 routes）；T4.1: build 成功+页面截图+apiClient 解包形状 |
| R3 | **T2**（agent cron，依赖 T1）+ **T4.2** | 双路并行 | T2: check:tool-refs+回填产出带 evidence 的 testing 条目（贴 psql 输出）；T4.2: 抽屉截图含全字段 |
| R4 | **T5** + **T6** + **T4.3** | 三路并行 | T5: 三 jest 用例输出（重启恢复/不补跑/超时）；T6: LoopGuardian 回归无新失败+hook 审计日志实证；T4.3: testing→active 前后截图 |
| R5 | **T4.4** + **T3**（C 组开始独占 agent-ts） | 双路（不同仓） | T4.4: 表格截图；T3: 压缩无孤儿 tool result 测试+占位符回读实证 |
| R6 | **T8**（Tool Search，最高风险） | 独占 | 三任务实测录像/日志+token 对比数据+全量 npm test 对比基线 |

**打回处理**：审计不过的工单，我把具体问题写入工单文件的"打回记录"节，原模型按修正点返工（不换新模型——返工成本低于重教）。

**每轮派单包装**（发给执行模型时的固定格式）：
```
领取工单 T<x>（文件：docs/superpowers/plans/2026-08-12-execution-tickets.md）。
必读：该文件的 §2 执行协议 + 你的工单节 + docs/superpowers/plans/2026-08-12-dispatch-prompts.md 的 §0 通用验收纪律。
严格按步骤执行，每步贴验证输出。完成后报告：每步验证的实际输出原文。
```

## 2. 执行协议（每个执行模型必读）

```
1. 一次只领一个 T 工单，按步骤顺序执行，禁止跳步、禁止"顺手优化"范围外代码。
2. 每步有【验证】：命令+预期输出。验证不过=立即停下报告，禁止继续。
3. 完成后报告：每步验证的实际输出（粘贴原文）。
4. 代码在 worktree 内开发（EnterWorktree）；.pi-invest 等运行态数据写主工作区。
5. 绝对禁止：git checkout -- . / 裸 npx jest / 直连生产库跑测试 / 改固定端口。
```

## 3. 并行编排（冲突矩阵）

| 组 | 工单 | 文件域 | 可并行 |
|---|---|---|---|
| **A 组（立即并行）** | T1（W1.5a v2 蒸馏服务）、T4（W1.6 web 面板全部）、T7（W2.5 审计） | quantsys-v2 / web-frontend / 只读 | ✅ 三者互不接触 |
| **B 组（A 组 T1 完成后）** | T2（W1.5b agent cron）、T5（W2.3 cron 硬化）、T6（W2.4 hook） | agent-ts/services 不同子目录 | ✅ 彼此不共享文件 |
| **C 组（独占）** | T3（W2.2 compaction）→ T8（W2.1 Tool Search） | agent-ts/services/compaction + session-factory → tools/index.ts + 提示词 | ❌ 必须串行且独占 agent-ts |

规则：同组工单同一时刻最多一个；C 组开工时 agent-ts 冻结其他工单。

---

## T1（W1.5a）v2 侧蒸馏服务 ✅ 2026-08-12（a7fb822，审计通过+生产实证 saved/skipped 正确）

**目标**：quantsys-v2 新增周日蒸馏服务，从 memory_entries + agent_decisions 产出 rule 候选（status=testing）。

**步骤**：

1. 读参照实现：`cat quantsys-v2/application/services/chan_knowledge_distiller.py`，理解其 upsert_knowledge 调用模式与置信度爬坡函数 `_confidence_for`。
2. 新建 `quantsys-v2/domain/memory/distiller.py`，实现 `MemoryDistiller` 类，方法 `collect_inputs(days=7) -> dict`：用 `MemoryRepository().list_filtered(kind='episode', max_rows=200)` 取近 7 天条目（按 created_at 过滤），再用 `infrastructure.persistence.orm.get_session` 查 `quant.agent_decisions`（近 7 天，按 created_at desc 限 100 行，只取 id/decision_type/reasoning/success 列）。返回 `{"episodes": [...], "decisions": [...]}`。排除规则：条目 `last_recalled_at` 非空且 `source='recall'` 的排除。
   【验证】`cd quantsys-v2 && PYTHONPATH=. venv/bin/python -c "from domain.memory.distiller import MemoryDistiller; d=MemoryDistiller().collect_inputs(14); print(len(d['episodes']), len(d['decisions']))"` 输出两个非负整数且不抛错。
3. 同文件实现 `build_prompt(inputs) -> str`：生成蒸馏 prompt，要求 LLM 输出 JSON 数组，每条 `{title, content, evidence_ids}`；prompt 中硬性要求 evidence_ids 必须引用输入里的条目 id 或 decision id，无证据的条目不得输出。
   【验证】`python -c "from domain.memory.distiller import MemoryDistiller; p=MemoryDistiller().build_prompt({'episodes':[{'id':1,'title':'t','content':'c'}],'decisions':[]}); assert 'evidence_ids' in p; print('prompt ok', len(p))"`
4. 同文件实现 `save_candidates(items, session)`：对每条候选调 `MemoryService.create()`（kind=rule, status=testing, source=distiller, evidence={"refs": evidence_ids}, provenance={"session_kind":"distiller","channel":"weekly_memory_distill"}）。evidence_ids 为空的跳过并计数。
   【验证】pytest 见第 5 步。
5. 新建 `quantsys-v2/tests/domain/memory/test_distiller.py`：3 个用例——(a) collect_inputs 排除 source=recall 条目；(b) save_candidates 跳过无证据候选；(c) save_candidates 正常写入 testing 条目。
   【验证】`venv/bin/python -m pytest tests/domain/memory/test_distiller.py -o addopts="" -q` 3 passed。
6. LLM 调用**不在本工单实现**（v2 不调 LLM 是架构约束）——distill 的 LLM 调用在 T2（agent 侧）完成：T1 的 API 面是：`GET /api/memory/distill/inputs?days=7`（返回 collect_inputs 结果）+ `POST /api/memory/distill/candidates`（接收 agent 蒸馏后的候选数组，走 save_candidates）。新建路由文件 `quantsys-v2/adapters/inbound/fastapi_app/routes/memory_distill_async.py` 实现这两个端点，并在 `main.py` 注册（仿照 memory_async 的注册块，紧跟其后）。
   【验证】`venv/bin/python -m pytest tests/domain/memory/test_distill_routes.py -o addopts="" -q`（先写该测试：TestClient 挂路由，GET inputs 返回 200 含 episodes/decisions 键；POST candidates 无证据条目被跳过）全过。

**产出**：4 个新文件 + main.py 注册 + 测试全绿输出。

---

## T2（W1.5b）agent 侧周日蒸馏任务 ✅ 2026-08-12（f62f5f7，审计通过；注：其 E2E 验证污染生产库 2 条已清除——后续工单 E2E 验证后必须清理测试数据，已并入审计点）

**依赖**：T1 完成（API 面存在）。

**步骤**：

1. 读 `agent-ts/src/services/scheduler/init-agent-tasks.ts` 现有任务注册模式（weekly_evolution 是参照）。
2. 新增任务 `weekly_memory_distill`，cron `0 21 * * 0`（周日 21:00，避开 20:00 的 weekly_evolution）。任务 prompt 内容：
   - 第 1 步：调用 backend API GET /api/memory/distill/inputs?days=7（用 runQuantV2 或 fetch）
   - 第 2 步：基于输入蒸馏规则候选，每条必须附 evidence_ids（引用输入条目 id）
   - 第 3 步：POST /api/memory/distill/candidates 提交（请求体字段名为 candidates：{"candidates": [{title, content, evidence_ids}]}——T1 已上线实证，用错字段名会 400）
   - 第 4 步：汇报本轮产出 N 条候选、跳过 M 条无证据
   【验证】`npm run check:tool-refs` 通过。
3. 新建 `agent-ts/src/services/memory/distill-task.test.ts`：mock fetch，验证任务函数正确调用两个端点、候选为空时不 POST。
   【验证】`npm test -- --testPathPattern "distill-task"` 全过。
4. 回填验证（真实跑一次）：agent 重启后手动触发该任务，或直接用 curl 模拟两轮调用，确认 memory_entries 新增 status=testing、source=distiller 的条目。
   【验证】`psql -d quant_investment -c "SELECT id,title,status,source FROM quant.memory_entries WHERE source='distiller' ORDER BY id DESC LIMIT 5;"` 有输出。

---

## T3（W2.2）Compaction 四件套 ✅ 2026-08-12（e834c4a 库交付 + 35c1745 主抓接线：split 守卫内嵌生效、压缩前钩子已接线、flush 顺序修正为压缩前）

### T3b 接线遗留 ✅ 2026-08-12（f6a0c57 + 主抓修复 61e89bf）
**审计记录**：f6a0c57 未经审查直接进 main（第二次门禁绕过），且静态 import 了 T6 未合并的 services/hooks 模块——**干净检出下 main 编译断裂**（其工作区有 T6 散落文件所以本地是绿的，典型的污染环境假绿）。主抓修复：hook 改懒加载+降级直通+hook 内部错误不阻断工具。溢出重试/TTL 接线本身质量合格（14 套件 76 测试过）。
**新审计规则**：审查必须在干净 worktree 跑 tsc——主工作区可能有其他工单的散落文件造成假绿。
**T6 审计点追加**：services/hooks/index.ts 必须导出 executeBeforeToolCallHooks（sdk-facade 懒加载按此名解析，名字不符=hook 静默失效）。

原工单内容存档：
1. **溢出重试接线**：`isOverflowError`（overflow-patterns.ts）目前无生产调用。接线点：LLM 调用错误处理路径（`agent-ts/src/services/llm/` 或 SDK 调用处）——捕获错误时先 `isOverflowError(err)` 匹配，命中则触发一次 compactConversationHistory 后重试，仍失败再上抛。jest：模拟溢出错误验证触发压缩重试。
2. **TTL 接线**：`applyToolResultTTL`（tool-result-ttl.ts）目前无生产调用。接线点：`tool-response-handler.ts` 落盘流程——新结果落盘后对历史结果执行 TTL 降级（20 轮/0.5×窗口预算）。jest：构造超限会话验证占位符替换+文件可回读。
【验收】两处接线后 `npm test` 无新回归 + 各贴一个生产路径触发证据（日志行）。

**依赖**：C 组独占窗口。参照 `/Volumes/ORICO/doc/github/openclaw/docs/concepts/compaction.md`。

**步骤**（每步独立验证）：
1. 在现有压缩服务（`agent-ts/src/services/` 下 compaction 相关文件，先 `grep -rn "compact" agent-ts/src/services --include="*.ts" -l` 定位）中找到消息切分点逻辑；添加守卫：split 点不得落在 assistant(tool_calls) 与其后续 tool result 之间。写单元测试：构造 20 轮对话含工具对，压缩后无孤儿 tool result。
2. 压缩前钩子：压缩执行前调用 memory provider 的 `syncTurn`（仅记录上下文，不写库——写入由 agent 自主用 memory_write）。若 provider 未初始化则跳过。
3. 溢出模式库：新建 `overflow-patterns.ts`，含至少 8 种 provider 溢出错误正则（context length/max tokens/window exceeded 等，参考 openclaw `docs/concepts/compaction.md` 与腾讯 offload 代码）；LLM 调用抛错时先匹配，命中则触发压缩重试一次，仍失败才上抛。
4. 工具结果 TTL：`tool-response-handler.ts` 落盘超过 N 轮（默认 20 轮）的结果替换为占位符 `[Old tool result cleared, ref: <path>]`，并保证 agent 可凭 path 用 Read 工具回读；聚合预算：单会话工具结果总量 ≤0.5×上下文窗口，超出从最旧开始降级。

**验收**：`npm test -- --testPathPattern "compaction"` 全绿（含新测试）；构造 60 轮模拟会话脚本跑出占位符替换日志。

---

## T4（W1.6）web 记忆面板（4 个可串行子票，一个模型顺序做完）

**T4.1 页面骨架与列表**
1. `web-frontend/src/api/` 下新建 `memory.ts`：封装 `/api/memory/search`、`/api/memory/{id}/validate`、`/api/memory/{id}/supersede`。**注意 apiClient 拦截器解包 {success,data}——用解包后的形状**。
2. 新建 `web-frontend/src/views/Memory.vue`：顶部 tab（rule/episode/experience/stock_note）+ scope/status 下拉过滤 + 关键词输入框（回车触发搜索）+ 结果表格（title/status/confidence/validation_count/updated_at）。
3. 路由注册（router/index.ts 加 /memory 路由）+ 侧边栏菜单项。
【验证】`cd web-frontend && npm run build` 成功；`npm run dev` 后页面可打开，能列出条目（截图）。

**T4.2 详情与证据链**
1. 点击行展开详情抽屉：content 全文、payload JSON 美化、provenance、evidence 列表。
2. evidence 中的 decision id 渲染为链接（跳到现有决策详情页或弹窗展示）。
【验证】截图证明抽屉展示完整字段。

**T4.3 确认门禁**
1. status=testing 的行显示"确认生效"/"废弃"按钮；点击弹确认框（说明文字：生效后进入 active 参与召回）。
2. 确认调 validate `{success:true, promote:true}`；废弃调 supersede 或状态变更 API（以 W1.2 API 为准，先读 memory_async.py 确认可用端点）。
【验证】对一条 testing 条目执行确认后，列表刷新显示 active（截图前后对比）。

**T4.4 调度观测简表**
1. Memory 页底部或新 tab：scheduler_runs 近 50 条表格（任务名/状态/开始/耗时/错误）。先 `grep -rn "scheduler_runs\|scheduler/runs" quantsys-v2/adapters/inbound/fastapi_app/routes/ | head` 找现有 API，有则复用，没有则本票只做前端占位并在报告中说明。
【验证】表格渲染截图。

---

## T5（W2.3）Cron 硬化 ✅ 2026-08-12（8d26b14+审查修正 36eba9a：jobs.json 路径回归 paths.piDir；31/31 测试真实通过；misfire/重排不补跑/watchdog 逻辑审查合格）

**步骤**：
1. `agent-ts/src/services/scheduler/` 下新建 `persistent-store.ts`：任务定义写 `.pi-invest/scheduler/jobs.json`（原子写：tmp+rename），接口与 InMemorySchedulerStore 一致。**选择文件而非 PG 的理由写进文件头注释**（agent 不直连 PG；经 v2 API 存任务定义会增加启动依赖环）。
2. 启动时加载 jobs.json 重注册（在 init-agent-tasks.ts 调用点接入）。
3. misfire 策略：任务过期 >5 分钟则跳过重排到下一周期，不补跑（写进调度器 tick 逻辑，附注释引用 OpenClaw isolated-agent 的过期重排设计）。
4. watchdog：单任务执行包一层超时（默认 60 分钟，可配），超时标记 failed 并写执行历史。
【验证】jest：重启恢复、过期不补跑、超时标记三个用例全过。

---

## T6（W2.4）Hook 三件套

**步骤**：
1. 新建 `agent-ts/src/services/hooks/`：`registry.ts`（register/hook 定义：{name, priority, timeoutMs, triggers[], handler}）、`executor.ts`（按 priority 排序执行，per-hook timeout 用 Promise.race 实现，trigger 门控过滤）。
2. hook 点：`before_tool_call`（可返回 {action: 'block'|'modify'|'allow', reason}）。
3. 把 LoopGuardian 的轮次纠偏与 no_tool 拦截逻辑迁移为两个注册 hook（优先级：纠偏 10，拦截 20）。
4. 审计日志：每次 hook 拦截写一行到 `.pi-invest/hooks.log`。
【验证】jest：优先级顺序/超时跳过/trigger 门控/拦截生效 4 用例；LoopGuardian 现有测试不回归。

---

## T7（W2.5）Prompt Cache 窄腰审计（纯调查，随时可做）

1. 读 `agent-ts/src/services/intelligence/system-prompt-builder.ts`，列出 8 层哪些是静态/动态。
2. 在 agent 运行日志或 API 响应中找 prompt cache 命中证据（DeepSeek usage 的 prompt_cache_hit_tokens 字段）；采样 10 轮对话估算命中率。
3. 写报告 `docs/superpowers/specs/2026-08-XX-prompt-cache-audit.md`（日期填实际）：现状/损失点/重构建议/预估收益。
【验证】报告文件存在且含数据表。

---

## T8（W2.1）Tool Search 三段式（独占，最后做）

**前置**：C 组窗口；先跑 W2.5 报告结论确认提示词收益点。

**步骤**：
1. 生成工具目录：`agent-ts/src/infrastructure/tools/catalog.ts`——从 allCustomTools 导出 {name, 一行简述}（从 description 首行截取），构建时生成。
2. core 常驻集（~20 个，名单需主抓确认后再动手）：memory/task/plan/portfolio_status/portfolio_trade/data_fetch_quote/data_fetch_kline/watch_manage/scheduler_manage/query_experience 等。
3. 三个元工具：`tool_search(query)` 查目录、`tool_describe(name)` 返回完整 schema、`tool_call(name, args)` 校验并调用。
4. system-prompt-builder 的 Tools 层改为：core 全量 + 三件套 + 目录使用说明。
5. **实测闸**：worktree 内用 3 个真实任务 prompt（盘前分析/盯盘唤醒/盘后复盘）各跑一遍 agent，确认任务完成且 tool_search 命中率正常。实测不过不得合 main。
【验证】三任务实测记录 + prompt token 前后对比 + npm test 无新回归。
