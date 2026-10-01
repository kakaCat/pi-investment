---
req_id: REQ-261001145152-3982
title: 优化条目契约与现状数据事实
doc: design/data-model
serves: FR-6, FR-3
---

# 数据模型设计（REQ-261001145152-3982）

**先说结论**：本需求**没有新增/修改任何数据结构**（无 DDL、无 schema 变更）。
本文件的"数据模型"是两样东西：

1. **优化条目的字段契约**（清单的数据形状——decomposing 阶段按它生成任务卡）；
2. **被记录的现状数据事实**（只读采集，作为证据与验收基线）。

## 新增/修改的数据结构（serves: FR-6）

### BacklogItem（优化条目） （serves: FR-6）

**用途**：优化清单里的一条待办；它是本需求的核心交付物，也是任务卡的生成源。

**定义**：

```jsonc
{
  "id": "P1-3",                     // 主键，格式 P<0-3>-<n>
  "priority": "P1",                 // 枚举：P0/P1/P2/P3
  "title": "删重复实现（纯删除，收益最高）",
  "evidence": ["md5 相同", "grep 零引用"],
  "action": "删除 infrastructure/quantlib/adapters/ 6 个模块",
  "impact": "可删 ≈10,700 行",
  "verify": "pytest tests/test_pipeline.py 结果与删除前一致",
  "risk": "low",                    // 枚举：low/medium/high
  "cost": "1 人日",
  "depends_on": ["P1-1"]            // 可选，引用同批 id
}
```

**字段说明**：

| 字段 | 类型 | 必填 | 说明 | 约束 |
|---|---|---|---|---|
| `id` | string | ✅ | 条目主键 | 正则 `^P[0-3]-\d+$`；唯一 |
| `priority` | enum | ✅ | 优先级 | 取值 `P0`/`P1`/`P2`/`P3` |
| `title` | string | ✅ | 条目标题 | ≤60 字，动词开头 |
| `evidence` | string[] | ✅ | 证据 | ≥1 条，且必须是**可直接执行**的命令或 `文件:行` |
| `action` | string | ✅ | 实施动作 | 明确到目录/文件 |
| `impact` | string | ✅ | 影响面 | 文件数 / 行数 / 调用方 |
| `verify` | string | ✅ | 验收方式 | **必须可执行**；出现"确认正常/看起来没问题"即不合格 |
| `risk` | enum | ✅ | 风险 | 取值 `low`/`medium`/`high` |
| `cost` | string | ✅ | 成本估计 | 人日量级 |
| `depends_on` | string[] | ❌ | 前置条目 | 引用同批 `id`；不得自指、不得成环 |

**索引设计**：

| 索引名 | 字段 | 类型 | 原因 |
|---|---|---|---|
| 主键 | `id` | 主键 | 条目唯一引用（`depends_on` 指向它） |
| 优先级分组 | `priority` | 普通 | 清单按四批次渲染与排期 |
| 依赖图 | `depends_on` | 普通 | 决定执行顺序（护栏先于治理等） |

**关联关系**：

| 关联到 | 类型 | 外键 | 说明 |
|---|---|---|---|
| Requirement FR-1…FR-7 | N:M | `serves`（文档级） | 每条目服务至少一条功能点 |
| TaskCard（decomposing 产出） | 1:1 | `id` → 卡 `key` | 批准后一条目落一张卡 |

### Priority（优先级枚举） （serves: FR-6）

**用途**：决定批次与"今天做什么"。

**定义**：

```jsonc
{
  "P0": "运行态——服务/数据已中断，不做则后续全部无法验证",
  "P1": "正确性——会静默产生错误结果（分叉副本、未声明依赖、空壳配置）",
  "P2": "结构——维护成本与漂移风险（分层、上帝文件、端口/DI 重复）",
  "P3": "卫生——文档、产物、体积、风格债（不修不报错，但持续腐蚀）"
}
```

**字段说明**：

| 字段 | 类型 | 必填 | 说明 | 约束 |
|---|---|---|---|---|
| key | enum | ✅ | 优先级键 | `P0`/`P1`/`P2`/`P3` |
| meaning | string | ✅ | 判定语义 | 按"不做会怎样"划分，不按代码量 |

**索引设计**：无需（枚举常量）。

**关联关系**：被 `BacklogItem.priority` 引用。

## 现状数据事实（只读采集，**无变更**）（serves: FR-3）

以下数据均通过只读查询采集，作为证据与后续验收基线：

### SchedulerTask 现状（`quant.scheduler_tasks`） （serves: FR-3）

**用途**：调度任务表；本需求**只读**，用于证明"同一时点存在重复任务"。

**字段说明**（仅列出用到的列）：

| 字段 | 类型 | 说明 | 本次观测 |
|---|---|---|---|
| `name` | text | 任务名（唯一约束） | 中英文两轮命名并存 |
| `cron_expression` | text | cron 表达式 | **4 个表达式各对应 2~3 个启用任务** |
| `is_enabled` | boolean | 是否启用 | 26 启用 / 7 禁用 |
| `last_status` | text | 最近状态 | 最新记录停在 2026-09-13 |

**索引设计**：表自带 `scheduler_tasks_name_key`（唯一）、`idx_…_is_enabled`、`idx_…_next_run_at`。

**关联关系**：

| 关联到 | 类型 | 外键 | 说明 |
|---|---|---|---|
| `quant.scheduler_runs` | 1:N | `task_id` | 执行台账；最新一行 = 2026-09-13 |

```sql
-- 复现：启用中的重复 cron
select cron_expression, count(*), string_agg(name,' + ')
from quant.scheduler_tasks where is_enabled group by 1 having count(*)>1;
```

### DailyKline 新鲜度（`quant.daily_klines`） （serves: FR-3）

**用途**：行情数据；本需求只读，用于证明数据管线中断。

| 字段 | 类型 | 说明 | 本次观测 |
|---|---|---|---|
| `trade_date` | date | 交易日 | `max(trade_date)` = **2026-09-11**（今天 2026-10-01） |

**关联关系**：下游因子表 / 信号表 / 筹码表的日期均应与之对齐（`P0-2` 的验收依据）。

### InProcessJobRun（`quant.inprocess_job_runs`） （serves: FR-3）

**用途**：DailyJobs 宿主线程的幂等台账，幂等键 `(job_id, run_date)`。

| 字段 | 类型 | 说明 | 本次观测 |
|---|---|---|---|
| `job_id` + `run_date` | text | 唯一键 | **表当前不存在**（`checkfirst` 建表发生在服务启动时；服务已停 18 天） |

**这是 `P0-1` 验收信号之一**：服务拉起后该表应出现，且每个 job 每日仅 1 条 success。

### LiveTradingLogArtifacts（`live_trading/logs/`） （serves: FR-5）

| 字段 | 类型 | 说明 | 本次观测 |
|---|---|---|---|
| 目录体积 | — | 运行日志堆积 | **5.2 G**（全仓最大单点垃圾） |
| git 跟踪数 | — | `git ls-files \| wc -l` | **0**（可安全清理） |

**索引设计 / 关联关系**：不适用（非数据库对象）。
