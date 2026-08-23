# P2-3 生产环境验证修复进度

**日期**: 2026-08-22  
**状态**: 部分修复完成，硬编码注册仍有问题

---

## 已完成的修复 ✅

### 1. 移除配置中不存在的服务 ✅
- ❌ `pool_member` Repository（IPoolMemberRepository 不存在）
- ❌ `chip_distribution_service`（模块不存在）
- ❌ `paper_trading_engine`（模块不存在）
- ❌ `dynamic_scoring_service`（模块不存在）

**结果**: 配置服务从 26 个减少到 22 个，全部成功注册

### 2. 添加 get_config 向后兼容 ✅
在 `infrastructure/config/__init__.py` 添加了 `get_config()` 函数，避免导入错误。

### 3. 重构 adapters/shared/services.py ✅
- 移除模块级的服务实例化
- 改用 `_LazyServiceModule` 代理类，属性延迟加载
- 避免循环依赖

---

## 当前验证结果

### ✅ 配置驱动注册：完全成功
- 22/22 服务成功注册
- 关键 Repository 可解析
- 环境变量控制正常

### ❌ 硬编码注册：仍然失败

**错误**:
```
TypeError: Can't instantiate abstract class IStockRepository without an implementation for abstract method 'get_stock_info'
```

**调用链**:
```
_register_services_hardcoded()
  → import ml_model_repository
    → import adapters.shared.ml_helpers
      → adapters.shared.services.get_data_service()  # 通过属性访问
        → ServiceFactory.get_data_service()
          → DataService(stock_repo=IStockRepository())  # 尝试实例化接口
```

---

## 剩余问题分析

### 问题：DataService 构造函数仍在实例化接口

即使使用了懒加载代理，当 `get_data_service()` 被调用时，`ServiceFactory.get_data_service()` 内部的 `DataService()` 构造函数仍然尝试实例化接口。

**DataService.__init__() 的问题代码**:
```python
def __init__(self, stock_repo=None, ...):
    self.stock = stock_repo or IStockRepository()  # ❌ 实例化接口
```

### 根本原因

硬编码注册路径中：
1. `_register_services_hardcoded()` 还没注册任何 Repository
2. 就已经在导入 `ml_model_repository` 时触发了 `ServiceFactory.get_data_service()`
3. 此时 ServiceFactory 中还没有注册的 Repository 实例
4. `DataService()` 构造函数尝试 fallback 到 `IStockRepository()`，失败

---

## 解决方案

### 方案 1: 修复 ServiceFactory.get_data_service() ✅ 推荐

确保 `get_data_service()` 在调用前先注册必要的 Repository。

### 方案 2: 修复 DataService 构造函数

将 `IStockRepository()` 改为 `None` 或延迟实例化。

### 方案 3: 调整硬编码注册顺序

先注册 Repository，再导入依赖它们的模块。

---

## 下一步行动

1. **检查 ServiceFactory.get_data_service() 实现**
2. **检查 DataService.__init__() 实现**
3. **选择最佳修复方案并实施**
4. **重新验证**

---

## 验收目标

- ✅ 配置驱动注册：22/22 成功（已达成）
- ⏳ 硬编码注册：不报错，成功注册核心服务
- ✅ 关键 Repository 可解析（已达成）
- ✅ 环境变量控制正常（已达成）

**当前进度**: 75% 完成
