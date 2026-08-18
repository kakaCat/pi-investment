# Phase 2 执行计划：Flask 删除预检查

**日期**: 2026-08-18  
**分支**: `feat/phase2-architecture-cleanup`  
**风险等级**: 🔴 HIGH - 删除操作不可逆

---

## ⚠️ 风险评估

**删除内容**: 62个Flask路由文件 + 多个Flask核心文件  
**影响范围**: 如果有遗漏的依赖，可能导致服务无法启动  
**回滚方案**: Git revert 或从 main 分支恢复

---

## 📋 删除前检查清单

### 1. 确认 FastAPI 已全面接管

根据 CLAUDE.md 文档：
> ⚠️ 重要: Flask → FastAPI 迁移（2026-08-02 更新：已切换）
> 
> **现状**：生产 5001 端口自 2026-08-02 起由 FastAPI 提供服务。
> Flask 已停止，仅保留作紧急回滚。

**结论**: ✅ 已确认 FastAPI 是当前生产服务

### 2. FastAPI vs Flask 路由对比

| 指标 | Flask | FastAPI | 状态 |
|------|-------|---------|------|
| 路由文件数 | 62 | 58 | FastAPI 基本覆盖 |
| Parity 路由 | - | 2个 (charts, backtest) | 需删除 |
| 启动入口 | server.py | main.py | FastAPI 生产中 |

### 3. 依赖检查

需要确认是否有代码还在导入 Flask 模块：

```bash
# 检查是否有代码导入 Flask routes
grep -r "from adapters.inbound.api.routes" quantsys-v2 --include="*.py" | grep -v ".pyc"
grep -r "from api.routes" quantsys-v2 --include="*.py" | grep -v ".pyc"
```

---

## 🗑️ 删除清单

### 阶段1: 删除 Flask 路由目录（62个文件）

```bash
rm -rf adapters/inbound/api/routes/
```

**包含文件**:
- 62个路由定义文件 (*.py)
- __init__.py
- 可能的 __pycache__

### 阶段2: 删除 Flask 核心文件

```bash
# 删除启动和基础设施文件
rm adapters/inbound/api/server.py
rm adapters/inbound/api/server_websocket.py
rm adapters/inbound/api/decorators.py
rm adapters/inbound/api/error_handlers.py
rm adapters/inbound/api/models.py
rm adapters/inbound/api/response_builder.py
rm adapters/inbound/api/shared.py
rm adapters/inbound/api/websocket.py
rm adapters/inbound/api/validators.py
rm adapters/inbound/api/test_server.py
rm adapters/inbound/api/ml_routes.py
```

### 阶段3: 保留文件（兼容性）

**保留**:
- `adapters/inbound/api/__init__.py` - 兼容旧 import
- `adapters/inbound/api/MIGRATION_GUIDE.py` - 供参考

---

## 🔧 代码修改

### 修改1: 删除 main.py 中的 Flask parity 路由

**文件**: `adapters/inbound/fastapi_app/main.py`

**删除内容**:
```python
# 删除 charts parity
from adapters.inbound.fastapi_app.routes.charts_async import flask_parity_router as charts_flask_parity_router
app.include_router(charts_flask_parity_router)

# 删除 backtest parity
from adapters.inbound.fastapi_app.routes.backtest_async import flask_parity_router as backtest_flask_parity_router
app.include_router(backtest_flask_parity_router)
```

### 修改2: 更新 CLAUDE.md

**文件**: `quantsys-v2/CLAUDE.md`

**删除章节**: Flask 相关启动命令和说明

---

## ✅ 执行前验证

### 1. 备份关键文件（可选）

```bash
# 创建备份目录
mkdir -p /tmp/flask-backup-2026-08-18

# 备份 Flask 目录
cp -r adapters/inbound/api /tmp/flask-backup-2026-08-18/
```

### 2. 检查是否有其他依赖

```bash
# 搜索可能的导入
rg "from.*api\.routes" quantsys-v2/
rg "import.*api\.routes" quantsys-v2/
rg "from.*api\.server" quantsys-v2/
```

### 3. 确认测试覆盖

```bash
# 检查是否有 Flask 相关测试
find quantsys-v2/tests -name "*flask*" -o -name "*api_test*"
```

---

## 🚨 回滚计划

如果删除后发现问题：

### 方案1: Git Revert
```bash
git revert HEAD
```

### 方案2: 从备份恢复
```bash
cp -r /tmp/flask-backup-2026-08-18/api adapters/inbound/
```

### 方案3: 从 main 分支恢复
```bash
git checkout main -- adapters/inbound/api
```

---

## 📊 预期结果

删除后：
- adapters/inbound/api/routes/ - **删除**
- adapters/inbound/api/*.py (除 __init__.py 和 MIGRATION_GUIDE.py) - **删除**
- FastAPI 继续正常运行
- 代码库减少约 3000-4000 行代码

---

## ⏭️ 下一步

执行删除后，需要：
1. 运行 FastAPI 启动测试
2. 检查路由注册
3. 提交变更
4. 执行任务 4：路由注册失败时中断启动

---

**状态**: ⏸️ 等待确认后执行  
**建议**: 先执行依赖检查，确认无遗漏后再删除
