---
req_id: REQ-261001145152-3982
title: V2 优化清单与执行契约
category: feature
doc: design/optimization-backlog
serves: FR-6, FR-7
---

# V2 优化清单（按收益/风险/成本排序）

**上游**：[audit-report.md](audit-report.md)（本清单每条都引用其中的证据）
**性质**：清单本身**不含代码改动**；它是 decomposing 阶段的输入——每条可直接映射为一张任务卡。

## TL;DR（serves: FR-6, FR-7）

```
21 条 → 4 个批次，批与批之间有硬前置关系

  批 1（P0 · 今天）     把服务救活 + 补自动探针 ────────┐ 不先做，后面所有验证都没有基线
                                                        │
  批 2（P1 · 本周）     护栏 + 依赖 + 删重复 + 修悬空 ──┤ 护栏必须先于治理，否则改完又漂
                                                        │
  批 3（P2 · 2~3 周）   分层收口 + 拆上帝文件 + 端口/DI 收敛
                                                        │
  批 4（P3 · 随时可做） 文档/产物/体积/卫生债 ───────────┘ 纯卫生，可与批 3 并行

  贯穿原则：先"删"（可验证、可 revert），后"改"（需回归）；先"加护栏"，后"动结构"。
```

**如果只能做三件**：`P0-1` 把服务救活 → `P1-1` 依赖收口（让 119 个测试模块能跑）→ `P2-1` 挂上护栏（让 117 处违规只减不增）。

---

## 1. 条目契约（清单的数据契约）（serves: FR-6）

### 1.0 接口适用性说明（为什么没有运行时接口）（serves: FR-6）

本需求是**只读审查 + 清单**，**不新增/不修改任何运行时接口**：
无 HTTP 端点变更、无 DB schema 变更、无新增对外契约。因此接口视角收敛为
"**文档交付物如何被下游消费**"——即下面这张条目契约表（decomposing 阶段按字段映射成任务卡）。

真正需要接口签名的是**清单里的实施条目**（如 P1-2 改 `get_config` 的签名），
那些在各自条目落成任务卡时由实施方定义，不在本设计内冻结。

### 1.1 条目字段契约（serves: FR-6）

decomposing 阶段把每条直接落成任务卡；字段与卡字段一一对应，不留空。

| 字段 | 类型 | 必填 | 约束 | 映射到任务卡 |
|---|---|---|---|---|
| `id` | string | ✅ | `P<0-3>-<n>`，前缀即优先级 | `key` |
| `priority` | enum | ✅ | `P0` 运行态 / `P1` 正确性 / `P2` 结构 / `P3` 卫生 | 分组 |
| `title` | string | ✅ | ≤60 字、动词开头 | `title` |
| `evidence` | string[] | ✅ | ≥1 条**可直接执行**的命令或 `文件:行` | `description` |
| `action` | string | ✅ | 明确到目录/文件（"删哪个、改哪个"） | `implementation` |
| `impact` | string | ✅ | 文件数 / 行数 / 受影响的调用方 | `description` |
| `verify` | string | ✅ | **可执行**验证：跑什么、看到什么算过 | `acceptance` |
| `risk` | enum | ✅ | `low` / `medium` / `high` | — |
| `cost` | string | ✅ | 人日量级 | — |
| `depends_on` | string[] | ❌ | 引用同批 `id` | `depends_on` |

**契约铁律**：`verify` 里出现"确认正常""看起来没问题"这类不可执行措辞 = 该条不合格，
禁止进入拆分（对应仓规"失败要响亮"）。

---

## 2. 批 1 · P0 运行态（最高优先，今天）（serves: FR-6）

### P0-1 把服务救活并留下"谁在跑"的证据（serves: FR-6）

| 字段 | 内容 |
|---|---|
| evidence | `ls -lT logs/fastapi_5001.log` → 2026-09-13 15:33；`curl -s -m3 127.0.0.1:5001/api/health` → `000`；`ls ~/Library/LaunchAgents/ \| grep v2-api` → 空 |
| action | 确认现网拉起方式（launchd plist 已丢失，需按实际部署方式重建或改用手工/其它守护）；启动 `adapters/inbound/fastapi_app/main.py`；首次启动会 `checkfirst` 建 `quant.inprocess_job_runs` 表 |
| impact | 全部 473 个端点 + 4 条后台线程恢复；无代码改动 |
| verify | ① `curl -s -o /dev/null -w "%{http_code}" 127.0.0.1:5001/docs` → `200`；② `psql -Atc "select count(*) from quant.inprocess_job_runs"` 不报 relation 不存在；③ 重启后 10 分钟内 `select max(started_at) from quant.scheduler_runs` 刷新 |
| risk | low |
| cost | 0.5 人日（含定位拉起方式） |

### P0-2 数据补跑（K 线滞后 20 天）（serves: FR-6）

| 字段 | 内容 |
|---|---|
| evidence | `select max(trade_date) from quant.daily_klines` → **2026-09-11**（今天 2026-10-01） |
| action | 服务恢复后按现有链路补跑：`kline_update` → 因子 → 筹码分布；用**已有**的 provider 入口（禁止新写脚本绕开 `DataProviderManager`） |
| impact | 09-11 之后的交易日数据；下游因子/信号/回测全部依赖 |
| verify | ① `select max(trade_date) from quant.daily_klines` = 最近交易日；② 因子表最新日期一致；③ `_job_freshness_guard` 手动跑一次返回 `status='fresh'` |
| risk | medium（补数据要防重复写入，走既有幂等链路） |
| depends_on | P0-1 |

### P0-3 给"静默死亡"装自动探针（本仓已经栽过 3 次）（serves: FR-6）

| 字段 | 内容 |
|---|---|
| evidence | CLAUDE.md 自述两次事故（08-02 盯盘消失一周、08-05 调度死讯静默 8 天）+ 本次实测第 3 次（停 18 天无人知晓） |
| action | 在**外部**（不依赖被监控进程）加两个探针：① 进程/端口心跳（5001 + 8080）；② 数据新鲜度（`max(trade_date)` 落后最近交易日 >1 天告警）。复用现有 `NotificationFacade`，不新写通知通道 |
| impact | 新文件 1~2 个（建议 `tools/` 或 launchd 定时脚本）+ 一条告警规则 |
| verify | ① 手工 `kill` 服务进程 → 5 分钟内收到飞书告警（截图/回执）；② 把探针的阈值改成 0 天 → 立即告警（证明不是"永不触发"的空壳） |
| risk | low |
| cost | 0.5 人日 |

---

## 3. 批 2 · P1 正确性（本周）（serves: FR-6）

### P1-1 依赖声明收口（让测试能跑）（serves: FR-6）

| 字段 | 内容 |
|---|---|
| evidence | `python -m pytest --collect-only -q` → `5264 collected, 119 errors`；错误聚合 `pybreaker 101 / pydantic_settings 10 / jieba 7`；`comm -23` 两清单 → 47 个包只在 `docs/misc/requirements.txt` |
| action | ① 把 `docs/misc/requirements.txt` 的内容合并进 `pyproject.toml`（pyproject 为唯一权威）；② **修正 `psycopg2-binary` → `psycopg2`**（requirements 注释记录 2026-08-11 double-OpenSSL 事故）；③ 声明 `pytest` 等 dev 依赖已在 optional-dependencies，保持 |
| impact | 依赖清单 13 → 60+；119 个测试模块恢复可收集 |
| verify | ① `python -m pytest --collect-only -q` → `errors` 为 **0**；② `python -c "import pybreaker, pydantic_settings, jieba"` 无异常；③ `grep -c psycopg2-binary pyproject.toml` → 0 |
| risk | medium（装依赖可能引入版本冲突；先建新 venv 验证再切换） |
| cost | 1 人日 |

### P1-2 修 `get_config()` 空壳（正确性缺陷，非风格）（serves: FR-6）

| 字段 | 内容 |
|---|---|
| evidence | `infrastructure/config/__init__.py:17-26` 只 `return default`；`python -c "from infrastructure.config import get_config; print(get_config('PGHOST','FALLBACK'))"` → `'FALLBACK'`；**29 处生产调用**（含 `persistence/database/engine.py` 取 DSN、`jwt_manager.py`、`llm_service.py`、`websocket_server.py`、`cli/main.py`） |
| action | 二选一并**一次性做完**：① 让 `get_config` 真正读 `settings`（pydantic）；或 ② 逐处改调用方到 `get_settings()`，然后删掉这个兼容层 |
| impact | 29 处调用点 / 12+ 文件；涉及 DSN、鉴权、LLM、WS |
| verify | ① 上述一行命令返回真实 `PGHOST`（非 `FALLBACK`）；② `grep -rn "get_config(" domain application adapters infrastructure \| grep -v "def get_config" \| wc -l` → 0（走方案 ②）；③ 服务能正常连库（启动日志无 DSN 异常） |
| risk | medium |
| cost | 0.5 人日 |

### P1-3 删重复实现（纯删除，收益最高）（serves: FR-6）

| 字段 | 内容 |
|---|---|
| evidence | ① `grep -rn "infrastructure\.quantlib\.adapters\." --include='*.py' .` 只命中该目录内部；② akshare 双份 `logger 定义 0 / 用法 17` vs `1 / 25`（修复只落一份）；③ `domain/quantlib/factors/` 只剩 8 个 `.py.bak` |
| action | 删除：① `infrastructure/quantlib/adapters/` 6 个克隆模块（**2,068 行，零外部引用**）；② `infrastructure/quantlib/core/{base_calculator,exceptions}.py`（516 行，**`core/pipeline.py` 不能删**——`tests/test_pipeline.py`、`tests/test_integration.py` 直接 import）；③ 13 个 `.bak`（8,097 行，全部未被 git 跟踪）+ 18 个孤儿 `__pycache__` + 9 个空壳包 |
| impact | 可删 **≈10,700 行**；消除"改错文件"与"修一半"复发源 |
| verify | ① 删除前 `python -m pytest tests/test_pipeline.py tests/test_integration.py -q` 有基线；② 删除后同命令**结果不变**；③ `git status` 无意外改动；④ `find . -name "*.bak" \| grep -v venv \| wc -l` → 0 |
| risk | low（已逐个验证引用方；`pipeline.py` 已排除） |
| cost | 1 人日 |

### P1-4 修悬空 import + 裁决 `BaseCalculator` 双类（serves: FR-6）

| 字段 | 内容 |
|---|---|
| evidence | `domain/quantlib/{stages,factor_analysis,factor_models,risk,backtest,prediction_markets,adapters}` 等 **9 个目录已无 `.py`**，但 `tools/backfill_factors.py:24`、`scripts/train_hs300_xgboost.py:185`、`scripts/tools/retrain_pipeline.py:19`、`tests/test_factor_compute_stage.py:18` 仍在 import → **必然 ImportError**；另有一处同形：`domain/quantlib/engine/{ensemble_vote_strategy,multi_factor_swing_strategy}.py` 从**同包内** import `strategy_base`/`strategy_combiner`/`strategy_factory`，而这三个文件**都不在该包**（实际在 `domain/backtest/engine/`）；`domain/quantlib/base_calculator.py`(501) 与 `domain/quantlib/core/base_calculator.py`(327) 是**两个不同的类对象** |
| action | ① 6+ 处悬空 import 改到现存位置（`domain/backtest/engine/strategy_base.py` 等）；② 人工裁决 `BaseCalculator` 唯一实现（建议收敛到 `domain/quantlib/core/`），逐调用方改导入 |
| impact | 6+ 个脚本/测试 + `domain/quantlib/engine/` 2 个文件；15+ 处 `BaseCalculator` 导入方 |
| verify | ① `python -c "import tools.backfill_factors"` 等逐个不报 ImportError；② `python -c "import domain.quantlib.engine.ensemble_vote_strategy"` 不再 ImportError；③ `grep -c "^class BaseCalculator" domain/quantlib/base_calculator.py domain/quantlib/core/base_calculator.py` → 只剩 1 处；④ 相关测试通过 |
| risk | **high**（跨侧 `isinstance` 静默失效，不能脚本批量改） |
| cost | 2 人日 |
| depends_on | P1-1（依赖不修，测试跑不起来，无法验证） |

### P1-5 调度去重：4 套 → 1 套（serves: FR-6）

| 字段 | 内容 |
|---|---|
| evidence | ① `sed -n '291,297p' infrastructure/scheduler/unified_scheduler.py` → `start()` 只翻标志位；② `grep -rn "run_job(" --include='*.py' . \| grep -v tests` → 0（生产无人调用）；③ DB `group by cron_expression having count(*)>1` → 4 个时点各 2~3 个启用任务；④ `grep -rn USE_AGENT_OS_SCHEDULER --include='*.py'` → 0（文档里的开关不存在） |
| action | ① 先**只禁用**DB 内重复任务（保留一份，观察一周台账）；② `UnifiedScheduler` 明确二选一：补驱动循环 or 删掉（连同 `config/scheduler_jobs.yml` + 路由 + 测试）；③ 文档里的 `USE_AGENT_OS_SCHEDULER` 与 `AGENT_OS_ENABLED` 统一 |
| impact | 6 个重复任务行；311 行空转模块 + 86 行 YAML + 路由；`main.py` lifespan 4 条线程 → 收敛 |
| verify | ① `select count(*) from (select cron_expression from quant.scheduler_tasks where is_enabled group by 1 having count(*)>1) t` → 0；② 连续 3 个交易日 `quant.inprocess_job_runs` 每个 job 每日仅 1 条 success；③ `grep -rn "unified_scheduler" --include='*.py' adapters/` 收敛到 0 或 1 个明确入口 |
| risk | medium（调度是生产命脉，**必须"先禁用观察、后删除"**，不可一次性停机重构） |
| cost | 2~3 人日 |
| depends_on | P0-1 |

### P1-6 删 5 个孤儿的重复 provider（792 行，数据访问规则的活标本）（serves: FR-6）

| 字段 | 内容 |
|---|---|
| evidence | `application/services/financial_providers/` 下 `{eastmoney,sina,akshare,tencent,tushare}_provider.py` 共 **792 行，无任何实例化方**；`adapters/outbound/datasources/manager.py:104` 实际装配的是 adapters 树里的 `SinaFinancialProvider` / `EastmoneyFinancialProvider` / `AkshareFinancialStatementProvider` |
| action | 删除这 5 个孤儿文件（先确认 `manager.py` 装配链与 `DATA_ACCESS_GUIDE` 口径一致），并入 P2-6 的 provider 归位一起裁决 |
| impact | 删 792 行；消除"同厂商两套 provider"的一半 |
| verify | ① `grep -rn "financial_providers\." --include='*.py' . \| grep -v "financial_providers/"` → 0；② `python -c "from adapters.outbound.datasources.manager import get_data_provider_manager"` 正常；③ 取数相关测试通过 |
| risk | low（已确认无实例化方） |
| cost | 0.5 人日 |
| depends_on | P1-1 |

---

## 4. 批 3 · P2 结构（2~3 周，需先有 P1-1 的测试基线）（serves: FR-6）

### P2-1 挂上护栏（**必须最先做**，否则改完继续漂）（serves: FR-6）

| 字段 | 内容 |
|---|---|
| evidence | `venv/bin/python tools/analyze_layer_violations.py` → **117 违规 / 54 文件**；`.git-hooks/pre-commit:37` → `BASELINE=7`（差 16 倍）；`core.hooksPath` 未指向 `.git-hooks`，真 git 目录下无任何已安装 hook；无 CI；tests 中无分层纯净性断言 |
| action | ① `git config core.hooksPath .git-hooks`；② `BASELINE` 7 → 117 并**按方向拆分**（区分"允许的 inbound"与真违规）；③ 加一条分层纯净性测试（把当前违规数写成断言，只许降不许升）；④ 可选：补最小 CI |
| impact | 1 个 hook 配置 + 1 个测试文件；此后所有分层改动可自动拦截 |
| verify | ① `git config --get core.hooksPath` → `.git-hooks`；② 故意在 `application/` 顶层加一行 `from adapters...` 后 `git commit` → **被 hook 拦下**（贴出拦截输出）；③ `pytest tests/test_layer_purity.py` 在无新增违规时通过 |
| risk | low |
| cost | 0.5 人日（**性价比最高的一条**） |

### P2-2 消 application 层 12 处顶层越层导入（serves: FR-6）

| 字段 | 内容 |
|---|---|
| evidence | `tools/analyze_layer_violations.py` 明细；`application/notification/notification_factory.py:20,28,29,30` 顶层导入 `infrastructure.config.settings` + `notification.channels.*` → **直接违反 CLAUDE.md 通知架构强制条款**；`application/services/scheduler.py:2` 是 `from infrastructure.scheduler.scheduler import *` 通配壳 |
| action | ① 12 处顶层导入改为经 port/工厂注入（或至少下沉到函数内，按裁定口径）；② 通知 factory 的装配点改为在 infrastructure 侧完成；③ 删通配 shim |
| impact | 12 处顶层 + 105 处函数内（B 类合计 117/54 文件） |
| verify | ① `tools/analyze_layer_violations.py` 违规数 **117 → 0（顶层部分）**；② `grep -rn "^from infrastructure.notification.channels" application/` → 0；③ 通知相关测试通过（`pytest tests/notification -q`） |
| risk | medium |
| cost | 2 人日 |
| depends_on | P2-1 |

### P2-3 拆两个"文件级上帝"（serves: FR-6）

| 字段 | 内容 |
|---|---|
| evidence | `application/services/scheduler_tasks.py` 1,607 行 / **0 类 35 个顶层函数**；`adapters/inbound/fastapi_app/daily_jobs_bootstrap.py` 1,147 行 / **42 个顶层函数** |
| action | 纯文件级拆分（按 job 域分文件，保持函数签名与注册表不变）；`daily_jobs_bootstrap` 拆成 `daily_jobs/{pipeline,jobs_health,pools}.py` + 保留薄注册层 |
| impact | 2 个大文件 → 8~10 个小文件；**不改调用契约** |
| verify | ① 拆分前后 `pytest tests/test_false_success_guard.py tests/e2e/p2_fixtures.py -q` 结果一致；② 两个文件行数 < 400；③ `JOBS` 列表内容与顺序 diff 为空 |
| risk | low（文件级搬运，逻辑不动） |
| cost | 1~2 人日 |

### P2-4 端口与 DI 收敛（serves: FR-6）

| 字段 | 内容 |
|---|---|
| evidence | `domain/ports/repository_ports.py` 与 `repository_ports_extended.py` **7 个同名接口**；另有 `domain/{trading,portfolio,watch}/ports/` 第三套；`service_factory.py`(893) / `enhanced_service_factory.py`(543) / `service_registry.py`(662) / `di/container.py` 四套装配；`adapters.outbound.repositories` 被 **87 处**直接 import（41 个 application 文件直连具体仓储） |
| action | ① 端口去重（7 个同名接口保留 `extended` 一份并 re-export）；② DI 收敛为 1 套入口，其余标 deprecated 后删；③ 直连仓储改走端口 |
| impact | 3 个端口文件 + 4 套 DI；87 处直连点 |
| verify | ① `comm -12` 两文件同名接口 → 空；② `grep -rc "enhanced_service_factory\|service_registry" application adapters \| ...` 收敛到 1 个入口；③ 全量测试基线不退化 |
| risk | **high**（24 节点强连通分量的枢纽在此） |
| cost | 5~8 人日 |
| depends_on | P2-1, P2-2 |

### P2-5 Repository 双轨收敛 + 修文档指向（serves: FR-6）

| 字段 | 内容 |
|---|---|
| evidence | `adapters/outbound/repositories/` 70 文件 / 84 类；`*_async_repository.py` ×9；`infrastructure/repositories/` **不存在**却被 CLAUDE.md 与 `docs/ARCHITECTURE.md` 写成 Repository 位置 |
| action | ① 统一为 async 优先或 sync 优先（需先定口径），另一轨删除；② 统一拆分粒度（`simulation_repository.py` 三实体同文件 vs async 版按实体拆）；③ 修文档指向 |
| impact | 9 组双轨（约 20 文件） |
| verify | ① `ls adapters/outbound/repositories/*async*.py` 收敛策略符合裁定；② `grep -rn "infrastructure/repositories" --include='*.md' .` → 0；③ 相关仓储测试通过 |
| risk | medium |
| cost | 3~5 人日 |

### P2-6 数据访问规则收口 + provider 归位（serves: FR-6）

| 字段 | 内容 |
|---|---|
| evidence | application 层 **7 处**直连外部数据源（`grep -rn "import akshare\|import tushare" --include='*.py' application`）：`core_plan_service.py:450`、`market_style_detector.py:250`、`financial_providers/{sina,akshare,eastmoney}_provider.py`、`quote_providers/akshare_provider.py:5`、`financial_providers/tushare_provider.py:35`；而 CLAUDE.md 明令 **NEVER directly import external data libraries** |
| action | ① 7 处改走 `DataProviderManager`；② 裁决 `application/services/{financial_providers,quote_providers}` 的去向——provider 属 adapters 职责，建议下沉（顺带解决"同厂商两套 provider"） |
| impact | 7 处直连 + 2 个 provider 包（约 10 文件） |
| verify | ① `grep -rn "import akshare\|import tushare\|import baostock\|import yfinance" --include='*.py' application domain` → 0；② `ls application/services/{financial_providers,quote_providers}` 已按裁定处置；③ 相关取数测试通过 |
| risk | medium |
| cost | 2 人日 |
| depends_on | P2-1 |

---

## 5. 批 4 · P3 卫生（随时可做，可与批 3 并行）（serves: FR-6）

### P3-1 docs 分层归位（140 个 md）（serves: FR-6）

| 字段 | 内容 |
|---|---|
| evidence | `find docs -maxdepth 1 -name "*.md" \| wc -l` → **140**；仓库已有 `tools/cleanup_quantsys_v2_docs.py`（在 monorepo 根，**无 dry-run**，未跑过） |
| action | ① 给该脚本加 `--dry-run`；② 先 dry-run 出迁移清单供人审；③ 再执行迁移；④ 跑 wiki 死链自检 |
| impact | 140 个文件 + 3 个 `docs/*.py` 示例 |
| verify | ① `find docs -maxdepth 1 -name "*.md" \| wc -l` → 仅剩 `README.md`；② `python3 agent-dh/scripts/wiki_probe.py` 无死链/孤儿页；③ `git status` 显示 rename 而非增删 |
| risk | low |
| cost | 0.5 人日 |

### P3-2 git 里的产物出库（serves: FR-6）

| 字段 | 内容 |
|---|---|
| evidence | ① `git ls-files \| grep -cE "\.(pyc\|pkl\|log)$"` → **98**；② **ignore 规则失效的已入库产物**：`git ls-files .pi-invest \| wc -l` → **19**（而 `.gitignore` 明确写 `.pi-invest/`）、`scripts` 170 + `tools` 55 仍被跟踪（ignore 里写了 `scripts/`）、`test_reports` 1、`data` 1、`ERROR_TRACKING.md` 1 |
| action | ① `git rm --cached`（保留工作区）清 98 个产物；② `.pi-invest/` 19 个改外部存储 + 保留说明；③ 决定 `scripts/`、`tools/` 是"入库"还是"忽略"——**当前自相矛盾**（ignore 说忽略、实际在跟踪），必须二选一；④ `git mv ERROR_TRACKING.md docs/work-logs/2026-09/` |
| impact | 98 + 19 + 1 + 1 + 1 个文件出库；1 个文件移动（保留历史） |
| verify | ① `git ls-files \| grep -cE "\.(pyc\|pkl\|log)$"` → 0；② `git ls-files .pi-invest \| wc -l` → 0；③ `git check-ignore -v scripts/<任一文件>` 与实际跟踪状态**一致**（不再自相矛盾）；④ `git status` 无文件被物理删除；⑤ `pytest` 基线不退化 |
| risk | low |
| cost | 1 人日 |

### P3-3 体积与虚拟环境（serves: FR-6）

| 字段 | 内容 |
|---|---|
| evidence | `du -sh`：**`live_trading/logs/` 5.2G（全仓最大单点垃圾，git 跟踪 0）**、`venv` 801M + `.venv` 642M、`logs/` 354M（单文件 174M）、`htmlcov/` 157M、`.pi-invest/` 43M |
| action | ① **先清 `live_trading/logs/`（5.2G，纯运行日志、零跟踪）**；② 统一到**一个** venv（对齐 `.python-version` 3.13）；③ 日志轮转（logrotate 或内置 `RotatingFileHandler`）——`live_trading/` 与主 `logs/` 都要覆盖；④ 清历史大日志 + `htmlcov/` 纳入清理流程 |
| impact | 合计可释放 **≈6.5G**（其中 5.2G 占 80%） |
| verify | ① `du -sh live_trading/logs` 显著下降；② `du -sh .` 合计下降 ≥5G；③ 新日志按大小轮转（触发一次可见 `.1` 文件）；④ 服务重启后仍能正常写日志 |
| risk | low |
| cost | 0.5 人日 |

### P3-4 修 CLAUDE.md 的 8 条矛盾（serves: FR-6）

| 字段 | 内容 |
|---|---|
| evidence | 见 [audit-report.md §5.6](audit-report.md)：入口路径、`requirements.txt`、`DATA_ACCESS_GUIDE.md`、Flask 回滚栈、`infrastructure/repositories/`、`unified_scheduler` 已删、`USE_AGENT_OS_SCHEDULER`、launchd plist |
| action | 逐条改写；`DATA_ACCESS_GUIDE.md` 若确已废弃则删引用，若有替代则补链接；入口路径统一为 `adapters/inbound/...` |
| impact | `CLAUDE.md`（含速查表）+ 至少 9 份提到 `pip install -r requirements.txt` 的文档 |
| verify | ① 8 条逐条命令复核（见 §6）；② `grep -rn "pip install -r requirements.txt" --include='*.md' . \| wc -l` → 0 或全部指向真实存在的路径 |
| risk | low |
| cost | 0.5 人日 |

### P3-5 卫生债批量清理（serves: FR-6）

| 字段 | 内容 |
|---|---|
| evidence | bare `except:` **41**；`except ...: pass` **≈134**；`sys.path.insert` **136**（16 处在库层）；库层裸 `print` **144**；`logging.basicConfig` **12**（pre-commit 明令禁止）；库层内嵌 `__main__` **20** |
| action | ① bare except 全部改为具体异常（至少 `except Exception`）；② `except: pass` 处补日志（结构化告警，不静默）；③ 库层 `sys.path.insert` 清零（入口统一由 `PYTHONPATH` 提供）；④ 库层 `print` → structlog；⑤ 清 `logging.basicConfig`；⑥ 库层 `__main__` 移到 `scripts/` |
| impact | 约 550 处改动，跨四层 |
| verify | ① 上述 6 个 grep 计数逐项下降至目标值（bare except 0 / basicConfig 0 / 库层 sys.path 0）；② 全量测试基线不退化；③ 每条改动按主题分批提交，便于 revert |
| risk | medium（量大，需分批；静默 except 补日志可能暴露既有隐患——这是好事但要有人接） |
| cost | 3~5 人日 |

### P3-6 scripts / tools 归位：删一次性脚本 + 回收误置测试（serves: FR-6）

| 字段 | 内容 |
|---|---|
| evidence | ① **已确认 0 引用**的 5 个日期戳一次性脚本：`calibrate_20260723_{v13,v14}_return.py`、`migrate_20260720_multi_account.py`、`migrate_20260813_{action_case_unify,scheduler_tasks}.py`（对 `docs/ infrastructure/ deployment/ config/ ~/Library/LaunchAgents` 全量 grep = 0，且对应迁移已完成）；② **14 个 `test_*.py` 误置在 `scripts/`**（`test_orm*.py` 被文档引用 10~11 次 → 不可盲删，需迁移+改文档）；③ 7 个 `_v2`/`_fixed`/`_new` 补丁产物（违反 CLAUDE.md 平行文件禁令，**调用方未验证**）；④ `scripts/` 已有 `{migrations,tools,examples,diagnostics,maintenance,refactor}/`，但**94 个仍平铺在根** |
| action | ① 删 5 个已确认 0 引用的一次性脚本；② 14 个误置测试 `git mv` 到 `tests/` 并更新文档引用；③ 7 个补丁产物逐个反查调用方后处理；④ 新脚本一律进分类子目录（把"已有体系但新增未遵守"补上） |
| impact | 5 删 + 14 迁移 + 7 待定；`scripts/` 根从 94 个平铺降下来 |
| verify | ① `ls scripts/*.py \| wc -l` 显著下降且 `scripts/test_*.py \| wc -l` → 0；② 迁移后的测试在 `tests/` 下能被 `pytest --collect-only` 收集（数目增加）；③ 文档里对 `scripts/test_orm*.py` 的引用已更新（`grep -rn "scripts/test_orm" --include='*.md' .` → 0 或指向新路径） |
| risk | low~medium（`_v2`/`_fixed` 未验证，须逐个确认） |
| cost | 1 人日 |

---

## 6. 复现校验（本设计的验收口径）（serves: FR-7）

任何人可按下表逐条复核；抽查 5 条，输出须与报告一致。

| # | 结论 | 复现命令 | 期望 |
|---|---|---|---|
| 1 | 服务停摆 | `ls -lT logs/fastapi_5001.log` | 2026-09-13 15:33 |
| 2 | 数据滞后 | `psql -h 127.0.0.1 -U mac -d quant_investment -At -c "select max(trade_date) from quant.daily_klines"` | 2026-09-11 |
| 3 | 测试不可收集 | `python -m pytest --collect-only -q 2>&1 \| tail -1` | `5264 tests collected, 119 errors` |
| 4 | 分层违规 | `venv/bin/python tools/analyze_layer_violations.py \| grep 违规导入总数` | `117` |
| 5 | 护栏失效 | `grep -n BASELINE .git-hooks/pre-commit` | `BASELINE=7` |
| 6 | `get_config` 空壳 | `python -c "from infrastructure.config import get_config; print(get_config('PGHOST','FALLBACK'))"` | `FALLBACK` |
| 7 | 调度重复 | `psql ... -c "select cron_expression, count(*) from quant.scheduler_tasks where is_enabled group by 1 having count(*)>1"` | 4 行（3/3/2/2） |
| 8 | UnifiedScheduler 空转 | `sed -n '291,297p' infrastructure/scheduler/unified_scheduler.py` | `start()` 只有 `self._running = True` + log |
| 9 | 双份端口 | `comm -12 <(grep -oE "^class I[A-Za-z]+" domain/ports/repository_ports.py \| sort) <(grep -oE "^class I[A-Za-z]+" domain/ports/repository_ports_extended.py \| sort)` | 7 个同名接口 |
| 10 | 删除项零引用 | `grep -rn "infrastructure\.quantlib\.adapters\." --include='*.py' .` | 仅命中该目录内部 |
| 11 | 被跟踪产物 | `git ls-files \| grep -cE "\.(pyc\|pkl\|log)$"` | 98 |
| 12 | 文档散落 | `find docs -maxdepth 1 -name "*.md" \| wc -l` | 140 |
| 13 | 最大单点垃圾 | `du -sh live_trading/logs` | 5.2G（`git ls-files live_trading/logs \| wc -l` → 0） |
| 14 | ignore 规则失效 | `git ls-files .pi-invest \| wc -l` | 19（`.gitignore` 却写 `.pi-invest/`） |
| 15 | 孤儿模块口径差 | 严格扫描 35 个真孤儿 vs 仅全限定名扫描 165 个 | 两值都成立，**差距本身是"不能靠静态扫描删代码"的证据** |

**完成判定**（可证伪）：

- [ ] 15 条命令全部可执行且输出与上表一致（抽查 5 条即可）。
- [ ] 清单条目 **21 条**，每条 `verify` 字段均为可执行命令/断言，无"确认正常"类措辞。
- [ ] 批 1 的 3 条给出明确的"看到什么算过"，且不依赖本次未做的工作。

---

## 7. 迁移与兼容设计（serves: FR-6）

本设计**不含代码改动**，因此"迁移"指**清单的执行顺序契约**：

| 规则 | 内容 | 理由 |
|---|---|---|
| 护栏先于治理 | P2-1 必须早于 P2-2/P2-4 | 否则"改完又被新代码漂回去"（117 vs 7 就是没护栏的后果） |
| 测试基线先于改动 | P1-1 必须早于 P1-4/P2-* | 119 个模块不可收集时，任何改动都无法验证 |
| 先删后改 | P1-3（纯删除）先做 | 删除可 revert、无需回归；改结构需要 |
| 调度"先禁用后删除" | P1-5 分两步，中间观察一周 | 调度是生产命脉，本仓已因调度死过两次 |
| 灰度 | 调度/依赖类改动走新 venv 或新进程验证后再切换 | 与 P1-1 的风险控制一致 |

**回滚路径**：每条独立 worktree + 独立 commit（遵仓库 `CLAUDE.md` 的多会话隔离规则）；
纯删除类改动直接 `git revert`；结构性改动回滚后须重跑当批的 `verify` 命令确认回到基线。

**本轮不做**：不评价 V13/V14 策略收益、不动数据库表结构、不重构 `domain/quantlib` 的算法实现。
