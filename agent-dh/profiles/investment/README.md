# DSH Investment Profile

这是 Agent-DH 的 DSH Profile 配置模板，使用**本地打包依赖**方式安装。

## 架构说明

```
agent-dh/
  ├── packages/          # 14 个插件源码（TypeScript）
  ├── scripts/
  │   └── pack-for-profile.sh   # 打包脚本
  └── profiles/investment/      # Profile 配置模板
      └── package.json          # 依赖配置（file:local-packages/*.tgz）

~/.dsh/profiles/investment/   # 实际安装位置
  ├── local-packages/         # 打包的 .tgz 文件
  │   ├── pi-investment-investment-0.2.0.tgz
  │   ├── pi-investment-trading-0.2.0.tgz
  │   └── ...
  ├── node_modules/           # pnpm 安装的依赖
  ├── package.json            # 从模板复制
  └── start.sh                # 启动脚本
```

## 安装方式

### 方式 1: 使用打包脚本（推荐）

```bash
# 1. 构建并打包所有插件
cd /path/to/pi-investment/agent-dh
./scripts/pack-for-profile.sh ~/.dsh/profiles/investment/local-packages

# 2. 复制 profile 配置到 DSH 目录
cp -r profiles/investment/* ~/.dsh/profiles/investment/

# 3. 安装依赖
cd ~/.dsh/profiles/investment
pnpm install

# 4. 启动
./start.sh
```

### 方式 2: 在 profile 中一键更新

```bash
cd ~/.dsh/profiles/investment
pnpm run repack    # 自动打包 + 安装
```

## 更新流程

当修改了插件代码后，需要重新打包：

```bash
# 方法 1: 从 agent-dh 目录
cd /path/to/pi-investment/agent-dh
./scripts/pack-for-profile.sh ~/.dsh/profiles/investment/local-packages
cd ~/.dsh/profiles/investment
pnpm install

# 方法 2: 在 profile 目录一键更新
cd ~/.dsh/profiles/investment
pnpm run repack
```

## 优点

✅ **完全自包含**: `local-packages/` 包含所有依赖，不依赖外部路径  
✅ **可移植性强**: 可以打包整个 `~/.dsh/profiles/investment` 目录到其他机器  
✅ **版本明确**: `.tgz` 文件名包含版本号，便于追踪  
✅ **无 symlink 问题**: 使用真实文件复制，不依赖符号链接  
✅ **跨平台**: Windows/Linux/macOS 都能正常工作  

## 目录结构

```
~/.dsh/profiles/investment/
├── local-packages/              # 打包的依赖（.tgz 文件）
│   ├── pi-investment-investment-0.2.0.tgz
│   ├── pi-investment-trading-0.2.0.tgz
│   └── ... (20 个包)
├── node_modules/                # pnpm 安装后的依赖
├── state/                       # 运行时状态（git ignore）
├── agents.json                  # Agent 身份注册表
├── cordis.yml                   # DSH 基础配置
├── cordis.patch.yml            # 插件加载配置
├── package.json                 # 依赖声明
├── pnpm-lock.yaml              # 锁文件
├── start.sh                     # 启动脚本
└── stop.sh                      # 停止脚本
```

## 配置文件

### package.json

使用 `file:local-packages/*.tgz` 引用本地打包文件：

```json
{
  "dependencies": {
    "@pi-investment/investment": "file:local-packages/pi-investment-investment-0.2.0.tgz"
  }
}
```

### 版本更新

当插件版本更新时，需要同步更新 `package.json` 中的 `.tgz` 文件名。

## 常见问题

### Q: 如何查看当前安装的插件版本？

```bash
cd ~/.dsh/profiles/investment
pnpm list --depth=0 | grep @pi-investment
```

### Q: 如何清理旧版本的 .tgz 文件？

```bash
rm -rf ~/.dsh/profiles/investment/local-packages/*.tgz
```

然后重新运行打包脚本。

### Q: 可以部分更新某个插件吗？

可以，只打包单个插件：

```bash
cd /path/to/pi-investment/agent-dh/packages/investment
pnpm pack --pack-destination ~/.dsh/profiles/investment/local-packages
cd ~/.dsh/profiles/investment
pnpm install
```

### Q: 如何在生产环境部署？

1. 在开发机打包：`./scripts/pack-for-profile.sh dist/local-packages`
2. 打包整个 profile 目录：`tar -czf investment-profile.tar.gz ~/.dsh/profiles/investment`
3. 在生产机解压：`tar -xzf investment-profile.tar.gz -C ~/`
4. 启动：`cd ~/.dsh/profiles/investment && ./start.sh`

## 参考

- [Agent-DH README](../../README.md)
- [Agent-DH CLAUDE.md](../../CLAUDE.md)
- [DSH 文档](https://github.com/deepseek-ai/dsh)
