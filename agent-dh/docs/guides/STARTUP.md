# Agent-DH 启动指南

## 架构变更

**之前**：启动配置在 `~/.dsh/profiles/investment/`（外部 DSH profile）  
**现在**：启动配置在 `agent-dh/` 项目内，agent-dh 是独立应用

## 快速启动

```bash
# 1. 安装依赖
pnpm install

# 2. 启动（默认端口 13080）
pnpm start

# 3. 或指定端口
pnpm start -- 13081

# 4. 开发模式（详细日志）
pnpm start:dev
```

## 项目结构

```
agent-dh/
├── config/
│   └── cordis.yml          # 插件配置（从 ~/.dsh 迁移）
├── scripts/
│   └── start.sh            # 启动脚本
├── packages/               # 业务插件
│   ├── investment/
│   ├── trading/
│   └── ...
├── src/
│   └── main.ts            # 启动入口（保留，未来可用）
└── package.json           # 包含启动命令
```

## 配置管理

### 插件配置

编辑 `config/cordis.yml` 来管理插件：

```yaml
- id: investment
  name: '@pi-investment/investment'
  config:
    quantsysV2:
      baseURL: http://localhost:5001
```

### 环境变量

在项目根目录创建 `.env` 文件：

```bash
DEEPSEEK_API_KEY=sk-...
QUANTSYS_V2_API_URL=http://localhost:5001
```

## 与旧方式的对比

### 旧方式（DSH Profile）

```bash
cd ~/.dsh/profiles/investment
./start.sh
```

- ✗ 配置在用户目录，不在版本控制中
- ✗ 源码和配置分离
- ✗ 部署时需要手动同步配置

### 新方式（项目内启动）

```bash
cd /Users/yunpeng/pi-investment/agent-dh
pnpm start
```

- ✓ 配置在项目内，纳入版本控制
- ✓ 源码和配置统一管理
- ✓ 部署简单（git clone + pnpm install + pnpm start）

## 迁移说明

如果你之前使用 DSH profile 方式启动，现在可以：

1. **停止旧实例**：
   ```bash
   launchctl bootout gui/$(id -u)/com.pi-investment.dsh
   ```

2. **使用新方式启动**：
   ```bash
   cd /Users/yunpeng/pi-investment/agent-dh
   pnpm start
   ```

3. **（可选）删除旧配置**：
   ```bash
   # 备份后可删除
   rm -rf ~/.dsh/profiles/investment
   rm ~/Library/LaunchAgents/com.pi-investment.dsh.plist
   ```

## launchd 托管（可选）

如果需要开机自启和自动重启，可以创建 launchd 配置：

```bash
# 使用项目内的启动脚本
cat > ~/Library/LaunchAgents/com.pi-investment.agent-dh.plist <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.pi-investment.agent-dh</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>/Users/yunpeng/pi-investment/agent-dh/scripts/start.sh</string>
        <string>13080</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/Users/yunpeng/pi-investment/agent-dh</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/Users/yunpeng/pi-investment/agent-dh/logs/stdout.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/yunpeng/pi-investment/agent-dh/logs/stderr.log</string>
</dict>
</plist>
EOF

# 加载
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.pi-investment.agent-dh.plist

# 重启
launchctl kickstart -k gui/$(id -u)/com.pi-investment.agent-dh

# 停止
launchctl bootout gui/$(id -u)/com.pi-investment.agent-dh
```

## 故障排查

### 问题：找不到 @deepseek-ai/dsh

**解决**：
```bash
pnpm install
```

### 问题：端口已被占用

**解决**：
```bash
# 查看占用端口的进程
lsof -ti:13080

# 杀死进程
kill $(lsof -ti:13080)

# 或使用其他端口
pnpm start -- 13081
```

### 问题：插件加载失败

**解决**：
```bash
# 检查插件是否已构建
pnpm build:clients

# 查看详细日志
pnpm start:dev
```

## 开发指南

### 添加新插件

1. 在 `packages/` 下创建新插件
2. 在 `config/cordis.yml` 中注册
3. 重启 agent-dh

### 修改配置

1. 编辑 `config/cordis.yml`
2. 重启 agent-dh（配置不支持热加载）

### 调试

```bash
# 详细日志模式
pnpm start:dev

# 或直接运行
node --import tsx/esm src/main.ts --verbose
```
