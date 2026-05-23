# CI/CD 配置文档

## 概述

本文档描述了 PI Investment Web Frontend 项目的 CI/CD 流程、配置说明和使用指南。

## 目录

- [CI/CD 流程](#cicd-流程)
- [GitHub Actions 工作流](#github-actions-工作流)
- [Docker 配置](#docker-配置)
- [部署方式](#部署方式)
- [环境变量配置](#环境变量配置)
- [使用指南](#使用指南)
- [故障排查](#故障排查)

---

## CI/CD 流程

### 整体流程图

```
代码提交 → CI检查 → 构建镜像 → 自动部署 → 健康检查 → 通知
   ↓          ↓          ↓          ↓          ↓         ↓
 Push     类型检查    Docker     SSH/Docker   HTTP     Slack
          测试       Build      Deploy      200
          构建
```

### 流程说明

1. **代码提交**: 开发者推送代码到 GitHub
2. **CI 检查**: 自动运行类型检查、构建验证
3. **构建镜像**: 构建 Docker 镜像并推送到 Docker Hub
4. **自动部署**: 部署到目标服务器（生产/预发布）
5. **健康检查**: 验证部署是否成功
6. **通知**: 发送部署结果通知

---

## GitHub Actions 工作流

### 1. CI 工作流 (`.github/workflows/ci.yml`)

**触发条件**:
- Push 到 `main` 或 `develop` 分支
- Pull Request 到 `main` 或 `develop` 分支

**执行步骤**:

1. **代码检查和测试**
   - 检出代码
   - 安装 Node.js 20.x
   - 安装依赖 (`npm ci`)
   - TypeScript 类型检查
   - 构建项目
   - 上传构建产物

2. **Docker 镜像构建**
   - 仅在 push 事件触发
   - 构建并推送 Docker 镜像到 Docker Hub
   - 使用构建缓存加速

3. **安全扫描**
   - 使用 Trivy 扫描漏洞
   - 上传结果到 GitHub Security

**示例输出**:
```
✓ Type check passed
✓ Build successful
✓ Docker image pushed: username/pi-investment-web:main-abc1234
```

### 2. Deploy 工作流 (`.github/workflows/deploy.yml`)

**触发条件**:
- Push 到 `main` 分支（自动部署到生产环境）
- 手动触发（可选择环境）

**执行步骤**:

1. **构建应用**
   - 安装依赖
   - 构建生产版本

2. **SSH 部署**
   - 上传构建产物到服务器
   - 备份当前版本
   - 部署新版本
   - 重载 Nginx

3. **健康检查**
   - 验证站点是否正常响应
   - HTTP 200 状态码检查

4. **通知**
   - 发送 Slack 通知

**手动触发**:
```bash
# 在 GitHub Actions 页面点击 "Run workflow"
# 选择环境: production 或 staging
```

### 3. Release 工作流 (`.github/workflows/release.yml`)

**触发条件**:
- 推送版本标签（如 `v1.0.0`）

**执行步骤**:

1. **创建发布**
   - 构建生产版本
   - 创建 tar.gz 和 zip 归档
   - 生成变更日志
   - 创建 GitHub Release

2. **构建发布镜像**
   - 构建并推送带版本标签的 Docker 镜像
   - 标签: `v1.0.0`, `1.0.0`, `latest`

3. **发送通知**
   - Slack 通知新版本发布

**创建发布**:
```bash
# 创建并推送标签
git tag -a v1.0.0 -m "Release version 1.0.0"
git push origin v1.0.0
```

---

## Docker 配置

### Dockerfile

**多阶段构建**:

1. **构建阶段** (`builder`)
   - 基于 `node:20-alpine`
   - 安装依赖
   - 构建应用

2. **生产阶段**
   - 基于 `nginx:1.25-alpine`
   - 复制构建产物
   - 配置 Nginx
   - 健康检查

**特性**:
- 最小化镜像大小
- 非 root 用户运行
- 健康检查支持
- 安全最佳实践

### docker-compose.yml

**服务**:

1. **web-frontend**
   - 前端应用容器
   - 端口: 8080:80
   - 健康检查
   - 自动重启

2. **nginx-proxy** (可选)
   - 反向代理
   - SSL 支持
   - 端口: 80, 443

**使用**:
```bash
# 启动服务
docker-compose up -d

# 查看日志
docker-compose logs -f web-frontend

# 停止服务
docker-compose down
```

---

## 部署方式

### 方式 1: SSH 部署

**适用场景**: 传统服务器部署

**配置要求**:
- SSH 访问权限
- Nginx 已安装
- 目标目录权限

**部署流程**:
1. 上传构建产物
2. 备份当前版本
3. 部署新版本
4. 设置权限
5. 重载 Nginx
6. 清理旧备份

**使用脚本**:
```bash
# 部署到生产环境
./scripts/deploy.sh production ssh

# 部署到预发布环境
./scripts/deploy.sh staging ssh
```

### 方式 2: Docker 部署

**适用场景**: 容器化部署

**配置要求**:
- Docker 已安装
- Docker Compose 已安装

**部署流程**:
1. 构建 Docker 镜像
2. 停止旧容器
3. 启动新容器
4. 验证容器状态

**使用脚本**:
```bash
# Docker 部署
./scripts/deploy.sh production docker
```

---

## 环境变量配置

### GitHub Secrets

在 GitHub 仓库设置中配置以下 Secrets:

#### Docker Hub
```
DOCKER_USERNAME=your-dockerhub-username
DOCKER_PASSWORD=your-dockerhub-password
```

#### SSH 部署
```
DEPLOY_HOST=your-server-ip
DEPLOY_USER=deploy-user
DEPLOY_SSH_KEY=your-private-ssh-key
DEPLOY_PORT=22
DEPLOY_URL=https://your-domain.com
```

#### Docker 部署
```
DOCKER_HOST=your-docker-host
DOCKER_USER=docker-user
DOCKER_SSH_KEY=your-private-ssh-key
DOCKER_PORT=22
```

#### 通知
```
SLACK_WEBHOOK=your-slack-webhook-url
```

### 本地部署配置

创建 `.deploy.config` 文件:

```bash
# SSH 部署配置
DEPLOY_HOST=192.168.1.100
DEPLOY_USER=deploy
DEPLOY_PATH=/var/www/pi-investment-web
DEPLOY_PORT=22
DEPLOY_URL=http://192.168.1.100

# 环境
ENVIRONMENT=production
```

---

## 使用指南

### 本地构建

```bash
# 使用构建脚本
./scripts/build.sh

# 或使用 npm
npm run build
```

### 本地部署

```bash
# SSH 部署
./scripts/deploy.sh production ssh

# Docker 部署
./scripts/deploy.sh production docker
```

### Docker 本地测试

```bash
# 构建镜像
docker build -t pi-investment-web:test .

# 运行容器
docker run -d -p 8080:80 pi-investment-web:test

# 访问应用
open http://localhost:8080

# 查看日志
docker logs -f <container-id>

# 停止容器
docker stop <container-id>
```

### 使用 docker-compose

```bash
# 启动所有服务
docker-compose up -d

# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f

# 重启服务
docker-compose restart web-frontend

# 停止服务
docker-compose down
```

### 版本发布

```bash
# 1. 更新版本号
npm version patch  # 或 minor, major

# 2. 推送标签
git push origin main --tags

# 3. GitHub Actions 自动创建 Release
```

---

## 故障排查

### 构建失败

**问题**: TypeScript 类型检查失败
```bash
# 本地检查
npx vue-tsc --noEmit

# 查看详细错误
npx vue-tsc --noEmit --pretty
```

**问题**: 依赖安装失败
```bash
# 清理缓存
rm -rf node_modules package-lock.json
npm install

# 或使用 ci
npm ci
```

### 部署失败

**问题**: SSH 连接失败
```bash
# 测试 SSH 连接
ssh -p 22 user@host

# 检查 SSH 密钥
ssh-keygen -l -f ~/.ssh/id_rsa
```

**问题**: Nginx 配置错误
```bash
# 测试 Nginx 配置
sudo nginx -t

# 查看 Nginx 日志
sudo tail -f /var/log/nginx/error.log
```

**问题**: 权限问题
```bash
# 设置正确的权限
sudo chown -R www-data:www-data /var/www/pi-investment-web
sudo chmod -R 755 /var/www/pi-investment-web
```

### Docker 问题

**问题**: 容器无法启动
```bash
# 查看容器日志
docker logs <container-id>

# 查看容器详情
docker inspect <container-id>

# 进入容器调试
docker exec -it <container-id> sh
```

**问题**: 健康检查失败
```bash
# 手动执行健康检查
docker exec <container-id> curl -f http://localhost:80/

# 查看健康状态
docker ps --format "table {{.Names}}\t{{.Status}}"
```

### 回滚部署

**SSH 部署回滚**:
```bash
# 自动回滚（部署脚本支持）
# 在健康检查失败时会提示是否回滚

# 手动回滚
ssh user@host
cd /var/www
sudo rm -rf pi-investment-web
sudo mv pi-investment-web.backup.YYYYMMDD_HHMMSS pi-investment-web
sudo systemctl reload nginx
```

**Docker 部署回滚**:
```bash
# 回滚到之前的镜像
docker-compose down
docker tag pi-investment-web:previous pi-investment-web:latest
docker-compose up -d
```

---

## 最佳实践

### 1. 分支策略

- `main`: 生产环境，自动部署
- `develop`: 开发环境，CI 检查
- `feature/*`: 功能分支，PR 到 develop

### 2. 版本管理

- 使用语义化版本: `v1.0.0`
- 主版本: 不兼容的 API 变更
- 次版本: 向后兼容的功能新增
- 修订版本: 向后兼容的问题修正

### 3. 部署策略

- **生产环境**: 仅从 `main` 分支部署
- **预发布环境**: 从 `develop` 分支部署
- **灰度发布**: 使用 Docker 部署，逐步切换流量

### 4. 监控和日志

- 配置应用监控（如 Sentry）
- 收集 Nginx 访问日志
- 设置告警规则

### 5. 安全

- 定期更新依赖
- 使用 Trivy 扫描漏洞
- 保护敏感信息（使用 Secrets）
- 使用 HTTPS（配置 SSL 证书）

---

## 附录

### Nginx 配置说明

主要配置项:

- **Gzip 压缩**: 减少传输大小
- **静态资源缓存**: 1年缓存期
- **HTML 不缓存**: 确保更新及时
- **SPA 路由支持**: `try_files` 配置
- **API 代理**: 反向代理到后端
- **WebSocket 支持**: Socket.io 配置
- **安全头**: XSS、CSRF 防护

### 性能优化

1. **构建优化**
   - 代码分割
   - Tree shaking
   - 压缩混淆

2. **缓存策略**
   - 静态资源长期缓存
   - HTML 不缓存
   - Service Worker（可选）

3. **CDN 加速**
   - 静态资源 CDN
   - 图片 CDN

### 相关链接

- [GitHub Actions 文档](https://docs.github.com/en/actions)
- [Docker 文档](https://docs.docker.com/)
- [Nginx 文档](https://nginx.org/en/docs/)
- [Vite 构建优化](https://vitejs.dev/guide/build.html)

---

## 联系方式

如有问题，请联系:
- 项目负责人: [Your Name]
- 邮箱: [your-email@example.com]
- Slack: #pi-investment-dev
