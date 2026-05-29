# Python 环境迁移指南

## 问题背景

原项目使用 Python 3.14，但 `pandas-ta` 的依赖 `numba==0.61.2` 不支持 Python 3.14（要求 >=3.10, <3.14）。

## 解决方案

已创建 Python 3.13 虚拟环境，所有依赖已成功安装。

## 使用新环境

### 方法 1：使用激活脚本（推荐）

```bash
source activate-py313.sh
```

### 方法 2：手动激活

```bash
source .venv-py313/bin/activate
```

## 验证安装

```bash
# 激活环境后
python --version  # 应显示 Python 3.13.x

# 验证关键依赖
python -c "import pandas_ta as ta; print(f'pandas-ta: {ta.version}')"
python -c "import numba; print(f'numba: {numba.__version__}')"

# 测试 quant_cli
cd quant && python -m quantsys.cli stock score --symbol 600519
```

## 更新开发流程

### 启动 Python 后端

```bash
# 激活 Python 3.13 环境
source activate-py313.sh

# 启动 v1 Flask API (端口 5002)
cd quant && python api/server.py

# 或启动 v2 Flask API (端口 5001 + 5003)
cd quantsys-v2 && python start_all.py
```

### 运行 TypeScript Agent

TypeScript agent 会自动调用系统 Python，确保在启动前已激活 `.venv-py313`：

```bash
# 终端 1：激活 Python 环境并启动后端
source activate-py313.sh
cd quant && python api/server.py

# 终端 2：启动 TypeScript agent
npm run dev
```

## 环境对比

| 项目 | 旧环境 (.venv) | 新环境 (.venv-py313) |
|------|---------------|---------------------|
| Python 版本 | 3.14.3 | 3.13.x |
| pandas-ta | ❌ 安装失败 | ✅ 0.4.71b0 |
| numba | ❌ 不兼容 | ✅ 0.61.2 |
| 其他依赖 | ✅ 正常 | ✅ 正常 |

## 故障排查

### 问题：quant_cli 仍然报错 "No module named 'pandas_ta'"

**原因**：未激活 Python 3.13 环境

**解决**：
```bash
source activate-py313.sh
```

### 问题：TypeScript agent 调用 Python 工具失败

**原因**：TypeScript agent 使用的 Python 解释器不是 `.venv-py313`

**解决**：
1. 在启动 agent 前激活环境：`source activate-py313.sh`
2. 或修改 `src/infrastructure/adapters/cli/base-cli-adapter.ts` 中的 Python 路径

### 问题：想回到旧环境

旧环境 `.venv` 仍然保留，可以随时切换：
```bash
source .venv/bin/activate
```

但注意：旧环境中 `pandas-ta` 无法正常工作。

## 后续计划

- [ ] 更新 CI/CD 配置使用 Python 3.13
- [ ] 更新 Docker 镜像使用 Python 3.13
- [ ] 考虑移除旧的 `.venv` 目录（确认无问题后）
- [ ] 等待 numba 支持 Python 3.14 后再升级

## 相关文件

- [activate-py313.sh](activate-py313.sh) - 环境激活脚本
- [CLAUDE.md](CLAUDE.md) - 项目文档（已更新环境要求）
- [quant/requirements.txt](quant/requirements.txt) - Python 依赖列表
