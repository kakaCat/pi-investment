# REQ-261001145152-3982: V2 项目全面审查与优化梳理

**需求ID**: REQ-261001145152-3982
**类型**: feature（存量体检 / spike 性质）
**作用域**: `quantsys-v2/`（V2 后端仓库，Python + FastAPI + PostgreSQL）
**档位**: 轻档（L3 依据见文末；一旦出现"要动架构 / 要新增子系统 / 要改数据模型"信号即单向升级重档）

## TL;DR

V2 不是"代码写得乱"，而是**同一个职责被实现了多份、且多份之间已经开始互相漂移**；
更紧的是：**服务自 2026-09-13 起就没再跑过（18 天），K 线数据停在 09-11（20 天前）**，
而这一事实在仓库里没有任何红灯。

```
                 ┌─────────────── 4 套调度并存 ───────────────┐
                 │ DailyJobs 线程(9) │ AgentOS webhook(33 占位) │
                 │ APScheduler 回退   │ UnifiedScheduler(空转)   │
                 └────────────────────┬────────────────────────┘
                                      ▼
   同一作业多份注册 ──▶ 4 个 cron 时点各有 2~3 个启用任务重复
                                      ▼
   2026-09-13 15:33 之后：日志/台账/进程 全部静止（今天 2026-10-01）

   代码侧同形问题：
   domain/quantlib(78f/30k行) ── vs ── infrastructure/quantlib(17f/3.7k行)
        └─ 628 行逐字相同；data_validator 已分叉（834 行 vs 395 行）
   akshare_adapter ×2（891 行 vs 885 行）：09-14 的 logger 修复只打了其中一份
```

## 边界

### 做什么

1. **盘点资产**：规模、分层、超大文件（god file）、tests 与源码的镜像关系。
2. **盘点重复与分叉**：同一职责的多份实现、逐字重复、已漂移的副本、双栈残留（Flask/FastAPI）。
3. **盘点运行态**：4 套调度器的真实驱动关系、DB 里的重复任务、数据新鲜度、服务存活证据。
4. **盘点可复现性**：依赖声明与真实 import 的差距、虚拟环境、CI/静态检查缺口。
5. **盘点文档与仓库卫生**：文档分层违规、git 跟踪的产物、日志与覆盖率目录体积、卫生债指标。
6. **产出优化清单**：按「收益 / 风险 / 成本」排序，每条附**可复现命令 + 证据 + 验证方式**。

### 不做什么

- **本轮不改任何生产代码**：只出审查报告与改造清单（改代码是后续独立需求的实施段）。
- **不动数据**：不清理 `quant_investment` 库里的表、不跑数据补救；只读取证据。
- **不评价策略与收益**：V13/V14 策略本身的赚钱能力不在本次审查范围（只审工程结构）。
- **不重构 `domain/quantlib` 内部算法**：只判断"该保留哪一份"。

### 边界理由

- 用户诉求是"内容特别多，需要**梳理**看看如何优化"——先要一张可信的地图与排序，
  直接动刀会在 40 万行存量上放大风险（且该仓库自身 CLAUDE.md 要求改代码走 worktree + 验证）。
- 运行态问题（服务停了 18 天）与代码结构问题（重复实现）**修复方式与风险完全不同**，
  必须先分开陈述、再分别排序，否则优化清单会被"重启服务"这类一小时能做完的事淹没。

## 产品定义

### 一句话

给 V2 交付一份**有证据链的健康体检报告 + 按收益排序的优化清单**，让"下一步该动哪里"不再靠猜。

### 为什么现在做

1. **体量与信噪比已经失衡**：1,864 个 Python 文件 / 408,958 行（排除双 venv），
   其中 `scripts/` 127 个文件、`tests/` 606 个文件；同一职责存在 2 份实现的地方已至少 4 处。
2. **重复已经产生真实缺陷**：两份 `akshare_adapter.py` 中，09-14 的 logger `NameError` 修复
   只落在 `adapters/` 那份，`infrastructure/quantlib/adapters/akshare_adapter.py` 至今
   仍用 `except Exception: pass` 吞掉实时行情抓取失败——同一 bug 修了一半。
3. **运行事实与文档严重不符**：`CLAUDE.md` 里"唯一宿主 / 已删除 / 固定端口"等多处描述
   与代码现状矛盾，新人（与 agent）按文档操作会直接踩空。
4. **本仓库历史上已两次因"静默死亡"付出代价**（CLAUDE.md 自述：08-05 调度死讯静默 8 天），
   而本次实测**第 3 次正在发生且无人知晓**。

### 现状实测（全部可复核，2026-10-01 采集）

| 维度 | 实测值 | 证据命令 |
|---|---|---|
| Python 文件 / 行数 | 1,864 / 408,958 | `find . -name "*.py" -not -path "./venv/*" -not -path "./.venv/*" -not -path "*/__pycache__/*" \| wc -l` |
| tests 文件 / 行数 | 606 / 107,221 | `find tests -name "*.py" \| wc -l` |
| pytest 收集 | **5,264 通过 + 119 模块 ImportError** | `python -m pytest --collect-only -q` |
| 收集失败主因 | pybreaker 101 / pydantic_settings 10 / jieba 7 | 同上，错误聚合 |
| 依赖声明 | pyproject 13 个 vs `docs/misc/requirements.txt` 61 个 | `comm -23` 两清单 |
| 服务最后活动 | **2026-09-13 15:33**（今天 2026-10-01） | `ls -lT logs/fastapi_5001.log`；`quant.scheduler_runs` 最新行 |
| K 线数据最新 | **2026-09-11** | `select max(trade_date) from quant.daily_klines` |
| DB 启用任务 | 26 启用 / 7 禁用，其中 **4 个 cron 时点重复 2~3 个任务** | `group by cron_expression having count(*)>1` |
| 调度器套数 | **4 套**（DailyJobs 线程 / Agent OS / APScheduler / UnifiedScheduler） | `adapters/inbound/fastapi_app/main.py:225-370` |
| quantlib 双份 | 628 行逐字相同；`data_validator` 已分叉 | `md5` / `diff` 对照 |
| docs 分层违规 | `docs/` 根目录散落 **140** 个 md | `find docs -maxdepth 1 -name "*.md" \| wc -l` |
| git 跟踪的产物 | 98 个 `.pyc/.pkl/.log` | `git ls-files \| grep -cE "\.(pyc\|pkl\|log)$"` |
| 体积垃圾 | `logs/` 354M、`htmlcov/` 157M、双 venv 1.4G | `du -sh` |
| 卫生债 | bare except 41、`except: pass` ≈134、`sys.path.insert` 136、库层裸 print 144 | `grep -rn` 计数 |
| 合规正例 | 通知架构已收口（26 个文件走 `NotificationFacade`，application 层无直连 channel） | `grep -rl NotificationFacade` |

### 已确认的矛盾点（文档 vs 代码）

| 文档说法 | 代码现状 |
|---|---|
| 入口 `api/server.py` / `cli/main.py` | 两者均**不存在**；实际为 `adapters/inbound/fastapi_app/main.py`、`adapters/inbound/cli/main.py` |
| `pip install -r requirements.txt` | 根目录**无** requirements.txt（完整版埋在 `docs/misc/`） |
| "Read `DATA_ACCESS_GUIDE.md`（mandatory）" | 全仓**无此文件** |
| Flask 路由"随回滚栈保留" | `adapters/inbound/api/` 只剩 3 个 `.bak`（且未被 git 跟踪）→ 回滚栈实际不存在 |
| `infrastructure/repositories/` 放 Repository | 该目录**为空**；真实位置是 `adapters/outbound/repositories/`（73 文件） |
| `scheduler_daemon/unified_scheduler` 已删除 | `unified_scheduler.py`（311 行）仍在，被 `main.py` 启动；但其 `start()` 只翻标志位、无驱动循环 |
| `USE_AGENT_OS_SCHEDULER` 开关 | 代码内**零引用**（只存在于文档），真实开关是 `AGENT_OS_ENABLED` |
| `launchctl kickstart ... com.pi-investment.v2-api` | `~/Library/LaunchAgents/` 下**无此 plist** |

## 用户与角色

- **项目所有者（人类）**：本次审查的主读者。需求是"内容太多，怎么优化"，
  拿到的应是**能直接排期**的清单，而不是又一份 4 万字的分析。
- **窗口 AI Agent（后续实施者）**：按清单逐条领任务。清单里的每条必须带
  文件路径 + 命令锚点，否则 agent 无法自证完成。
- **新加入的协作者 / 新会话**：`CLAUDE.md` 与 `docs/` 是唯一入口；上述矛盾点会让他们按错误路径操作。

## 功能点

**FR-1: 资产与分层盘点**
给出文件数/行数（按 domain/application/adapters/infrastructure/tests/scripts 分层）、
超大文件（>800 行）TOP 榜、以及分层反向依赖的**全量**发生点（domain→infrastructure 等）。

**FR-2: 重复实现与分叉盘点**
逐项列出同一职责的多份实现（quantlib 双份、akshare adapter 双份、Flask/FastAPI 双栈、
scheduler 多套），每项给出：位置、行数、谁在用、逐字重复行数、**是否已分叉**、合并建议。

**FR-3: 调度与运行态盘点**
画清 4 套调度器的真实驱动关系（谁真的会触发、谁是空转），
列出 DB 里重复的 cron 任务对，并给出服务存活 / 数据新鲜度的实测时间点。

**FR-4: 依赖与环境可复现性盘点**
对比 pyproject 与 `docs/misc/requirements.txt` 的差集；
列出"代码硬 import 但未安装"的模块（区分模块级硬导入 vs `try` 软导入 vs 函数内延迟导入）；
指出 `psycopg2` vs `psycopg2-binary` 这类**与历史事故记录直接冲突**的声明。

**FR-5: 文档与仓库卫生盘点**
docs 分层违规清单、git 跟踪的产物文件、日志/覆盖率/虚拟环境体积、
卫生债指标（bare except、`except: pass`、`sys.path.insert`、裸 print、TODO 数），
并标注哪些已被 `.gitignore` 覆盖、哪些仍在版本控制里。

**FR-6: 优化清单（本需求的核心产物）**
输出按「收益 / 风险 / 成本」三维排序的条目，每条包含：
`问题 → 证据（命令+输出） → 建议动作 → 影响面 → 验证方式`。
必须区分三类优先级：**P0 线上/运行态**（服务已停、数据已断）、
**P1 正确性风险**（分叉副本、未声明依赖导致的测试不可集）、
**P2 可维护性**（god file、文档、卫生债）。

**FR-7: 判定标准可证伪**
本需求的"完成"必须可被第三方复核：报告里每条结论都附可执行命令；
随机抽查 5 条结论，命令输出须与报告一致；清单里每条 P0/P1 必须能指出
"改哪个文件、验证看到什么"。

## 验收标准（跑什么、看到什么算过）

1. 产出审查报告（path 见设计阶段），其中**每条**结论带命令与输出摘要；
   抽查 5 条 → 输出与报告一致。
2. 优化清单条目 ≥ 12 条，每条都有「文件路径 + 验证方式」；
   按 P0/P1/P2 三类分组，组内按收益降序。
3. 报告明确列出"**本次不改代码**"，并给出后续实施建议的批次划分。
4. 矛盾点表（文档 vs 代码）中 8 条全部可复现。

## 相关

- 设计/报告：`docs/requirements/REQ-261001145152-3982/design/`（审查报告 + 优化清单）
- 拆分计划：`docs/requirements/REQ-261001145152-3982/decomposition.md`（后续阶段）
- 既有相关审计：`docs/audits/2026-09-06-live-trading-audit.md`、`docs/domain-boundary-audit-2026-08.md`

## 轻档依据（L3）与升级触发

- **为什么可以走轻档**：本轮产出是**只读审查报告**，不改代码、不改数据模型、不新增子系统，
  决策点唯一（"优化清单采不采纳、先做哪条"由人在拆分阶段裁定）。
- **单向升级触发**：一旦在实施段出现以下任一信号，立即升级重档并停手——
  要删除/合并 `quantlib` 任一份（动架构）、要改调度器拓扑（动运行时架构）、
  要改 `quant.scheduler_tasks` 表结构（改数据模型）。
