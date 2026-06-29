# 依赖注入集成测试指南

**日期**: 2026-06-26  
**状态**: 阶段 2 完成 - DI 容器已集成到 Flask

---

## ✅ 已完成的修改

### 1. 修改 server.py

在 `create_app()` 函数中添加了 DI 容器初始化：

```python
# ✅ 初始化依赖注入容器
try:
    from infrastructure.di.container import Container
    container = Container()
    app.container = container
    logger.info("✅ Dependency injection container initialized")
except Exception as e:
    logger.warning(f"⚠️ Failed to initialize DI container: {e}")
    logger.warning("Application will use legacy shared.py services (fallback mode)")
```

**关键特性**：
- ✅ 容错设计：如果容器初始化失败，应用仍可运行
- ✅ 向后兼容：不影响现有使用 `shared.py` 的路由
- ✅ 日志输出：清晰的初始化状态提示

### 2. 创建测试路由

新文件：`adapters/inbound/api/routes/test_di.py`

提供 3 个测试端点：

1. **GET /api/test/di/health** - 验证 DI 容器是否初始化
2. **GET /api/test/di/services** - 列出容器中的所有服务
3. **GET /api/test/di/inject-demo** - 演示自动注入 `data_service`

### 3. 注册测试路由

在 `server.py` 中注册了 `test_di_bp`。

---

## 🚀 测试步骤

### 步骤 1: 启动 Flask 应用

```bash
cd quantsys-v2
python adapters/inbound/api/server.py
```

**预期输出**：
```
✅ SQLAlchemy Engine initialized (pool_size=10, max_overflow=20, capacity=30)
✅ Dependency injection container initialized
 * Running on http://127.0.0.1:5001
```

如果看到第二行 ✅，说明 DI 容器已成功初始化！

如果看到 ⚠️ 警告，说明容器初始化失败，但应用仍在 fallback 模式运行。

---

### 步骤 2: 测试 DI 健康检查

```bash
curl http://localhost:5001/api/test/di/health
```

**预期响应**（成功）：
```json
{
  "success": true,
  "message": "DI container is working",
  "di_enabled": true,
  "container_type": "Container"
}
```

**预期响应**（失败）：
```json
{
  "success": false,
  "message": "DI container not initialized",
  "di_enabled": false
}
```

---

### 步骤 3: 查看可用服务

```bash
curl http://localhost:5001/api/test/di/services
```

**预期响应**：
```json
{
  "success": true,
  "available_services": [
    "data_service",
    "factor_adapter",
    "opportunity_scoring_service",
    "pool_repository",
    "pool_validation_service",
    "sector_rotation_service",
    "stock_pool_service",
    "stock_scoring_service",
    "strategy_repository",
    "strategy_service"
  ],
  "service_count": 10
}
```

---

### 步骤 4: 测试自动注入

```bash
curl http://localhost:5001/api/test/di/inject-demo
```

**预期响应**（成功）：
```json
{
  "success": true,
  "message": "Service injected successfully",
  "service_info": {
    "type": "DataService",
    "has_stock_repo": true,
    "has_kline_repo": true
  }
}
```

**预期响应**（失败）：
```json
{
  "success": false,
  "message": "data_service not injected"
}
```

---

## 📊 测试结果判断

### ✅ 全部成功（理想情况）

所有 3 个测试端点都返回 `"success": true`：

- ✅ DI 容器初始化成功
- ✅ 服务列表正确显示
- ✅ 自动注入功能正常

**下一步**：开始迁移真实路由（如 pools.py）

---

### ⚠️ 部分成功（容器初始化失败但应用运行）

- ❌ 健康检查失败：`"di_enabled": false`
- ❌ 其他测试也会失败

**原因**：容器初始化时遇到类型注解或导入错误

**下一步**：
1. 查看启动日志，找到具体错误信息
2. 修复类型注解问题
3. 或使用简化版容器

---

### ❌ 应用无法启动

启动时抛出异常，Flask 无法运行。

**原因**：server.py 修改有语法错误

**解决**：检查 server.py 修改是否正确

---

## 🎯 下一步行动

### 如果测试全部通过 ✅

**立即执行**：试点迁移一个真实路由

推荐从最简单的开始：

1. **health.py** - 健康检查（无业务逻辑）
2. **pools.py** - 股票池管理（常用路由）
3. **strategies.py** - 策略管理

我帮您选择并开始迁移？

---

### 如果容器初始化失败 ⚠️

**Option A**: 修复类型注解问题
- 定位具体错误服务
- 添加正确的类型导入

**Option B**: 创建简化版容器
- 只包含核心服务
- 跳过有问题的服务

**Option C**: 暂时禁用容器
- 注释掉容器初始化代码
- 先修复类型问题再启用

---

## 📝 测试检查清单

执行测试并记录结果：

- [ ] 应用启动成功
- [ ] 看到 "✅ Dependency injection container initialized"
- [ ] GET /api/test/di/health 返回 success: true
- [ ] GET /api/test/di/services 列出 10 个服务
- [ ] GET /api/test/di/inject-demo 自动注入成功

全部打勾 ✅ = 可以开始迁移路由  
部分打勾 ⚠️ = 需要修复问题  
无打勾 ❌ = 回退修改，重新评估

---

## 🚀 现在开始测试

请执行：

```bash
cd /Users/mac/Documents/ai/pi-investment/quantsys-v2
python adapters/inbound/api/server.py
```

然后在另一个终端执行测试命令。

**准备好了吗？我等待您的测试结果！**
