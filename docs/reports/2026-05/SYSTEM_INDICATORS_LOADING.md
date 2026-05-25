# 系统指标加载机制说明

## 概述

系统指标是预置的技术指标策略，存储在数据库中，通过 `strategy_type` 字段区分用户自定义指标和系统内置指标。

## 加载流程

### 1. 前端请求
```typescript
// web-frontend/src/services/api/indicator.ts
getSystemIndicators() {
  return apiClient.get('/api/indicators/list', { 
    params: { type: 'system' } 
  })
}
```

### 2. 后端API处理
```python
# quantsys-v2/api/server.py (行 3615-3616)
elif filter_type == 'system':
    indicators = [i for i in indicators if i.get('strategy_type') != 'custom']
```

**过滤逻辑**：
- `type=my`：返回 `strategy_type == 'custom'` 的指标（用户自定义）
- `type=system`：返回 `strategy_type != 'custom'` 的指标（系统内置）
- 不传 `type`：返回所有指标

### 3. 数据来源
系统指标存储在数据库的 `strategy_code` 表中，通过以下字段标识：
- `code_type = 'indicator'`：标识为指标（而非脚本）
- `strategy_type != 'custom'`：标识为系统指标（而非用户自定义）
- `is_public = True`：系统指标默认公开

## 创建系统指标

### 方法1：运行创建脚本（推荐）

```bash
cd quantsys-v2
python3 create_builtin_indicators.py
```

**脚本功能**：
- 创建5个常用技术指标：
  1. **RSI超买超卖策略** - 动量指标
  2. **双均线交叉策略** - 趋势指标
  3. **MACD金叉死叉策略** - 趋势指标
  4. **布林带突破策略** - 波动率指标
  5. **KDJ超买超卖策略** - 动量指标

- 自动检查重复，避免重复创建
- 验证代码有效性
- 设置 `is_public=True` 和 `strategy_type='builtin'`

**预期输出**：
```
======================================================================
创建系统内置指标
======================================================================

✓ 创建成功: RSI超买超卖策略
  ID: 1
  分类: momentum

✓ 创建成功: 双均线交叉策略
  ID: 2
  分类: trend

...

======================================================================
完成！成功创建 5/5 个系统指标
======================================================================
```

### 方法2：通过API创建

```python
from services.strategy_code_service import StrategyCodeService

service = StrategyCodeService()
result = service.create_strategy(
    name='我的系统指标',
    code='# 指标代码...',
    code_type='indicator',
    description='指标描述',
    category='trend',
    is_public=True  # 设为公开
)
```

**注意**：通过API创建的指标 `strategy_type` 默认为 `'custom'`，需要手动修改数据库才能变为系统指标。

### 方法3：直接修改数据库

```sql
-- 将现有指标设置为系统指标
UPDATE strategy_code 
SET strategy_type = 'builtin', is_public = true 
WHERE id = 1;

-- 或插入新的系统指标
INSERT INTO strategy_code (
    strategy_name, code_content, code_type, 
    strategy_type, is_public, description, category
) VALUES (
    'MA策略', '# 代码...', 'indicator',
    'builtin', true, '双均线策略', 'trend'
);
```

## 数据库表结构

### strategy_code 表关键字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | INTEGER | 主键 |
| `strategy_name` | TEXT | 策略名称 |
| `code_content` | TEXT | 策略代码 |
| `code_type` | TEXT | 代码类型：'indicator' 或 'script' |
| `strategy_type` | TEXT | 策略类型：'custom'（用户）或 'builtin'（系统） |
| `is_public` | BOOLEAN | 是否公开 |
| `description` | TEXT | 描述 |
| `category` | TEXT | 分类：trend, momentum, volatility, volume |
| `author` | TEXT | 作者 |
| `created_at` | TIMESTAMP | 创建时间 |

## 前端显示逻辑

```vue
<!-- web-frontend/src/views/IndicatorIDE/index.vue -->

<!-- 我的指标 -->
<div class="mb-4">
  <div class="text-xs text-slate-500 uppercase font-medium mb-2">
    我的指标 ({{ myIndicators.length }})
  </div>
  <div v-for="indicator in filteredMyIndicators" :key="indicator.id">
    {{ indicator.name }}
  </div>
</div>

<!-- 系统指标 -->
<div class="mb-4">
  <div class="text-xs text-slate-500 uppercase font-medium mb-2">
    系统指标 ({{ systemIndicators.length }})
  </div>
  <div v-for="indicator in filteredSystemIndicators" :key="indicator.id">
    {{ indicator.name }}
  </div>
</div>
```

**加载时机**：
- 组件挂载时（`onMounted`）调用 `loadIndicators()`
- 并行请求 `getMyIndicators()` 和 `getSystemIndicators()`
- 分别存储到 `myIndicators` 和 `systemIndicators` 响应式变量

## 故障排查

### 问题1：系统指标不显示

**可能原因**：
1. 数据库中没有系统指标数据
2. 数据库连接失败
3. `strategy_type` 字段值不正确

**解决方法**：
```bash
# 1. 检查数据库连接
python3 -c "from quantsys.data.db import get_db; print(get_db())"

# 2. 运行创建脚本
cd quantsys-v2
python3 create_builtin_indicators.py

# 3. 检查数据库内容
sqlite3 quantsys.db "SELECT id, strategy_name, strategy_type FROM strategy_code WHERE code_type='indicator';"
```

### 问题2：指标名称不显示

**可能原因**：
- 后端返回 `strategy_name`，前端期望 `name`

**解决方法**：
- 已通过 `normalize_indicator_fields()` 工具函数修复
- 在 API 响应中自动添加 `name` 字段映射

### 问题3：搜索功能无效

**可能原因**：
- 依赖问题2（名称字段映射错误）

**解决方法**：
- 修复字段映射后自动恢复

## 系统指标列表

### 当前内置指标（5个）

| 名称 | 分类 | 描述 |
|------|------|------|
| RSI超买超卖策略 | momentum | RSI < 30 买入，RSI > 70 卖出 |
| 双均线交叉策略 | trend | 短期均线上穿长期均线买入，下穿卖出 |
| MACD金叉死叉策略 | trend | MACD金叉买入，死叉卖出 |
| 布林带突破策略 | volatility | 价格突破下轨买入，突破上轨卖出 |
| KDJ超买超卖策略 | momentum | K线与D线金叉买入，死叉卖出 |

### 扩展系统指标

可以在 `create_builtin_indicators.py` 中添加更多指标：

```python
builtin_indicators.append({
    'name': 'CCI超买超卖策略',
    'code': '''# CCI策略代码...''',
    'description': 'CCI指标策略',
    'category': 'momentum'
})
```

## 最佳实践

### 1. 初始化系统指标
在部署新环境时，首先运行创建脚本：
```bash
cd quantsys-v2
python3 create_builtin_indicators.py
```

### 2. 定期更新
当添加新的系统指标时：
1. 更新 `create_builtin_indicators.py`
2. 运行脚本（自动跳过已存在的指标）
3. 重启服务

### 3. 版本控制
- 系统指标代码纳入版本控制
- 使用数据库迁移管理指标更新
- 记录指标版本和变更历史

### 4. 测试验证
```bash
# 测试系统指标加载
curl "http://127.0.0.1:5001/api/indicators/list?type=system"

# 测试用户指标加载
curl "http://127.0.0.1:5001/api/indicators/list?type=my"
```

## 总结

**系统指标加载路径**：
```
数据库 (strategy_code表)
  ↓ (strategy_type != 'custom')
后端API (/api/indicators/list?type=system)
  ↓ (normalize_indicator_fields)
前端API (getSystemIndicators)
  ↓
组件显示 (systemIndicators)
```

**关键点**：
1. 系统指标存储在数据库中，不是硬编码
2. 通过 `strategy_type` 字段区分系统和用户指标
3. 需要运行 `create_builtin_indicators.py` 初始化
4. 字段映射已通过工具函数统一处理

**下一步**：
运行 `python3 create_builtin_indicators.py` 创建系统指标。
