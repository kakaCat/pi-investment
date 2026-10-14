# t-f777da 修 CLAUDE.md 的 8 条矛盾

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
修 CLAUDE.md 的 8 条矛盾

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：doc
- 端侧：doc

## 得到什么结果
audit-report §5.6 的 8 条命令逐条复核通过；`grep -rn "pip install -r requirements.txt" --include='*.md' . | wc -l` 为 0 或全部指向真实存在的文件。

## 实施方案（implementation）
逐条改写 quantsys-v2/CLAUDE.md：入口路径（api/server.py、cli/main.py）、requirements.txt、DATA_ACCESS_GUIDE.md、Flask 回滚栈、infrastructure/repositories/、unified_scheduler 已删、USE_AGENT_OS_SCHEDULER、launchd plist；同步修 9 份提到 `pip install -r requirements.txt` 的文档。

## 上游产出摘要（dependsSummary）
- （无依赖）

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-10-01T07:37:27.606Z，窗口 session-7fc133ad-e896-4aa2-9cb5-443ac7c5af22）

这一步做完，变化是：**新人和新会话按 CLAUDE.md 操作不会再踩空**——8 处"说 A 实际是 B"的说明（入口文件、装依赖、数据访问规范、Flask 回滚栈、Repository 目录、调度器状态、开关名、重启命令）全部改成实测事实，另外 12 份文档里的安装命令也统一到真实存在的 pyproject。

### 完成项

- CLAUDE.md 的 8 条“文档说 A、实际是 B”全部改正（入口路径 / 依赖安装 / 数据访问文档 / Flask 回滚栈 / Repository 位置 / unified_scheduler 状态 / 调度开关 / 重启方式）
- 额外修正 5 处同批实测发现的错路径与过期状态（tools/ 与 scripts/、已删脚本、scheduler.py 移除声明未发生、Agent OS 章节状态）
- 12 份文档共 16 处安装命令统一为 pip install -e .（pyproject 为权威）
- 复核：旧说法只剩“已删/不存在”提示语境；旧安装命令在全仓 md 中命中 0

### 改动文件

- `CLAUDE.md`
- `README.md`
- `docs/DEVELOPER_ONBOARDING.md`
- `docs/guides/PYTHON_ENVIRONMENT.md`
- `docs/guides/INSTALLATION.md`
- `docs/guides/QUICK_START.md`
- `docs/guides/DEVELOPER-QUICKSTART.md`
- `domain/benchmarks/README.md`

---
