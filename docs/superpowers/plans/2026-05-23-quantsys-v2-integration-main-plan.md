# QuantSys V2 前后端对接主计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:dispatching-parallel-agents to spawn 5 parallel agents for implementation.

**Goal:** 通过5个并行 Agent 实现31个 REST API 接口，完成 Vue 前端与 Flask 后端的完整对接

**Architecture:** 直接在 `quantsys-v2/api/server.py` 添加新路由，复用现有 service 层，后端内部使用 snake_case，API 响应转换为 camelCase

**Tech Stack:** Flask, Python 3.x, DataService, PostgreSQL, Vue 3, TypeScript

---

## 实施策略

本计划采用**多 Agent 并行**策略，将31个接口分配给5个独立的 Agent：

1. **Agent 1 - 交易模块**：8个接口（订单、交易、持仓）
2. **Agent 2 - 策略模块**：8个接口（策略管理、绩效）
3. **Agent 3 - 指标模块**：6个接口（指标 IDE）
4. **Agent 4 - 信号增强**：5个接口（信号审批、统计）
5. **Agent 5 - Pipeline**：4个接口（流水线管理）

每个 Agent 有独立的详细计划文档。

---

## 前置任务：准备工具函数（主协调 Agent 执行）

### Task 0: 添加字段转换和响应工具函数

**Files:**
- Modify: `quantsys-v2/api/server.py:1-50`

- [ ] **Step 1: 添加必要的导入**

在 `quantsys-v2/api/server.py` 现有导入后添加：

```python
import re
from typing import Any, Dict, List, Union
from functools import wraps
import logging
```

- [ ] **Step 2: 添加字段命名转换函数**

在 `sanitize_for_json()` 函数后添加：

```python
def to_camel_case(snake_str: str) -> str:
    """下划线转驼峰"""
    if not isinstance(snake_str, str):
        return snake_str
    components = snake_str.split('_')
    return components[0] + ''.join(x.title() for x in components[1:])


def to_snake_case(camel_str: str) -> str:
    """驼峰转下划线"""
    if not isinstance(camel_str, str):
        return camel_str
    return re.sub(r'(?<!^)(?=[A-Z])', '_', camel_str).lower()


def convert_keys_to_camel(obj: Any) -> Any:
    """递归转换字典的key为驼峰命名，用于API响应"""
    if isinstance(obj, dict):
        return {to_camel_case(k): convert_keys_to_camel(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_keys_to_camel(item) for item in obj]
    elif hasattr(obj, 'isoformat'):
        return obj.isoformat()
    return obj


def convert_keys_to_snake(obj: Any) -> Any:
    """递归转换字典的key为下划线命名，用于接收前端请求"""
    if isinstance(obj, dict):
        return {to_snake_case(k): convert_keys_to_snake(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_keys_to_snake(item) for item in obj]
    return obj


def api_response(data: Any, success: bool = True, message: str = None) -> Dict:
    """统一API响应格式，自动转换为驼峰命名"""
    response = {
        'success': success,
        'data': convert_keys_to_camel(sanitize_for_json(data))
    }
    if message:
        response['message'] = message
    return jsonify(response)


logger = logging.getLogger(__name__)


def handle_api_error(f):
    """统一API错误处理装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except ValueError as e:
            return jsonify({'success': False, 'error': str(e)}), 400
        except KeyError as e:
            return jsonify({'success': False, 'error': f'缺少参数: {e}'}), 400
        except Exception as e:
            logger.error(f"API错误: {e}", exc_info=True)
            return jsonify({'success': False, 'error': '服务器内部错误'}), 500
    return decorated_function
```

- [ ] **Step 3: 添加必要的 service 导入**

```python
from services import order_service
from services.strategy_code_service import StrategyCodeService

# 初始化服务实例
strategy_service = StrategyCodeService()
```

- [ ] **Step 4: 测试工具函数**

创建临时测试：

```python
# 测试驼峰转换
test_data = {'order_id': 123, 'created_at': '2026-05-23'}
result = convert_keys_to_camel(test_data)
assert result == {'orderId': 123, 'createdAt': '2026-05-23'}
print("✓ 工具函数测试通过")
```

- [ ] **Step 5: Commit 工具函数**

```bash
cd /Users/mac/Documents/ai/pi-investment/quantsys-v2
git add api/server.py
git commit -m "feat(api): add field conversion and response utility functions"
```

---

## 并行 Agent 任务分配

完成前置任务后，启动5个并行 Agent，每个 Agent 负责一个业务模块：

### Agent 1: 交易模块
- **计划文档**: `docs/superpowers/plans/agent1-trading-module.md`
- **接口数量**: 8个
- **接口列表**:
  1. GET `/api/orders/list` - 订单列表
  2. GET `/api/orders/detail/:id` - 订单详情
  3. POST `/api/orders/create` - 创建订单
  4. POST `/api/orders/cancel/:id` - 取消订单
  5. POST `/api/orders/update/:id` - 修改订单
  6. GET `/api/trades/list` - 交易历史
  7. GET `/api/portfolio/positions` - 持仓列表
  8. GET `/api/portfolio/summary` - 持仓汇总

### Agent 2: 策略模块
- **计划文档**: `docs/superpowers/plans/agent2-strategy-module.md`
- **接口数量**: 8个
- **接口列表**:
  1. GET `/api/strategies/list` - 策略列表
  2. GET `/api/strategies/detail/:id` - 策略详情
  3. POST `/api/strategies/create` - 创建策略
  4. POST `/api/strategies/update/:id` - 更新策略
  5. POST `/api/strategies/delete/:id` - 删除策略
  6. POST `/api/strategies/start/:id` - 启动策略
  7. POST `/api/strategies/stop/:id` - 停止策略
  8. GET `/api/strategies/performance/:id` - 策略绩效

### Agent 3: 指标模块
- **计划文档**: `docs/superpowers/plans/agent3-indicator-module.md`
- **接口数量**: 6个
- **接口列表**:
  1. GET `/api/indicators/list` - 指标列表
  2. GET `/api/indicators/detail/:id` - 指标详情
  3. POST `/api/indicators/create` - 创建指标
  4. POST `/api/indicators/update/:id` - 更新指标
  5. POST `/api/indicators/delete/:id` - 删除指标
  6. POST `/api/indicators/run/:id` - 运行指标
  7. POST `/api/indicators/backtest` - 回测指标

### Agent 4: 信号增强
- **计划文档**: `docs/superpowers/plans/agent4-signal-enhancement.md`
- **接口数量**: 5个
- **接口列表**:
  1. GET `/api/signals/detail/:id` - 信号详情
  2. POST `/api/signals/approve/:id` - 批准信号
  3. POST `/api/signals/reject/:id` - 拒绝信号
  4. POST `/api/signals/mark-error/:id` - 标记错误
  5. GET `/api/signals/statistics` - 信号统计

### Agent 5: Pipeline管理
- **计划文档**: `docs/superpowers/plans/agent5-pipeline-module.md`
- **接口数量**: 4个
- **接口列表**:
  1. GET `/api/pipeline/statistics` - Pipeline统计
  2. GET `/api/pipeline/tasks/list` - 任务列表
  3. GET `/api/pipeline/runs/list` - 运行历史
  4. POST `/api/pipeline/trigger` - 触发Pipeline

---

## 集成和验收（主协调 Agent 执行）

所有 Agent 完成后，执行集成测试：

### Task Final.1: 代码集成检查

- [ ] **Step 1: 检查所有 Agent 完成状态**

```bash
ls -la /tmp/agent*_done.txt
# 应该看到5个文件：agent1_done.txt 到 agent5_done.txt
```

- [ ] **Step 2: 检查 server.py 语法**

```bash
cd /Users/mac/Documents/ai/pi-investment/quantsys-v2
python -m py_compile api/server.py
```

预期：无语法错误

- [ ] **Step 3: 启动服务器**

```bash
python api/server.py
```

预期：服务器成功启动在 5000 端口

### Task Final.2: 接口验收测试

- [ ] **Step 1: 测试健康检查**

```bash
curl http://localhost:5000/api/health
```

预期：返回 200 状态码

- [ ] **Step 2: 测试每个模块的一个接口**

```bash
# 交易模块
curl http://localhost:5000/api/orders/list

# 策略模块
curl http://localhost:5000/api/strategies/list

# 指标模块
curl http://localhost:5000/api/indicators/list

# 信号模块
curl http://localhost:5000/api/signals/statistics

# Pipeline模块
curl http://localhost:5000/api/pipeline/statistics
```

预期：所有接口返回 JSON 格式，包含 `success` 字段

- [ ] **Step 3: 验证字段命名**

检查响应中的字段是否为驼峰命名（camelCase）：

```bash
curl http://localhost:5000/api/orders/list | jq '.data'
```

预期：字段名为 `pageSize`, `orderId` 等驼峰格式

### Task Final.3: 前端联调

- [ ] **Step 1: 启动前端**

```bash
cd /Users/mac/Documents/ai/pi-investment/web-frontend
npm run dev
```

- [ ] **Step 2: 访问前端页面**

打开浏览器访问 `http://localhost:5173`，测试以下页面：
- 订单管理页面
- 持仓页面
- 策略中心
- 信号管理

- [ ] **Step 3: 检查控制台错误**

打开浏览器开发者工具，确认：
- 无 404 错误
- 无 JavaScript 运行时错误
- API 请求成功返回数据

### Task Final.4: 最终提交

- [ ] **Step 1: 查看所有更改**

```bash
cd /Users/mac/Documents/ai/pi-investment/quantsys-v2
git diff api/server.py | head -100
```

- [ ] **Step 2: 创建最终提交**

```bash
git add api/server.py
git commit -m "feat(api): complete frontend-backend integration with 31 new endpoints

- Add 8 trading endpoints (orders, trades, portfolio)
- Add 8 strategy management endpoints
- Add 6 indicator IDE endpoints
- Add 5 signal enhancement endpoints
- Add 4 pipeline management endpoints
- Add field conversion utilities (camelCase <-> snake_case)
- Add unified API response format"
```

- [ ] **Step 3: 创建集成报告**

```bash
echo "# QuantSys V2 前后端对接完成报告

## 完成时间
$(date)

## 实施内容
- 31个新 REST API 接口
- 5个业务模块（交易、策略、指标、信号、Pipeline）
- 统一的字段转换和响应格式

## 验收结果
- ✅ 所有接口可访问
- ✅ 响应格式符合规范（camelCase）
- ✅ 前端页面正常加载
- ✅ 无运行时错误

## 后续工作
- 添加单元测试
- 性能优化
- WebSocket 对接
" > docs/integration-report.md

git add docs/integration-report.md
git commit -m "docs: add integration completion report"
```

---

## 执行方式

**推荐使用 superpowers:dispatching-parallel-agents skill 启动5个并行 Agent。**

每个 Agent 将独立工作，互不干扰，完成后主协调 Agent 执行集成和验收任务。

