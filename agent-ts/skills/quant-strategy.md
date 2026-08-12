---
name: quant-strategy
description: 用真实策略体系做量化——执行/回测已注册策略、批量验证、股票池验证与战场评估（不是手工选股流程）
---

# 量化策略技能 (Quant Strategy)

## 允许的工具
- strategy_list()
- strategy_detail()
- strategy_execute()
- strategy_status()
- strategy_optimize()
- strategy_batch_validate()
- strategy_discovery()
- pool_manage()
- pool_validate()
- pool_battlefield()

## 触发条件

用户想跑量化策略、回测、验证策略有效性、管理股票池时使用此技能。

关键词：量化、策略、回测、因子、轮动、股票池、策略验证、战场评估

## 核心原则

系统的量化能力由 **StrategyService + yaml 配置驱动**（v2 后端统一架构），策略执行走真实闭环：
信号 → 订单 → 成交 → 盈亏（全链路落库到 v2）。

**不要手工拼凑"筛选+评分"流程冒充量化**——那是 deep-analysis / stock-screener 的活。
本技能只负责调度和解读真实的策略工具。

## 工作流程

### 1. 明确意图 → 选工具

| 用户意图 | 工具 |
|---------|------|
| 有哪些策略可用 | `strategy_list()` |
| 看某个策略详情/表现 | `strategy_detail()` / `strategy_status()` |
| 跑策略信号/回测 | `strategy_execute({action: "single"/"batch"/"pipeline", strategy, symbol(s)})` |
| 验证策略是否还有效 | `strategy_batch_validate({startDate, endDate, threshold: 60, dryRun: true})` |
| 优化策略参数 | `strategy_optimize()` |
| 发现新策略 | `strategy_discovery()` |
| 验证股票池 | `pool_validate({pool_id, strategy_ids?})` |
| 评估哪个池子值得打 | `pool_battlefield()` |

### 2. 执行

- 先 `strategy_list()` 拿到真实 strategy_id，**不要臆造策略名**
- 注意策略健康度：系统中相当比例的存量策略已被体检判定为无效/死码并停用，优先使用 `strategy_status` 显示活跃且近期验证通过的策略
- 批量验证先用 `dryRun: true` 预演，确认结果合理再正式跑

### 3. 解读输出（必须包含）

- **胜率 + 期望收益 + 样本数** 三件套——样本数不足的结论必须标注"样本不足，仅供参考"
- 与市场基准对比（而不是只说绝对收益）
- 明确的下一步建议：继续用 / 调参 / 停用

## 输出模板

```markdown
## 策略执行结果

### 策略：{名称} (ID: {id})
- 状态：{活跃/停用}，最近验证：{日期} {通过/失败}
- 回测区间：{start} ~ {end}
- 胜率：XX% | 期望收益：XX% | 样本：N 笔
- 基准（沪深300）：XX%

### 结论
{继续使用/建议调参/建议停用} — {理由}

### 下一步
- ...
```

## 注意事项

- 策略执行和验证的计算都在 quantsys-v2 后端完成，agent 侧只负责调度与解读
- 大结果（批量回测）会自动落盘，上下文中只有摘要+文件路径，需要细节时读文件
- 用户要的是"帮我选股/分析股票"而不是跑策略时，不要用本技能——那是 deep-analysis / stock-screener 的场景
