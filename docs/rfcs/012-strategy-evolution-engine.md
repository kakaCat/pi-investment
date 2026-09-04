# RFC 012：策略进化引擎——进化数据链完全修复

> 日期：2026-09-03
> 作者：investor（w-8366e526）
> 状态：P0（占位拦截）+ P1（qv2 引擎）+ P2（agent-dh 工具迁移）已实施（落位记录见 §10）；P3 收尾 B 链 producer 等已落地（见 §10 末/§11），agent-os 路由 deprecation 标注受并行会话脏文件阻塞待办
> 前置：docs/work-logs/2026-09/l4b-evolution-data-chain-audit-20260903.md（A/B 双链占位冒充实锤）

## 0. 背景与修复目标

进化数据链现状（实测坐实，2026-09-03）：

1. **A 链（agent-dh evolution_* 工具 → Agent OS :8080）**：10 条 completed runs 全是占位分（0.05×i 阶梯），`evolution_handler.go:182-186` baseline==0 时 0.05×i 冒充、`:135-175` baseline 拉取失败静默归零。且 **A 链从未产生过真实参数变体**（只调"风险乘数"，proposals.params 为空）。
2. **B 链（qv2 fitness_calculator 双侧捕获）**：算法真实但对象是**账户行为**（agent_virtual 等），与 evolution_run 声称的**策略参数进化**是不同对象——直接切 B 链是语义错配。数据停在 08-14、无生产者。
3. **更深一层事实**：工具声称的"策略参数进化"**在全系统从未真实存在过**——qv2 无策略进化引擎；策略 178/203/636 等从未跑过回测（backtest_count=0）→ performance 空 → baseline 0 → 占位。
4. **可用真腿**：qv2 `BacktestAsyncEngine.run_backtest`（async 程序内可调用，`backtest_async_engine.py:25`）+ `StrategyCodeService`（策略 CRUD，`strategy_code_service.py:107`）——真实回测与策略管理都在 qv2，**进化引擎建在 qv2 内无需跨服务**。

**修复目标（验收标准）**：
- `evolution_run` 真实化：对策略做**真实变异（参数网格或代码文本变异）→ 逐变体跑 qv2 真实回测 → fitness=回测指标 → 产出真实 proposals/best_params** 并落库。
- `evolution_leaderboard` 真实化：读真实进化结果表（按 strategy_id 排真实 fitness），不再读 agent-os 占位。
- 占位退役：agent-os evolution 链路停用并标注，或仅保留历史快照。
- 诚实降级：回测不可用/策略无标的时显式 degraded，绝不回退到任何占位数字。
- 保留 B 链账户行为双侧捕获为独立能力（对象不同，不合并；补生产者使其持续化，供"行为进化"语义使用）。

## 1. 目标架构

```
agent-dh evolution_* 工具（改连 qv2）
   │  quantsys-v2-client 新增 evolution 方法
   ▼
qv2 新增路由（evolution_engine_async.py）
   │
   ▼
StrategyEvolutionService（新增）            ← 核心引擎
   ├─ 变异器 VariantGenerator
   │    参数策略：读 strategy 配置 → 参数网格（每参数 ±20%/±10% 邻域）
   │    code 策略：code 文本变异（参数常量改写，见 §4 安全边界）
   ├─ 评估器：对每变体调 BacktestAsyncEngine.run_backtest（真实回测）
   │          同标的窗口 → 指标归一 fitness（收益/夏普/胜率加权，可配）
   └─ 落库：evolution_strategy_runs 表（新）+ 更新 strategy 当前最优
   │
   ▼
leaderboard GET：读 evolution_strategy_runs → 按 strategy 最新 fitness 排名
```

**不再消费**：agent-os :8080 /api/v1/evolution/*（legacy 占位）。Agent OS 侧不删代码（其他旧客户端可能引用），路由停用标注 deprecation。

## 2. 数据模型（新表 evolution_strategy_runs）

```sql
CREATE TABLE evolution_strategy_runs (
  id            BIGSERIAL PRIMARY KEY,
  strategy_id   INT  NOT NULL REFERENCES strategies(id),
  genome_run_id TEXT,                 -- 可选：与 L4-B genome 变异关联
  variant_key   TEXT NOT NULL,        -- 变体标识（如 base / p_lookback_20 / v_code_1）
  params        JSONB,                -- 真实参数变体（非占位）
  code_diff     TEXT,                 -- code 变体的差异摘要
  fitness       DOUBLE PRECISION,     -- 真实回测归一适应度
  metrics       JSONB,                -- 回测原始指标（return/sharpe/win_rate/max_dd）
  kline_window  TEXT,                 -- 回测数据窗口（如 2026-01-01..2026-08-31）
  status        TEXT NOT NULL DEFAULT 'running',  -- running/completed/degraded
  degraded_reason TEXT,
  created_at    TIMESTAMPTZ DEFAULT now(),
  completed_at  TIMESTAMPTZ
);
CREATE INDEX idx_evorun_strategy ON evolution_strategy_runs (strategy_id, created_at DESC);
```

## 3. qv2 新增/改动清单（逐文件）

| 文件 | 动作 | 内容 |
|---|---|---|
| `quantsys-v2/application/services/evolution/strategy_evolution_service.py` | **新增** | `StrategyEvolutionService.run(strategy_id, mode, generations)`：取策略 → 变异器生成 variants → 逐变体 await `BacktestAsyncEngine.run_backtest` → 归一 fitness → 落库；mode=propose 只生成不回测（写 status=pending）；full=变异+回测；validate=只对给定 variant 回测 |
| `quantsys-v2/application/services/evolution/variant_generator.py` | **新增** | 变异器：参数网格（numeric params ±x%）+ code 策略的数值常量改写候选（白名单行内常量）；返回 variant 列表（含 base 对照组）。⚠️ 不生成任意代码语义变异（见 §4） |
| `quantsys-v2/adapters/inbound/fastapi_app/routes/evolution_engine_async.py` | **新增** | `POST /api/evolution/strategies/run`（strategy_id/mode/generations → job 或同步）；`GET /api/evolution/strategies/{id}/runs`（历史）；复用现有 `GET /api/evolution/leaderboard` 语义升级为读策略 runs（保持响应形状兼容）或新 `GET /api/evolution/strategies/leaderboard` |
| `quantsys-v2/adapters/outbound/repositories/evolution_strategy_run_repository.py` | **新增** | ORM 仓储（对表 §2） |
| `quantsys-v2/adapters/inbound/fastapi_app/daily_jobs_bootstrap.py` 或启动钩子 | 改动 | 盘后例程注册 `compute_all_accounts`（B 链账户 fitness 续采，8/14 断点恢复）——若此文件属并行会话脏文件，则改在 **Agent OS scheduler 任务**里调用独立采集脚本 |
| 测试 | 新增 | 引擎单测（变异器确定性/回测 mock/落库）、路由测试、契约测试（schema 与 agent-dh 对齐） |

> **P1 实现落位裁决（2026-09 复查闭环登记，w-8366e526）**——§3 预期设计与实际实现的差异及理由：
>
> - **服务放 `application/services/` 根而非 `evolution/` 子包**：`evolution/` 子包是**行为进化**域（genome/evolution_fitness 等），本引擎是**策略参数进化**域——与同根的 `strategy_optimizer.py`/`strategy_code_service.py` 共享回测服务约定。主域归类按"依赖共享面"而非"进化字样"。
> - **执行腿为同步 ThreadPoolExecutor 并行**（§3 预期为异步引擎）：先串行跑 base 变体做 degraded 判定（零交易/失败即短路，不空跑并行池），通过后余量变体经 `ThreadPoolExecutor(max_workers=6)` 并行回测、按 variant index 保序组装——与既有 `StrategyOptimizer`（ThreadPoolExecutor 并行 backtest_strategy）同款模式，先例证明 `backtest_strategy` 线程安全。异步化（POST 返回 run_id）留给工具超时真出现时再做。
> - **服务已注册** `ServiceFactory.get_strategy_evolution_service()`（@lru_cache 单例）+ `adapters/shared/services.py` getter（路由经 PEP 562 `__getattr__` 惰性转发获取，不自建实例）。
> - **网格语义登记**：`StrategyEvolutionService._generate_variants` = base 邻域 ±%（先 base 再试邻近，进化用）；`application/services/search_space.py::SearchSpace` = min/max/step 显式搜索域（人工调参用）——两套互补，代码已互相注记，改动前须核对另一处。

## 4. 变异安全边界（防"假进化"复辟）

- **参数变体**只改策略配置中显式声明的数值参数（threshold/lookback 类），±20%/±10%/±5% 邻域网格；不触碰代码控制流。
- **code 变体**默认**不自动改写代码语义**（第一版只对声明了参数映射的 code 策略做常量替换候选）；纯 code 无参数面策略 → 如实报 degraded("无参数面，code 变异未启用")，不做启发式。
- **回测失败/无数据** → 该变体 fitness=NULL、status=degraded + reason；整轮全部失败 → 工具显式报错，**禁止任何 fallback 数字**。
- fitness 归一公式第一版：`0.5*收益百分位 + 0.3*夏普百分位 + 0.2*胜率百分位`（同一批变体窗口内相对归一，防跨窗口不可比）；公式可配并落库（metrics 留原始值）。

## 5. agent-dh 改动清单

| 文件 | 动作 | 内容 |
|---|---|---|
| `quantsys-v2-client/src/client.ts` | 改动 | 新增 `evolutionRunStrategy(params)` / `getStrategyEvolutionRuns(id)` / `getStrategyLeaderboard()`（对齐 §3 路由契约） |
| `packages/evolution/src/index.ts` | 改动 | 插件从 `agentOS` 依赖切到 `quantsysV2`（baseURL 5001）；保留 aos 作为 fallback 仅当 qv2 明确 404 |
| `packages/evolution/src/tools/EvolutionRunTool/EvolutionRunTool.ts` | 改动 | execute 改调 qv2；响应加 `data_source: 'qv2_real_backtest'` vs `'degraded'` 显式标记；去除 aos strategy_id string→number 兼容 hack（若不再需要） |
| `packages/evolution/src/tools/EvolutionLeaderboardTool/EvolutionLeaderboardTool.ts` | 改动 | 改读 qv2 真实 leaderboard；schema 加 `data_source`/`as_of` 字段；空榜返回 `{entries:[], data_source:'empty', note:'无真实进化记录'}` 而非占位 |
| prompt.ts ×2 | 改动 | description 补"基于 qv2 真实回测"；expectedResult 更新（不再示例占位分） |
| tests | 新增 | evolution 工具契约测试（mock qv2 响应 → 校验归一化与 degraded 路径）；schema smoke 已有（新包不新增） |

## 6. 分期实施（每期可独立验收、可回滚）

| 期 | 内容 | 验收 | 估时 |
|---|---|---|---|
| **P0 止血（占位退役最小步）** | agent-dh evolution_leaderboard/run：不再透传 agent-os 占位结果；detect 到 aos 占位特征（fitness∈{0.05×i}）即返回 degraded+说明；evolution_leaderboard 空榜诚实文案 | agent 调用两工具看到的是"degraded/空+原因"，不再有 0.1-0.2 假排名 | 0.5 天 |
| **P1 引擎（qv2 真实进化）** | §3 新增服务/仓储/路由/变异器 + 表迁移 + 引擎测试；对 1 个真实策略（如 635 macd-golden-cross-v1）跑通"参数网格→回测→fitness→落库" | curl POST /api/evolution/strategies/run 得到真实回测 fitness；evolution_strategy_runs 有 completed 行；变体间 fitness 有区分 | 1.5-2 天 |
| **P2 工具迁移** | agent-dh evolution 插件切 qv2 + client 方法 + prompt/schema 更新 + 契约测试 | 工具返回真实 fitness/真实排名；degraded 路径经契约测试覆盖；schema smoke 全绿 | 1 天 |
| **P3 收尾** | agent-os evolution 路由标注 deprecation（停调度触发）；B 链账户 fitness 盘后续采接入；更新 RFC 008/005 相关引用；L4-B work-log 追加 B5 完成记录 | agent-os leaderboard 不再被 agent-dh 消费；B 链 evolution_fitness 持续有新行（连续 3 日） | 0.5-1 天 |

P0 先行（当日可交付止血），P1-P2 为"完全修复"主体，P3 收尾。

## 7. 风险与对策

| 风险 | 对策 |
|---|---|
| 变体回测耗时（N 变体 × 回测窗口）超工具 timeout（evolution_run 现 60s） | 引擎异步化：POST 返回 run_id，GET runs 轮询；工具层 evolution_run 支持"提交后轮询"两段式（对 30s+ 场景） |
| code 策略无参数面 → 变异空间空 | 如实 degraded（§4），不发明启发式 |
| 并行会话脏文件冲突（qv2 routes/daily_jobs 多窗口在改） | 实施前 git status 核对；新文件为主（新增路由/服务不入已有脏文件）；daily_jobs 改走独立脚本+scheduler 任务 |
| fitness 跨窗口不可比 | 批内相对归一（§4）；窗口落库可审计 |
| 回测引擎自身缺陷传染 | P1 先用最小策略跑通人工核对回测指标合理性再批量 |

## 8. 不做的事（边界）

- ❌ 不把 B 链账户 fitness 冒充策略排名（对象不同）——B 链仅补生产者使其独立持续，语义标注"账户行为"。
- ❌ 不实现任意 code 语义变异（LLM 改写策略代码）——那是 L4 更远期能力，本 RFC 只做参数/常量邻域变异。
- ❌ 不删 agent-os evolution 代码（legacy 兼容），只停消费 + deprecation 标注。
- ❌ 不碰 genome（提示词文本）进化——那是 L4-B 已交付的独立链，本 RFC 只修策略参数/代码侧。

## 9. 关联

- 审计：docs/work-logs/2026-09/l4b-evolution-data-chain-audit-20260903.md
- L4-B：docs/work-logs/2026-09/l4b-genome-benchmark-implementation-20260903.md
- 上游：docs/work-logs/2026-09/profit-engine-autonomy-full-flow-audit-20260903.md
- agent-dh 自主文档：agent-dh/docs/rfcs/005-self-evolving-agent.md

## 10. 实施落位记录（P0-P2 实测，2026-09-05）

> 状态流转：RFC 012 收干净 = P0（占位拦截）→ P1（qv2 引擎）→ P2（agent-dh 工具迁移）已全部实施；P3 收尾（B 链 producer、RFC 008/005 引用、work-log）在本文档外推进。

| 期 | commit | 落位 | 验收证据 |
|---|---|---|---|
| P0 止血 | （并入 P1 前历次） | evolution 工具不再透传 aos 占位：detect 占位特征即 degraded+说明；空榜诚实文案 | 工具被调时返回 data_source=degraded，不再有 0.1-0.2 假排名 |
| P1 引擎 | `e00d4ee4` | qv2 `StrategyEvolutionService` + 变异器 + 路由 + 仓储；ThreadPoolExecutor 并行执行腿（§3 裁决 blockquote） | curl POST /api/evolution/engine/run：15 变体 full 19.7s 落库真实 fitness；strategy 635 有 b4f5212a（full 15 行）/07598ae7（propose）真实 run |
| P2 工具迁移 | `edd663f0` | agent-dh evolution 插件切 quantsysV2(:5001)；两工具 v2 重写；契约测试换代 | evolution-qv2-contract.test.ts 8/8 绿；plugin-schema.smoke 19/19 绿；profile 重启后 Live 调用返回 data_source=qv2_real |

**P2 落位与 §5 设计的差异（裁决登记，w-8366e526）**：

- **无 aos fallback**：§5 曾预期"保留 aos 作为 fallback 仅当 qv2 明确 404"。实施取消——aos 该链只剩占位语义，P0 已拦截其输出；保留 fallback 等于给"占位复辟"留后门（§0 占位退役目标）。qv2 引擎降级时返回 data_source=degraded，工具端不再有第二条腿。
- **leaderboard 语义升级**：§5 预期"读 qv2 真实 leaderboard"（跨策略）。引擎无跨策略全量榜（每个 run 属于单一 strategy_id）；跨策略比真实 fitness 无意义（不同策略/窗口/标的不可比）。实施为**按 strategy_id 读真实进化历史**（GET /api/evolution/engine/runs，每 run 一条 fitness 最优变体行，fitness DESC）：evolution_leaderboard 从"策略之间比占位分"变为"策略自身的进化轨迹排行"——`strategy_id` 参数随之必填。真实数据时 data_source=qv2_real；全批诚实失败=degraded；无记录=empty（三者均无占位数字）。
- **data_source 命名**：实际用 `qv2_real`（§5 预写 `qv2_real_backtest`）——短名无歧义（引擎只产真实回测 fitness，degraded 是唯一例外态）。
- **EvolutionRunTool 参数收紧**：strategy_id + symbol + 回测窗口（start_date/end_date 缺省自动 365 天）必填语义——qv2 引擎须指定标的与窗口（无"全策略默认范围"概念）；`mode` 枚举去掉 `validate`（引擎路由仅收 full/propose，validate 是引擎内部校验语义）。
- **client 方法**：§5 预写三方法，实际两方法——`getStrategyEvolutionRuns(strategyId, limit)` 即排行数据源（§5 的 `getStrategyLeaderboard` 无独立后端语义，不实现）。
- **placeholder.ts / P0 测试退役**：A 链占位检测工具随 aos 数据源删除（其唯一消费者是 P0 拦截分支）；测试换代 evolution-qv2-contract.test.ts。

**A 链 deprecation 状态**：agent-dh evolution 插件已完全停止消费 Agent OS（:8080）——代码级证据：`packages/evolution/src/index.ts` 无 agentOS 配置项、无 `AgentOSClient` import。Agent OS 侧 `/api/evolution` 代码保留（§8：不删 legacy），其产出不再被任何进化工具透传。调度器若仍有触发 aos evolution 的任务属 P3 清理项。

**P3 收尾状态（2026-09-05，w-8366e526 更新）**：
1. **B 链账户 fitness 盘后续采接入（8/14 断点恢复）**——✅ 完成：`quantsys-v2/adapters/inbound/fastapi_app/daily_jobs_bootstrap.py` 注册 `evolution_fitness` 盘后任务（20:35 周一~五）调 `EvolutionFitnessService.compute_all_accounts`（双侧捕获，幂等 upsert）。对象=账户行为，与策略参数进化分域（§0 修复目标）。验证：JOBS 注册冒烟通过 + Live trigger 落库新行（见 §11）。
2. **RFC 005/008 引用刷新**——✅ 完成：RFC 005 line 231 已标注 qv2 迁移（84f31bfa）；008 line 170 为 reward 占位、与 A 链数据源引用无关，不改。
3. **L4-B work-log 追加**——✅ 完成：`docs/work-logs/2026-09/l4b-genome-benchmark-implementation-20260903.md` §5 追加 B5 关闭记录。
4. **agent-os evolution 路由 deprecation 标注（停调度触发）**——⏸ 待办（受并行会话 in-flight 脏文件 `agent-os/internal/api/evolution_handler.go` 阻塞，冲突解除后执行：路由标注 deprecation + 检查清理调度器 aos evolution 任务）。agent-dh 侧消费已停（代码级证据见上）。

## 11. P3 Live 验证（2026-09-05）

| 项 | 证据 |
|---|---|
| JOBS 注册冒烟 | `JOBS` 含 evolution_fitness，handler `_job_evolution_fitness` 可导入 |
| Live trigger | `POST /api/jobs/inprocess/evolution_fitness/run`（force）→ evolution_fitness 表 window_end=当日新行（断点恢复；连续 3 日由定时任务自行验证） |
| L4-B B5 关闭 | l4b-genome-benchmark-implementation-20260903.md §5 |
