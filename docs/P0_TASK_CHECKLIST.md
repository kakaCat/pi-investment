# P0 任务检查清单

**任务**: 统一日志启动配置 + Decimal 使用  
**分支**: `optimize/p0-logging-decimal`  
**负责人**: _______  
**开始时间**: _______  
**完成时间**: _______

---

## ✅ Phase 0: 代码修改

### 任务 1.1: start_all.py
- [ ] 删除 `logging.basicConfig()` 调用
- [ ] 为 `run_rest_api()` 添加 `configure_structured_logging()`
- [ ] 添加 `check_environment()` 函数
- [ ] 添加 Python 版本检查（要求 3.12+）
- [ ] 添加虚拟环境检查
- [ ] 添加依赖检查（structlog, uvicorn, fastapi）

### 任务 1.2: fastapi_app/main.py
- [ ] 检查是否已使用 `configure_structured_logging()`
- [ ] 确保 `import os` 存在
- [ ] 验证无 `logging.basicConfig()` 调用

### 任务 1.3: websocket_server.py
- [ ] 删除 `logging.basicConfig()` 调用
- [ ] 添加 `import os`
- [ ] 使用 `configure_structured_logging()`
- [ ] 使用 `import structlog` 和 `structlog.get_logger(__name__)`

### 任务 1.4: simulation_trader.py
- [ ] 更新 `_setup_logging()` 方法使用 `configure_structured_logging()`
- [ ] 保留文件日志处理器功能

### 任务 1.5: simulation_broker.py
- [ ] 检查是否已使用 `Decimal`（应该已完成）
- [ ] 更新 `__main__` 块使用 `configure_structured_logging()`
- [ ] 确认所有金额计算使用 `Decimal`

---

## ✅ Phase 1: 环境配置

### 任务 2.1: Python 版本规范
- [ ] 创建 `.python-version` 文件（内容: 3.12.8）
- [ ] 验证 pyenv 用户可以自动切换版本

### 任务 2.2: 虚拟环境依赖
- [ ] 激活虚拟环境: `source .venv/bin/activate`
- [ ] 安装 structlog: `pip install structlog`
- [ ] 安装 uvicorn: `pip install uvicorn`
- [ ] 安装 fastapi: `pip install fastapi`
- [ ] 验证安装: `pip list | grep -E "structlog|uvicorn|fastapi"`

---

## ✅ Phase 2: 文档创建

### 任务 3.1: PYTHON_ENVIRONMENT.md
- [ ] 创建文件
- [ ] 包含 Python 版本要求（3.12+）
- [ ] 包含虚拟环境设置步骤
- [ ] 包含常见问题解决方案
- [ ] 包含依赖管理指南

### 任务 3.2: LOGGING_WORKFLOW.md
- [ ] 创建文件
- [ ] 定义 P0/P1/P2 阶段划分
- [ ] 定义每个阶段的门禁标准
- [ ] 包含反模式（禁止操作）
- [ ] 包含回滚策略

### 任务 3.3: README.md 更新
- [ ] 在开头添加环境要求警告
- [ ] 强调 Python 3.12+ 要求
- [ ] 强调必须使用虚拟环境
- [ ] 添加快速设置步骤
- [ ] 链接到 PYTHON_ENVIRONMENT.md

### 任务 3.4: P0 任务执行报告
- [ ] 创建 `docs/p0-task-execution-report.md`
- [ ] 记录所有修改的文件
- [ ] 记录完成标准验证结果
- [ ] 记录遇到的问题和解决方案

---

## ✅ Phase 3: 代码质量保障

### 任务 4.1: pre-commit hook
- [ ] 创建 `pre-commit` 脚本
- [ ] 添加 logging.basicConfig 检查
- [ ] 添加 structlog 推荐检查
- [ ] 添加 print() 使用检查
- [ ] 添加 Python 3.12+ 语法检查
- [ ] 添加结构化日志格式检查
- [ ] 设置可执行权限: `chmod +x pre-commit`

### 任务 4.2: CI/CD 配置
- [ ] 创建 `.github/workflows/ci.yml`
- [ ] 添加 Python 3.12 版本检查
- [ ] 添加日志规范检查
- [ ] 添加单元测试运行
- [ ] 添加服务启动测试
- [ ] 添加 P0 门禁检查

---

## ✅ Phase 4: 验证测试

### 任务 5.1: 本地验证
- [ ] 回滚 Service 层的 structlog 修改（如有）: `git checkout -- application/services/`
- [ ] 确认工作目录干净: `git status`
- [ ] 启动服务: `./start.sh` 或 `source .venv/bin/activate && python start_all.py`
- [ ] 验证环境检查输出正确
- [ ] 验证 Python 版本显示为 3.12.x

### 任务 5.2: 服务启动验证
- [ ] REST API 启动成功（端口 5001）
- [ ] WebSocket 启动成功（端口 5003）
- [ ] Scheduler 启动成功
- [ ] 无报错信息
- [ ] 日志输出包含 trace_id

### 任务 5.3: 日志格式验证
- [ ] 日志输出为彩色格式（开发环境）
- [ ] 日志包含时间戳（ISO 8601 格式）
- [ ] 日志包含 trace_id
- [ ] 日志包含结构化字段（key=value 格式）
- [ ] 查看示例: 应该看到类似 `[36mtrace_id[0m=[35m30543f46[0m`

### 任务 5.4: API 健康检查
```bash
curl http://localhost:5001/health
```
- [ ] 返回 200 状态码
- [ ] 返回 JSON 格式: `{"status": "ok", "framework": "fastapi", "version": "2.0.0"}`

### 任务 5.5: pre-commit hook 测试
```bash
# 安装 hook
cp pre-commit .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit

# 测试（创建一个包含 logging.basicConfig 的临时文件）
echo "import logging; logging.basicConfig()" > test_commit.py
git add test_commit.py
git commit -m "test"  # 应该被 hook 阻止
```
- [ ] Hook 成功阻止包含 `logging.basicConfig` 的提交
- [ ] 删除测试文件: `git reset HEAD test_commit.py && rm test_commit.py`

---

## ✅ Phase 5: Git 提交

### 任务 6.1: quantsys-v2 子模块提交
```bash
cd quantsys-v2
git add -A
git status  # 确认要提交的文件
```

确认包含以下文件:
- [ ] start_all.py
- [ ] adapters/inbound/fastapi_app/main.py（如有修改）
- [ ] adapters/inbound/fastapi_app/websocket_server.py
- [ ] live_trading/simulation_trader.py
- [ ] live_trading/simulation_broker.py
- [ ] .python-version
- [ ] PYTHON_ENVIRONMENT.md
- [ ] LOGGING_WORKFLOW.md
- [ ] README.md
- [ ] pre-commit

提交:
```bash
git commit -m "feat(P0): complete logging and decimal standardization + add enforcement

P0 Task 1: Unified Logging Configuration
- start_all.py: Added environment checks and structured logging
- fastapi_app/main.py: Verified structured logging setup
- websocket_server.py: Replaced logging.basicConfig
- simulation_trader.py: Updated _setup_logging()
- simulation_broker.py: Already using Decimal + updated __main__

P0 Task 2: Simulation Account Decimal Usage
- Already completed in previous work

Enforcement Measures:
- .python-version: Lock to Python 3.12.8
- PYTHON_ENVIRONMENT.md: Environment setup guide
- LOGGING_WORKFLOW.md: Phase-based workflow with gates
- README.md: Added environment requirements warning
- pre-commit: Hook to enforce logging standards
- CI/CD: Added .github/workflows/ci.yml

Verification:
- All services start successfully
- Structured logging confirmed working
- Environment checks pass
- Pre-commit hook blocks invalid commits"
```
- [ ] 提交完成
- [ ] 记录 commit hash: __________

### 任务 6.2: 主项目提交
```bash
cd /Users/mac/Documents/ai/pi-investment
git add quantsys-v2 .github/workflows/ci.yml
git status
```

提交:
```bash
git commit -m "chore: update quantsys-v2 with P0 completion and CI/CD

- quantsys-v2 updated to commit [填入上面的hash]
- Added GitHub Actions CI workflow
- Enforces Python 3.12+, logging standards, P0 gate checks"
```
- [ ] 提交完成
- [ ] 记录 commit hash: __________

---

## ✅ Phase 6: 最终检查

### 任务 7.1: 门禁清单
根据 `LOGGING_WORKFLOW.md` 中的 P0 门禁标准:

- [ ] ✅ 所有启动文件使用 `configure_structured_logging()`
- [ ] ✅ 移除所有 `logging.basicConfig()` 调用
- [ ] ✅ REST API 服务启动成功（端口 5001）
- [ ] ✅ WebSocket 服务启动成功（端口 5003）
- [ ] ✅ Scheduler 服务启动成功
- [ ] ✅ 日志输出包含 trace_id
- [ ] ✅ 日志输出为彩色格式（开发环境）
- [ ] ✅ 健康检查通过：`curl http://localhost:5001/health`
- [ ] ✅ 代码已提交到 `optimize/p0-logging-decimal` 分支
- [ ] ✅ 文档已更新（PYTHON_ENVIRONMENT.md, LOGGING_WORKFLOW.md, README.md, P0 报告）
- [ ] ✅ CI/CD 配置已添加

### 任务 7.2: 强制措施清单
- [ ] ✅ .python-version 文件已创建
- [ ] ✅ README 明确要求使用虚拟环境
- [ ] ✅ start_all.py 检查 Python 版本
- [ ] ✅ CI/CD 强制版本检查
- [ ] ✅ pre-commit hook 强制检查日志风格
- [ ] ✅ 任务检查清单已创建

### 任务 7.3: Code Review（可选）
- [ ] 创建 Pull Request
- [ ] 邀请团队成员 Review
- [ ] 解决 Review 意见
- [ ] 获得批准

---

## 📊 完成统计

- **修改文件数**: _______
- **新增文件数**: _______
- **代码行数变化**: +_______ / -_______
- **实际耗时**: _______ 小时

---

## 🎯 下一步（P1 任务准备）

P0 完成后，不要立即开始 P1！先完成以下准备：

- [ ] 在团队会议上展示 P0 成果
- [ ] 更新项目文档（CLAUDE.md）
- [ ] 培训团队成员使用新的日志规范
- [ ] 等待至少 1 天观察生产环境稳定性
- [ ] 创建 P1 分支: `optimize/p1-service-repo-logging`
- [ ] 阅读 `LOGGING_WORKFLOW.md` P1 部分
- [ ] 准备 P1 任务检查清单

**⚠️ 重要**: 只有当 P0 门禁 100% 通过后，才能进入 P1！

---

**清单创建时间**: 2026-06-29  
**最后更新**: 2026-06-29  
**维护者**: PI Investment Team
