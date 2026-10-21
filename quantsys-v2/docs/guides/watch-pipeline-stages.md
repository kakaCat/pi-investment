# Watch 触发流水线阶段维护指南

> 对象：`qs_watch` 盯盘引擎「评估后」流水线（`WatchEngine._process_condition`）。
> 落点：`packages/qs_watch/qs_watch/application/services/watch_engine/pipeline/`
> 引入：2026-10-21（卡 `pipeline-refactor`）——把 `_process_condition` 的 15 步
> 抽成 **Pipeline/Chain 阶段注册表**，行为等价（逐路径 trace 断言 + 既有测试回归）。

## 1. 为什么有这条流水线

改造前 `_process_condition` 是一个 ~370 行、6 处 `return` 的深缩进方法：闩锁、陈旧
驻留、环境闸、确认核验、日上限、抑噪、升级、处置、市场门、去重、通知、计数、待办、
记账、退役、闩锁回退、事件记录全挤在一起。要回答「这条触发为什么没通知」只能靠
读代码 + 猜 `return` 位置。

现在：

```
tick() ──> _process_condition(rule, idx, cond, quote, result, now, events, env_gate, verify_confirm)
              │  （只做一件事：构造 TriggerContext）
              ▼
        PIPELINE.run(ctx)  ──> 按 DEFAULT_STAGES 顺序跑 15 个阶段
                                 每阶段在 ctx.trace 留一条 {stage, status, reason}
              │
              ▼
        PipelineResult(stopped, stop_reason, trace)
```

- **engine 只认识流水线，不认识阶段**：`_process_condition` 里没有任何阶段名或分支；
- **顺序即语义**：`DEFAULT_STAGES` 的元组顺序就是执行顺序；
- **每条路径可断言**：终止路径在 trace 里停在哪个阶段（`status='stop'` + `reason`）。

## 2. 文件职责

| 文件 | 职责 | 什么时候改 |
|---|---|---|
| `pipeline/context.py` | `TriggerContext`（输入 + 阶段间中间结论 + trace）、`StageTrace` | 新增阶段需要跨阶段传值时（加字段） |
| `pipeline/stage.py` | `Stage` 协议（`name` + `run(ctx)`）、`StageResult`（`done` / `stop`） | 协议语义变更（极少） |
| `pipeline/pipeline.py` | `Pipeline.run`：顺序执行、终止、trace 落盘、异常语义 | 执行器语义变更（极少） |
| `pipeline/stages.py` | 15 个阶段实现（每个阶段一个类） | 改某一步的判定/出口 |
| `pipeline/registry.py` | `StageRegistry` + **`DEFAULT_STAGES`（唯一装配表）** + `PIPELINE` 单例 | **加 / 删 / 调阶段只改这里** |
| `pipeline/constants.py` | 归档理由文案（避免 `stages → engine` 反向 import 成环） | 仅当新增跨阶段复用的引擎级常量 |
| `engine.py::_process_condition` | 构造 `TriggerContext` 并 `PIPELINE.run(ctx)` | **不需要为阶段增删而改** |
| `docs/guides/watch-pipeline-stages.md` | 本文件 | 阶段表 / 维护流程变化时同步 |

## 3. 15 步 ↔ 阶段一一对应

`DEFAULT_STAGES` 里恰好 15 个阶段，按顺序。

> 口径说明：改造前 `_process_condition` 的 docstring 用 17 个箭头列步骤——其中
> 「介入记账 + 止损使命退役」原本就是同一段连续代码（现 `settle`），「闩锁回退 +
> 事件记录」原本也是同一段（现 `finalize`），合并后正好 **15 个阶段**，无一步遗漏。
> `settle` 还承接了原先紧跟 `notify` 的 `dedup.mark_notified`（送达后标记，顺序未变）。

| # | 阶段 `name` | 原来那一步 | 终止？ | 终止 reason（trace） |
|---|---|---|---|---|
| 1 | `latch` | 闩锁 / 冷却 / 迟滞带（`TriggerJudge.should_emit`） | 是 | `latch` |
| 2 | `stale_residency` | 陈旧驻留（昨收已在触发侧 → 规则失真治理） | 是 | `stale_residency` |
| 3 | `env_gate` | 全局环境闸（个股总闸；止损/保护线豁免） | 是 | `env_gate_blocked`（归档成功）/ `env_gate_archive_failed`（归档失败，下 tick 重试） |
| 4 | `confirm_verify` | 确认核验（仅 `staged_break` 确认：利空/流动性/共振） | 是 | `confirm_verify_failed` |
| 5 | `daily_cap` | 每日通知上限（宪法级意图豁免） | 是 | `daily_cap` |
| 6 | `noise_suppress` | 抑噪期短路（每日留一条 suppressed 样本） | 是 | `noise_suppressed` |
| 7 | `escalation` | 升级检查（L0/L1 → L2；同时定 `trigger_level`） | 否 | — |
| 8 | `disposition` | 处置决策五门（金额/增量/经济/预算/…） | 否 | — |
| 9 | `market_gate` | per-rule 市场环境复合门（加严项） | 是 | `market_gate_blocked` / `market_gate_archive_failed` |
| 10 | `dedup` | 去重合并 / 跨规则重叠转治理 | 否 | — |
| 11 | `deliver` | 通知或观察聚合缓冲（唯一出口） | 是 | `notify_failed`（不闩锁，下 tick 补发） |
| 12 | `daily_emit` | 日通知计数（送达成功才计数） | 否 | — |
| 13 | `todo` | 落待办（闭环载体；缓冲路径跳过） | 否 | — |
| 14 | `settle` | 送达后结算：去重标记 / 介入记账 / 止损使命退役 | 否 | — |
| 15 | `finalize` | 闩锁回退 + 事件记录（含环境闸豁免溯源） | 否 | — |

三条口径，改任何阶段都不得破坏：

1. **顺序是语义**：例如日上限（5）必须在升级（7）之前——否则「L1 升级成 L2」的触发
   会绕过上限；确认核验（4）必须在日上限/抑噪之前——先判真伪，再谈投送节流。
2. **终止 = 原来的 `return`**：`StageResult.stop(reason)` 之后阶段不再执行，且
   `reason` 是必填的（空 reason 直接 `ValueError`，trace 靠它定位路径）。
3. **trace 是排障事实源**：`status` 三态 `done` / `stop` / `error`；
   阶段抛异常时 trace 记 `error` 后**原样上抛**（不新增吞异常语义）。

## 4. 维护流程：加 / 删 / 调

### 4.1 加阶段（一步改注册表）

1. 在 `pipeline/stages.py` 写阶段类（无状态；`name` 全局唯一；`run(ctx)` 需要终止
   就返回 `StageResult.stop('...')`，否则 `None` 或 `StageResult.done(...)`）；
   需要新的跨阶段数据时，先在 `TriggerContext` 加字段。
2. 在 `pipeline/registry.py` 的 **`DEFAULT_STAGES`** 元组里插入一行（位置即执行位置）。
3. 跑 `pytest tests/application/test_watch_stage_pipeline.py tests/scenarios/test_watch_scenario_matrix.py -q`，
   并把本指南 §3 的表格补一行（测试会校验 15 个阶段名都在指南里）。

**不需要改 `engine.py`**：`_process_condition` 只调 `PIPELINE.run(ctx)`。

### 4.2 删阶段（一步改注册表）

1. 从 `pipeline/registry.py` 的 **`DEFAULT_STAGES`** 元组删掉那一行（阶段类可留可删；
   留着的类不注册就不会执行）。
2. 若该阶段是某条路径的终止点，确认下一条兜底路径（例如删 `daily_cap` 后，超限触发
   会继续走到 `deliver`），并同步 §3 表格与相关测试。
3. 跑同一组测试（场景矩阵会暴露行为变化）。

### 4.3 调流程（一步改顺序）

1. 在 `pipeline/registry.py` 的 **`DEFAULT_STAGES`** 元组里移动那一行到新位置。
2. 自问两个问题：前序阶段写入的字段，后序阶段是否已能读到（`TriggerContext` 字段
   语义）？终止阶段提前后，原来由后续阶段做的归档/记账/事件是否丢失？
3. 跑同一组测试；必要时在 `test_watch_stage_pipeline.py` 补一条该路径的 trace 断言。

> 一句话：**加、删、调都只动 `DEFAULT_STAGES` 这一张表**；阶段实现改动才动
> `stages.py`，而 `engine.py` 的 tick 骨架与 `_process_condition` 入口不用动。

## 5. 不变量（review checklist）

- [ ] `DEFAULT_STAGES` 恰好 15 项（本卡口径），名字唯一，顺序与本文 §3 一致；
- [ ] 每个阶段无实例状态（`PIPELINE` 是模块级单例，被所有触发复用）；
- [ ] 终止阶段都返回 `StageResult.stop(reason)`，`reason` 可读且唯一可检索；
- [ ] 阶段异常不被新吞掉（`Pipeline.run` 标 trace 后原样上抛）；
- [ ] `engine.py` 未新增任何阶段名/阶段分支；
- [ ] 本指南 §3 表格与实际注册表同步（`test_stage_guide_exists_...` 会兜底）。

## 6. 回归与排障

```bash
# 阶段契约（顺序 / 终态 / 每条路径 trace）
pytest tests/application/test_watch_stage_pipeline.py -q

# 场景矩阵 + 引擎既有测试（行为等价）
pytest tests/scenarios/test_watch_scenario_matrix.py tests/scenarios/test_watch_opp_loop_e2e.py -q
pytest tests/application tests/services -q
```

排障时直接看 `_process_condition` 的返回值（`PipelineResult`）：

```python
res = engine._process_condition(rule, idx, cond, quote, result, now, events, env_gate=...)
print(res.executed)     # 实际跑过的阶段（按顺序）
print(res.stopped_at)   # 停在哪；None = 跑完整条链
print([(t.stage, t.status, t.reason) for t in res.trace])
```

`tick()` 内部调用时返回值被忽略，副作用（通知/归档/落库/闩锁）与改造前一致。

## 7. 变更记录

| 日期 | 变更 | 依据 |
|---|---|---|
| 2026-10-21 | 初始版本：15 步抽成阶段注册表 + 本指南 | 卡 `pipeline-refactor`（RFC 017 §2.2/§2.3 的流水线部分） |
