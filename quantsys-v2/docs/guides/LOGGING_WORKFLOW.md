# 日志标准化工作流规范

## 🎯 目标

将 quantsys-v2 项目从传统日志（logging）迁移到结构化日志（structlog），分阶段执行，确保每个阶段稳定后再进入下一阶段。

---

## 📋 阶段划分与门禁

### Phase 0: 启动文件统一（P0）

**范围**：
- `start_all.py`
- `fastapi_app/main.py`
- `fastapi_app/websocket_server.py`
- `simulation_trader.py`
- `simulation_broker.py`

**任务**：
- 删除所有 `logging.basicConfig()` 调用
- 使用 `configure_structured_logging()` 统一配置
- 确保启动时日志格式一致

**完成标准（门禁）**：

- [ ] ✅ 所有启动文件使用 `configure_structured_logging()`
- [ ] ✅ 移除所有 `logging.basicConfig()` 调用
- [ ] ✅ REST API 服务启动成功（端口 5001）
- [ ] ✅ WebSocket 服务启动成功（端口 5003）
- [ ] ✅ Scheduler 服务启动成功
- [ ] ✅ 日志输出包含 trace_id
- [ ] ✅ 日志输出为彩色格式（开发环境）
- [ ] ✅ 健康检查通过：`curl http://localhost:5001/health`
- [ ] ✅ 单元测试通过（如有）
- [ ] ✅ 代码已提交到 `optimize/p0-logging-decimal` 分支
- [ ] ✅ Code Review 通过
- [ ] ✅ 文档已更新（PYTHON_ENVIRONMENT.md, P0 报告）

**门禁检查命令**：
```bash
# 检查服务启动
./start.sh

# 检查日志格式
curl http://localhost:5001/health

# 检查 trace_id（查看日志输出）
# 应该看到类似：[36mtrace_id[0m=[35m30543f46[0m
```

**❌ 未通过门禁不得进入 P1**

---

### Phase 1: 核心业务层迁移（P1）

**前置条件**：P0 门禁通过

**范围**：
- `application/services/` (~100 个文件)
- `adapters/outbound/repositories/` (~30 个文件)

**任务**：
```python
# 每个文件执行以下替换：
-import logging
+import structlog

-logger = logging.getLogger(__name__)
+logger = structlog.get_logger(__name__)
```

**迁移策略**：

1. **逐层迁移**：
   - Step 1: Service 层（50 个文件）
   - Step 2: Repository 层（30 个文件）
   - Step 3: 其他业务文件

2. **每层完成后验证**：
   - 运行完整测试套件
   - 启动服务检查无报错
   - 手动测试核心功能

3. **分批提交**：
   - 每迁移 10-20 个文件提交一次
   - 提交信息格式：`feat(P1): migrate Service layer to structlog (batch 1/5)`

**完成标准（门禁）**：

- [ ] ✅ 所有目标文件使用 `structlog.get_logger(__name__)`
- [ ] ✅ 无残留 `logging.getLogger()` 调用
- [ ] ✅ 所有服务启动成功
- [ ] ✅ 单元测试全部通过
- [ ] ✅ 集成测试通过
- [ ] ✅ 性能测试无明显退化
- [ ] ✅ 代码已提交到 `optimize/p1-service-repo-logging` 分支
- [ ] ✅ Code Review 通过

**门禁检查命令**：
```bash
# 检查是否有残留 logging
grep -r "import logging" application/services/ | grep -v "structlog" | wc -l
# 应该返回 0

# 运行测试
pytest tests/

# 启动服务
./start.sh
```

**❌ 未通过门禁不得进入 P2**

---

### Phase 2: 全面清理（P2）

**前置条件**：P1 门禁通过

**范围**：
- 所有剩余的 Python 文件
- 测试文件
- 工具脚本

**任务**：
1. 替换所有 `print()` 为 `logger.info()`
2. 清理所有残留的 `logging.basicConfig()`
3. 更新测试用例
4. 更新文档

**完成标准（门禁）**：

- [ ] ✅ 全项目无 `logging.basicConfig()` 调用
- [ ] ✅ 全项目无 `logging.getLogger()` 调用
- [ ] ✅ `print()` 使用仅限于 CLI 工具输出
- [ ] ✅ 所有测试通过
- [ ] ✅ 文档已更新
- [ ] ✅ CLAUDE.md 已更新日志规范
- [ ] ✅ 代码已合并到 `main` 分支

**门禁检查命令**：
```bash
# 全局检查
grep -r "logging.basicConfig" . --include="*.py" | wc -l  # 应该 = 0
grep -r "logging.getLogger" . --include="*.py" | wc -l    # 应该 = 0

# 检查 print() 使用
grep -r "print(" . --include="*.py" | grep -v "# CLI" | wc -l
# 应该只在 CLI 工具中使用
```

---

## 🚫 反模式（禁止操作）

### ❌ 不要跨阶段工作

```bash
# ❌ 错误：P0 未完成就开始 P1
cd quantsys-v2
# P0 任务还没提交
vim application/services/*.py  # 开始修改 Service 层

# ✅ 正确：完成 P0 → 验证 → 提交 → 进入 P1
git checkout optimize/p0-logging-decimal
# 完成 P0 所有任务
./start.sh  # 验证通过
git commit -m "feat(P0): ..."
git push
# 创建新分支进入 P1
git checkout -b optimize/p1-service-repo-logging
```

### ❌ 不要未验证就提交

```bash
# ❌ 错误：修改后直接提交
vim start_all.py
git commit -m "fix logging"

# ✅ 正确：修改 → 验证 → 提交
vim start_all.py
./start.sh  # 验证服务启动
pytest     # 验证测试通过
git commit -m "fix logging"
```

### ❌ 不要混用 Python 版本

```bash
# ❌ 错误：使用全局 Python
python3 start_all.py  # 可能是 Python 3.8

# ✅ 正确：使用虚拟环境
source .venv/bin/activate
python start_all.py  # 保证是 Python 3.12
```

---

## 📊 进度追踪

### 当前状态（2026-06-29）

| 阶段 | 状态 | 完成度 | 门禁 | 分支 |
|------|------|--------|------|------|
| P0 | ✅ 完成 | 7/7 | ✅ 通过 | optimize/p0-logging-decimal |
| P1 | 🔲 待开始 | 0/130 | - | - |
| P2 | 🔲 待开始 | 0/150 | - | - |

### P0 完成清单

- [x] start_all.py 使用 structured logging
- [x] fastapi_app/main.py 添加 import os
- [x] websocket_server.py 使用 structured logging
- [x] simulation_trader.py 使用 structured logging
- [x] simulation_broker.py 使用 structured logging
- [x] 安装 structlog, uvicorn, fastapi
- [x] 服务启动验证通过
- [x] 创建 PYTHON_ENVIRONMENT.md
- [x] 创建 .python-version
- [x] 提交 P0 报告

---

## 🔄 回滚策略

如果某个阶段出现严重问题：

```bash
# 回滚到上一个稳定状态
git checkout optimize/p0-logging-decimal  # 回到 P0
git reset --hard HEAD~1                    # 回退一个提交

# 重新验证
./start.sh
pytest

# 修复问题后重新提交
```

---

## 🎓 最佳实践

### 1. 小步快跑

每次修改不超过 20 个文件，及时验证和提交。

### 2. 保持分支清晰

```
main
  ↓
optimize/p0-logging-decimal (P0 完成后合并)
  ↓
optimize/p1-service-repo-logging (P1 完成后合并)
  ↓
main (最终合并)
```

### 3. 自动化检查

在 pre-commit hook 中添加：
```bash
#!/bin/bash
# .git/hooks/pre-commit
if git diff --cached | grep -E "logging\.basicConfig"; then
    echo "❌ 禁止使用 logging.basicConfig"
    exit 1
fi
```

---

**最后更新**：2026-06-29  
**维护者**：PI Investment Team
