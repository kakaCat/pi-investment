# t-0cff3a 修 CLAUDE.md 的 8 条矛盾·研发

> 需求：REQ-261001145152-3982 V2 项目全面审查与优化梳理

## 在做什么
修 CLAUDE.md 的 8 条矛盾·研发

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果
改动已落盘，相关测试或命令跑通并附输出摘要

---
## 汇报 1（2026-10-01T07:35:21.801Z，窗口 session-7fc133ad-e896-4aa2-9cb5-443ac7c5af22）

研发段：新人/新会话按文档操作不再踩空——入口路径、装依赖、Flask 回滚栈、Repository 位置、调度开关、重启方式这 8 处"说 A 实际是 B"全部改成实测事实，另有 5 处同批发现的错路径一并修正，12 份文档的安装命令统一到 pyproject。

### 完成项

- CLAUDE.md 修 8 条矛盾：① 入口路径改为 adapters/inbound/{fastapi_app/main.py,cli/main.py}；② 依赖改为 pip install -e .（根目录无 requirements.txt）；③ DATA_ACCESS_GUIDE.md 已失，改指本文件该节 + 真实入口 manager.py；④ 删掉“Flask 回滚栈保留”的错误说法（54851df0 已整体删除，仅剩未跟踪 .bak）；⑤ infrastructure/repositories/ 改为 adapters/outbound/repositories/；⑥ 修正“unified_scheduler 已删除”（它还在且被 lifespan 启动、但空转）；⑦ USE_AGENT_OS_SCHEDULER 改为真实开关 AGENT_OS_ENABLED + 四个 DISABLE_*；⑧ launchctl com.pi-investment.v2-api 标注 plist 不存在、改为手工启动方式
- 额外修正（同一批实测发现）：scripts/register_jobs_to_agent_os.py 与 scripts/monitor_scheduler.py 实际在 tools/；check_migration.py / auto_migrate.py 不存在；scheduler.py“2026-09-01 移除”未发生（仍被 22 文件引用）；Agent OS 章节标为“代码已实现但当前不生效”
- 同步 12 份文档的依赖安装命令：16 处 pip install -r requirements.txt / pip-sync 全部改为 pip install -e .（README、docs/…、domain/benchmarks/README.md）
- 复核：grep 全套旧命令在 *.md 中命中 0；8 条矛盾的旧说法均只出现在“修正/不存在”语境

### 改动文件

- `CLAUDE.md`
- `README.md`
- `docs/DEVELOPER_ONBOARDING.md`
- `docs/MODEL-TRAIN-TESTING-NOTES.md`
- `docs/P2-3-integration-progress.md`
- `docs/PROJECT_STATUS.md`
- `docs/REDIS_CACHE.md`
- `docs/application-layer-fixes-2026-08-22.md`
- `docs/guides/DEVELOPER-QUICKSTART.md`
- `docs/guides/INSTALLATION.md`
- `docs/guides/PYTHON_ENVIRONMENT.md`
- `docs/guides/QUICK_START.md`
- `domain/benchmarks/README.md`

---
