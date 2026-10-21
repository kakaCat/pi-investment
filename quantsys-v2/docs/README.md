# Quantsys-v2 文档中心

> 项目全景、硬规则（数据访问双禁止 / 调度归属 / 仓储双轨 / 通知架构）的**唯一权威**是根目录
> [CLAUDE.md](../CLAUDE.md)。本 README 只做文档树导航；引用某篇文档前先确认它在下表里——
> 不在的即已删除或归档（`archive/cleanup-2026-10/`），不要再引用旧路径。

## 📚 文档树导航

### 根目录（docs/*.md）

| 文件 | 内容 |
|---|---|
| [FRAMEWORK_CONSTRAINTS.md](FRAMEWORK_CONSTRAINTS.md) | ORM/Session/Repository 约束；**顶部 TL;DR = 最常见 5 个坑** |
| [database-schema.md](database-schema.md) | 数据库表结构 |
| [testing.md](testing.md) / [performance.md](performance.md) | 测试与性能 |
| [FEISHU_NOTIFICATIONS.md](FEISHU_NOTIFICATIONS.md) | 飞书通知（分群规则见其正文 + CLAUDE.md 通知架构节） |
| [REDIS_CACHE.md](REDIS_CACHE.md) | 缓存服务 |
| [PROJECT_STATUS.md](PROJECT_STATUS.md) / [MODEL-TRAIN-TESTING-NOTES.md](MODEL-TRAIN-TESTING-NOTES.md) | 项目状态 / 模型训练备注 |
| [strategy-validation.md](strategy-validation.md) / [simulation-account-standard.md](simulation-account-standard.md) | 策略校验 / 仿真账户标准 |
| [degradation-integration-guide.md](degradation-integration-guide.md) | 降级透明化集成（降级/回退/缺失在 API 响应可见） |

### guides/（使用指南）

- [QUICK_START.md](guides/QUICK_START.md) — **新开发者从这里开始**（环境 → 数据库 → 启动 → 测试 → 第一个功能）
- [API-GUIDE.md](guides/API-GUIDE.md) — REST API 使用手册（5001；⚠️ 基名命中 `*-GUIDE.md` ignore 规则，已显式 `-f` 入库）
- [BEST_PRACTICES.md](guides/BEST_PRACTICES.md) — 因子开发与策略优化
- [data-quality.md](guides/data-quality.md) — 数据质量检查任务（参数/护栏/调度接入）
- [LOGGING_WORKFLOW.md](guides/LOGGING_WORKFLOW.md) — 日志链路
- [agent-task-dispatch.md](guides/agent-task-dispatch.md) / [board-workflow.md](guides/board-workflow.md) — Agent 任务与需求看板流
- [watch-pipeline-stages.md](guides/watch-pipeline-stages.md) — 盯盘流水线

### architecture/（架构说明）

- [ARCHITECTURE.md](architecture/ARCHITECTURE.md) — 架构总览
- [FUNCTIONALITY_OVERVIEW.md](architecture/FUNCTIONALITY_OVERVIEW.md) — 功能全景
- [scheduler-architecture.md](architecture/scheduler-architecture.md) — 调度架构（归属见 ADR-004）
- [watch-rules.md](architecture/watch-rules.md) — 盯盘规则
- [REGISTRY_INTEGRATION.md](architecture/REGISTRY_INTEGRATION.md) — 服务注册集成

### 决策与提案

- [adr/](adr/) — 架构决策记录（001 Flask→FastAPI · 002 Agent OS 调度 · 003 六边形架构 · 004 调度归属）
- [rfcs/](rfcs/) — 设计提案（含 RFC 016 市况与两态取价）
- [plans/](plans/) — 进行中的方案卡（如 [package-boundaries-import-linter.md](plans/package-boundaries-import-linter.md)）

### 记录与档案

- [investigations/](investigations/) — 问题排查记录（issues/audits/fixes 已归拢至此）
- [work-logs/](work-logs/) — 工作日志（按月归档 2026-06 起）
- [superpowers/](superpowers/) — 历史设计卡（specs/plans；reports 已归档）
- [interfaces/](interfaces/) — 接口桩文件（py，供沙箱探查）
- [misc/requirements.txt](misc/requirements.txt) — 归档位（依赖权威是根 `pyproject.toml`，勿按它装环境）
- [archive/cleanup-2026-10/](archive/cleanup-2026-10/) — 2026-10 文档清理归档（过时报告/计划/旧 README 等只读史料）

## 🔧 开发常用入口

| 需求 | 去处 |
|---|---|
| 数据源怎么取 | CLAUDE.md「⚠️ Data Access Rules」节（`DataProviderManager` / `DataService` / Repository） |
| 调度体检 | `python tools/check_scheduler_dedup.py` |
| 分层违规检测 | `python tools/analyze_layer_violations.py` |
| 调度任务监控 | `python tools/monitor_scheduler.py` |

---

**最后更新**：2026-10-21（docs 重组后重写；旧版引用的 quant.factor_analysis/GPU/期权示例目录不存在，已移除）
