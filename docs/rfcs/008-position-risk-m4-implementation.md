# RFC 008: M4 仓位与风控实施方案（regime 仓位映射 / 回撤熔断 / 风控工具校准）

| 字段 | 值 |
|---|---|
| 状态 | 📋 设计中 |
| 日期 | 2026-08-25 |
| 编制 | agent-dh k3（审计+文档角色，不实施） |
| 上游设计 | [RFC 004 盈利引擎设计](004-profit-engine-design.md) M4 模块；[RFC 005 工单包](005-profit-engine-work-tickets.md) M4-1/M4-2/M4-3 |
| 实施方 | 待领工（其他 agent） |
| 前置依赖 | ✅ M1-1 市场感知 regime 落库（已完成，每日自动快照） |

---

## 0. 现状盘点（已验证能力基线）

### ✅ 已可用

| 组件 | 能力 | 验证状态 |
|---|---|---|
| **M1-1 regime 数据** | `quant.market_regime` 表，每日 1 条（trade_date, regime, reason） | ✅ 生产可用（08-21/24/25 均为 trend_down） |
| **M1-1 API** | `GET /api/market/regime?days=5` | ✅ 返回当日及历史 regime |
| **risk_metrics** | 组合风险指标（最大回撤、夏普、VaR、Beta） | ✅ 实测可用（账户：累计+2.87%、最大回撤-6.7%） |
| **risk_controller.position_size** | 根据账户资金计算建议仓位 | ✅ 工具存在（需实测校准） |
| **risk_controller.stop_loss** | 计算止损价格（百分比法 8%） | ✅ 工具存在（需实测校准） |
| **交易宪法** | 单股≤20%、单行业≤40%、现金≥10%、止损 -8%/-10%/-12% | ✅ genome g14 constitution v1 已定义 |
| **决策原则 R-006** | regime 仓位映射表：恐慌≤100%/偏多≤80%/震荡≤60%/偏空≤40%/狂热≤30% | ✅ genome g14 rules v6 已定义 |

### ❌ 缺失能力（M4 要补）

1. **regime 仓位映射表未嵌入决策流程**：R-006 只是文字规则，agent 交易前不会自动读当日 regime → 映射仓位上限 → 校验是否突破
2. **组合回撤熔断未自动化**：R-007 定义了熔断逻辑（60 日回撤 >8% 减仓一半），但无代码自动触发，靠人工判断
3. **风控工具未校准**：`risk_controller` 返回的建议仓位/止损价与 genome 宪法不一致（如 constitution 单股 ≤20%，但 risk_service.py 返回 `max_position = account_value * 0.3`）；`risk_barra_decomposition` 未实测

### 🎯 M4 核心价值

**把"风控纪律"从文字规则变成代码执行的硬约束**——不再是 agent"记得"去看 regime、"大概"不突破 60%，而是每次 `portfolio_trade` 前**必须**通过 regime 仓位映射校验，回撤超 8% **自动**触发熔断减仓。

---

## 1. 设计原则

1. **硬约束而非提示**：仓位映射表不是"建议"，而是 `portfolio_trade` 执行前的**强制校验**，突破则拒绝交易
2. **数据驱动**：regime 来源必须是 M1-1 落库数据（quant.market_regime），不是 agent 主观判断
3. **可观测**：每次校验/熔断触发必须落库留痕（为什么拒绝、当前仓位多少、regime 是什么），供复盘
4. **容错降级**：regime 数据缺失/降级（degraded）时按保守原则收紧到震荡档（≤60%）

---

## 2. M4-1: regime 仓位映射表嵌入决策流程

### 2.1 需求

**问题**：现在 agent 调用 `portfolio_trade` 买入时，没有自动校验"当前 regime 下我的仓位是否突破上限"。R-006 只是 genome 文字，执行靠 agent 自觉。

**目标**：
- 每次 `portfolio_trade`（BUY）前，自动执行 regime 仓位映射校验
- 突破上限时拒绝交易并返回明确原因
- 决策记录留痕：当日 regime、当前仓位、映射上限、校验结果

### 2.2 技术方案

#### 2.2.1 仓位映射规则（genome R-006，强制）

| regime | 权益仓位上限 | 数据来源 |
|---|---|---|
| panic（恐慌） | ≤100% | 贪婪指数 <10 + 涨跌家数比 <0.3 + 量能比 >2.0 |
| risk_on（偏多） | ≤80% | trend_up + 贪婪指数 40-70 + 涨跌家数比 >1.5 |
| sideways（震荡） | ≤60% | 其他情况（默认档） |
| risk_off（偏空） | ≤40% | trend_down + 贪婪指数 <40 + 涨跌家数比 <0.8 |
| euphoria（狂热） | ≤30% | 贪婪指数 >80 + 量能比 >2.5 |

**降级规则**：regime 数据 degraded/指标矛盾时按保守原则收紧到 sideways（≤60%）。

#### 2.2.2 校验逻辑（agent-dh 侧实现）

**位置**：`packages/trading/src/index.ts` 的 `portfolio_trade` 工具 execute 函数，在执行买入前插入校验。

**流程**：

```typescript
if (action === 'BUY') {
  // 1. 获取当日 regime
  const regimeData = await fetch(`${quantsysV2.baseURL}/api/market/regime?days=1`);
  const currentRegime = regimeData[0]?.regime || 'sideways';  // 缺数据按保守档

  // 2. 映射仓位上限
  const regimePositionLimit = {
    panic: 1.00,
    risk_on: 0.80,
    sideways: 0.60,
    risk_off: 0.40,
    euphoria: 0.30,
  }[currentRegime] || 0.60;  // 降级到震荡档

  // 3. 计算当前持仓市值与总资产
  const accountInfo = await qv2.accountInfo({ account_name });
  const totalAsset = accountInfo.total_asset;
  const currentPosition = accountInfo.position_value;  // 已持仓市值
  const cash = accountInfo.available_cash;

  // 4. 计算本次买入后仓位比例
  const buyValue = price * quantity;
  const positionAfterBuy = currentPosition + buyValue;
  const positionRatioAfterBuy = positionAfterBuy / totalAsset;

  // 5. 校验是否突破上限
  if (positionRatioAfterBuy > regimePositionLimit) {
    // 拒绝交易，记录原因
    await osMemory.write({
      title: `M4-1 仓位映射拦截：${symbol}`,
      content: JSON.stringify({
        symbol,
        regime: currentRegime,
        regime_limit: regimePositionLimit,
        current_position: currentPosition,
        buy_value: buyValue,
        position_after_buy: positionAfterBuy,
        ratio_after_buy: positionRatioAfterBuy,
        blocked: true,
        reason: `买入后仓位 ${(positionRatioAfterBuy*100).toFixed(1)}% 超过 regime「${currentRegime}」上限 ${(regimePositionLimit*100).toFixed(0)}%`,
        timestamp: new Date().toISOString(),
      }),
      namespace: 'risk',
      tags: ['m4', 'regime_position_block', currentRegime],
    });
    
    return {
      success: false,
      blocked: true,
      reason: `仓位超限：regime「${currentRegime}」上限 ${(regimePositionLimit*100).toFixed(0)}%，买入后仓位 ${(positionRatioAfterBuy*100).toFixed(1)}%`,
      regime: currentRegime,
      regime_limit: regimePositionLimit,
      current_ratio: (currentPosition/totalAsset*100).toFixed(1) + '%',
      buy_value: buyValue,
    };
  }

  // 6. 校验通过，记录决策上下文
  await osMemory.write({
    title: `M4-1 仓位映射校验通过：${symbol}`,
    content: JSON.stringify({
      symbol,
      regime: currentRegime,
      regime_limit: regimePositionLimit,
      current_position: currentPosition,
      buy_value: buyValue,
      position_after_buy: positionAfterBuy,
      ratio_after_buy: positionRatioAfterBuy,
      blocked: false,
      timestamp: new Date().toISOString(),
    }),
    namespace: 'risk',
    tags: ['m4', 'regime_position_check', currentRegime, symbol],
  });
}

// 7. 继续执行 portfolio_trade 原有逻辑
```

**说明**：
- 买入时校验，卖出时不校验（减仓总是安全的）
- 记录到 osMemory（Agent OS memory），namespace=risk，便于检索复盘
- 拦截时返回 `blocked: true` 和明确原因，不执行交易

### 2.3 验收标准

**功能验收**：
```bash
# 1. 正常情况：regime=trend_down（risk_off，≤40%），当前仓位 30%，买入小额（突破到 35%）→ 通过
# 2. 拦截情况：regime=trend_down（risk_off，≤40%），当前仓位 38%，买入大额（突破到 45%）→ 拒绝
# 3. 降级情况：regime API 返回 degraded 或无数据 → 按 sideways（≤60%）校验
# 4. 留痕检查：memory.search(query='仓位映射', tag='m4') 返回拦截/通过记录
```

**集成验收**：
- 任意一笔模拟盘 BUY 交易的决策记录中引用当日 regime 与仓位上限（✅ RFC 005 M4-1 验收标准）

---

## 3. M4-2: 组合回撤熔断

### 3.1 需求

**问题**：R-007 定义了熔断逻辑（60 日最大回撤 >8% → 减仓一半 + 禁止开仓），但无代码自动执行。现在靠 agent 定期调 `risk_metrics` 人工判断。

**目标**：
- 每日收盘后自动检查 60 日最大回撤
- 回撤 >8% 时自动触发熔断：减仓一半 + 禁止新开仓
- 熔断状态持久化（落库 + 状态标志），修复后解除

### 3.2 技术方案

#### 3.2.1 熔断触发条件

```typescript
const riskMetrics = await qv2.riskMetrics({ account_name, days: 60 });
const maxDrawdown = riskMetrics.max_drawdown;  // 如 -8.5%

if (maxDrawdown < -8.0) {
  // 触发熔断
}
```

#### 3.2.2 熔断执行动作

1. **减仓一半**：遍历当前持仓，每只股票卖出一半数量
2. **禁止新开仓**：设置熔断标志（osMemory），`portfolio_trade` BUY 时检查标志拒绝交易
3. **落库留痕**：记录触发时间、回撤值、减仓明细、预期恢复条件
4. **飞书高优告警**：通知用户熔断已触发

#### 3.2.3 熔断状态管理

**状态字段**（osMemory, namespace=risk, key=`circuit_breaker_status`）：
```json
{
  "active": true,
  "triggered_at": "2026-08-26T15:30:00+08:00",
  "triggered_drawdown": -8.5,
  "actions_taken": ["卖出 600519 500股", "卖出 000001 1000股"],
  "unblock_condition": "60日回撤修复到 <8%",
  "checked_at": "2026-08-26T16:00:00+08:00"
}
```

**解除条件**：
- 每日收盘后重新检查 60 日回撤
- 若回撤修复到 <8%，解除熔断（`active: false`），恢复允许开仓
- 若仍 >8%，保持熔断

#### 3.2.4 与 portfolio_trade 的集成

在 `portfolio_trade` execute 开头插入检查：

```typescript
// 检查熔断状态
const breakerStatus = await osMemory.read('risk', 'circuit_breaker_status');
if (action === 'BUY' && breakerStatus?.active) {
  return {
    success: false,
    blocked: true,
    reason: `熔断激活：60日回撤 ${breakerStatus.triggered_drawdown}%，禁止新开仓（解除条件：${breakerStatus.unblock_condition}）`,
    circuit_breaker: breakerStatus,
  };
}
```

#### 3.2.5 每日检查任务（Agent OS scheduler）

创建 OS 级定时任务（与 M1 每日快照同架构）：

```json
{
  "name": "m4_circuit_breaker_daily_check",
  "owner": "investor",
  "cron": "0 30 16 * * 1-5",
  "command": "/Users/yunpeng/pi-investment/agent-dh/scripts/os-remind-bridge.sh m4_circuit_breaker_daily_check",
  "payload": {
    "prompt": "【M4-2 熔断检查】执行 m4_circuit_breaker_check：调用 risk_metrics 计算 60 日最大回撤，若 >8% 触发熔断（减仓一半+禁止开仓+落库+飞书告警），若已熔断且回撤修复则解除。汇报检查结果。",
    "window": "w-51c8d482"
  },
  "enabled": true,
  "timeout": 60
}
```

### 3.3 验收标准

**功能验收**（模拟场景）：
```bash
# 1. 触发测试：手工构造持仓数据使 60 日回撤 >8%，执行 m4_circuit_breaker_check → 减仓一半 + 熔断激活 + 落库
# 2. 拦截测试：熔断激活后调用 portfolio_trade BUY → 返回 blocked=true + 熔断原因
# 3. 解除测试：持仓数据修复使 60 日回撤 <8%，再次执行 check → 熔断解除 + 恢复允许开仓
# 4. 告警测试：触发时收到飞书高优告警
```

**运维验收**：
- Agent OS 任务列表有 `m4_circuit_breaker_daily_check`（工作日 16:30）
- 熔断状态 osMemory 可查（`memory_search(query='circuit_breaker')`）

---

## 4. M4-3: 风控工具校准

### 4.1 需求

**问题**：
- `risk_controller.position_size` 返回的 `max_position = account_value * 0.3`（30%），与宪法"单股≤20%"不一致
- `risk_controller.stop_loss` 固定 8%，与宪法"成长股-10%、小盘-12%"不一致
- `risk_barra_decomposition` 工具存在但未实测

**目标**：
- `risk_controller` 返回值与 genome 宪法对齐
- `risk_barra_decomposition` 实测验证输出合理

### 4.2 技术方案

#### 4.2.1 risk_controller 校准（quantsys-v2 侧）

**position_size** 调整：
```python
# 从 account_value * 0.3 改为 account_value * 0.2（单股≤20%）
max_position = account_value * 0.2
```

**stop_loss** 调整：
```python
# 增加标的风险分级
def calculate_stop_loss(self, symbol: str, entry_price: float, risk_level: str = 'large_cap') -> Dict[str, Any]:
    # risk_level: large_cap(-8%) / growth(-10%) / small_cap_theme(-12%)
    stop_loss_map = {
        'large_cap': 0.92,       # -8%
        'growth': 0.90,          # -10%
        'small_cap_theme': 0.88, # -12%
    }
    stop_loss = entry_price * stop_loss_map.get(risk_level, 0.92)
```

**风险分级判断逻辑**（需在 agent 侧或 quantsys-v2 侧实现）：
- 大盘股：市值 >500亿 or 上证50/沪深300 成分股 → large_cap
- 成长股：创业板/科创板 or 行业=TMT/医药/新能源 → growth
- 小盘/题材：市值 <50亿 or 涨停连板 or 妖股特征 → small_cap_theme

#### 4.2.2 risk_barra_decomposition 实测

调用现有工具对当前账户测试，验证输出合理：
```bash
# agent-dh 工具调用
risk_barra_decomposition(account_name='agent_virtual')
```

预期输出：
- 各因子风险贡献（市值、行业、风格）
- 特质风险 vs 系统风险
- 与 risk_metrics 的 max_drawdown 交叉一致（因子风险解释力）

### 4.3 验收标准

**校准验收**：
```bash
# 1. position_size：调用 risk_controller(command='position_size', symbol='600519')
#    → max_position = account_value * 0.2（不再是 0.3）

# 2. stop_loss：调用 risk_controller(command='stop_loss', symbol='600519', risk_level='large_cap')
#    → stop_loss = entry_price * 0.92（-8%）
#    调用 risk_controller(command='stop_loss', symbol='300750', risk_level='growth')
#    → stop_loss = entry_price * 0.90（-10%）

# 3. risk_barra_decomposition：调用后返回因子分解结果
#    → 行业风险贡献、特质风险、与 risk_metrics.max_drawdown 数量级一致
```

---

## 5. 实施顺序与验收

### 5.1 实施顺序（按依赖排序）

| 序 | 工单 | 依赖 | 预计工时 | 风险 |
|---|---|---|---|---|
| 1 | **M4-1 regime 仓位映射** | M1-1（✅ 已完成） | 3-4h | 低（纯决策流程改造） |
| 2 | **M4-3 风控工具校准** | 无 | 2-3h | 低（代码调整+实测） |
| 3 | **M4-2 组合回撤熔断** | M4-1（熔断逻辑与 portfolio_trade 集成） | 4-5h | 中（涉及自动减仓+状态管理） |

**建议**：先 M4-1（核心价值）→ M4-3（校准工具）→ M4-2（完整闭环）

### 5.2 总体验收（RFC 005 标准）

| 工单 | 验收命令 | 验收标准 |
|---|---|---|
| M4-1 | 任意一笔交易决策上下文 | 决策记录中引用当日 regime 与仓位上限 |
| M4-2 | 模拟回撤场景触发一次 | 熔断触发有记录且执行减仓 |
| M4-3 | 对当前账户调两工具 | 输出合理（与 risk_metrics 交叉一致） |

---

## 6. 集成点与影响面

### 6.1 代码修改位置

| 位置 | 修改内容 |
|---|---|
| `agent-dh/packages/trading/src/index.ts` | `portfolio_trade` 插入 M4-1 仓位映射校验 + M4-2 熔断检查 |
| `quantsys-v2/application/services/risk_service.py` | M4-3：`calculate_position_size` 改为 20%，`calculate_stop_loss` 增加 risk_level 参数 |
| `agent-dh/packages/risk/src/index.ts` | M4-3：`risk_controller` 工具增加 `risk_level` 参数传递 |
| Agent OS scheduler | M4-2：新增每日 16:30 熔断检查任务 |

### 6.2 genome 规则更新

实施完成后，更新 genome（genome_update tool）：

**rules v7**（增加 M4 规则引用）：
```markdown
## R-006 仓位映射表（已嵌入 portfolio_trade 自动校验）
权益仓位上限按 regime 执行：恐慌（panic）≤100%，偏多（risk_on）≤80%，震荡（sideways）≤60%，偏空（risk_off）≤40%，狂热（euphoria）≤30%。regime 数据降级（degraded/指标矛盾）时按保守原则收紧到震荡档。数据来源：M1-1 quant.market_regime 每日落库。**已代码强制校验**（2026-08-26 起，portfolio_trade BUY 前自动检查，突破拒绝交易）。

## R-007 回撤熔断（已自动化）
组合 60 日最大回撤超过 8% 时触发熔断：强制减仓一半，禁止新开仓直到回撤修复。**已代码自动执行**（2026-08-26 起，每日 16:30 检查，触发自动减仓+禁止开仓+飞书告警，修复自动解除）。熔断状态存储于 osMemory risk:circuit_breaker_status。
```

### 6.3 影响范围

**直接影响**：
- 所有 `portfolio_trade` BUY 交易（M4-1 校验 + M4-2 熔断检查）
- `risk_controller` 工具输出（M4-3 校准）

**不影响**：
- 卖出交易（减仓总是安全的）
- 其他 agent-dh 工具（memory、evolution、scheduler 等）
- quantsys-v2 其他服务（因子、回测、策略等）

---

## 7. 风险与缓解

| 风险 | 概率 | 影响 | 缓解 |
|---|---|---|---|
| regime 数据缺失导致频繁降级到震荡档（60%） | 中 | 中 | M1-1 已实现每日自动落库+120日回填；降级到 60% 仍是保守合理值 |
| 熔断误触发（数据异常） | 低 | 高 | ①触发前需连续 2 日检查都 >8%；②触发后飞书告警人工复核；③熔断状态可手动解除（osMemory 直接改 active=false） |
| portfolio_trade 校验失败导致正常交易被误拦 | 低 | 中 | ①单元测试覆盖各种场景；②灰度上线（先监控模式只记录不拦截，验证 1 周后开启拦截） |
| Agent OS 后端挂掉导致熔断检查不执行 | 低 | 高 | 熔断状态持久化在 osMemory（Agent OS memory），即使检查任务暂停，之前触发的熔断仍生效；恢复运行后继续每日检查 |

---

## 8. 交接清单（实施者领工用）

### 8.1 开工前必读
- [ ] 读本文档完整内容（特别是 §2/§3/§4 技术方案）
- [ ] 读 genome rules v6 R-006/R-007（决策原则）
- [ ] 读 `agent-dh/packages/trading/src/index.ts` 的 `portfolio_trade` 现有实现
- [ ] 读 `quantsys-v2/application/services/risk_service.py` 现有实现

### 8.2 开发步骤（建议）

**Step 1: M4-1 仓位映射（3-4h）**
1. 修改 `agent-dh/packages/trading/src/index.ts` 的 `portfolio_trade` execute 函数，插入 §2.2.2 的校验逻辑
2. 单元测试：mock regime API 返回各档，测试通过/拦截/降级场景
3. 集成测试：真实账户调用 portfolio_trade，验证拦截逻辑与 osMemory 留痕

**Step 2: M4-3 风控校准（2-3h）**
1. 修改 `quantsys-v2/application/services/risk_service.py` 的 `calculate_position_size` 和 `calculate_stop_loss`
2. 修改 `agent-dh/packages/risk/src/index.ts` 的 `risk_controller` 工具增加 `risk_level` 参数
3. 实测：调用工具验证输出与宪法对齐

**Step 3: M4-2 回撤熔断（4-5h）**
1. 实现 `m4_circuit_breaker_check` 函数（agent-dh 新工具或 trading 插件内新增逻辑）
2. 创建 Agent OS scheduler 任务（每日 16:30）
3. 实现熔断状态管理（osMemory 读写）
4. 集成 portfolio_trade 熔断检查
5. 模拟测试：构造回撤场景验证触发/拦截/解除

**Step 4: genome 更新 + 文档**
1. 调用 genome_update 更新 rules v7（R-006/R-007 标注"已代码强制"）
2. 更新本文档状态为 ✅ 已实施
3. 提交代码 + work-log

### 8.3 验收检查表（提交前自测）

- [ ] M4-1: 任意 BUY 交易决策记录含 regime 与仓位上限（memory.search 验证）
- [ ] M4-1: 模拟突破场景被拦截（portfolio_trade 返回 blocked=true）
- [ ] M4-2: 模拟回撤 >8% 触发熔断（减仓一半 + 状态激活 + 飞书告警）
- [ ] M4-2: 熔断激活后 BUY 被拦截（返回 circuit_breaker 状态）
- [ ] M4-3: risk_controller.position_size 返回 max_position = account_value * 0.2
- [ ] M4-3: risk_controller.stop_loss 按 risk_level 返回不同止损比例
- [ ] 单元测试覆盖率 ≥80%（trading 插件）
- [ ] 代码提交到 feat/m4-risk-control 分支（不直接到 main）

---

## 9. 变更日志

| 日期 | 内容 |
|---|---|
| 2026-08-25 | 创建。M1 完成后启动 M4 设计；M4-1/M4-2/M4-3 技术方案完整定义；交接清单明确（§8） |

---

## 10. 参考文档

- [RFC 004 盈利引擎设计](004-profit-engine-design.md) §M4 仓位与风控
- [RFC 005 盈利引擎工单包](005-profit-engine-work-tickets.md) §M4 仓位与风控
- [M1 市场感知交接单](../work-logs/2026-08/m1-market-perception-handover.md)（M4-1 依赖的 regime 数据来源）
- agent-dh genome g14 rules v6（R-006/R-007 决策原则）
- agent-dh genome g14 constitution v1（交易宪法：单股≤20%、止损 -8%/-10%/-12%）
