# M5-1 滑点追踪验收指南

| 字段 | 值 |
|---|---|
| 日期 | 2026-08-28 |
| 编制 | agent-dh investor (w-5b708a8b) |
| 任务 | RFC 005 M5-1: 滑点建模（成交价 vs 决策时价差逐笔落库） |
| 代码状态 | ✅ 已修复并加载 |

---

## 代码状态确认

### 修复历史

| Commit | 日期 | 内容 |
|--------|------|------|
| `aaa27865` | 2026-08-25 22:07 | 初始实现：portfolio_trade 抓决策时价 → 成交后算滑点 → 落库 `qv2.createMemory` |
| `70fb8639` | 2026-08-28 13:19 | **修复**：滑点读写从 qv2 旧通道迁移到 `this.osMemory`（OsMemoryStore） |
| `02ba42b0` | 2026-08-28 13:22 | 合并修复 |

### 当前状态 ✅

- **代码版本**：70fb8639（已加载到 DSH，13:34 启动）
- **落库通道**：Agent OS Memory（`OsMemoryStore`，scope=`trade:slippage`）
- **工具可用**：
  - `portfolio_trade`：下单时自动记录滑点
  - `slippage_report`：汇总滑点统计

### 验证结果

```bash
# 1. Agent OS 在线
$ lsof -ti:8080 -sTCP:LISTEN
46375  ✅

# 2. DSH 已加载新代码
$ ls -la ~/.dsh/profiles/investment/node_modules/@pi-investment/trading/src/index.ts
-rw-r--r--@ 1 yunpeng  staff  42745 Aug 28 13:19  ✅

# 3. 滑点记录搜索（当前为空，等待真实交易）
$ curl -s 'http://localhost:8080/api/v1/memory/search?q=trade:slippage&limit=20' | jq '.memories | length'
0  ⏳ 等待首次交易触发
```

---

## 验收标准（RFC 005）

| # | 验收项 | 方法 | 通过标准 |
|---|---|---|---|
| 1 | 端到端滑点记录 | 交易时段（9:30-15:00）模拟盘下一笔小额单（如 100 股低价股），portfolio_trade 返回体应含 `slippage{decision_price, fill_price, slippage_pct, decision_time}` | 返回含 slippage 块，数值合理（\|slippage_pct\| 一般 <1%） |
| 2 | 方向归一正确性 | 一笔 BUY + 一笔 SELL，核对符号规则：滑点正=更差（买贵/卖便宜） | BUY: (fill-decision)/decision×100；SELL: 取负。符号符合定义 |
| 3 | 落库可检索 | `slippage_report` 调用（无参 + 带 symbol 各一次） | 笔数≥实测成交笔数；avg/max/bySymbol 分布数值与落库记录一致 |
| 4 | 非阻塞性 | 静态审查已确认 try/catch 包裹 getQuote 与落库 | ✅ 代码审查通过；可选：断网/mock 失败验证下单不受影响 |
| 5 | 数据归属正确 | 落库记录 scope=`trade:slippage`、status、payload 字段完整（symbol/action/quantity/decision_price/fill_price/slippage_pct/decision_time/order_id/ts） | 字段齐全，且落在 OsMemoryStore（Agent OS） |
| 6 | reason 透传 | 落库 content 含下单理由 | R-005 联动成立 |

---

## 验收步骤

### 前置条件

- ✅ 当前时间在交易时段（9:30-15:00）
- ✅ DSH 已启动（:13080）
- ✅ Agent OS 在线（:8080）
- ✅ quantsys-v2 在线（:5001）
- ⚠️ **需要初始化虚拟账户**（当前账户数据为 null）

### Step 1: 初始化虚拟账户（如需）

```bash
# 检查账户状态
curl -s http://localhost:5001/api/account/info?account_name=agent_virtual | jq '{total_assets, cash_available}'

# 如果为 null，需要初始化
# TODO: 确认初始化方法（可能需要后端脚本或 API）
```

### Step 2: 执行测试交易

**通过 DSH Web UI 执行**（推荐）：

1. 访问 http://localhost:13080
2. 发送消息：
   ```
   测试滑点追踪：买入 100 股 600000（浦发银行），使用 R-001 确认流程
   ```
3. Agent 会自动：
   - 调用 `data_fetch_quote` 获取当前价
   - 调用 `account_info` 确认可用资金
   - 调用 `regime_position_limit` 确认仓位
   - 调用 `risk_controller position_size` 计算建议仓位
   - 调用 `portfolio_trade` 下单
   - **自动记录滑点到 Agent OS**

**或通过 curl 直接调用工具**（需要构造完整参数）：

```bash
# 不推荐：需要手动构造 tool execution payload
```

### Step 3: 验证滑点记录

```bash
# 1. 搜索滑点记录
curl -s 'http://localhost:8080/api/v1/memory/search?q=trade:slippage&limit=20' | jq '
{
  total: (.memories | length),
  records: .memories[] | {
    id,
    title,
    created_at,
    content_preview: (.content | fromjson | {
      scope,
      kind,
      payload: .payload | {symbol, action, slippage_pct}
    })
  }
}'

# 2. 调用 slippage_report 工具（通过 DSH）
# 在 Web UI 发送：查看滑点报告
```

### Step 4: 验证数据完整性

检查落库记录是否包含所有必需字段：

```bash
# 获取具体记录
curl -s 'http://localhost:8080/api/v1/memory/search?q=trade:slippage&limit=1' | jq '
.memories[0].content | fromjson | {
  scope,
  kind,
  status,
  payload: {
    symbol,
    action,
    quantity,
    decision_price,
    fill_price,
    slippage_pct,
    decision_time,
    order_id,
    ts,
    reason
  }
}'
```

---

## 预期结果示例

### portfolio_trade 返回（含 slippage 块）

```json
{
  "success": true,
  "order_id": "ord_20260828_001",
  "symbol": "600000",
  "action": "BUY",
  "quantity": 100,
  "fill_price": 10.25,
  "slippage": {
    "decision_price": 10.23,
    "fill_price": 10.25,
    "slippage_pct": 0.195,
    "decision_time": "2026-08-28T14:05:32Z"
  }
}
```

### Agent OS 落库记录

```json
{
  "id": "mem_abc123",
  "title": "Trade slippage: BUY 600000",
  "created_at": "2026-08-28T14:05:35Z",
  "content": "{\"kind\":\"episode\",\"scope\":\"trade:slippage\",\"status\":\"testing\",\"payload\":{\"symbol\":\"600000\",\"action\":\"BUY\",\"quantity\":100,\"decision_price\":10.23,\"fill_price\":10.25,\"slippage_pct\":0.195,\"decision_time\":\"2026-08-28T14:05:32Z\",\"order_id\":\"ord_20260828_001\",\"ts\":\"2026-08-28T14:05:35Z\",\"reason\":\"R-001 测试滑点追踪\"},\"body\":\"...\"}"
}
```

### slippage_report 输出

```json
{
  "total_fills": 1,
  "avg_slippage_pct": 0.195,
  "max_slippage_pct": 0.195,
  "min_slippage_pct": 0.195,
  "by_symbol": {
    "600000": {
      "fills": 1,
      "avg_slippage": 0.195
    }
  }
}
```

---

## 已知限制与风险

| 项目 | 说明 | 影响 | 缓解 |
|------|------|------|------|
| **虚拟账户未初始化** | 当前账户数据为 null | 无法下单测试 | 需确认初始化方法 |
| **Agent OS 稳定性** | 历史有宕机记录（08-27 23:59） | 落库失败时被 try/catch 吞掉 | 建议在 catch 里加日志告警 |
| **决策时价精度** | getQuote 可能返回延迟价格 | 滑点计算偏差 | 可接受（记录实际差异即可） |
| **非交易时段** | 15:00 后无法下单 | 验收窗口窄 | 只能在 9:30-15:00 测试 |

---

## 后续改进建议

1. **增强监控**：在 catch 块添加 console.error/structlog，避免静默失败
2. **批量回测**：历史成交回填滑点（如有存档决策时价）
3. **告警阈值**：滑点 >1% 自动告警（可能是执行异常）
4. **P6 准备**：真金交易前，必须积累 ≥100 笔滑点样本，验证模拟盘与真实成交的系统性偏差

---

## 验收结论模板

验收通过条件：
- ✅ 至少 1 笔真实交易触发滑点记录
- ✅ Agent OS 中可检索到 `scope=trade:slippage` 记录
- ✅ `slippage_report` 输出数值正确
- ✅ 滑点计算符号正确（买贵/卖便宜为正）

---

## 变更日志

| 日期 | 内容 |
|---|---|
| 2026-08-28 | 创建。确认代码已修复并加载，编写验收步骤 |
