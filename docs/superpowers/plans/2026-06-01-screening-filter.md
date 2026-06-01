# Screening Filter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace hardcoded boolean tag filters with flexible condition expressions supporting "ROE≥15%, PE≤30" style numeric conditions.

**Architecture:** Add `_evaluate_conditions` method to OpportunityScoringService, validate filter conditions in API layer, update frontend to use condition builder UI instead of checkboxes.

**Tech Stack:** Python (backend), Vue 3 + Element Plus (frontend), PostgreSQL (data source)

---

## File Structure

### Backend Files

| File | Change | Responsibility |
|------|--------|----------------|
| `quantsys-v2/services/opportunity_scoring_service.py` | Modify | Add `_evaluate_conditions` method, update `_score_single_stock` |
| `quantsys-v2/api/routes/pools.py` | Modify | Add `validate_filter` function, call in routes |
| `quantsys-v2/tests/services/test_opportunity_scoring_service.py` | Create | Test condition evaluation logic |

### Frontend Files

| File | Change | Responsibility |
|------|--------|----------------|
| `web-frontend/src/views/PoolList/index.vue` | Modify | Replace checkbox UI with condition builder |
| `web-frontend/src/views/PoolDetail/index.vue` | Modify | Update filter display to show conditions |

---

### Task 1: Backend - Add Condition Evaluation

**Files:**
- Modify: `quantsys-v2/services/opportunity_scoring_service.py`
- Create: `quantsys-v2/tests/services/test_opportunity_scoring_service.py`

- [ ] **Step 1: Create test file with failing test**

Create `quantsys-v2/tests/services/test_opportunity_scoring_service.py`:

```python
import pytest
from services.opportunity_scoring_service import OpportunityScoringService

def test_evaluate_conditions_and_logic():
    """Test AND logic with all conditions met"""
    service = OpportunityScoringService(None, None, None)
    
    conditions = [
        {"field": "roe", "operator": ">=", "value": 15},
        {"field": "debt_ratio", "operator": "<=", "value": 50}
    ]
    stock_data = {"roe": 20, "debt_ratio": 40}
    factors = {}
    
    result = service._evaluate_conditions(conditions, "AND", stock_data, factors)
    assert result is True

def test_evaluate_conditions_and_logic_fail():
    """Test AND logic with one condition not met"""
    service = OpportunityScoringService(None, None, None)
    
    conditions = [
        {"field": "roe", "operator": ">=", "value": 15},
        {"field": "debt_ratio", "operator": "<=", "value": 50}
    ]
    stock_data = {"roe": 10, "debt_ratio": 40}  # roe too low
    factors = {}
    
    result = service._evaluate_conditions(conditions, "AND", stock_data, factors)
    assert result is False

def test_evaluate_conditions_or_logic():
    """Test OR logic with one condition met"""
    service = OpportunityScoringService(None, None, None)
    
    conditions = [
        {"field": "roe", "operator": ">=", "value": 15},
        {"field": "pe", "operator": "<=", "value": 10}
    ]
    stock_data = {"roe": 20, "pe": 50}  # only roe meets condition
    factors = {}
    
    result = service._evaluate_conditions(conditions, "OR", stock_data, factors)
    assert result is True

def test_evaluate_conditions_missing_field():
    """Test with missing field returns False"""
    service = OpportunityScoringService(None, None, None)
    
    conditions = [{"field": "roe", "operator": ">=", "value": 15}]
    stock_data = {}  # missing roe
    factors = {}
    
    result = service._evaluate_conditions(conditions, "AND", stock_data, factors)
    assert result is False

def test_evaluate_conditions_from_factors():
    """Test reading field from factors dict"""
    service = OpportunityScoringService(None, None, None)
    
    conditions = [{"field": "rsi", "operator": "<=", "value": 30}]
    stock_data = {}
    factors = {"rsi": 25}
    
    result = service._evaluate_conditions(conditions, "AND", stock_data, factors)
    assert result is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
cd quantsys-v2 && python -m pytest tests/services/test_opportunity_scoring_service.py -v
```
Expected: FAIL with "AttributeError: 'OpportunityScoringService' object has no attribute '_evaluate_conditions'"

- [ ] **Step 3: Implement `_evaluate_conditions` method**

Add to `quantsys-v2/services/opportunity_scoring_service.py` after `_calculate_risk_level` method:

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
            field = cond.get('field')
            operator = cond.get('operator')
            threshold = cond.get('value')
            
            # 从 stock_data 或 factors 中获取字段值
            value = stock_data.get(field) if stock_data else None
            if value is None:
                value = factors.get(field)
            
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

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
cd quantsys-v2 && python -m pytest tests/services/test_opportunity_scoring_service.py -v
```
Expected: 5 tests PASS

- [ ] **Step 5: Commit**

```bash
cd quantsys-v2 && git add services/opportunity_scoring_service.py tests/services/test_opportunity_scoring_service.py
git commit -m "feat(screening): add condition evaluation logic to OpportunityScoringService"
```

---

### Task 2: Backend - Integrate Condition Evaluation

**Files:**
- Modify: `quantsys-v2/services/opportunity_scoring_service.py:81-146`

- [ ] **Step 1: Update `_score_single_stock` to use conditions**

Find the `_score_single_stock` method (around line 81) and add condition evaluation after calculating factors (around line 106):

```python
    def _score_single_stock(
        self,
        symbol: str,
        klines: List[Dict],
        fundamental: Optional[Dict],
        filters: Dict
    ) -> Optional[Dict]:
        """评分单只股票"""
        try:
            # 检查K线数据是否充足
            if len(klines) < 30:
                logger.warning(f"{symbol}: K线数据不足 ({len(klines)}条)")
                return None

            # 计算技术指标因子
            factors = self._calculate_factors(klines)

            # 新增：评估筛选条件（优先使用新格式）
            conditions = filters.get('conditions', [])
            logic = filters.get('logic', 'AND')
            
            if conditions:
                if not self._evaluate_conditions(conditions, logic, fundamental or {}, factors):
                    return None  # 不满足条件，跳过

            # 计算三维评分（保留旧逻辑以向后兼容）
            tech_score = self._calculate_technical_score(
                factors,
                filters.get('technical', [])
            )
            fund_score = self._calculate_fundamental_score(
                fundamental,
                filters.get('fundamental', [])
            )
            capital_score = self._calculate_capital_score(factors)

            # ... 其余代码不变 ...
```

- [ ] **Step 2: Test with real data**

Run:
```bash
cd quantsys-v2 && python -c "
from services.opportunity_scoring_service import OpportunityScoringService
from repositories.kline_repository import KlineRepository
from repositories.stock_repository import StockRepository
from quantlib.adapters import get_factor_adapter
from infrastructure.db import get_db_connection

db = get_db_connection()
kline_repo = KlineRepository(db)
stock_repo = StockRepository(db)
factor_adapter = get_factor_adapter()

service = OpportunityScoringService(kline_repo, stock_repo, factor_adapter)

# Test with new condition format
filters = {
    'conditions': [
        {'field': 'roe', 'operator': '>=', 'value': 15},
        {'field': 'pe', 'operator': '<=', 'value': 30}
    ],
    'logic': 'AND'
}

results = service.score_stocks(['600519.SH', '000858.SZ'], filters)
print(f'Found {len(results)} stocks matching conditions')
for r in results:
    print(f\"  {r['symbol']}: score={r['score']}\")
"
```
Expected: Output showing filtered stocks

- [ ] **Step 3: Commit**

```bash
cd quantsys-v2 && git add services/opportunity_scoring_service.py
git commit -m "feat(screening): integrate condition evaluation into stock scoring"
```

---

### Task 3: Backend - API Validation

**Files:**
- Modify: `quantsys-v2/api/routes/pools.py`

- [ ] **Step 1: Add validation constants and function**

Add at the top of `quantsys-v2/api/routes/pools.py` after imports:

```python
# Screening filter validation
ALLOWED_FIELDS = {
    'roe', 'pe', 'pb', 'gross_margin', 'debt_ratio', 
    'net_profit_growth', 'market_cap', 'circulating_mv',
    'avg_turnover_rate', 'rsi', 'macd', 'volume_ratio_5d'
}
ALLOWED_OPERATORS = {'>=', '<=', '>', '<', '==', '!='}

def validate_filter(filter_dict):
    """
    校验筛选条件合法性
    
    Args:
        filter_dict: 筛选条件字典
        
    Raises:
        ValueError: 条件不合法时抛出
    """
    conditions = filter_dict.get('conditions', [])
    
    for cond in conditions:
        field = cond.get('field')
        operator = cond.get('operator')
        value = cond.get('value')
        
        if field not in ALLOWED_FIELDS:
            raise ValueError(f"Invalid field: {field}. Allowed: {', '.join(sorted(ALLOWED_FIELDS))}")
        
        if operator not in ALLOWED_OPERATORS:
            raise ValueError(f"Invalid operator: {operator}. Allowed: {', '.join(sorted(ALLOWED_OPERATORS))}")
        
        if not isinstance(value, (int, float)):
            raise ValueError(f"Invalid value type for field '{field}': {type(value).__name__}. Must be number.")
    
    return True
```

- [ ] **Step 2: Add validation to scan_and_create route**

Find the `scan_and_create` function and add validation after getting filter_params:

```python
@pools_bp.route('/api/pools/scan-and-create', methods=['POST'])
def scan_and_create():
    """筛选并创建股票池"""
    try:
        data = request.get_json()
        
        # ... existing validation ...
        
        filter_params = data.get('filter') or {}
        
        # 新增：校验筛选条件
        if filter_params.get('conditions'):
            validate_filter(filter_params)
        
        # ... rest of function ...
```

- [ ] **Step 3: Add validation to create route**

Find the `create` function and add similar validation:

```python
@pools_bp.route('/api/pools', methods=['POST'])
def create():
    """创建股票池"""
    try:
        data = request.get_json()
        
        # ... existing validation ...
        
        filter_template = data.get('filterTemplate')
        
        # 新增：校验筛选条件
        if filter_template and filter_template.get('conditions'):
            validate_filter(filter_template)
        
        # ... rest of function ...
```

- [ ] **Step 4: Test validation with curl**

```bash
# Test valid conditions
curl -X POST http://127.0.0.1:5001/api/pools/scan-and-create \
  -H "Content-Type: application/json" \
  -d '{
    "name": "测试条件池",
    "poolType": "static",
    "filter": {
      "conditions": [
        {"field": "roe", "operator": ">=", "value": 15}
      ],
      "logic": "AND"
    }
  }'

# Test invalid field
curl -X POST http://127.0.0.1:5001/api/pools/scan-and-create \
  -H "Content-Type: application/json" \
  -d '{
    "name": "测试非法字段",
    "poolType": "static",
    "filter": {
      "conditions": [
        {"field": "invalid_field", "operator": ">=", "value": 15}
      ]
    }
  }'
```
Expected: First succeeds, second returns 400 error with "Invalid field" message

- [ ] **Step 5: Commit**

```bash
cd quantsys-v2 && git add api/routes/pools.py
git commit -m "feat(screening): add filter validation to pool API routes"
```

---

### Task 4: Frontend - Update PoolList Scan Dialog

**Files:**
- Modify: `web-frontend/src/views/PoolList/index.vue`

- [ ] **Step 1: Replace scanForm data structure**

Find the `scanForm` ref (around line 200) and replace with:

```typescript
const scanForm = ref({
  name: '',
  poolType: 'dynamic' as 'static' | 'dynamic',
  conditions: [
    { field: 'roe', operator: '>=', value: 15 }
  ] as Array<{ field: string; operator: string; value: number }>,
  logic: 'AND' as 'AND' | 'OR',
  topN: 20,
  refreshInterval: 'weekly' as 'daily' | 'weekly',
  description: ''
})
```

- [ ] **Step 2: Add field and operator options**

Add after scanForm definition:

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

const addCondition = () => {
  scanForm.value.conditions.push({ field: 'roe', operator: '>=', value: 0 })
}

const removeCondition = (index: number) => {
  if (scanForm.value.conditions.length > 1) {
    scanForm.value.conditions.splice(index, 1)
  }
}
```

- [ ] **Step 3: Replace scan dialog template**

Find the scan dialog (search for `<el-dialog v-model="showScanDialog" title="筛选建池"`) and replace its content with:

```vue
<el-dialog v-model="showScanDialog" title="筛选建池" width="700px">
  <el-form :model="scanForm" label-width="100px">
    <el-form-item label="名称" required>
      <el-input v-model="scanForm.name" placeholder="如：低估值蓝筹池" />
    </el-form-item>
    <el-form-item label="池子类型">
      <el-radio-group v-model="scanForm.poolType">
        <el-radio value="static">静态池</el-radio>
        <el-radio value="dynamic">动态池</el-radio>
      </el-radio-group>
    </el-form-item>
    
    <el-form-item label="筛选条件">
      <div style="width: 100%;">
        <div v-for="(cond, index) in scanForm.conditions" :key="index" style="display: flex; gap: 8px; margin-bottom: 8px;">
          <el-select v-model="cond.field" placeholder="选择字段" style="flex: 2;">
            <el-option v-for="opt in fieldOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
          </el-select>
          <el-select v-model="cond.operator" placeholder="运算符" style="flex: 1;">
            <el-option v-for="opt in operatorOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
          </el-select>
          <el-input-number v-model="cond.value" :controls="false" placeholder="阈值" style="flex: 1;" />
          <el-button type="danger" :icon="Delete" circle @click="removeCondition(index)" :disabled="scanForm.conditions.length === 1" />
        </div>
        <el-button type="primary" :icon="Plus" size="small" @click="addCondition">添加条件</el-button>
      </div>
    </el-form-item>
    
    <el-form-item label="条件逻辑">
      <el-radio-group v-model="scanForm.logic">
        <el-radio value="AND">AND (所有条件都满足)</el-radio>
        <el-radio value="OR">OR (任一条件满足)</el-radio>
      </el-radio-group>
    </el-form-item>
    
    <el-form-item label="取前N只">
      <el-input-number v-model="scanForm.topN" :min="5" :max="100" :step="5" />
    </el-form-item>
    <el-form-item label="刷新周期" v-if="scanForm.poolType === 'dynamic'">
      <el-radio-group v-model="scanForm.refreshInterval">
        <el-radio value="daily">每日</el-radio>
        <el-radio value="weekly">每周</el-radio>
      </el-radio-group>
    </el-form-item>
    <el-form-item label="描述">
      <el-input v-model="scanForm.description" placeholder="可选描述" />
    </el-form-item>
  </el-form>
  <template #footer>
    <el-button @click="showScanDialog = false">取消</el-button>
    <el-button type="primary" :loading="submitting" @click="handleScanCreate">筛选建池</el-button>
  </template>
</el-dialog>
```

- [ ] **Step 4: Add icon imports**

Add to the script imports section:

```typescript
import { Delete, Plus } from '@element-plus/icons-vue'
```

- [ ] **Step 5: Update handleScanCreate function**

Replace the `handleScanCreate` function with:

```typescript
const handleScanCreate = async () => {
  if (!scanForm.value.name) {
    ElMessage.warning('请填写名称')
    return
  }
  if (scanForm.value.conditions.length === 0) {
    ElMessage.warning('请至少添加一个筛选条件')
    return
  }
  submitting.value = true
  try {
    await poolApi.scanAndCreate({
      name: scanForm.value.name,
      poolType: scanForm.value.poolType,
      filter: {
        conditions: scanForm.value.conditions,
        logic: scanForm.value.logic,
        top_n: scanForm.value.topN
      },
      refreshInterval: scanForm.value.poolType === 'dynamic' ? scanForm.value.refreshInterval : undefined,
      description: scanForm.value.description || undefined
    })
    ElMessage.success('筛选建池成功')
    showScanDialog.value = false
    await fetchPools()
  } catch {
    ElMessage.error('筛选建池失败')
  } finally {
    submitting.value = false
  }
}
```

- [ ] **Step 6: Test in browser**

Run:
```bash
cd web-frontend && npm run dev
```
Open `http://127.0.0.1:3001/pools` → click "筛选建池" → verify new UI with condition builder

- [ ] **Step 7: Commit**

```bash
cd web-frontend && git add src/views/PoolList/index.vue
git commit -m "feat(screening): replace checkbox filters with condition builder UI"
```

---

### Task 5: Frontend - Update PoolDetail Filter Display

**Files:**
- Modify: `web-frontend/src/views/PoolDetail/index.vue`

- [ ] **Step 1: Add condition formatting function**

Add after the `filterLabels` constant (around line 180):

```typescript
const formatCondition = (cond: any) => {
  const fieldLabel = fieldOptions.find(f => f.value === cond.field)?.label || cond.field
  const operatorSymbol = {
    '>=': '≥', '<=': '≤', '>': '>', '<': '<', '==': '=', '!=': '≠'
  }[cond.operator] || cond.operator
  return `${fieldLabel} ${operatorSymbol} ${cond.value}`
}

const fieldOptions = [
  { value: 'roe', label: 'ROE' },
  { value: 'pe', label: 'PE' },
  { value: 'pb', label: 'PB' },
  { value: 'gross_margin', label: '毛利率' },
  { value: 'debt_ratio', label: '负债率' },
  { value: 'net_profit_growth', label: '净利润增长' },
  { value: 'market_cap', label: '总市值' },
  { value: 'circulating_mv', label: '流通市值' },
  { value: 'rsi', label: 'RSI' },
  { value: 'volume_ratio_5d', label: '5日量比' }
]
```

- [ ] **Step 2: Update filter display template**

Find the "筛选条件标签" section (around line 40) and replace with:

```vue
<!-- 筛选条件标签 -->
<div v-if="pool.filter_template" style="margin-top: 16px;">
  <span style="color: var(--el-text-color-secondary); margin-right: 8px;">筛选条件:</span>
  
  <!-- 新格式：条件数组 -->
  <template v-if="pool.filter_template.conditions && pool.filter_template.conditions.length > 0">
    <el-tag 
      v-for="(cond, i) in pool.filter_template.conditions" 
      :key="i" 
      type="primary" 
      size="small" 
      style="margin-right: 4px;"
    >
      {{ formatCondition(cond) }}
    </el-tag>
    <el-tag type="info" size="small">逻辑: {{ pool.filter_template.logic || 'AND' }}</el-tag>
  </template>
  
  <!-- 旧格式：布尔标签（向后兼容） -->
  <template v-else>
    <el-tag v-for="t in pool.filter_template?.technical || []" :key="t" size="small" style="margin-right: 4px;">{{ filterLabels[t] || t }}</el-tag>
    <el-tag v-for="f in pool.filter_template?.fundamental || []" :key="f" type="warning" size="small" style="margin-right: 4px;">{{ filterLabels[f] || f }}</el-tag>
  </template>
  
  <el-tag v-if="pool.filter_template?.min_score" type="info" size="small" style="margin-right: 4px;">最低分: {{ pool.filter_template.min_score }}</el-tag>
  <el-tag v-if="pool.filter_template?.top_n" type="info" size="small">Top {{ pool.filter_template.top_n }}</el-tag>
</div>
```

- [ ] **Step 3: Test in browser**

Open `http://127.0.0.1:3001/pools` → create a pool with conditions → click to view detail → verify conditions display correctly

- [ ] **Step 4: Commit**

```bash
cd web-frontend && git add src/views/PoolDetail/index.vue
git commit -m "feat(screening): update filter display to show condition expressions"
```

---

### Task 6: End-to-End Test

**Files:**
- None (manual testing)

- [ ] **Step 1: Create pool with conditions via UI**

1. Open `http://127.0.0.1:3001/pools`
2. Click "筛选建池"
3. Set conditions:
   - ROE ≥ 15
   - 负债率 ≤ 50
   - PE ≤ 30
4. Logic: AND
5. Top N: 20
6. Submit

Expected: Pool created successfully, appears in list

- [ ] **Step 2: Verify pool detail shows conditions**

1. Click pool name to open detail
2. Verify "筛选条件" section shows: `[ROE ≥ 15] [负债率 ≤ 50] [PE ≤ 30] [逻辑: AND]`

- [ ] **Step 3: Test validation with invalid field**

Use curl to test backend validation:
```bash
curl -X POST http://127.0.0.1:5001/api/pools/scan-and-create \
  -H "Content-Type: application/json" \
  -d '{
    "name": "测试非法字段",
    "poolType": "static",
    "filter": {
      "conditions": [{"field": "invalid", "operator": ">=", "value": 15}]
    }
  }'
```
Expected: 400 error with "Invalid field" message

- [ ] **Step 4: Test backward compatibility**

Create pool with old format:
```bash
curl -X POST http://127.0.0.1:5001/api/pools/scan-and-create \
  -H "Content-Type: application/json" \
  -d '{
    "name": "旧格式测试池",
    "poolType": "static",
    "filter": {
      "technical": ["rsi_oversold"],
      "fundamental": ["pe_low", "roe_high"]
    }
  }'
```
Expected: Pool created successfully (old logic still works)

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "feat(screening): complete condition-based filter implementation"
```

---

## Self-Review

**Spec coverage:**
- ✅ Condition evaluation logic → Task 1
- ✅ Integration into scoring → Task 2
- ✅ API validation → Task 3
- ✅ Frontend condition builder → Task 4
- ✅ Frontend display → Task 5
- ✅ Backward compatibility → All tasks
- ✅ Testing → Task 1 (unit), Task 6 (E2E)

**Placeholder scan:** No TBD/TODO. All code complete. ✅

**Type consistency:** `conditions` array structure matches across backend/frontend. Field names match white list. ✅
