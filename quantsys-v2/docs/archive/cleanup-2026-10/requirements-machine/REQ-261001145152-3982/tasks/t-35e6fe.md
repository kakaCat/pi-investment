# t-35e6fe docs 分层归位（140 个 md）·研发

> 需求：REQ-261001145152-3982 V2 项目全面审查与优化梳理

## 在做什么
docs 分层归位（140 个 md）·研发

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果
`npx vitest run <本卡改动涉及的测试文件>` → 全绿；并附 `git diff --stat` 摘要

---
## 汇报 1（2026-10-01T13:03:36.116Z，窗口 session-7fc133ad-e896-4aa2-9cb5-443ac7c5af22）

研发段：**卡片点名的迁移工具原先是坏的**（在同一台机器上直接崩、只能清项目根、还会留下 235 处死链），我把它修成了能真正用的迁移器（可先空跑看清单、可指定目录、可顺带改引用），并自己揪出并修掉一个让"引用改写预估恒为 0"的 bug；同时把 3 个放错位置的示例脚本和 2 个散落文档归了位。

### 完成项

- **实测推翻卡片四个前提**：① 卡片点名的 `tools/cleanup_quantsys_v2_docs.py` 扫的是 **quantsys-v2 项目根**（只有 2 个散落文件），不是 `docs/` 根（140 个文件在那里）；② 该工具在本机 `python3`（3.8.10）下**直接崩**（`tuple[str,str]` 不支持）；③ 它**不处理引用**——实测有 **235 处**引用指向 docs/ 根（99 个不同路径）；④ 验收依赖的 `agent-dh/scripts/wiki_probe.py` 自己声明**只对 agent-dh 文档树判失败**，不校验 `quantsys-v2/docs`
- 按用户裁定：**先修工具、不做 140 文件整迁**（卡面 executorHint 亦建议"优先新窗口或 subagent 执行"）
- 工具修补四处（`tools/cleanup_quantsys_v2_docs.py`）：① 加 `from __future__ import annotations` 修 py3.8 崩溃；② 加 `--dry-run`（只打清单、不动盘）；③ 加 `--root`（默认仍是项目根，`--root docs` 指向真正待迁的 140 个）；④ 加 `--update-refs`（迁移后把 `docs/<旧>` 重写为 `docs/<新>`，扫描范围排除 .git/venv/node_modules）
- **修补过程中自查出并修掉自己的一个 bug**：`update_references` 初版给旧路径又拼了一次 `docs/` 前缀（去找 `docs/docs/...`），导致引用改写预估恒为 **0**；修正后预估 **118 个文件**会被触及
- dry-run 实测证据：项目根模式 → 2 个文件待迁；`--root docs --dry-run` → 扫描 **140** 个文件、139 个待迁（README.md 保留）、分类为 misc 82 / work-logs 44 / scheduler 11 / api 1 / architecture 1；全程**未改任何文件**（git status 仅显示工具自身修改）
- 低风险归位已做：3 个 `.py` 示例 `git mv` 到 `docs/examples/`（git 记 `R` 重命名，可入库）；2 个散落文档（`BUG_FIX_COMMIT_MESSAGE.txt`、`数据补救完成总结.md`）移到 `docs/work-logs/2026-09/`（**它们未被 git 跟踪**，故仅改本地）；项目根现在只剩 CLAUDE.md + README.md
- **留给后续窗口的两个明确缺口**（已写进工具 docstring 与本汇报）：① 分类规则偏粗且滞后——140 个里 82 个落 `misc`，还新出现规则里没有目标目录的 `scheduler`(11)，整迁前需先扩规则并按规范复核去向；② `--update-refs` 扫**整个 monorepo**（含 agent-dh 等其它项目），会改到别的项目文件——执行前务必先看 dry-run 的数量

### 改动文件

- `docs/examples/exception_handling_migration_guide.py`
- `docs/examples/orm_session_migration_example.py`
- `docs/examples/scheduler_tasks_migration_example.py`
- `tools/cleanup_quantsys_v2_docs.py`

---
## 汇报 2（2026-10-01T13:04:52.682Z，窗口 session-7fc133ad-e896-4aa2-9cb5-443ac7c5af22）

研发段：**卡片点名的迁移工具原先是坏的**（同一台机器上直接崩、只会清项目根、还会留下 235 处死链），我把它修成真能用的迁移器（可空跑看清单、可指定目录、可顺带改引用），并自己揪出修掉一个让"引用改写预估恒为 0"的 bug；同时把 3 个放错位置的示例脚本与 2 个散落文档归了位，并产出可审的 dry-run 迁移清单。

### 完成项

- **实测推翻卡片四个前提**（逐个可复核）：① 卡片点名的 `tools/cleanup_quantsys_v2_docs.py` 扫的是 **quantsys-v2 项目根**（只剩 2 个散落文件），不是 `docs/` 根（140 个文件在那里）；② 该工具在本机 `python3`（**3.8.10**）下**直接崩**（`tuple[str,str]` 不支持）；③ 它**不处理引用**——实测 **235 处**引用（99 个不同路径）指向 docs/ 根；④ 验收依赖的 `agent-dh/scripts/wiki_probe.py` 自己声明**只对 agent-dh 文档树判失败**，不校验本仓 docs
- 按用户裁定推进：**先修工具、不做 140 文件整迁**（卡面 executorHint 亦建议优先新窗口/subagent 执行）
- 工具修补四处：① `from __future__ import annotations` 修 py3.8 崩溃；② 新增 `--dry-run`；③ 新增 `--root`（默认项目根，`--root docs` 指向真正待迁的 140 个）；④ 新增 `--update-refs`（迁移后重写 `docs/<旧>`→`docs/<新>`，排除 .git/venv/node_modules）
- **自查出并修掉自己的 bug**：`update_references` 初版多拼了一次 `docs/` 前缀（去找 `docs/docs/...`），引用改写预估恒为 0；修正后预估 **118 个文件**会被触及
- dry-run 证据（全程未改盘）：项目根模式 2 个待迁；`--root docs --dry-run` 扫描 **140**、待迁 **139**（README.md 保留）、分类 misc 82 / work-logs 44 / scheduler 11 / api 1 / architecture 1
- 低风险归位已做：3 个 `.py` 示例 `git mv` → `docs/examples/`（git 记 `R`，可入库）；2 个散落文档 → `docs/work-logs/2026-09/`（**未被 git 跟踪**，仅本地）；项目根现在只剩 CLAUDE.md + README.md、docs/ 根 `.py` 归零
- **留给后续窗口的缺口**（已写进工具 docstring）：① 分类规则偏粗且滞后——82 个落 misc，还出现规则里无目标目录的 `scheduler`(11)，整迁前需扩规则并按规范复核去向；② `--update-refs` 扫**整个 monorepo**（会触及 agent-dh 等其它项目文件），执行前务必先看 dry-run 数量

### 改动文件

- `docs/examples/exception_handling_migration_guide.py`
- `docs/examples/orm_session_migration_example.py`
- `docs/examples/scheduler_tasks_migration_example.py`

---
