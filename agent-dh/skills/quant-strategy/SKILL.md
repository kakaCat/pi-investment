---
name: quant-strategy
description: 量化策略执行 SOP：用已注册的真实策略做信号/回测（strategy_list 拿真实 ID → 先核验策略健康 R-011 → strategy_execute → 输出含胜率/样本/基准对比），不做手工拼凑"筛选+评分"冒充量化。回答"跑策略/回测/策略验证/看策略表现"时按此执行，禁止臆造策略名或采信 error 策略输出。
whenToUse: 用户要求跑策略信号、回测验证策略、评估策略有效性、优化参数（"跑一下均线策略/哪个策略能用/回测看看/策略优化"），或策略信号批量推送需先核验信号源健康时
---

# 量化策略执行 SOP（Quant Strategy）

> 定位：DH 的量化能力由 quantsys-v2 后端驱动——strategy_list 看到的是真实注册策略，strategy_execute 跑的是真实信号/回测闭环。本技能负责"调度 + 核验 + 解读"，不做手工选股流程冒充量化（那是 deep-analysis / stock-screener / opportunity-funnel 的活）。
> 铁律：**先核验再执行（R-011）**——批量信号/策略输出前必须 strategy_list 核验策略健康，status=error 或 validationStatus=invalid 的输出不可信，默认跳过不执行。

## 第 0 步：核验信号源健康（R-011，批量信号执行前必做）

1. `strategy_list` 拿全部策略清单，重点看目标策略的 `status` 与 `validationStatus`。
2. **异常特征清单**（命中即默认跳过该策略输出，不逐条重复核查）：
   - status=error 或 validationStatus=invalid
   - 全市场同向（如全 SELL）+ 数量异常（一次 50+ 只）
   - indicators 字段为空 / confidence=null
   - reason 模板化重复
3. 与持仓零交集且无独立维度确认时：按宪法第 6 条零交易合法，跳过并在 reason 记录核验结论。
4. 策略健康时再对信号做 R-009 A/B/C 分级（先核验源健康、再分级，两级次序不可颠倒）。

## 第 1 步：意图 → 选工具（全部用真实工具，不臆造）

| 用户意图 | DH 工具 |
|---------|--------|
| 有哪些策略可用 | `strategy_list` |
| 跑某策略当前信号 | `strategy_execute`(mode=signal, strategy_id, symbols?) |
| 策略历史回测 | `strategy_execute`(mode=backtest, strategy_id, start_date, end_date, initial_capital) |
| 优化策略参数 | `strategy_optimize`(strategy_id, param_ranges, symbols, 区间, target) |
| 策略进化（每周/表现下滑时） | `evolution_run`(strategy_id, symbol, mode=propose/full) → `evolution_leaderboard` 看各轮效果 |
| 评估股票池战场 | `pool_battlefield`(pool_id/pool_name) |
| 股票池策略校验 | `pool_manage`(action=validate, pool_id, strategy_ids) |
| 策略批量验证/发现新策略 | 无独立工具——用 `strategy_execute` backtest 逐策略验证 + `learning_analyze` 归纳 |

## 第 2 步：执行（拿真实 ID，先核验再跑）

1. `strategy_list` 拿真实 strategy_id——**禁止臆造策略名/ID**（R-011 实证：error 策略曾连日出全 SELL 异常批量）。
2. 优先选 status 活跃且近期验证通过的策略；error/invalid 策略输出不可信。
3. 回测/验证：先小样本试跑确认结果合理，再扩大（参数化地控制，不一次性大范围盲跑）。
4. 策略信号进交易决策前：按 R-009 分级 + R-008 memory_search 检索 + R-001 确认仓位三件套走完才可下单。

## 第 3 步：解读输出（必须包含三件套，禁止只说绝对收益）

- **胜率 + 期望收益 + 样本数**——样本不足的结论必须标注"样本不足，仅供参考"
- **与基准对比**（沪深300 等），而不是只看绝对收益
- **明确的下一步**：继续用 / 调参 / 停用（给出依据）

## 输出模板

```markdown
## 策略执行结果

### 策略：{名称} (ID: {id})
- 状态：{活跃/error/invalid} | 信号源健康核验：{R-011 结论}
- 模式：{signal/backtest} | 区间：{start} ~ {end}（backtest）
- 信号/胜率：{signal 数量与方向 / 胜率 XX% + 期望收益 XX% + 样本 N 笔}
- 基准对比：{沪深300 等同期表现}

### 结论
{继续使用/建议调参/建议停用} — {理由（基于数据，不拍脑袋）}

### 下一步
- ...
```

## 注意事项

- 策略信号批量推送时先做 R-011 核验，再对可信信号做 R-009 分级。
- `evolution_run` 返回 data_source=degraded 表示引擎诚实降级（无 proposals），禁止基于降级结果做决策。
- 用户要的是"帮我选股/分析股票"而非跑策略时，不用本技能——那是 deep-analysis（单只尽调）/ stock-screener（按条件选股）/ opportunity-funnel（全市场扫机会）的场景，别串技能。
- 大回测结果上下文放不下时，只保留摘要，细节按需再取。
