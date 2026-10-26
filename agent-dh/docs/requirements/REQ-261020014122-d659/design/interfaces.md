# 接口设计（REQ-261020014122-d659）

> 本需求不新增工具/API；以下为两个**既有接口的返回契约变更**（均为 additive）。

## 修改的接口 `serves: FR-1, FR-2, FR-3`

### run_backtest_from_signals（qv2 内部服务方法）`serves: FR-1, FR-2`

**用途**：从信号 DataFrame 跑回测，经 `/api/backtest/strategy` 与 agent 工具 `strategy_execute(mode=backtest)` 原样透传 metrics。

**调用方**：StrategyEvolutionService（进化判据）、`/api/backtest/strategy`、agent-dh strategy 插件。

**接口定义（变更部分）**：

```python
def run_backtest_from_signals(
    self,
    signals_df: pd.DataFrame,
    initial_cash: float = 1000000,
    period: Optional[str] = None   # None=日线；'5min'等=分钟线（T+1 约束，本次不动）
) -> Dict:
    # 返回 metrics dict，本次新增两个键（恒存在）：
    #   open_position_at_end: bool  —— 窗口结束时是否有未平仓持仓
    #   forced_closes: int          —— 窗口末强制平仓计账笔数（0 或 1）
    # trades[] 元素在强制平仓条目上新增键：
    #   forced_close: true          —— 仅强制平仓条目携带；普通条目无此键
```

**强制平仓条目契约**（与全清分支同构，strategy_backtest_service.py:343-363 形状）：

| 字段 | 取值 | 说明 |
|---|---|---|
| `entry_date` | 首笔 tier 入场日 | 同现有 trades 条目 |
| `exit_date` | 窗口末日 `date_str` | 最后一条 K 线日期 |
| `entry_price` | 加权平均入场价 | `sum(t.shares×t.entry_price)/total_shares` |
| `exit_price` | 末日 `close_price` | 不用自定义卖价（窗口已结束，无信号行） |
| `shares` | 全部持仓股数 | |
| `pnl` / `pnl_pct` | `shares×(exit−avg_entry)` | **不计卖出费用**——与权益曲线口径一致（权益未扣卖出费） |
| `tiers` | 逐 tier 明细 | 与全清分支同构 |
| `forced_close` | `true` | 计账标记 |

**副作用边界**：不回改 `cash`、不追加 `equity_curve` 点（计账不动账）；不受 `enable_t1_constraint` 限制（记账非真实交易，分钟线窗口末同样计账）；`signals_df` 为空/无持仓时不触发。

**错误语义**：不变（原有校验与 `_empty_metrics` 路径不动；空 equity_curve 时 `open_position_at_end=false`、`forced_closes=0`）。

### evolution_run（agent-dh 工具）`serves: FR-3`

**用途**：触发 qv2 策略进化引擎一轮真实回测进化。

**调用方**：投资脑 agent（每周进化任务、策略优化）。

**接口定义（变更部分）**：输入参数不变。输出契约变化——

```typescript
interface EvolutionRunResult {
  // ……既有字段不变……
  data_source: 'qv2_real' | 'degraded';
  degraded_reason?: string;        // degraded 时恒非空（引擎保证 + 空响应兜底）
  // 以下 4 键：值为 null/undefined 时整体省略（不出现在输出对象），
  // 仅 qv2_real 且引擎产出真实值时出现：
  best_params?: Record<string, any>;
  best_metrics?: Record<string, any>;
  fitness?: number;
  fitness_improvement?: number;
}
```

**变更后行为对照**：

| 场景 | 修复前 | 修复后 |
|---|---|---|
| 引擎降级（显式 null 四键） | `returned invalid output` 硬错误，degraded_reason 丢失 | `success: true` + `data_source: 'degraded'` + 可读 `degraded_reason` |
| 引擎 qv2_real | 正常（不变） | 正常（不变） |
| 引擎空响应 | 兜底 degraded（EvolutionRunTool.ts:8，不变） | 不变 |

**实现落点**：`normalizeRunResult`（EvolutionRunTool.ts:26-47）在现有 `degraded_reason == null` 剔除之后，对 `['best_params','best_metrics','fitness','fitness_improvement']` 白名单做同款剔除。prompt.ts 的 output schema **零改动**（键本可缺省；schema 无 required 数组）。

**不选方案 B（引擎侧补占位字段）的理由**：在降级响应里补 `best_params={}`/`fitness=0` = 编造占位数字，违反诚实降级语义；且引擎响应被 evolution_leaderboard 等其他消费方共享，改动面更大。
