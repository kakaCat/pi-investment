# Phase 2 任务 4: 路由注册失败时中断启动

**目标**: 核心路由注册失败时中断启动，非核心路由失败时告警但继续

## 实现方案

### 核心路由（P0 - CRITICAL）
注册失败时抛出 RuntimeError，中断应用启动

**定义标准**:
- agent-ts 依赖的核心 API
- 健康检查端点
- 认证授权
- 调度器 webhook（Agent OS 集成）

**核心路由清单**:
1. `health` - 健康检查（监控依赖）
2. `auth` - 认证授权（安全基础）
3. `config` - 配置管理（系统配置）
4. `scheduler_webhook` - Agent OS 调度器集成（关键依赖）

### 可选路由（P1 - OPTIONAL）
注册失败时记录 warning，但不中断启动

**定义标准**:
- 业务功能路由
- 数据查询路由
- 分析工具路由

### 实现代码

```python
def register_routes():
    """注册所有路由 —— 核心路由失败时中断启动"""
    
    # ===== P0 核心路由 —— 失败时中断 =====
    CRITICAL_ROUTES = [
        ('health', 'adapters.inbound.fastapi_app.routes.health_async'),
        ('auth', 'adapters.inbound.fastapi_app.routes.auth_async', '/api'),
        ('config', 'adapters.inbound.fastapi_app.routes.config_async', '/api'),
        ('scheduler_webhook', 'api.internal.scheduler_webhook', None),
    ]
    
    for route_info in CRITICAL_ROUTES:
        name = route_info[0]
        module_path = route_info[1]
        prefix = route_info[2] if len(route_info) > 2 else None
        
        try:
            module = __import__(module_path, fromlist=['router'])
            router = getattr(module, 'router')
            if prefix:
                app.include_router(router, prefix=prefix)
            else:
                app.include_router(router)
            logger.info(f"✅ Registered (CRITICAL): {name}")
        except (ImportError, AttributeError) as e:
            logger.error(f"❌ CRITICAL route failed: {name} - {e}")
            raise RuntimeError(f"Critical route '{name}' failed to register: {e}") from e
    
    # ===== P1 业务路由 —— 失败时告警但继续 =====
    OPTIONAL_ROUTES = [
        ('executions', 'adapters.inbound.fastapi_app.routes.executions_async'),
        ('market', 'adapters.inbound.fastapi_app.routes.market_async', '/api'),
        ('analysis', 'adapters.inbound.fastapi_app.routes.analysis_async'),
        ('market_data', 'adapters.inbound.fastapi_app.routes.market_data_async'),
        ('quote_market', 'adapters.inbound.fastapi_app.routes.quote_market_async'),
        ('charts', 'adapters.inbound.fastapi_app.routes.charts_async', '/api'),
        ('portfolio_opt', 'adapters.inbound.fastapi_app.routes.portfolio_opt_async'),
        ('factor_models', 'adapters.inbound.fastapi_app.routes.factor_models_async'),
        # ... 其他路由
    ]
    
    failed_routes = []
    for route_info in OPTIONAL_ROUTES:
        name = route_info[0]
        module_path = route_info[1]
        prefix = route_info[2] if len(route_info) > 2 else None
        
        try:
            module = __import__(module_path, fromlist=['router'])
            router = getattr(module, 'router')
            if prefix:
                app.include_router(router, prefix=prefix)
            else:
                app.include_router(router)
            logger.info(f"✅ Registered: {name}")
        except (ImportError, AttributeError) as e:
            logger.warning(f"⚠️ Optional route failed: {name} - {e}")
            failed_routes.append(name)
    
    # 启动报告
    logger.info("=" * 60)
    logger.info(f"Routes registered: {len(CRITICAL_ROUTES) + len(OPTIONAL_ROUTES) - len(failed_routes)} total")
    logger.info(f"  Critical: {len(CRITICAL_ROUTES)} (all must succeed)")
    logger.info(f"  Optional: {len(OPTIONAL_ROUTES) - len(failed_routes)}/{len(OPTIONAL_ROUTES)}")
    if failed_routes:
        logger.warning(f"  Failed: {failed_routes}")
    logger.info("=" * 60)
```

### 预期效果

**成功情况**:
```
✅ Registered (CRITICAL): health
✅ Registered (CRITICAL): auth
✅ Registered (CRITICAL): config
✅ Registered (CRITICAL): scheduler_webhook
✅ Registered: executions
⚠️ Optional route failed: charts - No module named 'polars'
============================================================
Routes registered: 52 total
  Critical: 4 (all must succeed)
  Optional: 48/49
  Failed: ['charts']
============================================================
```

**失败情况**（核心路由失败）:
```
✅ Registered (CRITICAL): health
❌ CRITICAL route failed: auth - No module named 'xxx'
RuntimeError: Critical route 'auth' failed to register: No module named 'xxx'
[应用启动中断]
```

### 好处

1. **快速失败** - 核心功能缺失时立即发现，避免半残状态
2. **明确依赖** - 清晰区分哪些是关键依赖
3. **容错性** - 非核心功能失败不影响基本服务
4. **可观测性** - 启动报告清晰展示注册状态

### 风险

| 风险 | 可能性 | 影响 | 缓解措施 |
|------|--------|------|---------|
| 核心路由定义不准确 | 低 | 中 | 基于实际依赖分析 |
| 环境问题导致启动失败 | 中 | 高 | 提供清晰的错误信息 |

### 测试验证

```bash
# 1. 正常启动测试
python adapters/inbound/fastapi_app/main.py

# 2. 模拟核心路由失败（修改 import 路径）
# 应该看到 RuntimeError 并启动失败

# 3. 模拟可选路由失败
# 应该看到 warning 但启动成功
```
