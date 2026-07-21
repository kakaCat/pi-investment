# ========================================
# quantsys-v2 多阶段 Docker 构建
# ========================================

# ── Stage 1: Builder ──
FROM python:3.12-slim as builder

WORKDIR /app

# 安装构建依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    git \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 创建 wheel 包（加速后续安装）
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /app/wheels -r requirements.txt

# ── Stage 2: Runtime ──
FROM python:3.12-slim

WORKDIR /app

# 安装运行时依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# 从 builder 复制 wheel 包
COPY --from=builder /app/wheels /wheels
COPY --from=builder /app/requirements.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir --no-index --find-links=/wheels -r requirements.txt \
    && rm -rf /wheels

# 复制应用代码
COPY . .

# 创建非 root 用户
RUN useradd -m -u 1000 quantsys && chown -R quantsys:quantsys /app
USER quantsys

# 健康检查
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
  CMD curl -f http://localhost:5001/api/health || exit 1

# 暴露端口
EXPOSE 5001 5003

# 启动服务
CMD ["python", "start_all.py"]
