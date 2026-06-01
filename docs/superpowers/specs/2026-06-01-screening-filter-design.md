# 量化条件筛选器设计文档

**日期**: 2026-06-01  
**状态**: 设计完成，待实施  
**目标**: 替换硬编码的布尔标签筛选，支持"ROE≥15%、PE≤30"等数值条件组合选股

## 问题背景

当前股票池筛选使用硬编码的布尔标签：
- 技术面：`rsi_oversold`, `macd_golden_cross`, `bollinger_breakout`, `volume_surge`
- 基本面：`pe_low`, `roe_high`, `gross_margin_high`, `debt_ratio_low`

**缺陷：**
1. 阈值固定（PE<30、ROE>15%），无法自定义
2. 无法组合复杂条件（如"ROE≥15% AND 负债率≤50%"）
3. 不符合真实选股器使用习惯（同花顺、雪球等都是字段+运算符+数值）

## 设计方案

### 方案选择：条件表达式数组

**数据结构：**
```typescript
interface FilterCondition {
  field: string        // 字段名，如 "roe", "pe", "debt_ratio"
  operator: string     // 运算符: ">=", "<=", ">", "<", "==", "!="
  value: number        // 阈值
}

interface ScreeningFilter {
  conditions: FilterCondition[]
  logic: "AND" | "OR"  // 条件间逻辑关系，默认 AND
}
```

**优势：**
- 简单直观，前端易于构建UI（字段下拉 + 运算符 + 数值输入）
- 后端易于解析和执行（遍历条件列表，逐个判断）
- 安全（字段名和运算符白名单校验，无SQL注入风险）
- 可扩展（未来可加 OR 逻辑、条件分组）

## 支持的字段白名单

### 基本面字段（来自 stocks 表）

| 字段 | 中文名 | 单位 | 数据来源 | 示例条件 |
|------|--------|------|----------|----------|
| `roe` | ROE净资产收益率 | % | stocks.roe | roe >= 15 |
| `pe` | 市盈率 | 倍 | stocks.pe | pe <= 30 |
| `pb` | 市净率 | 倍 | stocks.pb | pb <= 2 |
| `gross_margin` | 毛利率 | % | stocks.gross_margin | gross_margin >= 30 |
| `debt_ratio` | 资产负债率 | % | stocks.debt_ratio | debt_ratio <= 50 |
| `net_profit_growth` | 净利润增长率 | % | stocks.net_profit_growth | net_profit_growth >= 20 |
| `market_cap` | 总市值 | 亿元 | stocks.market_cap | market_cap >= 50 |
| `circulating_mv` | 流通市值 | 亿元 | stocks.circulating_mv | circulating_mv >= 30 |
| `avg_turnover_rate` | 平均换手率 | % | stocks.avg_turnover_rate | avg_turnover_rate >= 2 |

### 技术指标字段（从 klines 计算）

| 字段 | 中文名 | 单位 | 计算来源 | 示例条件 |
|------|--------|------|----------|----------|
| `rsi` | RSI指标 | 0-100 | factor_adapter.calculate('rsi14') | rsi <= 30 |
| `macd` | MACD值 | — | factor_adapter.calculate('macd') | macd > 0 |
| `volume_ratio_5d` | 5日量比 | 倍 | 近5日均量/前5日均量 | volume_ratio_5d >= 1.5 |

### 运算符白名单

`>=`, `<=`, `>`, `<`, `==`, `!=`

## 示例筛选条件

### 稳健价值型
```json
{
  "conditions": [
    {"field": "roe", "operator": ">=", "value": 15},
    {"field": "debt_ratio", "operator": "<=", "value": 50},
    {"field": "pe", "operator": "<=", "value": 30},
    {"field": "gross_margin", "operator": ">=", "value": 30}
  ],
  "logic": "AND"
}
```

### 成长型
```json
{
  "conditions": [
    {"field": "net_profit_growth", "operator": ">=", "value": 20},
    {"field": "roe", "operator": ">=", "value": 15},
    {"field": "market_cap", "operator": ">=", "value": 50}
  ],
  "logic": "AND"
}
```

### 烟蒂型（深度价值）
```json
{
  "conditions": [
    {"field": "pb", "operator": "<=", "value": 1},
    {"field": "pe", "operator": "<=", "value": 10},
    {"field": "debt_ratio", "operator": "<=", "value": 50}
  ],
  "logic": "AND"
}
```

## 后端实现

### 1. OpportunityScoringService 改造

**新增方法：`_evaluate_conditions`**

```python
def _evaluate_conditions(
    self,
    conditions: List[Dict],
    logic: str,
    stock_data: Dict,
    factors: Dict
) -> bool:
    """
    评估筛选条件
    
    Args:
        conditions: 条件列表 [{"field": "roe", "operator": ">=", "value": 15}, ...]
        logic: 逻辑关系 "AND" 或 "OR"
        stock_data: 基本面数据（来自 stocks 表）
        factors: 技术指标数据（从 klines 计算）
    
    Returns:
        是否满足条件
    """
    if not conditions:
        return True
    
    results = []
    for cond in conditions:
        field = cond['field']
        operator = cond['operator']
        threshold = cond['value']
        
        # 从 stock_data 或 factors 中获取字段值
        value = stock_data.get(field) or factors.get(field)
        
        if value is None:
            results.append(False)
            continue
        
        # 执行比较
        if operator == '>=':
            results.append(value >= threshold)
        elif operator == '<=':
            results.append(value <= threshold)
        elif operator == '>':
            results.append(value > threshold)
        elif operator == '<':
            results.append(value < threshold)
        elif operator == '==':
            results.append(value == threshold)
        elif operator == '!=':
            results.append(value != threshold)
        else:
            results.append(False)
    
    # 根据逻辑关系合并结果
    if logic == 'OR':
        return any(results)
    else:  # AND
        return all(results)
```

**修改 `_score_single_stock` 方法：**

在计算评分前，先用 `_evaluate_conditions` 过滤：

```python
def _score_single_stock(self, symbol, klines, fundamental, filters):
    # ... 计算 factors ...
    
    # 新增：评估筛选条件
    conditions = filters.get('conditions', [])
    logic = filters.get('logic', 'AND')
    
    if conditions:
        if not self._evaluate_conditions(conditions, logic, fundamental or {}, factors):
            return None  # 不满足条件，跳过
    
    # 保留旧逻辑（向后兼容）
    tech_score = self._calculate_technical_score(factors, filters.get('technical', []))
    fund_score = self._calculate_fundamental_score(fundamental, filters.get('fundamental', []))
    # ...
```

### 2. API 层校验

在 `api/routes/pools.py` 添加白名单校验：

```python
ALLOWED_FIELDS = {
    'roe', 'pe', 'pb', 'gross_margin', 'debt_ratio', 
    'net_profit_growth', 'market_cap', 'circulating_mv',
    'avg_turnover_rate', 'rsi', 'macd', 'volume_ratio_5d'
}
ALLOWED_OPERATORS = {'>=', '<=', '>', '<', '==', '!='}

def validate_filter(filter_dict):
    """校验筛选条件合法性"""
    conditions = filter_dict.get('conditions', [])
    for cond in conditions:
        if cond.get('field') not in ALLOWED_FIELDS:
            raise ValueError(f"Invalid field: {cond.get('field')}")
        if cond.get('operator') not in ALLOWED_OPERATORS:
            raise ValueError(f"Invalid operator: {cond.get('operator')}")
        if not isinstance(cond.get('value'), (int, float)):
            raise ValueError(f"Invalid value type: {type(cond.get('value'))}")
    return True
```

在 `scan_and_create` 和 `create` 路由中调用：

```python
@pools_bp.route('/api/pools/scan-and-create', methods=['POST'])
def scan_and_create():
    data = request.get_json()
    filter_params = data.get('filter') or {}
    
    # 校验筛选条件
    if filter_params.get('conditions'):
        validate_filter(filter_params)
    
    # ... 原有逻辑 ...
```

### 3. 向后兼容

同时支持新旧两种格式：

**旧格式（保留）：**
```json
{
  "filter": {
    "technical": ["rsi_oversold"],
    "fundamental": ["pe_low", "roe_high"]
  }
}
```

**新格式：**
```json
{
  "filter": {
    "conditions": [
      {"field": "roe", "operator": ">=", "value": 15},
      {"field": "pe", "operator": "<=", "value": 30}
    ],
    "logic": "AND"
  }
}
```

后端优先使用 `conditions`，如果不存在则回退到 `technical`/`fundamental`。

## 前端实现

### 1. 筛选建池弹窗改造

**旧UI（删除）：**
- 技术面条件：多选框（RSI超卖、MACD金叉...）
- 基本面条件：多选框（低PE、高ROE...）

**新UI：**

```
┌─ 筛选建池 ────────────────────────────┐
│ 名称: [输入框]                         │
│ 池子类型: ○静态池 ●动态池              │
│                                        │
│ 筛选条件:                              │
│ ┌────────────────────────────────────┐│
│ │ [ROE净资产收益率 ▼] [>= ▼] [15   ]││
│ │ [资产负债率     ▼] [<= ▼] [50   ]││
│ │ [市盈率PE       ▼] [<= ▼] [30   ]││
│ │ [+ 添加条件] [删除]                ││
│ └────────────────────────────────────┘│
│                                        │
│ 条件逻辑: ●AND ○OR                    │
│ 取前N只: [20]                          │
│ 刷新周期: ○每日 ●每周                 │
│                                        │
│ [取消] [筛选建池]                      │
└────────────────────────────────────────┘
```

### 2. Vue 组件实现

**数据结构：**
```typescript
const scanForm = ref({
  name: '',
  poolType: 'dynamic' as 'static' | 'dynamic',
  conditions: [
    { field: 'roe', operator: '>=', value: 15 },
    { field: 'debt_ratio', operator: '<=', value: 50 }
  ] as FilterCondition[],
  logic: 'AND' as 'AND' | 'OR',
  topN: 20,
  refreshInterval: 'weekly' as 'daily' | 'weekly',
  description: ''
})
```

**字段选项：**
```typescript
const fieldOptions = [
  { value: 'roe', label: 'ROE净资产收益率 (%)' },
  { value: 'pe', label: '市盈率PE (倍)' },
  { value: 'pb', label: '市净率PB (倍)' },
  { value: 'gross_margin', label: '毛利率 (%)' },
  { value: 'debt_ratio', label: '资产负债率 (%)' },
  { value: 'net_profit_growth', label: '净利润增长率 (%)' },
  { value: 'market_cap', label: '总市值 (亿元)' },
  { value: 'circulating_mv', label: '流通市值 (亿元)' },
  { value: 'rsi', label: 'RSI指标 (0-100)' },
  { value: 'volume_ratio_5d', label: '5日量比 (倍)' }
]

const operatorOptions = [
  { value: '>=', label: '≥ 大于等于' },
  { value: '<=', label: '≤ 小于等于' },
  { value: '>', label: '> 大于' },
  { value: '<', label: '< 小于' },
  { value: '==', label: '= 等于' },
  { value: '!=', label: '≠ 不等于' }
]
```

**添加/删除条件：**
```typescript
const addCondition = () => {
  scanForm.value.conditions.push({ field: 'roe', operator: '>=', value: 0 })
}

const removeCondition = (index: number) => {
  scanForm.value.conditions.splice(index, 1)
}
```

**提交时转换格式：**
```typescript
const handleScanCreate = async () => {
  await poolApi.scanAndCreate({
    name: scanForm.value.name,
    poolType: scanForm.value.poolType,
    filter: {
      conditions: scanForm.value.conditions,
      logic: scanForm.value.logic,
      top_n: scanForm.value.topN
    },
    refreshInterval: scanForm.value.poolType === 'dynamic' ? scanForm.value.refreshInterval : undefined,
    description: scanForm.value.description
  })
}
```

### 3. 池子详情页展示

筛选条件标签改为：

```
筛选条件: [ROE ≥ 15%] [负债率 ≤ 50%] [PE ≤ 30] [逻辑: AND]
```

实现：
```typescript
const formatCondition = (cond: FilterCondition) => {
  const fieldLabel = fieldOptions.find(f => f.value === cond.field)?.label || cond.field
  const operatorSymbol = {
    '>=': '≥', '<=': '≤', '>': '>', '<': '<', '==': '=', '!=': '≠'
  }[cond.operator] || cond.operator
  return `${fieldLabel} ${operatorSymbol} ${cond.value}`
}
```

## 测试用例

### 后端测试

**test_evaluate_conditions.py:**
```python
def test_evaluate_conditions_and_logic():
    service = OpportunityScoringService(...)
    conditions = [
        {"field": "roe", "operator": ">=", "value": 15},
        {"field": "debt_ratio", "operator": "<=", "value": 50}
    ]
    stock_data = {"roe": 20, "debt_ratio": 40}
    factors = {}
    
    result = service._evaluate_conditions(conditions, "AND", stock_data, factors)
    assert result is True

def test_evaluate_conditions_or_logic():
    service = OpportunityScoringService(...)
    conditions = [
        {"field": "roe", "operator": ">=", "value": 15},
        {"field": "pe", "operator": "<=", "value": 10}
    ]
    stock_data = {"roe": 20, "pe": 50}  # 只满足第一个条件
    factors = {}
    
    result = service._evaluate_conditions(conditions, "OR", stock_data, factors)
    assert result is True

def test_evaluate_conditions_missing_field():
    service = OpportunityScoringService(...)
    conditions = [{"field": "roe", "operator": ">=", "value": 15}]
    stock_data = {}  # 缺少 roe 字段
    factors = {}
    
    result = service._evaluate_conditions(conditions, "AND", stock_data, factors)
    assert result is False
```

### 前端测试

手动测试流程：
1. 打开筛选建池弹窗
2. 添加条件：ROE ≥ 15、负债率 ≤ 50、PE ≤ 30
3. 选择逻辑：AND
4. 提交 → 验证后端收到正确的 JSON 格式
5. 查看池子详情 → 验证筛选条件标签正确显示

## 迁移策略

1. **Phase 1（本次实施）：** 新增 `conditions` 支持，保留旧的 `technical`/`fundamental` 逻辑
2. **Phase 2（未来）：** 前端完全切换到新UI，不再生成旧格式
3. **Phase 3（未来）：** 删除旧逻辑代码（`_calculate_technical_score` 中的硬编码阈值）

## 约束

- 单个池子最多支持 20 个筛选条件（前端限制）
- 字段值必须是数值类型（不支持字符串比较）
- 暂不支持嵌套逻辑（如 "(A AND B) OR C"），只支持单层 AND/OR
- 技术指标字段需要至少 30 条 K 线数据才能计算
