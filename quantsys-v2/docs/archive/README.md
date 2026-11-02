# Archive（只读史料区）

本目录存放**历史文件，仅供追溯**：不参与生产、不应被 import、不应作为当前实现的依据。
新人/agent 只读，**不要在此新增文件**（新增历史件请走 docs/README.md 规定的归档流程）。

## 目录结构

### `cleanup-2026-10/` — 2026-10/11 文档清理归档

| 子区 | 内容 | 数量 |
|---|---|---|
| `superpowers/specs/` | 历史设计卡（design specs，2026-05 ~ 2026-08） | 14 |
| `superpowers/plans/` | 历史实施计划（plans，2026-05 ~ 2026-08） | 12 |
| `superpowers/analysis/` | 历史扫描分析（hardcoded-dependencies-scan） | 1 |
| `superpowers-reports/` | 历史完成报告（completion/summary） | 5 |
| `work-logs-process/` | 过程类工作日志（状态/完成/重构/迁移/需求执行日志） | 31 |
| `requirements-machine/` | dsh 需求工作流机器工件（任务卡 / rtm 状态 / queue） | ~200 |
| 根级 `*.md` | 早期指南与模块说明（scheduler / ORM / 模训自动化 / TIMESERIES·STATISTICS 模块 / Flask 时代 AGENTS / INSTALLATION legacy 等） | ~40 |

### 根级 legacy 代码

- `v13_strategy_legacy.py` — 原 V13 策略单体实现（`domain/strategies/v13_strategy.py`）。
  已拆分替代：`domain/strategies/xgboost_strategy.py`（纯算法）+ `application/strategies/v13_use_case.py`（编排）。
- `v14_strategy_legacy.py` — 原 V14 策略单体实现。
  已拆分替代：`domain/strategies/xgboost_strategy.py` + `application/strategies/v14_use_case.py`。
- 归档于 2026-09-02（策略重构 Part 6.1），保留用于历史比对与审计。

## 使用规则

1. **不要修改**本目录文件（归档即冻结）。
2. 活文档若需引用，必须写全归档路径并在文中标注“（历史件，已归档）”。
3. `requirements-machine/` 里的 `queue.json` 已将 `cardDoc` 路径同步为归档路径；若某需求要复工，需把对应 `tasks/` 与 `rtm-*` 移回 `docs/requirements/<REQ>/` 再改回路径。
4. 删除过的历史件仍可从 git 历史找回（未入库的本地倾倒物除外）。
