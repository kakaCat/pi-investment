# 拆分计划（REQ-261001145152-3982）

**上游**：[audit-report.md](design/audit-report.md)（证据）· [optimization-backlog.md](design/optimization-backlog.md)（21 条条目）
**目标**：把 21 条优化条目落成可独立执行、可独立验收的任务卡，并锁定批次顺序与回滚路径。

## TL;DR

```
  21 张卡 / 4 个批次 / 一条硬前置链

  批 1 (P0, 3 卡)  救活服务 → 补数据 → 装探针
        │                （不先做，后面所有 verify 都没有基线）
        ▼
  批 2 (P1, 6 卡)  依赖收口 → get_config → 删重复 → 修悬空 → 调度去重 → 删孤儿 provider
        │                （P1-1 是 P1-4 的硬前置：测试不可收集则无法验证任何改动）
        ▼
  批 3 (P2, 6 卡)  挂护栏 → 消越层 → 拆上帝文件 → 端口/DI → Repository 双轨 → 数据访问
        │                （P2-1 必须最先：护栏是"不再漂回去"的保险）
        ▼
  批 4 (P3, 6 卡)  文档归位 / 产物出库 / 体积 / CLAUDE.md / 卫生债 / scripts 归位
                        （与批 3 无依赖，可并行；也可最先清 5.2G 垃圾）

  ★ 三张必做：P0-1 → P1-1 → P2-1
```

## 改动盘点（对照设计文档）

| 类别 | 内容 | 规模 | 归属卡 |
|---|---|---|---|
| **删除** | `infrastructure/quantlib/adapters/` 6 模块 | 2,068 行 | P1-3 |
| **删除** | `infrastructure/quantlib/core/{base_calculator,exceptions}.py` | 516 行 | P1-3 |
| **删除** | 13 个 `.bak` + 18 个孤儿 `__pycache__` + 9 个空壳包 | 8,097 行 | P1-3 |
| **删除** | 5 个孤儿 provider（`financial_providers/`） | 792 行 | P1-6 |
| **删除** | 5 个一次性脚本 + 14 个误置测试迁移 | ~2,000 行 | P3-6 |
| **修改** | `pyproject.toml` 依赖收口（13 → 60+） | 1 文件 | P1-1 |
| **修改** | `infrastructure/config/__init__.py` + 29 处调用点 | 12+ 文件 | P1-2 |
| **修改** | 悬空 import 6+ 处 + `BaseCalculator` 双类裁决 | 20+ 文件 | P1-4 |
| **修改** | `quant.scheduler_tasks` 6 行禁用 + `UnifiedScheduler` 二选一 | 6 行 + 311 行 | P1-5 |
| **修改** | `.git-hooks/pre-commit`（BASELINE 7→117）+ hook 安装 + 纯净性测试 | 2 文件 | P2-1 |
| **修改** | 12 处 application 顶层越层导入 | 12 处 | P2-2 |
| **新增** | 分层纯净性断言测试 | 1 文件 | P2-1 |
| **新增** | 外部存活/新鲜度探针 | 1~2 文件 | P0-3 |
| **无改动** | 数据库 schema / HTTP 接口 | 0 | — |

**数据契约**：本计划**不改任何数据结构**（无 DDL）。唯一涉及的库内变更是
`quant.scheduler_tasks` 的 **6 行 `is_enabled` 置 false**（P1-5），可 `update … set is_enabled=true` 回滚。

**迁移与兼容卡**：由 **P1-5** 承接（调度"先禁用观察一周 → 再删除"的分步灰度），
它是本计划里唯一需要"旧行为与新行为并存一段时间"的改动。

## 需求条款覆盖对照表

说明：FR-1…FR-5、FR-7 描述的是**审查动作本身**（已在设计阶段交付：
[audit-report.md](design/audit-report.md) + [test-cases.md](design/test-cases.md)）。
下表把它们映射到**落实这些结论的实施卡**——即"审查出来的问题由谁改"。

| 需求条款 | 条款内容 | 接收任务 |
|---|---|---|
| FR-1 | 资产与分层盘点 | t-p2-1, t-p2-2 |
| FR-2 | 重复实现与分叉盘点 | t-p1-3, t-p1-6 |
| FR-3 | 调度与运行态盘点 | t-p0-1, t-p0-2, t-p0-3, t-p1-5 |
| FR-4 | 依赖与环境可复现性盘点 | t-p1-1, t-p3-3 |
| FR-5 | 文档与仓库卫生盘点 | t-p3-1, t-p3-2, t-p3-4, t-p3-6 |
| FR-6 | 优化清单（本需求核心产物） | t-p0-1, t-p0-2, t-p0-3, t-p1-1, t-p1-2, t-p1-3, t-p1-4, t-p1-5, t-p1-6, t-p2-1, t-p2-2, t-p2-3, t-p2-4, t-p2-5, t-p2-6, t-p3-1, t-p3-2, t-p3-3, t-p3-4, t-p3-5, t-p3-6 |
| FR-7 | 判定标准可证伪 | t-p2-1, t-p2-2, t-p2-3, t-p2-4, t-p2-5, t-p2-6, t-p3-5（每卡 acceptance 即可执行的证伪口径；护栏类卡另加断言测试） |

**无"本轮不做"条款**：FR-1…FR-7 全部有接收任务。

## 任务表

| key | 标题 | phase | side | depends_on | 验收要点（可跑） |
|---|---|---|---|---|---|
| t-p0-1 | 把 V2 服务救活并留下运行证据 | implement | backend | — | `curl -s -o /dev/null -w "%{http_code}" 127.0.0.1:5001/docs` → 200；`quant.inprocess_job_runs` 表存在 |
| t-p0-2 | 补跑中断的行情与因子数据 | implement | backend | t-p0-1 | `select max(trade_date) from quant.daily_klines` = 最近交易日；freshness_guard 返回 `fresh` |
| t-p0-3 | 装外部存活与数据新鲜度探针 | implement | backend | t-p0-1 | kill 服务后 5 分钟内收到飞书告警；阈值改 0 天立即告警 |
| t-p1-1 | 依赖声明收口（pyproject 为唯一权威） | implement | backend | t-p0-1 | `pytest --collect-only -q` errors = 0；`grep -c psycopg2-binary pyproject.toml` = 0 |
| t-p1-2 | 修 `get_config()` 空壳 | implement | backend | t-p1-1 | `get_config('PGHOST','FALLBACK')` 返回真实值；调用点收敛为 0 或全走 settings |
| t-p1-3 | 删重复实现（零引用项） | implement | backend | t-p1-1 | 删除前后 `pytest tests/test_pipeline.py tests/test_integration.py -q` 结果一致；`.bak` 计数 = 0 |
| t-p1-4 | 修悬空 import + 裁决 `BaseCalculator` 双类 | implement | backend | t-p1-1 | 6+ 处 `python -c "import …"` 不再 ImportError；`^class BaseCalculator` 只剩 1 处 |
| t-p1-5 | 调度去重：4 套 → 1 套（分步灰度） | implement | backend | t-p0-1 | 重复 cron 分组查询 = 0 行；连续 3 交易日每 job 每日 1 条 success |
| t-p1-6 | 删 5 个孤儿的重复 provider | implement | backend | t-p1-1 | `grep -rn "financial_providers\." … \| grep -v "financial_providers/"` = 0；取数测试通过 |
| t-p2-1 | 挂上分层护栏（hook + 基线 + 纯净性断言） | implement | backend | t-p1-1 | `git config --get core.hooksPath` = `.git-hooks`；故意加违规行 → commit 被拦；纯净性测试通过 |
| t-p2-2 | 消 application 层 12 处顶层越层导入 | implement | backend | t-p2-1 | 顶层违规 = 0；`grep -rn "^from infrastructure.notification.channels" application/` = 0 |
| t-p2-3 | 拆两个"文件级上帝" | implement | backend | t-p2-1 | `scheduler_tasks.py` / `daily_jobs_bootstrap.py` 行数 < 400；`JOBS` 列表 diff 为空 |
| t-p2-4 | 端口与 DI 收敛 | implement | backend | t-p2-1, t-p2-2 | 两端口文件同名接口 `comm -12` = 空；DI 入口收敛为 1 |
| t-p2-5 | Repository 双轨收敛 + 修文档指向 | implement | backend | t-p2-1 | 双轨按裁定收敛；`grep -rn "infrastructure/repositories" --include='*.md'` = 0 |
| t-p2-6 | 数据访问规则收口 + provider 归位 | implement | backend | t-p2-1 | application/domain 层 `import akshare\|tushare` = 0 |
| t-p3-1 | docs 分层归位（140 个 md） | doc | doc | — | `find docs -maxdepth 1 -name "*.md" \| wc -l` = 1；wiki 自检无死链 |
| t-p3-2 | git 产物出库（含 ignore 失效项） | implement | backend | — | 产物计数 = 0；`.pi-invest` 跟踪数 = 0；ignore 与实际一致 |
| t-p3-3 | 体积与虚拟环境（先清 5.2G） | implement | backend | — | `du -sh live_trading/logs` 显著下降；`du -sh .` 合计降 ≥5G；日志轮转生效 |
| t-p3-4 | 修 CLAUDE.md 的 8 条矛盾 | doc | doc | — | 8 条命令逐条复核通过；`pip install -r requirements.txt` 引用 = 0 或指向真实文件 |
| t-p3-5 | 卫生债批量清理（550 处） | implement | backend | t-p1-1 | bare except = 0；basicConfig = 0；库层 sys.path.insert = 0；测试基线不退化 |
| t-p3-6 | scripts/tools 归位 | implement | backend | — | `scripts/test_*.py` = 0；5 个一次性脚本已删；文档引用已更新 |

## 依赖图

```
  t-p0-1 ─┬─▶ t-p0-2
          ├─▶ t-p0-3
          └─▶ t-p1-5
  t-p0-1 ─▶ t-p1-1 ─┬─▶ t-p1-2
                    ├─▶ t-p1-3
                    ├─▶ t-p1-4
                    ├─▶ t-p1-6
                    ├─▶ t-p2-1 ─┬─▶ t-p2-2 ─▶ t-p2-4
                    │           ├─▶ t-p2-3
                    │           ├─▶ t-p2-5
                    │           └─▶ t-p2-6
                    └─▶ t-p3-5

  独立（无前置）：t-p3-1  t-p3-2  t-p3-3  t-p3-4  t-p3-6
```

## 执行顺序契约（不可协商）

| 规则 | 内容 | 理由 |
|---|---|---|
| 护栏先于治理 | `t-p2-1` 早于 `t-p2-2`…`t-p2-6` | 117 vs 基线 7 就是"没护栏"的后果 |
| 测试基线先于改动 | `t-p1-1` 早于 `t-p1-4` / `t-p2-*` / `t-p3-5` | 119 模块不可收集时无法验证任何改动 |
| 先删后改 | `t-p1-3`、`t-p1-6` 先做 | 纯删除可 revert、无需回归 |
| 调度先禁用后删除 | `t-p1-5` 分两步，中间观察一周 | 调度是生产命脉，本仓已因调度死过两次 |
| 灰度 | `t-p1-1` 走新 venv 验证后再切换 | 装依赖可能引入版本冲突 |

**回滚路径**：每卡独立 worktree + 独立 commit（遵仓库 `CLAUDE.md` 多会话隔离规则）。
纯删除类直接 `git revert`；`t-p1-5` 回滚 = `update quant.scheduler_tasks set is_enabled=true where name in (…)`；
`t-p2-1` 回滚 = `git config --unset core.hooksPath`。每卡回滚后须重跑该卡 `verify` 确认回到基线。

## 不在本计划内

- V13/V14 策略收益评价、数据库表结构变更、`domain/quantlib` 算法重构。
- FastAPI 端点 parity 的运行时内省（依赖 `t-p1-1` 完成后另行安排）。
