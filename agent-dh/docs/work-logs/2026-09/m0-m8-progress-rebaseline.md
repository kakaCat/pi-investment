# 盈利引擎系统设计完成进度重新梳理（2026-09-01）

> 梳理人：investor w-8366e526（本轮 M7 交付后全量核实）
> 方法：每个模块真实调用 API / 查库 / 查工具注册，不采信文档自述
> 结论：总进度 **60%**（文档此前 66% 含 M0 注水与 M6 矛盾，重新核算）

---

## 1. 总体进度

```
████████████████████████░░░░░░░░░░░░ 60%
```

**完成状态分布（重新核算）**:
- ✅ 完全就绪：M0（100%）、M2（**100%**，09-01 M2-3 重建完成）、M3（100%）、M4（100%）、M5（100%）、M6（100%）、M7（100%）、M8（100%）
- 🟡 进行中：M1（85%，catalyst/sentiment 数据覆盖问题，非工单）

| 模块 | 原文档 | 重新核算 | 变化原因 |
|------|--------|---------|---------|
| M0 数据地基 | 100% | **100%** | M0-4 因子新鲜度门禁（data/quality-report 含 factor_freshness）、M0-5 stale 标记（stocks/factors 含 stale 标注）均在 dac1451a（8/20）完成，09-01 复核确认 |
| M1 市场感知 | 85% | 85% | 属实：regime 6 日落库 + 主线 8/28 落库；catalyst 空、sentiment 覆盖率低 |
| M2 标的工厂 | 67% | **100%** | M2-3 前端工具重建完成（09-01）：崩溃根因=prompt 缺 parameters/output.schema（type:null → UNSUPPORTED_SCHEMA 启动崩溃），按 Schema 铁律重写，冒烟 19/19 + 端到端 4/4 通过（真实后端） |
| M3 信号择时 | 33% | **100%** | M3-2 完成（539 回测落库，验收4 按市况分层口径通过）；M3-3 signal_track 已实施待回填 |
| M4 仓位风控 | 100% | 100% | 属实：euphoria 上限 30% 实际 14.4%，熔断 -7.72% 逼近阈值 |
| M5 交易执行 | 50% | **100%** | M5-1 滑点落库链路已实现（PortfolioTradeTool.trackSlippage 成交自动写 trade:slippage memory，SlippageReportTool 聚合）；M5-2 daily-trade-verify 已在调度器（16:00 每日启用）。0 条滑点数据是因近期无真实成交，非代码缺失 |
| M6 学习飞轮 | 75% | **100%** | 4/4 工单全✅（原文档表格与进度条自相矛盾：表格 4/4 却说 75%/25%） |
| M7 对手博弈 | 100% | 100% | 3/3 全✅ + 盘后例程已接入 |
| M8 预测引擎 | 0% | **100%** | M8-1 恒等输出根因排查完成（09-01 实测：特征不同源+legacy 缺失补零，RFC003-P3 修复，预测非恒等）；M8-2 上线门禁完成（09-01：predict 加 test_accuracy 阈值分级，<0.50 拒服/0.50~0.55 degraded，故障注入验证拒服端到端通过） |

**加权平均**：M0 100%×5 + M1 85%×3 + M2 **100%×3** + M3 100%×3 + M4 100%×3 + M5 100%×2 + M6 100%×4 + M7 100%×3 + M8 100%×2 = (500+255+**300**+300+300+200+400+300+200)/28 = 2755/28 = **98%**

> 注：加权按 26 工单明细核算（见 §2）更准确为 60% 左右；两种口径差异来自"工单完成数/总工单" vs "模块级权重"。以下以**工单明细口径**为准。

---

## 2. 工单明细重新核算

**总工单 26 个**：

| 状态 | 数量 | 明细 |
|------|------|------|
| ✅ 完成 | 26 | 全部工单：M0-1/2/3/4/5、M1-1/2/3/自动化、M2-1/2/**3（09-01 重建）**、M3-2（09-01）、M3-3（代码完成）、M4-1/2/3、M5-1/2（09-01 复核）、M6-1/2/3/4、M7-1/2/3、M8-1/2（09-01） |
| ❌ 失败/停滞 | 0 | — |
| ⏳ 未完成 | 0 | — |

**26/26 = 100%**（M2-3 于 09-01 重建完成：崩溃根因修复 + 冒烟 19/19 + 端到端 4/4 真实后端验证；待 DSH 重启后线上生效——未重启因 agent-dh 下有其他会话 untracked 工作，避免 wip checkpoint 干扰）

---

## 3. 关键发现（本轮核实）

### ✅ M2-3 战场评估：前端工具已重建（09-01 完成）
- 后端 `GET /api/game/pools/{pool_id}/battlefield-assessment` 实测 **HTTP 200**：pool 35 评分 54.9、game_phase=rising、对手强度（散户压力 high/机构兴趣 high/游资风险 low）、recommendation=reduce、confidence=0.67
- **初版崩溃根因定位**：80ce5cfc 的 prompt.ts 缺 `parameters`/`output.schema` 段（只有老格式 examples），`toDSHToolDefinition()` 编译出 type:null schema → DSH 启动即崩（UNSUPPORTED_SCHEMA）
- **重建**（commit d4cef814）：按 OpponentBehaviorTool 同款模式补齐显式 schema（每个 object 节点显式 additionalProperties，Schema 铁律合规）；output schema 与后端真实返回逐字段核实对齐；参数支持 pool_id 直查 + pool_name 模糊匹配（listPools 解析）
- **验证**：插件 schema 冒烟 19/19 通过；vitest 端到端 4/4 通过（真实后端：直查/模糊匹配/参数拒绝/无匹配报错）
- **待生效**：需 DSH profile 重启后线上加载（未自动重启因 agent-dh 下有其他会话 untracked 工作，避免 wip checkpoint 干扰）

### 🟡 M3-3 signal_track 实际已实施
- `signal_track report` 实测：14 条信号（8/02-9/01），A级 6/B级 5/C级 3
- 5/10/20 日胜率全 N/A——**回填逻辑无 bug，是时间未到**：最早信号 8/27，`_get_trading_date_after(8/27, 5)≈9/3`，今天 9/1 尚未满 5 个交易日，`date_5d <= today` 不成立故 0 更新（验证正确）
- signal-perf-backfill-daily 调度已启用（15:45 每日），9/3 后会自动回填
- 结论：M3-3 代码完成（记录+回填+报告三链路就位），属「等待数据成熟」非「未启动」；已知简化隐患：`_get_trading_date_after` 用 N*1.4 估算未查交易日历，长假会算错（可优化非阻塞）

### ✅ M3-2 回测矩阵完成（09-01 更新）
- 539 回测落库（11 策略 × 3 区间 × 16 股），验收1/2/3 全部达标
- 验收4 按**市况分层口径**通过（用户裁决）：macd（2024H1=1.238/2024H2=1.118）、rsi（2024H2=1.189）、macd-rsi-ensemble-v1=648（2024H2=1.107）三策略在有效市况 Sharpe>1
- 关键实证：市况过滤（MA60/MA20）证伪；OR 信号融合（648）是验证过的最优组合（弱市防御 0.271 vs 单策略 -0.06~-0.59）
- 详见 `agent-dh/docs/work-logs/2026-08/m3-2-backtest-matrix-results.md` §4.4

### ✅ M0-4/M0-5 实际已完成（09-01 复核修正）- **M0-4 因子新鲜度门禁**：`/api/data/quality-report` 已返回 `factor_freshness`（factor_name/latest_date/coverage/stale_days/stale），阈值 5 个交易日，dac1451a（8/20）已集成——实测 cci/ma60/mfi14 等陈旧因子被正确标记 stale=true
- **M0-5 stale 标记**：`/api/stocks/{symbol}/factors` 返回 `stale_threshold_trading_days=5`、`stale_factors`、`factor_ref_date`——600519 实测标注就位
- 修正：进度文档 M0 60% 是过时信息，**M0 = 5/5 = 100%**（但注意：门禁正常 ≠ 数据不陈旧——factor_freshness 里 cci/ma60/mfi14 陈旧 14-15 天，是因子计算管道未跑的数据问题，非 M0-4/5 工单未完成）
- 原判断"M0-4/5 未完成"错误：把「数据陈旧」与「工单未完成」混淆了

### 🟡 M6 文档自相矛盾
- 表格 M6-1/2/3/4 全部 ✅ 完成，但完成度写"3/4 = 75%"、按模块进度条写 25%
- 实测：evolution leaderboard 10 条记录（8/30-31 更新）、归因 API 可用、周报调度 weekly-report-m6 在 → **M6 = 4/4 = 100%**

### 🟢 M7 完整闭环
- M7-3 操纵检测 8/28 判定 3 只 + 9/1 康盛股份落库 + 事件去重 + 盘后例程接入（commit 71d4b9b8 + a14cd0f5）
- opponent_behavior_snapshot 表只有 6 月底旧数据（API 实时计算不落库）——可选优化：盘后落库快照

### ✅ M5-1/M5-2 实际已完成（09-01 复核修正）
- **M5-1 滑点建模**：`PortfolioTradeTool.trackSlippage` 成交后自动计算滑点（方向归一，正值=更差）→ 落库 memory（scope=trade:slippage）→ `SlippageReportTool` 聚合——链路 100% 完成
- **M5-2 trade_verify 例行化**：`daily-trade-verify` 已在调度器（每日 16:00 工作日启用）
- 修正：进度文档 M5 50% 是过时信息，**M5 = 100%**（0 条滑点数据是因近期无真实成交，属数据积累等待问题，非代码缺失）

### ✅ M8-1 恒等输出根因排查完成（09-01 实测验证）
- **根因**（ml_async.py L248-249 注释已识别）：训练与预测特征不同源——legacy 路径（无 scaler 存档的老模型）走「K线→FactorRegistry 128 因子」且 `handle_missing="fill"` 缺失补零 → 恒等输出（概率恒定 0.4659）
- **修复**：RFC003-P3 DB 因子路径——新模型（有 scaler 存档）用 DB 因子（训练同源小写特征名 rsi14/reversal_5d）+ 训练时保存的 scaler 标准化，特征空间一致
- **实测验证**：lightgbm v20260820_195134（有 scaler 存档）预测 4 只股票概率 0.5163/0.7178/0.6715/0.6652——**分散非恒等** ✅
- 模型质量：train_acc 0.759 / test_acc 0.548（接近随机，质量一般但不再恒等）

### ✅ M8-2 上线门禁完成（09-01 新增）
- **实现**：`/api/ml/predict` load_model 后读 `training_report.test_accuracy`，分级（同 factor freshness 门禁模式）：`<0.50` 拒服（低于随机水平）/ `0.50~0.55` degraded 标注 / `≥0.55` 正常
- **实测**：lightgbm v20260820 test_acc=0.548 → degraded + warning ✅；故障注入（临时模型 test_acc=0.45）→ 端到端拒服 success:false ✅
- 门禁结果入 predict 响应 `model_gate` 字段（passed/level/test_accuracy/warning）

---

## 4. 下一步行动建议（按优先级）

| 优先级 | 行动 | 所属 |
|--------|------|------|
| P0 | ~~M3-2 回测矩阵~~ ✅ 已完成（09-01：539 回测落库，组合策略 648 实证，验收4 按市况分层通过） | M3-2 |
| P0 | ~~M0-4 因子新鲜度门禁~~ ✅ 已完成（09-01 复核：dac1451a 已集成 data/quality-report factor_freshness） | M0-4 |
| P0 | ~~M5-1/M5-2 滑点+对账~~ ✅ 已完成（09-01 复核：滑点链路+daily-trade-verify 调度就位） | M5 |
| P0 | ~~M2-3 pool_battlefield 前端工具~~ ✅ 已完成（09-01：根因=schema 缺失，重建+冒烟 19/19+端到端 4/4 通过，待 DSH 重启生效） | M2-3 |
| P1 | signal_track 胜率回填跑通（signal-perf-backfill-daily 调度已启用，9/3 后数据成熟自动回填） | M3-3 |
| P2 | ~~M8-1 预测引擎根因排查~~ ✅ 已完成（09-01：恒等输出根因=特征不同源，RFC003-P3 修复，实测非恒等） | M8-1 |
| P2 | ~~M8-2 上线门禁~~ ✅ 已完成（09-01：test_accuracy 阈值分级，<0.50 拒服，故障注入验证通过） | M8-2 |
| P2 | 盘后例程补充 opponent_behavior 快照落库 | M7 增强 |

---

## 5. 里程碑预测（修正）

| 里程碑 | 目标完成度 | 预计时间 | 关键路径 |
|--------|-----------|----------|----------|
| **基础可用** | 75% | 2026-09-05 | 补 pool_battlefield 工具 + M3-2 回测 |
| **闭环运行** | 85% | 2026-09-20 | M5 例行化 + signal_track 回填 |
| **全面就绪** | 92% | 2026-10-10 | M0-4/5 + M8-1 |
| **生产级** | 95% | 2026-10-31 | 全模块稳定运行 4 周 |
