# Web接口404问题修复报告

**日期**: 2026-06-29  
**问题**: Web前端访问API返回404错误

## 问题分析

### 根本原因

系统使用 **Python 3.8.10**（默认版本），不支持代码中的 `Dict | List` 类型联合语法（该语法需要Python 3.10+），导致路由模块导入失败。

### 影响范围

- `/api/sentiment/market` 
- `/api/signals/scan`
- 以及其他多个API端点（总共88个端点未注册）

## 解决方案

### 1. 修复类型注解（已完成）

将所有路由文件中的类型联合语法替换为兼容的写法：

```python
# 修复前
data: Optional[Dict | List] = None

# 修复后  
data: Optional[Any] = None
```

**修复的文件**（共15个）：
- `signals_async.py`
- `p1_batch_async.py`
- `p2_batch1_async.py`
- `p2_batch2_async.py`
- `market_async.py`
- `executions_async.py`
- `decision_tracking_async.py`
- `pool_scan_async.py`
- `charts_async.py`
- `risk_async.py`
- `backtest_async.py`
- `realtime_signals_async.py`
- `pools_async.py`
- `strategies_async.py`
- 并添加 `from typing import Any` 到所有文件

### 2. 修复路由注册（已完成）

修正 `main.py` 中 p2_batch1_async 和 p2_batch2_async 的导入方式：

```python
# 修复前（错误）
from .routes.p2_batch1_async import router as p2_batch1_router

# 修复后（正确）
from .routes import p2_batch1_async
app.include_router(p2_batch1_async.diagnosis_router, prefix="/api")
app.include_router(p2_batch1_async.dividends_router, prefix="/api")
# ... 其他子路由
```

### 3. Python版本统一（已完成）

#### 创建启动脚本

- `start.sh`: 明确使用 Python 3.13 启动
- `start_with_py313.sh`: 备用脚本

#### Homebrew符号链接

在 `/opt/homebrew/bin/` 创建链接：
```bash
python3 -> python3.13
python -> python3.13
pip3 -> pip3.13
pip -> pip3.13
```

#### 推荐启动方式

```bash
cd quantsys-v2
./start.sh
```

## 验证结果

### ✅ 所有问题已解决

1. **API端点恢复**
   - sentiment/market: ✅ 正常
   - signals/scan: ✅ 正常
   - 已注册端点: **90个**（从原来的2个）

2. **端点分类**
   - sentiment相关: 2个
   - signal相关: 11个
   - 其他: 77个

3. **代码兼容性**
   - 所有类型注解已修改为兼容 Python 3.8+
   - 同时支持 Python 3.13 的原生类型联合语法

## 系统配置

### Python版本

- 系统默认: Python 3.8.10 (`/usr/local/bin/python3`)
- Conda: Python 3.12.8 (`/opt/miniconda3/bin/python`)
- Homebrew: Python 3.13.12 (`/opt/homebrew/bin/python3.13`) **← 推荐使用**

### 启动服务

```bash
# 方式1: 使用统一启动脚本（推荐）
cd quantsys-v2
./start.sh

# 方式2: 手动指定Python版本
/opt/homebrew/bin/python3.13 start_all.py

# 方式3: 使用备用脚本
./start_with_py313.sh
```

### 验证服务

```bash
# 检查端点数量
curl -s http://127.0.0.1:5001/openapi.json | python3 -c "import sys, json; print(len(json.load(sys.stdin).get('paths', {})))"

# 测试具体端点
curl http://127.0.0.1:5001/api/sentiment/market
curl -X POST http://127.0.0.1:5001/api/signals/scan -H "Content-Type: application/json" -d '{}'
```

## 相关文档

- `README_PYTHON.md`: Python版本配置说明
- `start.sh`: 统一启动脚本
- `start_with_py313.sh`: 备用启动脚本

## 经验教训

1. **类型注解兼容性**: Python 3.10+ 的类型联合语法 `X | Y` 在旧版本中会导致语法错误
2. **端口冲突检测**: 启动前需要检查端口占用，避免多个实例冲突
3. **Python版本管理**: 系统中存在多个Python版本时，需要明确指定使用哪个版本
4. **路由注册验证**: 路由显示"已注册"不代表实际可用，需要检查 OpenAPI 文档确认

## 后续建议

1. 在 CI/CD 中添加 Python 版本检查
2. 考虑使用 `pyproject.toml` 明确指定 Python >= 3.10
3. 或者保持使用 `Optional[Any]` 以兼容更多Python版本
