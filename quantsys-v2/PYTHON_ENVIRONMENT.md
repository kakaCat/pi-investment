# Python 环境规范

## 🎯 版本要求

**强制要求**：Python **3.13+**

- ❌ 不支持 Python 3.8、3.9、3.10、3.11
- ✅ 当前使用 Python 3.13.12
- ✅ 建议使用 Python 3.13.x

## 📦 环境配置

### 1. 创建虚拟环境

```bash
# 使用 Python 3.13 创建虚拟环境
/opt/homebrew/bin/python3.13 -m venv venv

# 激活虚拟环境
source venv/bin/activate
# 或使用激活脚本
source activate-py313.sh

# 验证 Python 版本
python --version  # 应该显示 Python 3.13.x
```

### 2. 安装依赖

```bash
# 激活虚拟环境后
pip install -r requirements.txt

# 或使用 pip-tools
pip-sync requirements.txt
```

### 3. 版本锁定

项目使用 Python 3.13.12，通过激活脚本 `activate-py313.sh` 确保版本一致：

```bash
source activate-py313.sh
# 输出: ✅ 已激活 Python 3.13 虚拟环境: Python 3.13.12
```

## 🚀 启动服务

### 推荐方式：使用激活脚本

```bash
# 1. 进入quantsys-v2目录
cd /Users/mac/Documents/ai/pi-investment/quantsys-v2

# 2. 激活虚拟环境
source activate-py313.sh

# 3. 启动服务
python start_all.py
```

激活脚本会：
- ✅ 自动激活虚拟环境
- ✅ 验证 Python 版本（3.13.x）
- ✅ 显示确认信息

### 手动启动

```bash
# 1. 激活虚拟环境
source venv/bin/activate

# 2. 启动服务
python start_all.py
```

## ⚠️ 常见问题

### 问题 1：使用了全局 Python 导致依赖缺失

**错误现象**：
```
ModuleNotFoundError: No module named 'structlog'
ModuleNotFoundError: No module named 'psycopg2'
```

**原因**：使用了系统全局 Python（如 `python3` 命令）而非虚拟环境

**解决方案**：
```bash
# 先激活虚拟环境
source activate-py313.sh
# 或
source venv/bin/activate

# 然后再运行
python start_all.py
```

### 问题 2：Python 版本过旧

**错误现象**：
```
TypeError: unsupported operand type(s) for |: 'type' and 'type'
```

**原因**：使用了 Python 3.8/3.9，不支持 `Dict | List` 语法

**解决方案**：
```bash
# 升级到 Python 3.13
brew install python@3.13  # macOS
# 或
apt install python3.13     # Ubuntu

# 重新创建虚拟环境
rm -rf venv
/opt/homebrew/bin/python3.13 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 问题 3：多个 Python 版本混用

**错误现象**：依赖在一个环境安装，运行时找不到

**原因**：
- 全局 Python 3.8：`/usr/local/bin/python3`
- 虚拟环境 Python 3.13：`venv/bin/python`
- 混用导致依赖不一致

**解决方案**：
```bash
# 1. 明确使用虚拟环境
source activate-py313.sh

# 2. 验证使用的是虚拟环境
which python  # 应该显示 quantsys-v2/venv/bin/python

# 3. 验证版本
python --version  # 应该显示 3.13.x
```

## 🔒 CI/CD 要求

持续集成环境应使用相同的 Python 版本：

```yaml
# .github/workflows/test.yml
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/setup-python@v4
        with:
          python-version: '3.13'
```

## 📚 依赖管理

### 核心依赖

- **数据库**：SQLAlchemy, psycopg2-binary 2.9.12
- **日志**：structlog 26.1+
- **数据处理**：pandas 3.0.4, numpy
- **数据源**：akshare 1.18.64, tushare 1.4.29
- **Web框架**：Flask, Flask-CORS
- **环境变量**：python-dotenv

### 依赖更新

```bash
# 更新单个包
pip install --upgrade structlog

# 更新所有包（谨慎）
pip install --upgrade -r requirements.txt

# 锁定版本
pip freeze > requirements.txt
```

## ✅ 环境验证清单

启动前检查：

- [ ] Python 版本 = 3.13+
- [ ] 虚拟环境已激活 (`source activate-py313.sh`)
- [ ] `which python` 指向 `quantsys-v2/venv/bin/python`
- [ ] `pip list` 包含 structlog, psycopg2-binary, pandas, akshare
- [ ] 依赖包数量 >= 80个

## 🆘 获取帮助

遇到环境问题：

1. 检查 Python 版本：`python --version`
2. 检查虚拟环境：`which python`
3. 查看已安装包：`pip list`
4. 查看启动日志中的 Python 版本信息

---

**最后更新**：2026-06-29  
**维护者**：PI Investment Team
