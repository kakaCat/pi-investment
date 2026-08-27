# A-1 M5-1 滑点追踪验收指南

| 字段 | 值 |
|---|---|
| 日期 | 2026-08-28 01:15 |
| 编制 | agent-dh k3 |
| 代码状态 | ✅ 已在 main 分支（commit `aaa27865`） |
| 工具状态 | ✅ `slippage_report` 已注册（packages/trading/src/index.ts） |
| 验收状态 | 🟡 等新交易触发测试 |

---

## 验收步骤（需在 DSH Web UI 执行）

### 1. 确认代码已加载

访问 `http://localhost:13080`，检查 `slippage_report` 工具是否可用：

```
列出所有可用工具，确认 slippage_report 在列表中
```

如果不在，说明 DSH 未重启加载新代码，需要：
```bash
cd ~/.dsh/profiles/investment
./stop.sh && ./start.sh
```

### 2. 执行一笔模拟交易（触发滑点追踪）

**重要**：选择**小额、高流动性标的**避免实际风险。

```
用 account_info 查可用资金，然后：

portfolio_trade({
  action: "BUY",
  symbol: "600519",  // 贵州茅台，高流动性
  quantity: 100,     // 1手，最小单位
  reason: "A-1验收：测试滑点追踪功能（M5-1）"
})
```

**预期行为**：
- portfolio_trade 执行前调用 data_fetch_quote 抓决策时价
- 成交后计算滑点（成交价 vs 决策价，方向归一）
- 滑点记录写入 Agent OS memory（namespace: trade:slippage）

### 3. 验收滑点追踪

```
调用 slippage_report 工具
```

**预期输出**：
```json
{
  "total_trades": 1,
  "average_slippage": <数值>,
  "max_slippage": <数值>,
  "by_symbol": {
    "600519": {
      "count": 1,
      "avg_slippage": <数值>
    }
  }
}
```

**验收标准**：
- ✅ total_trades ≥ 1
- ✅ 滑点值方向归一正确（正值 = 买贵/卖便宜）
- ✅ by_symbol 包含 600519

### 4. 清理（可选）

如果不想持有测试仓位：
```
portfolio_trade({
  action: "SELL",
  symbol: "600519",
  quantity: 100,
  reason: "A-1验收清理"
})
```

第二笔交易也会产生滑点记录，`slippage_report` 应显示 total_trades=2。

---

## 降级方案（如果 Agent OS 不稳定）

滑点追踪依赖 Agent OS memory（namespace: trade:slippage）。如果 Agent OS 宕机：

**预期降级行为**（根据 `aaa27865` 提交信息推测）：
- portfolio_trade 不应阻塞（交易照常执行）
- 滑点数据写入失败，应有日志记录
- slippage_report 返回空或降级提示

**验收要求**：即使 Agent OS 宕机，**交易不能被滑点追踪阻塞**。

---

## 当前阻塞

**系统 pre-trading 阶段**：7-8 月仅 1 笔交易（08-25 10:57，代码部署之前），无法用现有交易验收。

**两个选择**：
1. **推荐**：按上述步骤做 1 笔测试交易（100 股茅台，~170 元成本）
2. **保守**：推迟 A-1 验收，等模拟盘进入交易活跃期

---

## 验收报告模板

完成测试后，请提供：

```
A-1 验收结果：
- slippage_report 输出：<贴JSON>
- 决策时价 vs 成交价对比：
  - 决策时 600519 价格：<price> (data_fetch_quote时刻)
  - 实际成交价：<fill_price>
  - 滑点：<slippage> (方向归一)
- 验收结论：通过/失败
```

我将根据报告做最终复核。
