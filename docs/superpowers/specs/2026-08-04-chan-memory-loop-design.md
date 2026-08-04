# 缠论 × 记忆学习闭环设计

**日期**: 2026-08-04
**状态**: 已确认（用户逐节审定）
**范围**: quantsys-v2 + agent-ts

## 背景

v2 的缠论模块（`domain/chan/`，约 900 行）是一个 demo 级实现且集成断链：

- `ChanService._format_bi` 与 domain `Bi` 类型契约错位（`bi.start` → 应为 `bi.start_fenxing`，`bi.amplitude` → 应为 `bi.price_change`），导致 `POST /api/chan/analyze` 线上 500，任何有数据的 symbol 都无法分析
- agent-ts 全库对 `/api/chan` 零引用，没有任何缠论工具
- 唯一消费者是 web-frontend StockDetail 页（硬编码 fetch，同样调的是 500 端点）
- tests/chan 只剩 2 个 domain 层用例，service 层零覆盖（500 漏网的原因）

## 目标

建立学习闭环验证缠论信号的有效性：

```
定时扫描产生缠论买卖点 → 落 signals 表 → 复用 heatmap/verify_judgments 验证
→ 蒸馏成 agent_knowledge（按买卖点类型的胜率）→ 回喂 agent 决策置信度
```

**核心目标**（用户确认）：学习闭环验证缠论有效性。
**信号产生方式**（用户确认）：定时批量扫描（池内股票）。
**知识粒度**（用户确认）：按买卖点类型起步（"chan_1买 胜率 62% / 37 样本"）。
**架构方案**（用户确认）：方案 A —— 信号表直通，复用现有验证链路，不建独立缠论信号表。
**低置信信号处理**（用户确认）：全部进 signals，confidence 映射 strength，靠 agent 决策链强度阈值自然过滤。

## 总览数据流

```
每日 18:10 (v2 scheduler: chan_scan job)
  │  对池内股票跑 ChanAnalyzer，新买卖点落 signals 表 (status='pending')
  ▼
signals 表 (strategy_id → 内置策略 chan_1买/chan_2买/chan_3买)
  │  ┌──────────────────────────────────┐
  ▼  ▼                                  │
heatmap → verify_judgments              │ (已有链路，零改动)
  │  1/5/20 日窗对照实际涨跌              │
  ▼                                     │
agent 复盘看到"缠论信号准不准"            │
                                        ▼
              每周日 chan_knowledge_distill job
                按策略聚合胜率/平均收益/样本数 → upsert agent_knowledge
                                        │
                                        ▼
              agent 调 chan_analyze 工具 → v2 响应附加该类型历史胜率
              → 影响 agent 决策置信度

推送链路（现有，零新增）：
signals(pending) → SignalExecutionScheduler._collect_signals（不过滤策略）
  → signals_ready 唤醒 agent → 决策链评估/交易 → feishu_notify 推送分析结果
```

## 分期交付

### P1：缠论链路修通 + agent 工具

**v2 侧修复**：
- 修 `application/services/chan_service.py` `_format_bi` 契约错位：
  - `bi.start.index` → `bi.start_fenxing.index`
  - `bi.end.index` → `bi.end_fenxing.index`
  - `bi.start.price` → `bi.start_fenxing.price`
  - `bi.end.price` → `bi.end_fenxing.price`
  - `bi.amplitude` → `bi.price_change`（响应字段名同步改为 `price_change`）
- 补 ChanService 格式化契约测试（mock kline repo，断言响应字段与 domain 类型一致）

**agent-ts 侧**：
- 新增 `chan_analyze` 工具 → `POST /api/chan/analyze`
- 注册进 V2 命令映射表（V2_ROUTES）
- 工具返回：走势类型、笔/线段/中枢结构、买卖点列表（类型/价格/日期/置信度/仓位建议/理由）

**验收**：`curl -X POST :5001/api/chan/analyze {"symbol":"600519.SH"}` 返回 200；agent 可调用 chan_analyze 拿到结构。

### P2：chan_scan 定时 job + signals 落库

**内置策略注册**：
- strategies 表插入 3 个内置策略行：`chan_1买` / `chan_2买` / `chan_3买`（source 标记为 builtin）
- 迁移脚本幂等（ON CONFLICT 或查重插入）

**chan_scan job**：
- v2 scheduler 新增 `chan_scan`，每日 18:10 运行（kline_update 17:40 之后，保证当日 K 线已落库）
- 范围：全部动态池成员去重；每只取近 250 根日 K 跑 `ChanAnalyzer`
- **只落新信号**：买卖点日期 = 最近一个交易日才写入；`(symbol, strategy_id, signal_date)` 去重防重复
- **strength 映射**：缠论 confidence × 100 → signals.strength（1买 0.9→90，2买 0.7→70，3买 0.5→50），落库 status='pending'
- 单股异常 catch 记 errors，不中断批扫；K 线为空记 skipped；run 结果含 scanned/signals_written/skipped/errors 计数

**推送继承**（零新增机制）：
- 落库后由现有 `SignalExecutionScheduler._collect_signals` 收集（按日期捞全部 pending，不过滤策略）
- `signals_ready` 唤醒 agent → 决策链评估（agent 侧有"信号强度≥70"的评估习惯，3买 strength=50 自然被过滤但留痕）→ feishu_notify 推送

### P3：知识蒸馏 + 胜率回喂

**chan_knowledge_distill job**：
- v2 scheduler 新增，每周日晚运行
- 对每个 chan 策略：取 signal_date 在 `[今-90天, 今-20天]` 的信号（留 20 日验证窗），对照 signal 后 5/20 日实际涨跌
- 判定规则与 verify_judgments 一致：buy & 涨 = 对；buy & 跌 = 错；涨跌为 0 不计
- 聚合：`win_rate`、`avg_return`、`samples`（按 5 日/20 日窗分别统计）
- upsert `agent_knowledge`：
  - `domain='chan_theory'`, `knowledge_type='signal_effectiveness'`
  - `content={strategy, window, win_rate, avg_return, samples, period_start, period_end}`
  - `validation_count=samples, success_count=胜次数`
  - confidence 随样本量爬坡：samples<10 封顶 0.3，10-30 → 0.5，>30 → 0.7
  - `knowledge_id` 按 `chan_{strategy}_{window}d` 定值，保证 upsert 幂等

**chan_analyze 响应增强（v2 侧）**：
- `ChanService.analyze` 响应附加 `knowledge` 块：每个买卖点带该类型历史胜率、样本数、建议置信度
- agent 看到：`1买 @ 1620.5，历史胜率 62%（37 样本），建议置信度中高`
- 知识不存在（蒸馏未跑/样本不足）时 knowledge 块为 null，不阻塞分析

## 错误处理

| 场景 | 处理 |
|---|---|
| K 线数据为空/不足 | chan_scan 跳过该股，记 skipped 计数 |
| 单股分析异常 | catch 记 errors 列表，不中断批扫 |
| 蒸馏样本 < 10 | confidence 封顶 0.3，content 标注"样本不足" |
| 蒸馏时 K 线缺失（验证窗内无数据） | 该信号不计入统计 |
| agent_knowledge 无对应知识 | chan_analyze knowledge 块返回 null |

## 测试策略

**v2（pytest）**：
- ChanService 格式化契约测试：mock kline repo 返回已知 K 线，断言 `_format_bi` 输出字段与 `Bi` dataclass 对齐（防再次 500）
- chan_scan：mock analyzer/repo，验证 dedup（同 symbol+strategy+date 不重复写）、strength 映射、errors/skipped 计数
- chan_knowledge_distill：构造已知涨跌序列的信号，验证胜率/平均收益计算与 verify_judgments 判定规则一致

**agent-ts（jest，npm test）**：
- chan_analyze 工具：mock runQuantV2，断言请求路径/参数与响应透传（含 knowledge 块）

## 明确不做（YAGNI）

- 卖点实现（detector 目前只有 1买/2买/3买，1卖/2卖/3卖 未实现）——列入后续迭代
- 标准线段识别（特征序列法）、标准 3 买定义（回抽不入中枢）、多级别联立/区间套
- 类型 × 市场环境二维知识（样本摊薄，待一维知识积累后再升级）
- 独立缠论信号表、独立验证 job（违反复用原则）
- 新增飞书推送机制（复用 signals_ready 链路）
- 不动 verify_judgments / heatmap 任何代码

## 涉及文件

**v2 修改**：
- `application/services/chan_service.py`（修 bug + knowledge 块）
- `application/services/scheduler_tasks.py`（注册 chan_scan / chan_knowledge_distill 任务）
- `infrastructure/scheduler/scheduler.py`（job 调度注册）
- 新增 `application/services/chan_scan_service.py`、`chan_knowledge_distiller.py`
- 新增迁移：内置策略行插入
- 新增测试：`tests/services/test_chan_service.py`、`test_chan_scan_service.py`、`test_chan_knowledge_distiller.py`

**agent-ts 新增**：
- `src/infrastructure/tools/analysis/chan-analyze-tool.ts`（+ 测试）
- V2 命令映射表注册
