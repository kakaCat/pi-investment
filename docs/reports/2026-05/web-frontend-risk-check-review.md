# Web-Frontend 风控检查页面 - 前后端集成审查报告

**审查日期**: 2026-05-24  
**审查范围**: web-frontend 风控检查页面的前后端集成和业务逻辑

---

## 一、前端实现审查

### 1.1 核心文件
- **页面组件**: [web-frontend/src/views/RiskCheck/index.vue](web-frontend/src/views/RiskCheck/index.vue)
- **API 服务**: [web-frontend/src/services/api/risk.ts](web-frontend/src/services/api/risk.ts)

### 1.2 前端调用的接口

| 接口路径 | 方法 | 用途 | 调用位置 |
|---------|------|------|---------|
| `/api/risk/check` | POST | 执行风险检查 | `handleRunCheck()` (line 472) |
| `/api/risk/stop-loss/rules` | GET | 获取止损规则列表 | `loadStopLossRules()` (line 548) |
| `/api/risk/stop-loss/rules` | POST | 创建止损规则 | `handleSaveStopLoss()` (line 604) |
| `/api/risk/stop-loss/rules/batch` | POST | 批量创建止损规则 | `handleSaveBatchStopLoss()` (line 650) |
| `/api/risk/stop-loss/rules/:id` | PUT | 更新止损规则 | `handleSaveStopLoss()` (line 601) |
| `/api/risk/stop-loss/rules/:id` | DELETE | 删除止损规则 | `handleDeleteStopLoss()` (line 675) |

### 1.3 前端数据流

```
用户点击"执行检查" 
  → handleRunCheck() 
  → riskApi.checkRisk({ accountValue })
  → 后端 POST /api/risk/check
  → 解析响应数据
  → 更新 riskOverview, riskIndicators, positionRisks, warnings
```

---

## 二、后端实现审查

### 2.1 核心文件
- **API 路由**: [quantsys-v2/api/server.py](quantsys-v2/api/server.py) (line 1725-1895)
- **风控服务**: [quantsys-v2/services/risk_service.py](quantsys-v2/services/risk_service.py)
- **数据存储**: `~/.pi-invest/stop_loss_rules.json` (JSON 文件)

### 2.2 后端接口实现

#### 2.2.1 风险检查接口 (`/api/risk/check`)

**位置**: server.py:1725-1779

**业务逻辑**:
```python
1. 接收参数: { accountValue, symbols? }
2. 获取持仓列表: ds.portfolio.get_all_holdings()
3. 对每个持仓执行检查:
   a. 集中度检查: 仓位占比 > 30% → 高风险
   b. VaR 检查: VaR 95% < -5% → 中风险
4. 返回: { total_holdings, checks: [{symbol, position_value, checks}], risk_level }
```

**返回数据结构**:
```json
{
  "total_holdings": 5,
  "checks": [
    {
      "symbol": "600519",
      "position_value": 500000,
      "checks": [
        {
          "type": "concentration",
          "level": "high",
          "message": "600519 仓位集中度 39.7% > 30%",
          "suggestion": "建议分散持仓"
        }
      ]
    }
  ],
  "risk_level": "high"
}
```

#### 2.2.2 止损规则接口

**数据存储**: JSON 文件 (`~/.pi-invest/stop_loss_rules.json`)

**规则结构**:
```json
{
  "rules": [
    {
      "id": "1716537600000",
      "symbol": "600519",
      "name": "600519止损",
      "type": "fixed_percent",
      "stopLossPercent": 5,
      "trailingPercent": null,
      "atrMultiplier": null,
      "status": "active",
      "createdAt": "2026-05-24T10:00:00",
      "updatedAt": "2026-05-24T10:00:00"
    }
  ]
}
```

---

## 三、前后端集成问题

### ⚠️ 问题 1: 字段命名不一致

**问题描述**: 前端期望 camelCase，后端返回 snake_case

**影响范围**:
- 风险检查接口返回的字段名不匹配
- 前端需要手动映射 `data.riskLevel ?? data.risk_level`

**当前状态**: ✅ **已处理**
- 前端在 line 477-482 做了兼容处理
- 使用 `??` 运算符同时支持两种命名

**代码示例** (RiskCheck/index.vue:477-482):
```typescript
const rawLevel: string = data.riskLevel ?? data.risk_level ?? 'low'
const totalHoldings: number = data.total_holdings ?? data.totalHoldings ?? 0
```

### ⚠️ 问题 2: 止损规则字段映射错误

**问题描述**: 前端和后端的止损类型字段名不一致

| 前端字段 | 后端字段 | 说明 |
|---------|---------|------|
| `type` | `type` | ✅ 一致 |
| `triggerPrice` | ❌ 无对应 | 前端独有 |
| `triggerPercent` | `stopLossPercent` | ❌ **不一致** |
| `trailingPercent` | `trailingPercent` | ✅ 一致 |

**影响**: 
- 前端发送 `triggerPercent: 5`
- 后端期望 `stopLossPercent`
- **止损规则创建会失败或数据丢失**

**位置**:
- 前端: RiskCheck/index.vue:594, 642
- 后端: server.py:1814

### ⚠️ 问题 3: 止损类型值不匹配

**问题描述**: 前端和后端使用不同的类型枚举值

| 前端 `type` | 后端 `type` | 说明 |
|------------|------------|------|
| `price` | ❌ 无对应 | 前端独有 |
| `percent` | `fixed_percent` | ❌ **不一致** |
| `trailing` | ❌ 无对应 | 前端独有 |

**影响**: 
- 前端发送 `type: "percent"`
- 后端默认使用 `type: "fixed_percent"`
- **类型不匹配导致规则无法正确识别**

**位置**:
- 前端: RiskCheck/index.vue:224-227, 455
- 后端: server.py:1813

### ⚠️ 问题 4: 风险指标计算不完整

**问题描述**: 前端显示的部分风险指标后端未提供数据

**缺失数据**:
- `var` (VaR 95%) - 后端有数据但未返回
- `volatility` (波动率) - 后端有数据但未返回
- `maxDrawdown` (最大回撤) - 后端有数据但未返回
- `行业集中度` - 后端未计算
- `Beta暴露` - 后端未计算

**当前状态**: 前端显示为 0 或空值

**位置**:
- 前端: RiskCheck/index.vue:516-528
- 后端: server.py:1756-1764 (有 risk_metrics 但未使用)

### ⚠️ 问题 5: 持仓当前价格缺失

**问题描述**: 设置止损时需要当前价格，但后端未返回

**影响**:
- 前端 `stopLossForm.currentPrice` 默认为 0
- 无法正确计算止损价格和百分比

**位置**:
- 前端: RiskCheck/index.vue:562
- 后端: server.py:1767 (未返回 current_price)

---

## 四、业务逻辑审查

### 4.1 风险检查逻辑

#### ✅ 正确的部分:
1. **集中度检查**: 单只股票仓位 > 30% 触发预警 ✅
2. **VaR 检查**: VaR 95% < -5% 触发预警 ✅
3. **风险等级判断**: checks > 3 → high, 否则 low ✅

#### ⚠️ 需要改进的部分:

1. **风险等级过于简单**
   - 当前: `checks > 3 ? 'high' : 'low'`
   - 建议: 考虑检查项的 level (high/medium/low) 权重

2. **缺少行业集中度检查**
   - 前端显示了"行业集中度"指标
   - 后端未实现该检查

3. **VaR 数据未充分利用**
   - 后端获取了 `risk_metrics` 但只检查了 VaR
   - 未返回波动率、最大回撤等其他指标

### 4.2 止损规则逻辑

#### ✅ 正确的部分:
1. **CRUD 操作完整**: 创建、读取、更新、删除都已实现 ✅
2. **批量创建支持**: 支持批量设置止损规则 ✅
3. **文件存储**: 使用 JSON 文件持久化 ✅

#### ⚠️ 需要改进的部分:

1. **止损规则未生效**
   - 规则只是存储，没有实际的监控和触发机制
   - 需要后台任务定期检查价格并触发止损

2. **缺少规则验证**
   - 未验证 `triggerPercent` 是否在合理范围 (0-100)
   - 未验证 `symbol` 是否存在于持仓中

3. **ID 生成可能冲突**
   - 使用时间戳作为 ID: `str(int(datetime.now().timestamp() * 1000))`
   - 批量创建时可能产生相同 ID

---

## 五、数据依赖审查

### 5.1 后端数据源

风险检查依赖以下数据服务:

| 数据 | 来源 | 方法 |
|-----|------|------|
| 持仓列表 | DataService.portfolio | `get_all_holdings()` |
| 风险指标 | DataService.risk | `get_latest_risk_metrics(symbol)` |
| 账户余额 | DataService.risk | `get_latest_balance()` |

### 5.2 数据完整性

**检查项**:
- ✅ 持仓数据: 包含 symbol, quantity, avg_cost, total_invested
- ⚠️ 风险指标: 有数据但未完全返回给前端
- ⚠️ 当前价格: 未从 K线数据获取

---

## 六、修复建议

### 优先级 P0 (必须修复)

#### 1. 修复止损规则字段映射

**文件**: quantsys-v2/api/server.py:1799-1825

**修改**:
```python
# 修改前
'stopLossPercent': body.get('stopLossPercent'),

# 修改后
'stopLossPercent': body.get('stopLossPercent') or body.get('triggerPercent'),
'triggerPercent': body.get('triggerPercent') or body.get('stopLossPercent'),
```

#### 2. 统一止损类型枚举

**选项 A**: 后端适配前端 (推荐)
```python
# server.py:1813
'type': body.get('type', 'percent'),  # 改为 'percent'

# 映射逻辑
type_mapping = {
    'price': 'fixed_price',
    'percent': 'fixed_percent', 
    'trailing': 'trailing_stop'
}
rule_type = type_mapping.get(body.get('type'), 'fixed_percent')
```

**选项 B**: 前端适配后端
```typescript
// RiskCheck/index.vue
const typeMapping = {
  price: 'fixed_price',
  percent: 'fixed_percent',
  trailing: 'trailing_stop'
}
data.type = typeMapping[stopLossForm.type]
```

### 优先级 P1 (重要)

#### 3. 返回完整的风险指标

**文件**: quantsys-v2/api/server.py:1756-1771

**修改**:
```python
# 获取当前价格
latest_kline = ds.kline.get_latest_daily_kline(symbol)
current_price = latest_kline.get('close') if latest_kline else 0

# 返回完整数据
if item_checks:
    checks.append({
        'symbol': symbol,
        'position_value': position_value,
        'current_price': current_price,  # 新增
        'var_95': risk_metrics.get('var_95', 0) if risk_metrics else 0,  # 新增
        'volatility': risk_metrics.get('volatility', 0) if risk_metrics else 0,  # 新增
        'max_drawdown': risk_metrics.get('max_drawdown', 0) if risk_metrics else 0,  # 新增
        'checks': item_checks
    })
```

#### 4. 添加行业集中度检查

**文件**: quantsys-v2/api/server.py:1744-1754

**新增**:
```python
# 行业集中度检查
holdings_stats = ds.portfolio.get_holdings_stats()
if holdings_stats:
    sector_dist = holdings_stats.get('sector_distribution', [])
    for sector in sector_dist:
        sector_ratio = sector.get('invested', 0) / account_value if account_value > 0 else 0
        if sector_ratio > 0.5:  # 50% 阈值
            item_checks.append({
                'type': 'sector_concentration',
                'level': 'high',
                'message': f'行业 {sector.get("sector")} 集中度 {sector_ratio:.1%} > 50%',
                'suggestion': '建议分散行业配置'
            })
```

### 优先级 P2 (优化)

#### 5. 改进风险等级计算

**文件**: quantsys-v2/api/server.py:1776

**修改**:
```python
# 修改前
'risk_level': 'high' if len(checks) > 3 else 'low'

# 修改后
high_count = sum(1 for c in checks for check in c['checks'] if check['level'] == 'high')
medium_count = sum(1 for c in checks for check in c['checks'] if check['level'] == 'medium')

if high_count >= 2:
    risk_level = 'high'
elif high_count >= 1 or medium_count >= 3:
    risk_level = 'medium'
else:
    risk_level = 'low'
```

#### 6. 添加止损规则验证

**文件**: quantsys-v2/api/server.py:1799-1825

**新增**:
```python
# 验证参数
if body.get('type') == 'percent':
    trigger_percent = body.get('triggerPercent') or body.get('stopLossPercent')
    if not trigger_percent or trigger_percent <= 0 or trigger_percent > 100:
        return jsonify({'success': False, 'error': '止损比例必须在 0-100 之间'}), 400

# 验证持仓存在
holding = ds.portfolio.get_holding(body['symbol'])
if not holding:
    return jsonify({'success': False, 'error': f'持仓 {body["symbol"]} 不存在'}), 400
```

---

## 七、测试建议

### 7.1 集成测试

1. **风险检查流程**
   ```bash
   # 1. 确保有持仓数据
   # 2. 调用风险检查接口
   curl -X POST http://127.0.0.1:5001/api/risk/check \
     -H "Content-Type: application/json" \
     -d '{"accountValue": 1000000}'
   
   # 3. 验证返回数据结构
   # 4. 检查前端是否正确显示
   ```

2. **止损规则 CRUD**
   ```bash
   # 创建规则
   curl -X POST http://127.0.0.1:5001/api/risk/stop-loss/rules \
     -H "Content-Type: application/json" \
     -d '{"symbol": "600519", "type": "percent", "triggerPercent": 5}'
   
   # 获取规则
   curl http://127.0.0.1:5001/api/risk/stop-loss/rules
   
   # 更新规则
   curl -X PUT http://127.0.0.1:5001/api/risk/stop-loss/rules/{id} \
     -H "Content-Type: application/json" \
     -d '{"triggerPercent": 8}'
   
   # 删除规则
   curl -X DELETE http://127.0.0.1:5001/api/risk/stop-loss/rules/{id}
   ```

### 7.2 边界测试

1. **空持仓**: accountValue = 0
2. **无风险指标**: risk_metrics 为空
3. **极端集中度**: 单只股票 100%
4. **批量创建**: 10+ 规则同时创建

---

## 八、总结

### 8.1 当前状态

| 功能模块 | 前端实现 | 后端实现 | 集成状态 | 评分 |
|---------|---------|---------|---------|------|
| 风险检查 | ✅ 完整 | ⚠️ 部分 | ⚠️ 字段不匹配 | 6/10 |
| 止损规则 CRUD | ✅ 完整 | ✅ 完整 | ❌ 字段错误 | 4/10 |
| 风险指标展示 | ✅ 完整 | ❌ 数据缺失 | ❌ 无数据 | 3/10 |
| 持仓风险明细 | ✅ 完整 | ⚠️ 部分 | ⚠️ 价格缺失 | 5/10 |

**总体评分**: 4.5/10

### 8.2 关键问题

1. ❌ **止损规则字段映射错误** - 导致功能无法正常使用
2. ❌ **止损类型枚举不匹配** - 导致规则类型识别失败
3. ⚠️ **风险指标数据不完整** - 前端显示为空
4. ⚠️ **持仓当前价格缺失** - 无法正确计算止损

### 8.3 修复优先级

1. **P0 - 立即修复**: 止损规则字段映射 (阻塞功能)
2. **P1 - 本周修复**: 风险指标数据补全 (影响体验)
3. **P2 - 下周优化**: 风险等级算法、规则验证 (提升质量)

---

**审查人**: Claude (Kiro)  
**审查完成时间**: 2026-05-24
