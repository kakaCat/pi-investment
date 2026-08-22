# 服务配置说明

## 配置文件结构

```
config/
├── services.yaml       # 基础配置（所有环境共享）
├── services.dev.yaml   # 开发环境覆盖
├── services.test.yaml  # 测试环境覆盖
└── services.prod.yaml  # 生产环境覆盖
```

## 配置格式

### 基础结构

```yaml
version: '1.0'
description: '配置描述'

repositories:
  <name>:
    interface: <接口路径>
    implementation: <实现路径>
    lifecycle: singleton|transient|scoped
    config: {}
    enabled: true
    description: '描述'

services:
  <name>:
    class: <类路径>
    lifecycle: singleton|transient|scoped
    dependencies:
      <参数名>: <依赖服务名>
    config: {}
    enabled: true
    description: '描述'

environments:
  dev:
    services: {}
    repositories: {}
```

### 服务注册方式

#### 1. 直接类路径

```yaml
services:
  chan_service:
    class: application.services.chan_service.ChanService
    lifecycle: singleton
    dependencies:
      kline_repo: repositories.kline
```

#### 2. 接口-实现（用于 Repository）

```yaml
repositories:
  stock:
    interface: domain.ports.IStockRepository
    implementation: adapters.outbound.repositories.StockORMRepository
    lifecycle: singleton
```

等价于：

```yaml
services:
  repositories.stock:
    interface: domain.ports.IStockRepository
    implementation: adapters.outbound.repositories.StockORMRepository
    lifecycle: singleton
```

#### 3. 工厂函数（复杂初始化）

```yaml
services:
  data_service:
    class: application.services.data_service.DataService
    factory: infrastructure.factories.create_data_service
    lifecycle: singleton
```

## 依赖引用

### 引用 Repository

```yaml
services:
  chan_service:
    class: application.services.chan_service.ChanService
    dependencies:
      kline_repo: repositories.kline  # 引用 repositories 下的 kline
```

### 引用其他服务

```yaml
services:
  chan_scan_service:
    class: application.services.chan_scan_service.ChanScanService
    dependencies:
      chan_service: chan_service  # 引用 services 下的 chan_service
      pool_repo: repositories.stock_pool
```

### 依赖自动解析

ServiceFactory 会根据类型注解自动解析依赖：

```python
class ChanService:
    def __init__(self, kline_repo: IKlineRepository):
        # ServiceFactory 会自动查找 IKlineRepository 的实现
        pass
```

## 环境特定配置

### 环境检测

环境通过以下方式确定（优先级从高到低）：

1. `QUANTSYS_ENV` 环境变量
2. `PYTHON_ENV` 环境变量
3. 默认为 `dev`

```bash
# 设置环境
export QUANTSYS_ENV=prod

# 或
export PYTHON_ENV=test
```

### 配置合并

环境配置会覆盖基础配置：

```yaml
# services.yaml（基础）
services:
  data_service:
    config:
      cache_enabled: true
      debug: false

# services.dev.yaml（开发环境）
services:
  data_service:
    config:
      debug: true  # 覆盖 debug，cache_enabled 保持 true
```

最终开发环境配置：

```yaml
data_service:
  config:
    cache_enabled: true  # 来自基础配置
    debug: true          # 来自环境配置
```

## 环境变量覆盖

可以使用环境变量覆盖服务配置：

```bash
# 格式：QUANTSYS_SERVICE_<service_name>_<config_key>=value
export QUANTSYS_SERVICE_data_service_cache_enabled=false
export QUANTSYS_SERVICE_watch_engine_check_interval=60
```

支持的值类型：
- `true`/`false` → bool
- 数字 → int/float
- 其他 → string

## 服务生命周期

### SINGLETON（单例）

每次解析返回同一个实例：

```yaml
services:
  data_service:
    lifecycle: singleton
```

适用于：
- 无状态服务
- 共享资源（数据库连接池、缓存）
- 大部分 Application 服务

### TRANSIENT（瞬态）

每次解析创建新实例：

```yaml
services:
  report_generator:
    lifecycle: transient
```

适用于：
- 有状态服务
- 短生命周期任务

### SCOPED（作用域）

同一作用域内返回同一实例：

```yaml
services:
  request_context:
    lifecycle: scoped
```

适用于：
- HTTP 请求处理
- 事务上下文

## 配置验证

### 命令行验证

```bash
cd quantsys-v2
python -m infrastructure.config.validator config/services.yaml
```

### 程序化验证

```python
from infrastructure.config import ConfigLoader, ConfigValidator

loader = ConfigLoader()
config = loader.load()

validator = ConfigValidator(strict=True)
errors = validator.validate(config)

if errors:
    for error in errors:
        print(error)
```

## 使用示例

### 加载配置并注册服务

```python
from infrastructure.config import load_config
from infrastructure.services import EnhancedServiceFactory

# 1. 加载配置
config = load_config()  # 自动检测环境

# 2. 从配置注册服务
EnhancedServiceFactory.register_from_config(config)

# 3. 解析服务
from application.services.chan_service import ChanService
chan_service = EnhancedServiceFactory.resolve(ChanService)
```

### 指定环境

```python
config = load_config(environment='prod')
```

### 访问服务配置

```python
# 获取服务的 config 字段
data_service = EnhancedServiceFactory.resolve(DataService)
cache_enabled = data_service.config.get('cache_enabled', True)
```

## 最佳实践

### 1. 基础配置保持通用

`services.yaml` 应包含所有环境共享的配置，具体参数放在环境配置中。

### 2. 环境配置只覆盖差异

不要在环境配置中重复基础配置，只写需要覆盖的部分。

### 3. 使用描述字段

为每个服务添加 `description`，便于理解：

```yaml
services:
  chan_service:
    class: application.services.chan_service.ChanService
    description: '缠论分析服务 - 提供笔、段、中枢识别'
```

### 4. 敏感信息使用环境变量

不要在配置文件中硬编码密码、API Key：

```yaml
services:
  external_api:
    config:
      # ❌ 错误
      api_key: 'sk-1234567890abcdef'
      
      # ✅ 正确：从环境变量读取
      # 在代码中：os.environ.get('EXTERNAL_API_KEY')
```

### 5. 禁用不需要的服务

测试时禁用不必要的服务：

```yaml
# services.test.yaml
services:
  watch_engine:
    enabled: false  # 测试时禁用盯盘
```

### 6. 使用工厂函数处理复杂初始化

当服务初始化逻辑复杂时，使用工厂函数：

```yaml
services:
  data_service:
    factory: infrastructure.factories.create_data_service
```

```python
# infrastructure/factories.py
def create_data_service():
    # 复杂的初始化逻辑
    stock_repo = EnhancedServiceFactory.resolve(IStockRepository)
    kline_repo = EnhancedServiceFactory.resolve(IKlineRepository)
    # ... 其他依赖
    
    return DataService(
        stock_repo=stock_repo,
        kline_repo=kline_repo,
        # ... 其他参数
    )
```

## 迁移指南

### 从硬编码注册迁移到配置驱动

#### 之前（硬编码）

```python
# infrastructure/services/service_registry.py
from application.services.chan_service import ChanService

def create_chan_service():
    kline_repo = EnhancedServiceFactory.resolve(IKlineRepository)
    return ChanService(kline_repo=kline_repo)

EnhancedServiceFactory.register(
    ChanService,
    factory=create_chan_service,
    lifecycle=ServiceLifecycle.SINGLETON
)
```

#### 之后（配置驱动）

```yaml
# config/services.yaml
services:
  chan_service:
    class: application.services.chan_service.ChanService
    lifecycle: singleton
    dependencies:
      kline_repo: repositories.kline
```

```python
# infrastructure/services/service_registry.py
from infrastructure.config import load_config

def register_all_services():
    config = load_config()
    EnhancedServiceFactory.register_from_config(config)
```

### 渐进式迁移

1. 保留原有硬编码注册
2. 添加配置文件注册
3. 两套系统并存测试
4. 逐步移除硬编码

```python
def register_all_services():
    # Phase 1: 从配置加载
    try:
        config = load_config()
        EnhancedServiceFactory.register_from_config(config)
    except FileNotFoundError:
        # Phase 2: 降级到硬编码（向后兼容）
        register_hardcoded_services()
```

## 故障排查

### 配置文件不存在

```
FileNotFoundError: Base config file not found: /path/to/config/services.yaml
```

解决：创建配置文件或检查路径。

### 依赖未找到

```
[INVALID_DEPENDENCY] chan_service: Dependency 'kline_repository' not found
```

解决：检查依赖名称，确保引用的服务已定义。

### 循环依赖

```
[CIRCULAR_DEPENDENCY] service_a: Circular dependency detected: service_a -> service_b -> service_a
```

解决：重构服务依赖，引入中间层或使用延迟初始化。

### 类无法导入

```
[MODULE_NOT_FOUND] chan_service: Cannot import module 'application.services.chan_service'
```

解决：检查类路径是否正确，模块是否存在。

## 参考

- [P2-3 实施计划](../docs/P2-3-implementation-plan.md)
- [P2-1 依赖注入标准化](../docs/P2-1-completion-report.md)
- [P2-2 ServiceFactory 实施](../docs/P2-2-completion-report.md)
