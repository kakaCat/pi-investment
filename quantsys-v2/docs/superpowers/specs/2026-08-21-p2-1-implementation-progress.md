# P2-1 依赖注入标准化 - 实施进度

**任务**: P2-1: Dependency Injection Standardization  
**开始时间**: 2026-08-21  
**状态**: 进行中 - Phase 1

---

## 总体进度

- [x] Phase 0: 硬编码依赖扫描
- [x] Phase 1.1: EnhancedServiceFactory 实现
- [x] Phase 1.2: 服务注册表 (service_registry.py)
- [x] Phase 1.3: ServiceFactory 集成桥接
- [x] Phase 1.4: 单元测试 (14/14 通过)
- [ ] Phase 2: 服务重构 (0/59 完成)
- [ ] Phase 3: FastAPI 集成
- [ ] Phase 4: 文档和迁移指南

---

## Phase 1: Enhanced ServiceFactory ✅

### 完成的工作

1. **EnhancedServiceFactory 核心功能** (`infrastructure/services/enhanced_service_factory.py`)
   - ✅ 服务注册 (register)
   - ✅ 自动依赖解析 (依赖推断)
   - ✅ 生命周期管理 (Singleton/Transient/Scoped)
   - ✅ 循环依赖检测
   - ✅ 工厂函数支持
   - ✅ @inject 装饰器
   - ✅ @register_service 装饰器

2. **服务注册表** (`infrastructure/services/service_registry.py`)
   - ✅ 注册所有 Repository 层 (6个)
   - ✅ 注册核心 Application Services (6个)
   - ✅ 兼容桥接函数

3. **ServiceFactory 集成** (`infrastructure/services/service_factory.py`)
   - ✅ 添加 `_try_get_from_enhanced()` 辅助函数
   - ✅ 更新 9 个关键服务方法支持 EnhancedServiceFactory
   - ✅ 新增 5 个 Repository 工厂方法
   - ✅ 更新 `reset_all()` 包含 EnhancedServiceFactory

4. **单元测试** (`tests/unit/infrastructure/test_enhanced_service_factory.py`)
   - ✅ 14 个测试全部通过
   - ✅ 覆盖所有核心功能
   - ✅ 包含边界情况测试

### 测试结果

```
14 passed in 0.03s
- 服务注册测试: 3/3 ✅
- 依赖解析测试: 4/4 ✅
- 生命周期管理: 2/2 ✅
- 循环依赖检测: 1/1 ✅
- @inject 装饰器: 2/2 ✅
- 重置功能: 2/2 ✅
```

---

## Phase 2: 服务重构 (进行中)

### 扫描结果概览

```
总问题数: 151
影响文件: 59
主要问题类型:
- 直接实例化: 137 (90.7%)
- 方法内 ServiceFactory 调用: 11 (7.3%)
- 硬编码服务调用: 2 (1.3%)
- 内联适配器导入: 1 (0.7%)
```

### 重构优先级

#### P0 - 高优先级 (11 issues，问题最多的文件)

1. **data_service.py** - 11 issues
   - 问题: `__init__` 中直接实例化 10 个 Repository
   - 计划: 改为构造函数注入

2. **data_service_orm.py** - 10 issues
   - 问题: 同 data_service.py
   - 计划: 统一重构策略

3. **signal_execution_scheduler.py** - 7 issues
   - 问题: 多处直接实例化
   - 计划: 构造函数注入

4. **ml_train_task.py** - 7 issues
   - 状态: ✅ 已在 P1-2 Phase 2 修复（4个违规已修复）
   - 遗留: 方法内 ServiceFactory 调用需要改为构造函数注入

#### P1 - 中优先级 (5-6 issues)

5. pool_change_log_service.py - 6 issues
6. signal_lifecycle_service.py - 6 issues
7. opportunity_scoring_service.py - 5 issues
8. stock_pool_service.py - 5 issues

#### P2 - 低优先级 (3-4 issues)

9-15. 其他服务 (37 个文件，3-4 issues 每个)

---

## 下一步计划

### 立即任务

1. **重构 data_service.py**
   - 定义清晰的依赖接口
   - 改为构造函数注入
   - 更新 service_registry.py 注册
   - 编写迁移测试

2. **重构 data_service_orm.py**
   - 应用相同策略
   - 确保向后兼容

3. **更新依赖该服务的其他组件**
   - 检查调用方
   - 逐步迁移

### 后续任务

- Phase 3: FastAPI 依赖注入集成
- Phase 4: 开发者文档和迁移指南
- Phase 5: 清理旧的 ServiceFactory 模式

---

## 技术决策记录

### 1. 渐进式迁移策略

**决策**: 使用桥接模式，优先从 EnhancedServiceFactory 获取，如果未注册则回退到旧实现

**原因**:
- 避免一次性大规模重构的风险
- 允许逐步验证每个服务的迁移
- 保持系统始终可运行

### 2. Repository 层优先

**决策**: 先迁移 Repository 层，再迁移 Application Services

**原因**:
- Repository 层已有清晰的 Port 接口
- 依赖关系简单（通常无依赖或依赖其他 Repository）
- 为上层服务提供稳定基础

### 3. 工厂函数用于复杂初始化

**决策**: DataService 等复杂服务使用工厂函数而非自动依赖解析

**原因**:
- 这些服务有复杂的内部初始化逻辑
- 避免改动太多现有代码
- 保持向后兼容性

---

## 遇到的问题和解决方案

### 问题 1: 字符串类型注解导致依赖推断失败

**现象**: 循环依赖测试失败，`AttributeError: 'str' object has no attribute '__name__'`

**原因**: Python 的 forward reference 使用字符串注解

**解决**: 在 `_infer_dependencies()` 中跳过字符串注解，要求显式声明依赖

### 问题 2: Pytest 警告测试类名冲突

**现象**: `PytestCollectionWarning: cannot collect test class 'TestRepository'`

**原因**: Pytest 默认收集所有 `Test` 前缀的类

**解决**: 重命名测试辅助类为 `Mock` 前缀

---

## 性能指标

### 测试执行时间

- EnhancedServiceFactory 单元测试: 0.03s (14 tests)
- 预期全量测试影响: < 5% 增加（依赖注入开销很小）

### 内存影响

- Singleton 实例: 与旧 ServiceFactory 相同
- 额外元数据: 每个服务约 1KB (ServiceDescriptor)
- 预期总增加: < 100KB

---

## 参考文档

- [P2-1 实施计划](2026-08-21-p2-1-di-standardization-plan.md)
- [硬编码依赖扫描报告](../../tools/scan_hardcoded_dependencies.py)
- [依赖注入最佳实践](https://martinfowler.com/articles/injection.html)
