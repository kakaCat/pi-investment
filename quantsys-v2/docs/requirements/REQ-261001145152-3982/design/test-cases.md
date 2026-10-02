---
req_id: REQ-261001145152-3982
title: 审查结论的复现校验用例
doc: design/test-cases
serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7
---

# 测试用例设计（REQ-261001145152-3982）

> 本需求是**只读审查**，没有代码可测。因此"测试"= **报告的结论能否被第三方复现**。
> `covers` 指向清单条目 id（任务卡在 decomposing 阶段生成，届时可改为 `t-xxx`）。

## 功能测试用例 · serves: FR-7

### TC-1: 运行态停摆结论可复现 `covers: P0-1, P0-2` `validates: FR-3` · serves: FR-3

**测试目标**：证明"服务停摆 18 天、数据滞后 20 天"不是推测，而是可复核的硬事实。

**前置条件**：
- 工作目录 = `quantsys-v2/`
- 可访问 `quant_investment` 库（`.env` 的 PG 配置）

**测试步骤**：
1. `ls -lT logs/fastapi_5001.log`
2. `psql -h 127.0.0.1 -U mac -d quant_investment -At -c "select max(started_at) from quant.scheduler_runs;"`
3. `psql -h 127.0.0.1 -U mac -d quant_investment -At -c "select max(trade_date) from quant.daily_klines;"`
4. `curl -s -m 3 -o /dev/null -w "%{http_code}\n" http://127.0.0.1:5001/api/health`
5. `ls ~/Library/LaunchAgents/ | grep v2-api || echo "(无此 plist)"`

**预期结果**（可证伪）：
- 步骤 1 → 时间戳 `2026-09-13 15:33`
- 步骤 2 → `2026-09-13` 附近，**不是**今天
- 步骤 3 → `2026-09-11`
- 步骤 4 → `000`（连接失败）
- 步骤 5 → `(无此 plist)`

**测试数据**：无（实测环境即数据）

**覆盖场景**：
- [x] 正常流程（复现停摆）
- [x] 边界值（"今天"的判定以系统时间为准）
- [x] 异常处理（DB 不可达时应报"无法复核"，而非编造值）

### TC-2: 调度重复与空转可复现 `covers: P1-5` `validates: FR-3` · serves: FR-3

**测试目标**：证明 4 套调度器并存 + DB 内 cron 重复 + UnifiedScheduler 空转。

**前置条件**：可访问 `quant_investment`；工作目录 = `quantsys-v2/`

**测试步骤**：
1. `psql -h 127.0.0.1 -U mac -d quant_investment -At -F'|' -c "select cron_expression, count(*), string_agg(name,' + ') from quant.scheduler_tasks where is_enabled group by 1 having count(*)>1 order by 2 desc;"`
2. `sed -n '291,297p' infrastructure/scheduler/unified_scheduler.py`
3. `grep -rn "run_job(" --include='*.py' . | grep -v tests | wc -l`
4. `grep -rn "USE_AGENT_OS_SCHEDULER" --include='*.py' . | wc -l`

**预期结果**：
- 步骤 1 → **4 行**，count 分别为 `3 / 3 / 2 / 2`
- 步骤 2 → `start()` 方法体只有 `self._running = True` 与一行 log
- 步骤 3 → `0`（生产代码无人调用）
- 步骤 4 → `0`（文档里的开关在代码中不存在）

**覆盖场景**：
- [x] 正常流程
- [x] 边界值（`is_enabled` 过滤——禁用任务不参与重复判定）
- [x] 异常处理（若 DB 不可达，第 2/3/4 步仍可独立复核）

### TC-3: 依赖缺口与测试不可收集可复现 `covers: P1-1` `validates: FR-4` · serves: FR-4

**测试目标**：证明 119 个测试模块连 import 都过不去，且原因是未声明依赖。

**前置条件**：`source activate-py313.sh`

**测试步骤**：
1. `python -m pytest --collect-only -q 2>&1 | tail -1`
2. `python -m pytest --collect-only -q 2>&1 | grep -E "^E   ModuleNotFoundError" | sort | uniq -c | sort -rn | head -3`
3. `python -c "import pybreaker" 2>&1 | tail -1`
4. `comm -23 <(grep -vE "^\s*#|^\s*$" docs/misc/requirements.txt | sed 's/[><=!].*//' | tr -d ' ' | sort) <(sed -n '/^dependencies = \[/,/^\]/p' pyproject.toml | grep -oE '"[a-zA-Z0-9_.-]+' | tr -d '"' | sort) | wc -l`
5. `grep -c psycopg2-binary pyproject.toml`

**预期结果**：
- 步骤 1 → 包含 `119 errors`
- 步骤 2 → 首行为 `101 ... pybreaker`（其后 pydantic_settings 10、jieba 7）
- 步骤 3 → `ModuleNotFoundError: No module named 'pybreaker'`
- 步骤 4 → **47**（只在文档清单里声明的包数）
- 步骤 5 → `1`（与 requirements 的"禁止用 psycopg2-binary"注释直接冲突）

**覆盖场景**：
- [x] 正常流程
- [x] 边界值（可选依赖 torch/tensorflow 等为 `try` 软导入，**不应**计入缺陷）
- [x] 异常处理（未激活 venv 时会报不同的 ModuleNotFoundError，需先激活）

### TC-4: 分层违规与护栏失效可复现 `covers: P2-1, P2-2` `validates: FR-1` · serves: FR-1

**测试目标**：证明违规 117 处、护栏基线写 7、hook 未安装。

**测试步骤**：
1. `venv/bin/python tools/analyze_layer_violations.py 2>&1 | grep -E "违规导入总数|违规文件数量"`
2. `grep -n "BASELINE=" .git-hooks/pre-commit`
3. `git config --get core.hooksPath`
4. `ls /Users/mac/Documents/ai/pi-investment/.git/hooks/ | grep -v sample | wc -l`

**预期结果**：
- 步骤 1 → `违规导入总数: 117`、`违规文件数量: 54`
- 步骤 2 → `BASELINE=7`（与 117 差 16 倍）
- 步骤 3 → `/Users/mac/Documents/ai/pi-investment/.git/hooks`（**不是** `.git-hooks`）
- 步骤 4 → `0`（没有任何已安装 hook）

**覆盖场景**：
- [x] 正常流程
- [x] 边界值（`tools/analyze_layer_violations.py` 自身的口径要先裁定——见 audit-report §1.3 三种标准冲突）
- [x] 异常处理（工具需 `venv/bin/python`，用系统 python 可能缺包）

### TC-5: 重复实现的可删性可复现 `covers: P1-3, P1-6` `validates: FR-2` · serves: FR-2

**测试目标**：证明待删项**确实零引用**（删除安全），且重复是逐字级而非"看着像"。

**测试步骤**：
1. `grep -rn "infrastructure\.quantlib\.adapters\." --include='*.py' . | grep -v "^./infrastructure/quantlib/adapters/" | wc -l`
2. `for f in base_calculator exceptions pipeline; do md5 -q domain/quantlib/core/$f.py infrastructure/quantlib/core/$f.py; done`
3. `for f in adapters/outbound/datasources/providers/quantlib/akshare_adapter.py infrastructure/quantlib/adapters/akshare_adapter.py; do echo "$f logger定义:$(grep -c '^logger = logging' $f) 用法:$(grep -c 'logger\.' $f)"; done`
4. `diff scripts/backtest_ml_v6_strategy_optimized_v13.py scripts/backtest_ml_v6_strategy_fast_rebalance_v15.py | grep -c '^[<>]'`
5. `grep -rn "financial_providers\." --include='*.py' . | grep -v "financial_providers/" | wc -l`

**预期结果**：
- 步骤 1 → `0`（零外部引用 → 删除安全）
- 步骤 2 → 每对输出**两个相同 md5**（逐字重复）
- 步骤 3 → providers 侧 `1 / 25`；infrastructure 侧 `0 / 17` → **缺陷只在一边修了**
- 步骤 4 → `4`（两行改动 / 各 1069 行）
- 步骤 5 → `0`（5 个孤儿 provider 无实例化方）

**覆盖场景**：
- [x] 正常流程
- [x] 边界值（`core/pipeline.py` 虽逐字相同但**有测试依赖**，属"不可删"的例外）
- [x] 异常处理（数值口径差：严格扫描 35 vs 全限定名扫描 165 → 必须人工确认）

### TC-6: 交付物契约完整性可复现 `covers: P3-1, P3-2, P3-3` `validates: FR-6, FR-7` · serves: FR-6, FR-7

**测试目标**：证明清单条目字段齐全、可执行，且报告结论带命令。

**测试步骤**：
1. `grep -c "^### P" docs/requirements/REQ-261001145152-3982/design/optimization-backlog.md`
2. `grep -c "| verify |" docs/requirements/REQ-261001145152-3982/design/optimization-backlog.md`
3. `grep -nE "^#{2,3} " docs/requirements/REQ-261001145152-3982/design/*.md | grep -vc "serves"` → 期望 `0`
4. `find docs -maxdepth 1 -name "*.md" | wc -l`
5. `git ls-files | grep -cE "\.(pyc|pkl|log)$"`
6. `du -sh live_trading/logs`

**预期结果**：
- 步骤 1 → `21`
- 步骤 2 → `21`（每条目都有 verify 字段）
- 步骤 3 → `0`（无孤儿章节）
- 步骤 4 → `140`
- 步骤 5 → `98`
- 步骤 6 → `5.2G`

**覆盖场景**：
- [x] 正常流程
- [x] 边界值（`verify` 内容是否"可执行"需人工判读，不能只数个数）
- [x] 异常处理（文档被改动后计数会变——属预期）

## 测试覆盖度统计 · serves: FR-7

| 需求条款 | 关联条目 | 测试用例 | 覆盖状态 |
|---|---|---|---|
| FR-1 资产与分层盘点 | P2-1, P2-2 | TC-4 | ✅ 已覆盖 |
| FR-2 重复与分叉盘点 | P1-3, P1-6 | TC-5 | ✅ 已覆盖 |
| FR-3 调度与运行态盘点 | P0-1, P0-2, P1-5 | TC-1, TC-2 | ✅ 已覆盖 |
| FR-4 依赖与环境可复现 | P1-1 | TC-3 | ✅ 已覆盖 |
| FR-5 文档与仓库卫生 | P3-1, P3-2, P3-3 | TC-6 | ✅ 已覆盖 |
| FR-6 优化清单 | 全部 21 条 | TC-6 | ✅ 已覆盖（字段契约） |
| FR-7 判定标准可证伪 | 全部 15 条复现命令 | TC-1…TC-6 | ✅ 已覆盖 |
