---
req_id: REQ-261001145152-3982
title: 交付物接口与复现命令接口
doc: design/interfaces
serves: FR-1, FR-6, FR-7
---

# 接口设计（REQ-261001145152-3982）

**先说清楚**：本需求**没有 HTTP API 变更、没有工具签名变更、没有事件协议变更**。
本文件的"接口"是两类**交付物接口**：

1. **文档交付接口**——谁读、怎么消费；
2. **复现命令接口**——每条结论的"调用方式"与"期望返回"，这是本需求的验收手段。

## 新增/修改的工具接口（serves: FR-7）

### 复现命令接口（15 条） （serves: FR-7）

**用途**：把报告里每条结论变成一条任何人可执行、输出确定的命令——这是本需求唯一的"可证伪接口"。

**调用方**：人类复核者 / 验收人 / 后续 agent（自证完成）。

**接口定义**：

```bash
# 输入：无（命令自带全部上下文）
# 输出：确定值（下表"期望返回"列）
$ <command>
<expected>
```

**参数说明**：

| 参数 | 类型 | 必填 | 说明 | 默认值 |
|---|---|---|---|---|
| 工作目录 | path | ✅ | 必须是 `quantsys-v2/`（含 `logs/`、`adapters/` 的那一层） | 无 |
| Python 环境 | env | 条件 | 涉及 pytest 的命令需 `source activate-py313.sh` | 无 |
| DB 连接 | env | 条件 | 涉及 psql 的命令需 `PGHOST/PGUSER/PGDATABASE` | `.env` 值 |

**返回值说明**（15 条：命令 → 期望）：

| # | 结论 | 命令 | 期望返回 | 关联条目 |
|---|---|---|---|---|
| 1 | 服务停摆 | `ls -lT logs/fastapi_5001.log` | `2026-09-13 15:33` | P0-1 |
| 2 | 数据滞后 | `psql ... -c "select max(trade_date) from quant.daily_klines"` | `2026-09-11` | P0-2 |
| 3 | 测试不可收集 | `python -m pytest --collect-only -q 2>&1 \| tail -1` | `5264 tests collected, 119 errors` | P1-1 |
| 4 | 分层违规 | `venv/bin/python tools/analyze_layer_violations.py \| grep 违规导入总数` | `117` | P2-1 |
| 5 | 护栏失效 | `grep -n BASELINE .git-hooks/pre-commit` | `BASELINE=7` | P2-1 |
| 6 | `get_config` 空壳 | `python -c "from infrastructure.config import get_config; print(get_config('PGHOST','FALLBACK'))"` | `FALLBACK` | P1-2 |
| 7 | 调度重复 | `psql ... -c "... group by cron_expression having count(*)>1"` | 4 行（3/3/2/2） | P1-5 |
| 8 | UnifiedScheduler 空转 | `sed -n '291,297p' infrastructure/scheduler/unified_scheduler.py` | `start()` 仅 `self._running = True` + log | P1-5 |
| 9 | 双份端口 | `comm -12 <(grep -oE "^class I[A-Za-z]+" domain/ports/repository_ports.py \| sort) <(..._extended.py \| sort)` | 7 个同名接口 | P2-4 |
| 10 | 删除项零引用 | `grep -rn "infrastructure\.quantlib\.adapters\." --include='*.py' .` | 仅命中该目录内部 | P1-3 |
| 11 | 被跟踪产物 | `git ls-files \| grep -cE "\.(pyc\|pkl\|log)$"` | `98` | P3-2 |
| 12 | 文档散落 | `find docs -maxdepth 1 -name "*.md" \| wc -l` | `140` | P3-1 |
| 13 | 最大单点垃圾 | `du -sh live_trading/logs` | `5.2G`（且 `git ls-files live_trading/logs \| wc -l` → `0`） | P3-3 |
| 14 | ignore 规则失效 | `git ls-files .pi-invest \| wc -l` | `19` | P3-2 |
| 15 | 孤儿口径差 | 严格扫描 35 vs 全限定名扫描 165 | 两值都成立 | P1-3 |

**异常情况**：

| 错误码 | 触发条件 | 返回内容 |
|---|---|---|
| `CMD_ENV_MISSING` | 未激活 venv 导致 `ModuleNotFoundError` | 命令报错**不是**结论失效；先 `source activate-py313.sh` 再跑 |
| `DB_UNREACHABLE` | psql 连不上 | 报"无法复核 DB 类结论"，其余 11 条仍可复核 |
| `PATH_DRIFT` | 命令里的行号因文件被改动而偏移 | 属预期：**改动后行号会变**，此时应按"期望返回的语义"而非行号复核 |

**使用示例**：

```bash
cd /Users/mac/Documents/ai/pi-investment/quantsys-v2
source activate-py313.sh
python -m pytest --collect-only -q 2>&1 | tail -1
# → 5264 tests collected, 119 errors in 17.12s
```

### 文档交付接口：体检报告 （serves: FR-1）

**用途**：让读者在 5 分钟内知道"最紧的三件事"，在 30 分钟内能复核任意一条结论。

**读者与消费方式**：

| 读者 | 读哪一节 | 期望动作 |
|---|---|---|
| 项目所有者（人类） | TL;DR + 总览表 | 决定先做哪一批 |
| 后续实施 agent | §1–§5 对应小节 + 复现命令 | 领任务时自证现状 |
| 新会话 / 新人 | §5.6 矛盾点表 | 避免按错误文档操作 |

**接口定义**：

```text
输入：无（文档自带全部证据）
输出：结构化的现状结论 + 每条结论的可执行命令
文件：docs/requirements/REQ-261001145152-3982/design/audit-report.md
```

**返回值说明**：

| 小节 | 内容 | 是否带命令 |
|---|---|---|
| TL;DR | 四层问题图 + 一句话结论 | — |
| 总览表 | 10 个维度的实测值 | 部分 |
| §1–§5 | 资产/重复/调度/依赖/卫生 | ✅ 每节≥1 条 |
| §5.6 | 文档 vs 代码 8 条矛盾 | ✅ |
| §5.7 | 一个正例（通知架构） | ✅ |

### 文档交付接口：优化清单 （serves: FR-6）

**用途**：把审查结论变成**可排期、可验收**的 21 条待办。

**接口定义**：

```text
输入：audit-report.md 的证据
输出：21 条 BacklogItem（字段契约见 data-model.md）+ 四批次 + 执行顺序契约
文件：docs/requirements/REQ-261001145152-3982/design/optimization-backlog.md
消费方：decomposing 阶段（一条目 → 一张任务卡）
```

**返回值说明**：

| 字段 | 说明 |
|---|---|
| 批次 | P0（3 条）/ P1（6 条）/ P2（6 条）/ P3（6 条） |
| 每条 | id / priority / title / evidence / action / impact / verify / risk / cost / depends_on |
| 附加 | 复现校验表（15 条）、执行顺序与回滚契约（§7） |

**异常情况**：

| 错误码 | 触发条件 | 返回内容 |
|---|---|---|
| `VERIFY_NOT_EXECUTABLE` | 某条 `verify` 写成"确认正常" | 该条**不合格**，禁止进入拆分（仓规"失败要响亮"） |
| `DEP_CYCLE` | `depends_on` 成环 | 拆分阶段应报错并打回 |

## 删除的接口（serves: FR-1）

**无删除**。审查过程中未删除任何接口。
（清单中建议删除的接口/模块——如 `UnifiedScheduler` 路由、5 个孤儿 provider——属后续批次。）

## HTTP API 变更（serves: FR-1）

**无变更**。现有 473 个 FastAPI 端点在本次审查前后完全一致。
