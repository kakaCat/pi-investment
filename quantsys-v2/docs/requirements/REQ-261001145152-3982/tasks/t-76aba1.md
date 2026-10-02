# t-76aba1 卫生债批量清理（550 处）·研发

> 需求：REQ-261001145152-3982 V2 项目全面审查与优化梳理

## 在做什么
卫生债批量清理（550 处）·研发

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果
`npx vitest run <本卡改动涉及的测试文件>` → 全绿；并附 `git diff --stat` 摘要

---
## 汇报 1（2026-10-01T13:44:22.757Z，窗口 session-7fc133ad-e896-4aa2-9cb5-443ac7c5af22）

研发段：**卫生债验收的三条"归零"全部达成**——41 处会连 Ctrl-C 一起吞掉的裸 except 收紧了、12 处库层擅自配置日志的调用清掉了（其中 4 处是"import 就改全局日志"的副作用）、16 处库层代码自己改 Python 路径的行删掉了，并且把因此会失效的 13 份运行说明同步改对；全程用 AST 定位与回退对照来定因果，不靠"看起来没问题"。

### 完成项

- **实测先对齐口径**（六项对照审计）：bare except 41 ✓、`except: pass` 118（审计 ≈134）、sys.path.insert 135/其中 infra 16 ✓、basicConfig 12 ✓、库层 `__main__` 23 文件（审计 20）、库层裸 print 200 行（审计 144）——**本卡数字基本准确**（与前几张卡不同）
- **验收三条全部达成**：① `grep -rn "except:" domain application adapters infrastructure --include='*.py'` = 41 → **0**；② `grep -rln "logging.basicConfig" 同四层` = 12 文件 → **0**；③ `grep -rn "sys.path.insert" infrastructure --include='*.py'` = 16 → **0**
- **主题A（commit 4790d14b）**：41 处 bare except → `except Exception:`，用 **AST 精确定位**（`ExceptHandler(type is None)`）而非 grep 盲替；只收紧异常类型、不改控制流；21 个文件
- **主题B（commit 41fac465）**：12 处 basicConfig 按形态分三类——4 处**模块级**（import 即改 root logger 的全局副作用）**删除**；6 处函数内改调中央 `configure_structured_logging`（保留独立运行可见日志、顺带结构化）；1 处 domain 示例删除（domain 不许依赖 infrastructure）；1 处**中央日志模块自身**用新增的 `_apply_root_handlers()` 显式装配 root handler 替代（语义对齐 `basicConfig(force=False)`：已有 handler 则不动、重复调用幂等）
- **主题C（commit 379b1f96）**：16 处库层 sys.path.insert 清除（9 处三行式 + 4 处顶层单行 + 2 处 job），并**同步修掉 13 个迁移文件里会因此失效的运行命令**（补 `PYTHONPATH=. ` 前缀）——不然就是我在制造失效说明
- 验证方式（不是只看 grep）：主题A 用 AST 复核；主题B 实测 `LOG_FILE` 轮转仍工作（handlers=[StreamHandler, RotatingFileHandler]、文件已写）、二次调用 handlers 仍 2（幂等）、日志相关测试 3 passed；主题C 按 `PYTHONPATH=.` 口径**逐一导入 16 个模块（16/16 成功）**、并用文档命令真跑 dry-run
- **归因纪律（三处回退对照）**：主题A 的目标选择 4 failed/4 errors、主题C 的 18 failed —— 各自**回退改动后跑同一选择得到完全相同的清单**（差异集为空）→ 均为既有债，非本批引入
- **AST 安全校验**：16 个主题C 文件逐个检查是否有变量被删但仍被引用（防 NameError）→ 无未定义引用（`data_contracts.py` 的 ROOT 因另有用途被正确保留）
- **如实披露一个副作用**：验证时我按文档命令跑了 `20260911_data_contracts.py`（它**没有 dry-run 开关**，默认即同步契约表）——对生产库 `quant_investment` 执行了一次**幂等重同步**（表内始终 11 条契约，未增未减）；另 `20260911_daily_klines_market.py` 只跑了默认 dry-run（纯读）
- **范围边界（重要）**：卡片「实施方案」列的 ②`except: pass` 118、④库层裸 print 200 行、⑥库层 `__main__` 23 文件**不在「验收标准」里**，按"不加功能、不扩范围"未动；实测数字已记下供后续卡使用
- 顺带发现（未改，属既有）：3 个迁移根本不导入项目模块（那行插入本就冗余）；`data_contracts._engine()` 把项目导入裹在 `try/except Exception` 里静默回退到 libpq 默认 DSN——从任意目录跑都"看起来成功"，是"静默降级"的又一实例

### 改动文件

- `domain/backtest/engine/smart_backtest_engine.py`
- `domain/quantlib/data_validator.py`
- `domain/risk/copula.py`
- `infrastructure/logging/config.py`
- `infrastructure/persistence/migrations/20260911_data_contracts.py`
- `infrastructure/persistence/migrations/20260911_daily_klines_market.py`
- `infrastructure/jobs/risk_check_job.py`
- `infrastructure/jobs/index_constituents_update_job.py`
- `adapters/outbound/datasources/multi_source_data_fetcher.py`

---
