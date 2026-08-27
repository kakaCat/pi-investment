# 通知系统 + pool_manage get 成员 500 修复记录（2026-08-25）

## 任务来源

用户飞书指令「修复问题」（两次均未细化）→ 按最合理解读：修复全部故障类问题。

## 已确认的两个故障

### 故障 A：通知系统 Warning（非完全故障）

**实测**：`../agent-os/agent-os notify send --channel alerts --title ... --content ... --color blue`
- ✅ 三个渠道（trading/alerts/reports）均能发送，Log ID 正常返回
- ⚠️ 每次都有 Warning：`Failed to initialize auth: failed to read permissions config: open config/permissions.yaml: no such file or directory`

**根因**：`agent-ts/src/infrastructure/tools/notification/notification-tools.ts` 用 exec 调用
`../agent-os/agent-os notify send ...`，`cwd: process.cwd()`（= agent-ts/）。
agent-os 二进制的 auth 初始化在 cwd 下找 `config/permissions.yaml`，找不到。
真实文件在 `agent-os/config/permissions.yaml`（存在，57 行，含 roles/agents 定义）。

**影响**：auth 初始化失败 → 权限校验失效（当前按 warning 降级放行）。属功能缺陷非致命，但必须修。

**修复方向（未定）**：
1. notification-tools.ts 里把 cwd 改为 agent-os 目录，或
2. 给 agent-os 传配置路径参数（internal/config/config.go 有 `AGENT_OS_` env 前缀，待查是否支持 config path）
3. 检查 notify.go:391 `cfg := config.Get()` 上下文

### 故障 B：pool_manage get 成员 500（已复现）

**实测**：
- `GET http://127.0.0.1:5001/api/pools` → ✅ 200，29 池正常
- `GET http://127.0.0.1:5001/api/pools/27` → ❌ 500：`{"success":false,"error":"'NoneType' object has no attribute 'batch_get_names'"}`

**代码路径**：
- `adapters/inbound/fastapi_app/routes/pools_async.py:188` get_pool → `svc.get_pool(pool_id)`
- `svc = stock_pool_service`（shared 层懒加载 → `ServiceFactory.get_stock_pool_service()`）
- `service_factory.py:128` get_stock_pool_service：**优先 `_try_get_from_enhanced(StockPoolService)`**，fallback 旧实现（正确注入 ds.stock + StockPoolORMRepository）
- `stock_pool_service.py:167/177` `get_pool` 调 `self.stock_repo.batch_get_names()` → None 崩

**嫌疑根因**：`EnhancedServiceFactory` 注册了 StockPoolService（enhanced_service_factory.py:123），
若其 dependencies 未正确解析出 IStockRepository（如依赖接口类型但注册缺失/顺序问题），
则 resolve 出 `StockPoolService(stock_repo=None)` 且被 lru_cache 缓存为坏单例 →
所有 get_pool 都崩。list_pools 不调 stock_repo 所以正常。

**下一步**：
1. 看 `_try_get_from_enhanced`（service_factory.py:36）与 enhanced_service_factory.py:123 注册代码
2. 确认 StockPoolService 的 dependencies 声明
3. 在 Python REPL 里实测 `ServiceFactory.get_stock_pool_service()` 的 stock_repo 是否为 None
4. 修复（正确注入 or 修复 Enhanced 注册 or 回退逻辑）

## 最终修复与验证（2026-08-25 10:00 完成）

### 修复清单

1. **quantsys-v2/infrastructure/services/enhanced_service_factory.py**
   - `_infer_dependencies()` 跳过 Optional/Union 注解（origin is Union/Optional）
   - 补 `Union` 导入
2. **quantsys-v2/infrastructure/services/service_factory.py（关键修复）**
   - `get_data_service()` / `get_strategy_code_service()` 在检查 `is_registered` 前
     先调 `_ensure_enhanced_factory()`——**这是运行进程 stock_repo=None 的真正根因**：
     FastAPI import 链（shared.py `from adapters.shared import ds`）先访问 ds →
     get_data_service 时 EnhancedServiceFactory 尚未注册任何服务 → is_registered=False →
     缓存 DataService(stock_repo=None) 坏实例（@lru_cache 永久生效）→
     get_stock_pool_service fallback 拿到 ds.stock=None → batch_get_names 崩
3. **quantsys-v2/infrastructure/persistence/database/engine.py**：补 `import os`
4. **agent-ts/src/infrastructure/tools/notification/notification-tools.ts**
   - cwd 改为 agentOsDir（path.resolve(__dirname, '../../../../../agent-os')，src/dist 结构均正确解析）

### 验证结果

- [x] curl /api/pools/27 → success:true, 30 成员（石头科技/盛美上海/佰维存储...）✅
- [x] agent 工具 pool_manage get pool_id=27 → 30 成员正常返回 ✅
- [x] REPL 模拟 FastAPI import 链 → stock_repo=StockORMRepository ✅
- [x] agent-os 目录下 notify send 无 Warning ✅（agent 重启后 TS 修复生效）
- [x] TSC 编译通过

### 进程说明

backend_control start 使用旧路径 adapters/inbound/api/server.py（已不存在）启动失败；
实际由 supervisor 自动拉起 adapters/inbound/fastapi_app/main.py。
重启方式：kill $(lsof -ti:5001) → supervisor 自动拉起新进程加载新代码。

## 根因定位结论（2026-08-25 第二轮，已确认）

### 故障 B 根因（pool get 成员 500）

链路：`GET /api/pools/{id}` → pools_async.py → shared.stock_pool_service（懒加载）
→ `ServiceFactory.get_stock_pool_service()` → 优先 `_try_get_from_enhanced(StockPoolService)`。

实际崩溃点：`EnhancedServiceFactory` 注册 FinancialDataService 时，
`ServiceDescriptor._infer_dependencies()` 从构造函数签名推断依赖：
`FinancialDataService.__init__(self, providers: Optional[List] = None, ...)`
→ 把 `Optional[List]` 注解当作依赖 → `resolve(Optional[List])` →
`ValueError: Service not registered: Optional` → `_try_get_from_enhanced` 捕获后返回 None →
fallback 旧实现 `StockPoolService(ds.stock, ...)`，但 ds.stock 也可能因同样链路损坏。

**已修复（2026-08-25）**：`infrastructure/services/enhanced_service_factory.py`
`_infer_dependencies()` 增加 Optional/Union 注解跳过逻辑（origin is Union or origin is Optional），
并补 `Union` 导入。验证：`Optional[List].__origin__ is Union` = True ✓。

REPL 实测复现（修复前）：`ServiceFactory.get_stock_pool_service()` →
`ValueError: Service not registered: Optional`（traceback 指向 factories.py:42
→ EnhancedServiceFactory.resolve(FinancialDataService)）。

### 故障 A 根因（通知 Warning）

agent-os 二进制 root.go PersistentPreRun 用 `filepath.Join("config", "permissions.yaml")`
相对 cwd 找权限配置。agent-ts 的 notification-tools.ts 以 cwd=process.cwd()（agent-ts/）
exec `../agent-os/agent-os notify send` → agent-os 在 agent-ts/config/ 下找不到 → Warning。
真实文件在 agent-os/config/permissions.yaml（存在，57 行）。

修复方向（待实施）：
1. notification-tools.ts 中 exec 时把 cwd 设为 agent-os 目录，或
2. 检查 agent-os 是否支持 AGENT_OS_ 环境变量覆盖权限路径；
   最简方案：exec cwd 改为 agent-os 目录（config.AddConfigPath 支持 . 和 ./configs）

### 注意：运行进程 PID 37631 09:41 启动（hotfix 后），改代码后必须重启后端才生效
（lsof -ti:5001 确认 PID → kill → supervisor 自动拉起 或 backend_control restart）。
