"""
依赖注入实施指南

## 阶段 1: 创建 DI 容器 ✅

已完成文件：
- infrastructure/di/__init__.py
- infrastructure/di/container.py
- infrastructure/di/decorators.py

## 阶段 2: 修改 Flask 应用（server.py）

### 步骤 1: 导入容器

```python
# adapters/inbound/api/server.py
from infrastructure.di.container import Container
```

### 步骤 2: 在 create_app() 中初始化容器

```python
def create_app():
    app = Flask(__name__)
    CORS(app)
    
    # ✅ 初始化依赖注入容器
    container = Container()
    app.container = container
    
    # 初始化数据库引擎
    init_engine(pool_size=10, max_overflow=20)
    
    # 注册 blueprints...
    return app
```

## 阶段 3: 改造路由文件（示例）

### 示例 1: pools.py 改造

**改造前：**
```python
# ❌ 旧代码
_stock_pool_service = None

def _get_services():
    global _stock_pool_service
    if _stock_pool_service is None:
        from adapters.inbound.api.shared import stock_pool_service
        _stock_pool_service = stock_pool_service
    return _stock_pool_service

@pools_bp.route('/api/pools', methods=['GET'])
def list_pools():
    svc = _get_services()
    pools = svc.list_pools()
    return jsonify({'success': True, 'data': pools})
```

**改造后：**
```python
# ✅ 新代码
from infrastructure.di.decorators import inject

@pools_bp.route('/api/pools', methods=['GET'])
@inject
def list_pools(stock_pool_service):
    pools = stock_pool_service.list_pools()
    return jsonify({'success': True, 'data': pools})
```

### 示例 2: 多个服务注入

```python
@pools_bp.route('/api/pools/<int:pool_id>/validate', methods=['POST'])
@inject
def validate_pool(pool_id, stock_pool_service, pool_validation_service):
    # 两个服务都自动注入
    pool = stock_pool_service.get_pool(pool_id)
    validation = pool_validation_service.validate(pool)
    return jsonify({'success': True, 'data': validation})
```

### 示例 3: 路径参数 + 服务注入

```python
@pools_bp.route('/api/pools/<int:pool_id>', methods=['GET'])
@inject
def get_pool(pool_id, stock_pool_service):
    # pool_id 来自路由
    # stock_pool_service 来自容器
    pool = stock_pool_service.get_pool(pool_id)
    return jsonify({'success': True, 'data': pool})
```

## 阶段 4: 逐步迁移策略

### 优先级 P0（先迁移）：
1. ✅ routes/pools.py
2. ✅ routes/strategies.py
3. ✅ routes/signals.py
4. ✅ routes/backtest.py

### 优先级 P1（随后迁移）：
5. routes/market.py
6. routes/portfolio.py
7. 其余 52 个路由文件

### 迁移检查清单：

对于每个路由文件：
- [ ] 删除 `_get_services()` 函数
- [ ] 删除 `global` 变量声明
- [ ] 删除 `from adapters.inbound.api.shared import ...`
- [ ] 添加 `from infrastructure.di.decorators import inject`
- [ ] 为路由函数添加 `@inject` 装饰器
- [ ] 在函数参数中声明需要的服务
- [ ] 测试验证功能正常

## 阶段 5: 清理 shared.py

当所有路由迁移完成后：

```python
# adapters/inbound/api/shared.py
# ⚠️ 标记为废弃，但暂时保留以防回滚

import warnings

warnings.warn(
    "shared.py is deprecated. Use dependency injection instead.",
    DeprecationWarning,
    stacklevel=2
)

# 保留导出以兼容未迁移代码
from infrastructure.di.container import get_container

_container = get_container()

# 兼容性导出（废弃）
ds = _container.data_service()
strategy_service = _container.strategy_service()
# ... 其他服务
```

## 验证测试

### 1. 启动测试
```bash
cd quantsys-v2
python adapters/inbound/api/server.py
```

预期输出：
```
✅ SQLAlchemy Engine initialized
✅ Dependency injection container initialized
 * Running on http://127.0.0.1:5001
```

### 2. API 测试
```bash
# 测试股票池 API
curl http://localhost:5001/api/pools

# 测试健康检查
curl http://localhost:5001/api/health
```

### 3. 单元测试

创建测试用例验证依赖注入：

```python
# tests/test_di_container.py
import pytest
from infrastructure.di.container import Container

def test_container_provides_services():
    container = Container()
    
    # 测试单例服务
    data_service1 = container.data_service()
    data_service2 = container.data_service()
    assert data_service1 is data_service2  # 同一实例
    
    # 测试工厂服务
    pool_service1 = container.stock_pool_service()
    pool_service2 = container.stock_pool_service()
    assert pool_service1 is not pool_service2  # 不同实例

def test_inject_decorator():
    from flask import Flask
    from infrastructure.di.decorators import inject
    
    app = Flask(__name__)
    app.container = Container()
    
    @inject
    def test_func(stock_pool_service):
        return stock_pool_service
    
    with app.app_context():
        service = test_func()
        assert service is not None
```

## 预期收益

### 代码质量
- ✅ 消除全局变量
- ✅ 消除懒加载反模式
- ✅ 依赖关系清晰可见
- ✅ 代码行数减少 20-30%

### 可测试性
- ✅ 可以轻松注入 Mock 对象
- ✅ 单元测试更容易编写
- ✅ 测试覆盖率可提升到 60%+

### 可维护性
- ✅ 新增服务只需在容器中声明
- ✅ 修改依赖关系只需改容器配置
- ✅ 服务生命周期可控

## 下一步

1. **立即执行**: 修改 server.py 集成容器
2. **试点迁移**: 选择 1-2 个简单路由文件测试
3. **逐步推广**: 迁移剩余路由文件
4. **清理遗留**: 废弃 shared.py

---

**准备好开始了吗？**

选择下一步行动：
- A. 修改 server.py 集成容器
- B. 试点迁移一个路由文件（如 pools.py）
- C. 先编写单元测试验证容器
- D. 一次性迁移所有文件
