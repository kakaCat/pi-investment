# P2-3 生产环境验证问题修复计划

**日期**: 2026-08-22  
**验证结果**: 配置驱动 20/26 成功，硬编码注册失败

---

## 发现的问题

### 问题 1: 硬编码注册失败 - 循环依赖 ❌

**错误**:
```
TypeError: Can't instantiate abstract class IStockRepository without an implementation for abstract method 'get_stock_info'
```

**根因**:
`adapters/shared/services.py` 在模块加载时调用 `ServiceFactory.get_data_service()`，而 `get_data_service()` 又尝试实例化接口 `IStockRepository()`。

**调用链**:
```
service_registry._register_services_hardcoded()
  → import adapters.outbound.ml.ml_model_repository
    → import adapters.shared.ml_helpers
      → import adapters.shared.__init__
        → import adapters.shared.services
          → ServiceFactory.get_data_service()  # 模块加载时执行!
            → DataService(stock_repo=IStockRepository())  # 尝试实例化接口
```

**修复方案**:
- 将 `adapters/shared/services.py` 中的全局服务获取改为懒加载函数
- 或者移除这个反模式（不应该在模块顶层调用 ServiceFactory）

---

### 问题 2: `get_config` 导入失败 (2 个服务) ❌

**错误**:
```
cannot import name 'get_config' from 'infrastructure.config'
```

**影响服务**:
- `strategy_code_service`
- `signal_execution_scheduler`

**根因**:
P2-3 重构了 `infrastructure/config/__init__.py`，移除了 `get_config` 函数，但这两个服务仍在使用旧 API。

**修复方案**:
- 更新这两个服务使用新的配置 API
- 或者在 `__init__.py` 添加向后兼容的 `get_config` 函数

---

### 问题 3: IPoolMemberRepository 未导出 ❌

**错误**:
```
module 'domain.ports' has no attribute 'IPoolMemberRepository'
```

**根因**:
接口定义在 `repository_ports_extended.py` 但未在 `domain/ports/__init__.py` 中导出。

**修复方案**:
- 在 `domain/ports/__init__.py` 添加 `IPoolMemberRepository` 到导入和 `__all__`

---

### 问题 4: 缺失的服务模块 (3 个) ❌

**错误**:
```
No module named 'application.services.chip_distribution_service'
No module named 'application.services.paper_trading_engine'
No module named 'application.services.dynamic_scoring_service'
```

**根因**:
配置文件引用了不存在的服务。

**修复方案**:
- 从 `config/services.yaml` 移除这三个不存在的服务
- 或者确认它们是否应该存在（可能文件名不同）

---

## 修复优先级

### P0 - 必须修复（阻塞硬编码注册）

1. **修复循环依赖** (`adapters/shared/services.py`)
2. **添加 IPoolMemberRepository 导出**
3. **修复 get_config 导入错误**（2 个服务）

### P1 - 清理配置

4. **从配置移除不存在的服务**（3 个）

---

## 修复顺序

1. IPoolMemberRepository 导出（最简单）
2. adapters/shared/services.py 循环依赖（最关键）
3. get_config 导入错误（2 个服务）
4. 清理配置文件（3 个不存在的服务）

---

## 验收标准

- ✅ 配置驱动注册：23/23 成功（移除 3 个不存在的）
- ✅ 硬编码注册：不报错，成功注册核心服务
- ✅ 关键 Repository 可解析
- ✅ 环境变量控制正常

---

**执行**: 按顺序修复，每步验证
