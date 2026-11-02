# 高复杂度函数修复进度报告

**日期**: 2026-09-06  
**目标**: 修复 142 个高复杂度函数（复杂度 > 15）  
**当前进度**: 2/142 完成

---

## 已完成修复

### 1. register_routes (main.py) ✅
- **原复杂度**: 78
- **新复杂度**: 15
- **方法**: 拆分为 RouteRegistrar 类 + 15 个小方法
- **文件**: `adapters/inbound/fastapi_app/route_registrar.py`

### 2. run_backtest (analysis_async.py) ✅
- **原复杂度**: 37
- **新复杂度**: 8
- **方法**: 拆分为 BacktestRequestProcessor 类 + 8 个小方法
- **文件**: `adapters/inbound/fastapi_app/routes/backtest_refactored.py`

---

## 待修复函数（按优先级）

### P0 - 超高复杂度 (>30) - 10 个函数

剩余需要立即修复的：

| 文件 | 函数 | 复杂度 | 优先级 |
|------|------|--------|--------|
| analysis_async.py | compute_factors | 17 | P0 |
| analysis_async.py | _annotate_stale_factors | 18 | P0 |
| analysis_async.py | get_stock_factors | 19 | P0 |
| analysis_async.py | calculate_risk_metrics | 20 | P0 |
| analysis_async.py | factor_analyze | 22 | P0 |
| analysis_async.py | sector_aggregate | 20 | P0 |

**预计时间**: 12-15 小时

### P1 - 高复杂度 (20-30) - 约 30 个函数

**预计时间**: 20-25 小时

### P2 - 中等复杂度 (15-20) - 约 100 个函数

**预计时间**: 30-40 小时

---

## 修复策略

### 通用模式

1. **提取验证逻辑**
   ```python
   # Before: 所有验证在一个函数
   def big_function(data):
       if not data: return error
       if 'field' not in data: return error
       if invalid(data['field']): return error
       # ... 更多验证
       # ... 业务逻辑
   
   # After: 验证器类
   class RequestValidator:
       def validate_required(self): ...
       def validate_format(self): ...
       def validate_business_rules(self): ...
   ```

2. **提取数据转换**
   ```python
   # Before: 所有转换在一个函数
   def process(data):
       data['snake'] = data.pop('camel')
       data['new'] = transform(data['old'])
       # ... 更多转换
   
   # After: 转换器类
   class DataTransformer:
       def normalize_keys(self): ...
       def map_legacy_fields(self): ...
       def apply_defaults(self): ...
   ```

3. **提取业务逻辑分支**
   ```python
   # Before: 巨大的 if-elif-else
   def execute(strategy_type, data):
       if strategy_type == 'pe':
           # 50 行逻辑
       elif strategy_type == 'pb':
           # 50 行逻辑
       elif ...
   
   # After: 策略模式
   class StrategyExecutor:
       def execute_pe(self): ...
       def execute_pb(self): ...
       
       def execute(self):
           method = getattr(self, f'execute_{strategy_type}')
           return method()
   ```

---

## 快速批量修复方案

为了在 2 周内完成，采用增量策略：

### Week 1: P0 函数（复杂度 > 30）

**Day 1-2**: analysis_async.py 中的 6 个函数
- compute_factors (17)
- _annotate_stale_factors (18)
- get_stock_factors (19)
- calculate_risk_metrics (20)
- factor_analyze (22)
- sector_aggregate (20)

**Day 3-4**: 其他文件中复杂度 > 30 的函数

**Day 5**: 集成测试和验证

### Week 2: P1 函数（复杂度 20-30）

**Day 6-10**: 批量重构 30 个函数
- 每天 6 个函数
- 使用模板加速

---

## 自动化工具

创建批量重构工具：

```python
# tools/refactor_complexity.py
class ComplexityRefactorer:
    def analyze_function(self, func):
        """分析函数找出可提取的部分"""
        pass
    
    def suggest_refactoring(self, func):
        """建议重构方案"""
        pass
    
    def generate_refactored_code(self, func):
        """生成重构后代码（需人工审核）"""
        pass
```

---

## 质量保证

### 重构检查清单

每个重构函数必须：

- [ ] 复杂度 < 15
- [ ] 保持原有功能
- [ ] 通过现有测试
- [ ] 添加单元测试
- [ ] 代码审查通过

### 测试策略

1. **保留原函数**（临时）
   ```python
   def old_function():  # DEPRECATED
       pass
   
   def new_function():  # 重构版本
       pass
   ```

2. **对比测试**
   ```python
   def test_refactoring():
       result_old = old_function(data)
       result_new = new_function(data)
       assert result_old == result_new
   ```

3. **集成测试**
   - 确保端到端流程正常

---

## 风险与缓解

### 风险 1: 破坏现有功能

**缓解**:
- 保留原函数作为备份
- 对比测试
- 渐进式替换

### 风险 2: 时间不足

**缓解**:
- 优先修复 P0（>30）
- P1/P2 可以渐进式修复
- 使用自动化工具加速

### 风险 3: 引入新 Bug

**缓解**:
- 完整的测试覆盖
- 代码审查
- 分批上线

---

## 成功指标

### 目标指标

| 指标 | 当前 | 目标 | 进度 |
|------|------|------|------|
| 复杂度 > 30 的函数 | 10 个 | 0 个 | 20% ✅ |
| 复杂度 > 20 的函数 | 40 个 | 0 个 | 5% |
| 复杂度 > 15 的函数 | 142 个 | 0 个 | 1.4% |
| 平均复杂度 | ~8 | < 10 | - |

### Week 1 目标

- P0 函数全部修复（10 个）
- 复杂度 > 30: 10 → 0
- 进度: 1.4% → 7%

### Week 2 目标

- P1 函数全部修复（30 个）
- 复杂度 > 20: 40 → 0
- 进度: 7% → 28%

---

## 下一步行动

### 立即执行（今天）

1. ✅ 修复 register_routes (78 → 15)
2. ✅ 修复 run_backtest (37 → 8)
3. ⏳ 修复 analysis_async.py 中剩余 6 个函数
4. ⏳ 创建自动化重构工具

### 明天

5. 继续修复 P0 函数
6. 建立重构测试框架
7. 开始 Week 1 Day 3-4 任务

---

**报告时间**: 2026-09-06  
**下次更新**: 完成 Week 1 Day 1-2 任务后
