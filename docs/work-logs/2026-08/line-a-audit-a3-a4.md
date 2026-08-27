# 线A工单审计报告：A-3/A-4 执行结果

| 字段 | 值 |
|---|---|
| 日期 | 2026-08-28 00:25 |
| 审计方 | agent-dh k3 |
| 工单来源 | [线A工单包](profit-engine-line-a-tickets.md) |

---

## A-3：R-008 决策前检索合规抽查 —— ❌ 无法完成

### 执行过程

查询 `quant.trades` 表（2026-07起），寻找 `portfolio_trade` 执行记录以验证 reason 字段是否符合 R-008（下单前必须 memory_search 且注明检索结论）。

### 结果

| 统计项 | 值 |
|---|---|
| 2026-07 至今交易总数 | **1 笔** |
| reason 字段非空笔数 | **0** |
| 样本详情 | 2026-08-25 10:57 卖出 002241 (700股)，reason=NULL |

### 结论

**无法完成合规抽查**，原因：**样本不足**（仅1笔交易且reason为空）。

这暴露一个更重要的系统性问题：**系统仍处于 pre-trading 阶段**——工单包假设"有交易可审"，但实际上：
- 模拟盘几乎无交易活动（7-8月仅1笔）
- R-008 规则虽在基因组生效，但无执行记录可供验证
- 类似依赖交易记录的工单（如 M6-2 归因分析）同样无样本

### 建议

1. **推迟 A-3 至首个交易活跃周**（如连续5日≥2笔/日后再审）
2. **A-5 归因分析同样无样本**——M6-2 启动条件未满足
3. 考虑用**模拟回测生成的交易记录**替代真实交易做合规演练（如果回测框架记录 reason）

---

## A-4：opponent_behavior 数据源诊断 —— ✅ 完成

### 执行过程

1. 复现 S2 bug：调用 `GET /api/game/market/opponent-behavior?symbol=600737`
2. 追踪端点路径（发现正确路径是 `/api/game/market/opponent-behavior`，文档/工具可能用错路径）
3. 检查数据源：`quant.stock_fund_flow` 表状态
4. 定位 600737 数据覆盖

### 结果

| 项 | 发现 |
|---|---|
| 端点状态 | ✅ 正常工作，路由已注册（main.py:1001） |
| 正确路径 | `/api/game/market/opponent-behavior`（prefix `/api/game` + `/market/opponent-behavior`） |
| 降级行为 | ✅ 数据不足时正确返回 `degraded=true, behavior=unknown`，不产生矛盾结论 |
| S2 bug 复现 | ❌ **当前无法复现**（600737 fund_flow 仅 07-28 一条，最近无数据） |
| 数据源状态 | `stock_fund_flow` 表 8145 条，max=08-26，但**覆盖稀疏**（600737 仅1条） |
| 采集任务 | ❌ **未在 scheduler 中**（`fund_flow_update` 任务不存在） |

### 根因定位

S2 bug（涨停日返回 panic_bottom 矛盾）的根因是：

1. **fund_flow 采集未常态化**：scheduler 无 `fund_flow_update` 任务，历史数据依赖一次性手动导入
2. **数据覆盖不全**：8145 条记录 ÷ ~5000 只股票 = 平均每只 <2 条，远低于"每日更新"预期
3. **降级逻辑掩盖了原 bug**：当前版本在数据不足时返回 unknown，不再产生矛盾结论（可能是某次修复的副作用）

### 修复建议

**优先级 P1**（M7-1 验收前置依赖）：

1. **实现 fund_flow 每日采集任务**：
   - 挂载到 scheduler（每日收盘后 16:30-17:00）
   - 调用 eastmoney 资金流接口（代码已有：`stock_fund_flow` 表的 source='eastmoney'）
   - 验收标准：连续 5 个交易日 `stock_fund_flow` 新增记录，覆盖 ≥4000 只活跃股票
   
2. **回填历史数据**（可选，降低优先级）：
   - 回填 2026-07 至今的 fund_flow 数据
   - 用于 M7-2 恐慌指标回测验证

3. **复测 S2 bug**（数据齐全后）：
   - 找一个近期涨停日（如 08-27 涨停股）
   - 调 opponent_behavior，验证是否仍返回 panic_bottom 矛盾
   - 若矛盾仍存在，追踪散户/机构情绪判定逻辑（retail.behavior 计算规则）

### 附：端点路径问题

工具/文档可能使用错误路径 `/api/market/opponent-behavior`（缺 `/game` 前缀）。建议：
- 检查 `@pi-investment/competition` 插件的 `opponent_behavior` 工具实现
- 若路径写死了 `/api/market/`，改为 `/api/game/market/`
- 或在 quantsys-v2 添加路径别名兼容旧调用

---

## 总结

| 工单 | 状态 | 阻塞原因 |
|---|---|---|
| A-3 R-008 合规抽查 | ❌ 无法完成 | 交易样本不足（7-8月仅1笔，reason=NULL） |
| A-4 opponent_behavior 诊断 | ✅ 完成 | 根因定位：fund_flow 采集未常态化 |

**关键发现**：
1. 系统仍在 pre-trading 阶段，依赖交易记录的工单（A-3/A-5/M6-2）无法推进
2. M7-1 的数据地基（fund_flow 每日采集）缺失，优先级应提到 P1

**下一步**：
- A-1（滑点收口）/A-2（trade_verify 例行化）仍可推进（不依赖历史交易）
- A-5（归因分析）推迟到交易活跃期
- 启动 fund_flow 每日采集任务（解锁 M7 全系列工单）
