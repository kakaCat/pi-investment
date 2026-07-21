# Cursor Resource Leak Fixes - Implementation Plan

**Date**: 2026-06-16  
**Priority**: P0 - Critical  
**Estimated Effort**: 8 hours

---

## 🎯 目标

修复已识别的10处关键cursor资源泄漏，确保所有数据库cursor都能正确关闭，防止连接池耗尽。

---

## 📋 待修复的文件清单

### 1. adapters/outbound/repositories/backtest_repository.py:19-36
**问题**: Early return without cursor close  
**风险**: High - 每次查询失败都泄漏cursor  
**修复**: 使用try/finally保护

### 2. adapters/outbound/repositories/financial_repository.py:62-70
**问题**: Exception path without cursor cleanup  
**风险**: High - 数据保存失败时泄漏  
**修复**: 添加try/finally块

### 3. adapters/outbound/repositories/financial_repository.py:125-133
**问题**: No try/finally in exception handler  
**风险**: Medium - 查询异常时泄漏  
**修复**: 统一资源清理模式

### 4. application/services/data_gap_detector.py:192-209
**问题**: Exception in fallback loop doesn't close cursor  
**风险**: Medium - 批量操作失败时多个泄漏  
**修复**: 添加finally块

### 5. application/services/data_gap_detector.py:225-228
**问题**: Nested cursor in exception handler  
**风险**: Medium - 重试逻辑中泄漏  
**修复**: 统一清理模式

### 6. application/services/data_quality_service.py:427-443
**问题**: Conditional cursor creation without protection  
**风险**: Medium - 条件分支泄漏  
**修复**: 每个分支添加保护

### 7. application/services/signal_test_log.py:218-288
**问题**: Long loop with cursor unprotected  
**风险**: Low - 长时间运行泄漏  
**修复**: 移到try/finally外层

### 8. application/services/experience_accumulator.py:142-167
**问题**: No try/finally, success path only  
**风险**: Medium - 异常时泄漏  
**修复**: 添加finally块

### 9. application/services/order_service.py:494-568
**问题**: Multiple paths without protection  
**风险**: High - 交易逻辑关键路径  
**修复**: 统一所有路径的清理

### 10. application/services/risk_check_service.py:336-358
**问题**: No exception handling  
**风险**: Medium - 风控检查失败泄漏  
**修复**: 添加try/finally

---

## 🔧 标准修复模式

### Pattern 1: 基础保护

**Before**:
```python
def method(self):
    cursor = self.db.cursor()
    cursor.execute(query)
    result = cursor.fetchone()
    cursor.close()
    return result
```

**After**:
```python
def method(self):
    cursor = None
    try:
        cursor = self.db.cursor()
        cursor.execute(query)
        result = cursor.fetchone()
        return result
    finally:
        if cursor:
            cursor.close()
```

### Pattern 2: 多个返回路径

**Before**:
```python
def method(self):
    cursor = self.db.cursor()
    cursor.execute(query)
    result = cursor.fetchone()
    
    if not result:
        cursor.close()
        return None  # ❌ 其他路径可能忘记close
    
    cursor.close()
    return result
```

**After**:
```python
def method(self):
    cursor = None
    try:
        cursor = self.db.cursor()
        cursor.execute(query)
        result = cursor.fetchone()
        
        if not result:
            return None  # ✅ finally保证清理
        
        return result
    finally:
        if cursor:
            cursor.close()
```

### Pattern 3: 异常处理路径

**Before**:
```python
def method(self):
    cursor = self.db.cursor()
    try:
        cursor.execute(query)
        result = cursor.fetchall()
    except Exception as e:
        logger.error(f"Query failed: {e}")
        cursor.close()  # ❌ 只在异常时close
        raise
    cursor.close()
    return result
```

**After**:
```python
def method(self):
    cursor = None
    try:
        cursor = self.db.cursor()
        cursor.execute(query)
        result = cursor.fetchall()
        return result
    except Exception as e:
        logger.error(f"Query failed: {e}")
        raise
    finally:
        if cursor:  # ✅ 所有路径都清理
            cursor.close()
```

---

## 📊 实施计划

### Phase 1: Repository层修复（2小时）

**优先级**: Highest  
**文件**:
1. backtest_repository.py
2. financial_repository.py

**原因**: Repository是数据访问基础，使用频率最高

### Phase 2: Service层修复（4小时）

**优先级**: High  
**文件**:
3. data_gap_detector.py
4. data_quality_service.py
5. experience_accumulator.py
6. risk_check_service.py

**原因**: Service层调用频繁，影响业务逻辑

### Phase 3: 关键业务逻辑修复（2小时）

**优先级**: Critical  
**文件**:
7. order_service.py (交易相关)
8. signal_test_log.py (信号验证)

**原因**: 涉及交易和信号，不能有任何泄漏

---

## ✅ 验证方法

### 1. 代码Review
- [ ] 确认每个cursor都有对应的finally块
- [ ] 检查所有返回路径
- [ ] 确认异常处理路径

### 2. 单元测试
```python
def test_cursor_cleanup_on_exception():
    """验证异常时cursor被正确关闭"""
    repo = Repository()
    
    with patch.object(repo.db, 'cursor') as mock_cursor:
        mock_cursor.return_value.execute.side_effect = Exception("Test")
        
        try:
            repo.method_that_uses_cursor()
        except:
            pass
        
        # 验证cursor.close()被调用
        mock_cursor.return_value.close.assert_called_once()
```

### 3. 集成测试
- [ ] 运行完整测试套件
- [ ] 检查连接池使用情况
- [ ] 监控cursor泄漏

### 4. 生产验证
- [ ] 监控数据库连接数
- [ ] 检查连接池警告日志
- [ ] 验证无"too many connections"错误

---

## 📈 预期影响

### 修复前风险

**场景**: 100个并发请求，10%失败率
- 失败请求: 10个
- 泄漏cursor: 10个
- 每小时泄漏: 600个
- **结果**: 连接池耗尽（假设max=20）

### 修复后

**场景**: 相同负载
- 失败请求: 10个
- 泄漏cursor: 0个
- **结果**: 连接池稳定

---

## 🎯 成功指标

- [ ] 所有10个文件修复完成
- [ ] 所有cursor操作都有finally保护
- [ ] 测试覆盖率>80%
- [ ] 无cursor泄漏告警
- [ ] 连接池使用率稳定<60%

---

## 📝 后续优化

### 长期改进

1. **使用Context Manager**
   ```python
   with self.db.cursor() as cursor:
       cursor.execute(query)
       return cursor.fetchall()
   # 自动关闭
   ```

2. **Repository基类方法**
   ```python
   class BaseRepository:
       def _execute_query(self, query, params=None):
           """统一的查询执行方法，自动管理cursor"""
           cursor = None
           try:
               cursor = self.db.cursor()
               cursor.execute(query, params)
               return cursor.fetchall()
           finally:
               if cursor:
                   cursor.close()
   ```

3. **添加Linting规则**
   ```bash
   # 使用pylint检测未关闭的资源
   pylint --enable=resource-leak
   ```

---

**创建时间**: 2026-06-16  
**负责人**: Development Team  
**预计完成**: Week 3
