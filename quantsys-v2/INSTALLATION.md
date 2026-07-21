# quantsys-v2 标准化改造 - 安装指南

## 📦 新增依赖安装

标准化改造新增了 5 个 Python 包，需要安装才能使用新功能。

---

## 方式 1: 快速安装（推荐）

```bash
cd /Users/mac/Documents/ai/pi-investment/quantsys-v2

# 安装所有新依赖
pip install sentry-sdk structlog python-json-logger pyjwt flask-limiter

# 或从 requirements.txt 安装
pip install -r requirements.txt
```

---

## 方式 2: 分步安装

### 1. 错误监控（Sentry）
```bash
pip install sentry-sdk
```

**功能**: 自动捕获异常、性能追踪

### 2. 结构化日志（structlog）
```bash
pip install structlog python-json-logger
```

**功能**: JSON 格式日志、trace ID 追踪

### 3. JWT 认证
```bash
pip install pyjwt
```

**功能**: API 认证、Token 管理

### 4. API 限流
```bash
pip install flask-limiter
```

**功能**: 防止 DDoS、速率限制

---

## 验证安装

```bash
# 检查是否安装成功
python -c "import sentry_sdk; import structlog; import jwt; from flask_limiter import Limiter; print('✅ All dependencies installed')"
```

**预期输出**: `✅ All dependencies installed`

---

## 环境变量配置

在 `.env` 文件中添加以下配置（可选）：

```bash
# Sentry 配置（可选，不配置也能运行）
SENTRY_DSN=https://your-key@o123456.ingest.sentry.io/987654
ENVIRONMENT=development

# JWT 配置（可选，不配置使用默认）
JWT_SECRET_KEY=your-secret-key-change-in-production

# Redis 配置（限流使用，已有配置无需改动）
REDIS_HOST=127.0.0.1
REDIS_PORT=6379

# 日志配置（可选）
LOG_LEVEL=INFO
```

---

## 可选：使用 Poetry 管理依赖

如果你想使用更现代的依赖管理工具：

```bash
# 安装 Poetry
curl -sSL https://install.python-poetry.org | python3 -

# 初始化项目（如果还没有 pyproject.toml）
cd /Users/mac/Documents/ai/pi-investment/quantsys-v2
poetry init --no-interaction

# 添加依赖
poetry add sentry-sdk structlog python-json-logger pyjwt flask-limiter

# 安装所有依赖
poetry install
```

---

## 常见问题

### Q: 安装失败怎么办？

1. **升级 pip**
   ```bash
   pip install --upgrade pip
   ```

2. **使用国内镜像**
   ```bash
   pip install -i https://pypi.tuna.tsinghua.edu.cn/simple sentry-sdk structlog python-json-logger pyjwt flask-limiter
   ```

3. **检查 Python 版本**
   ```bash
   python --version  # 需要 Python 3.12+
   ```

### Q: 是否必须安装所有依赖？

**可选安装**:
- **Sentry** - 没有也能运行，只是没有错误追踪
- **structlog** - 没有会降级到标准 logging
- **JWT + 限流** - 没有则 API 无认证保护

**建议**: 全部安装，获得完整功能

### Q: 会影响现有代码吗？

**不会**。新模块是可选的，不会破坏现有功能：
- 没有 Sentry DSN，自动跳过初始化
- 没有 structlog，自动降级到 logging
- JWT 和限流需要手动启用

---

## 下一步

安装完成后，请查看：
- [QUICKSTART.md](QUICKSTART.md) - 快速开始
- [INTEGRATION_GUIDE.md](INTEGRATION_GUIDE.md) - 集成到现有代码

---

**安装耗时**: 约 2-5 分钟  
**版本要求**: Python 3.12+
