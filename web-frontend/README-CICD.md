# PI Investment Web Frontend - CI/CD Setup

## 📋 概述

本项目已配置完整的 CI/CD 流程，包括：
- ✅ GitHub Actions 自动化工作流
- ✅ Docker 容器化部署
- ✅ Nginx 反向代理配置
- ✅ 自动化部署脚本

## 🚀 快速开始

### 本地构建

```bash
# 使用构建脚本
./scripts/build.sh

# 或使用 npm
npm run build
```

### Docker 本地测试

```bash
# 构建镜像
docker build -t pi-investment-web:test .

# 运行容器
docker run -d -p 8080:80 pi-investment-web:test

# 访问应用
open http://localhost:8080
```

### 使用 docker-compose

```bash
# 启动所有服务
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down
```

## 📁 文件结构

```
web-frontend/
├── .github/
│   └── workflows/
│       ├── ci.yml           # CI 工作流
│       ├── deploy.yml       # 部署工作流
│       └── release.yml      # 发布工作流
├── scripts/
│   ├── build.sh            # 构建脚本
│   └── deploy.sh           # 部署脚本
├── Dockerfile              # Docker 镜像配置
├── docker-compose.yml      # Docker Compose 配置
├── .dockerignore           # Docker 忽略文件
├── nginx.conf              # Nginx 配置（容器内）
├── nginx-proxy.conf        # Nginx 代理配置（生产环境）
└── .deploy.config.example  # 部署配置示例
```

## 🔧 配置说明

### 1. GitHub Secrets 配置

在 GitHub 仓库设置中添加以下 Secrets：

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

#### 通知（可选）
```
SLACK_WEBHOOK=your-slack-webhook-url
```

### 2. 本地部署配置

复制配置文件并填入实际值：

```bash
cp .deploy.config.example .deploy.config
# 编辑 .deploy.config 填入实际配置
```

## 🔄 CI/CD 流程

### CI 工作流（自动触发）

**触发条件**: Push 或 PR 到 `main`/`develop` 分支

**执行步骤**:
1. TypeScript 类型检查
2. 构建应用
3. 构建 Docker 镜像
4. 安全漏洞扫描

### Deploy 工作流

**触发条件**: 
- Push 到 `main` 分支（自动）
- 手动触发（可选环境）

**执行步骤**:
1. 构建生产版本
2. 部署到服务器
3. 健康检查
4. 发送通知

### Release 工作流

**触发条件**: 推送版本标签（如 `v1.0.0`）

**执行步骤**:
1. 创建 GitHub Release
2. 生成变更日志
3. 构建发布镜像
4. 发送通知

## 📦 部署方式

### 方式 1: SSH 部署

```bash
# 部署到生产环境
./scripts/deploy.sh production ssh

# 部署到预发布环境
./scripts/deploy.sh staging ssh
```

**特性**:
- 自动备份当前版本
- 原子性部署
- 自动回滚支持
- 健康检查

### 方式 2: Docker 部署

```bash
# Docker 部署
./scripts/deploy.sh production docker
```

**特性**:
- 容器化隔离
- 快速回滚
- 资源限制
- 健康检查

## 🔍 健康检查

部署后自动执行健康检查：

```bash
# 检查站点是否正常响应
curl -f http://your-domain.com/health
```

如果健康检查失败，脚本会提示是否回滚。

## 🔄 版本发布

```bash
# 1. 更新版本号
npm version patch  # 或 minor, major

# 2. 推送标签
git push origin main --tags

# 3. GitHub Actions 自动创建 Release
```

## 🛠️ 故障排查

### 构建失败

```bash
# 清理并重新构建
rm -rf node_modules dist
npm ci
npm run build
```

### 部署失败

```bash
# 检查 SSH 连接
ssh -p 22 user@host

# 查看 Nginx 日志
sudo tail -f /var/log/nginx/error.log

# 测试 Nginx 配置
sudo nginx -t
```

### Docker 问题

```bash
# 查看容器日志
docker logs <container-id>

# 进入容器调试
docker exec -it <container-id> sh

# 重启容器
docker-compose restart web-frontend
```

## 📚 详细文档

完整的 CI/CD 配置文档请查看: [/docs/CICD.md](/docs/CICD.md)

包含:
- 详细的工作流说明
- 配置参数说明
- 最佳实践
- 性能优化建议
- 安全配置指南

## 🔐 安全注意事项

1. **保护敏感信息**
   - 使用 GitHub Secrets 存储密钥
   - 不要提交 `.deploy.config` 文件
   - 不要提交 SSL 证书

2. **定期更新**
   - 定期更新依赖包
   - 关注安全漏洞扫描结果
   - 及时应用安全补丁

3. **访问控制**
   - 限制 SSH 访问权限
   - 使用强密码和密钥
   - 配置防火墙规则

## 📞 支持

如有问题，请：
1. 查看 [CI/CD 文档](/docs/CICD.md)
2. 检查 GitHub Actions 日志
3. 联系项目维护者

## 📄 许可证

本项目采用 MIT 许可证。
