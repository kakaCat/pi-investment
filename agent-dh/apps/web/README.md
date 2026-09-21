# Agent-DH Web Application

完整的 Agent-DH Web 应用，包含服务器和前端。

## 目录结构

```
apps/web/
├── src/
│   ├── main.ts              # 服务器启动入口（Node.js）
│   └── client/              # 前端代码（浏览器）
│       ├── main.ts          # 浏览器入口
│       ├── node-module-stub.ts
│       └── vite-env.d.ts
├── config/                  # 服务器配置
│   ├── cordis.yml          # Cordis 插件配置
│   └── agent-presets/      # Agent 预设
├── tests/                   # 测试文件
├── scripts/                 # 工具脚本
├── examples/                # 使用示例
├── public/                  # 前端静态资源
├── index.html              # 前端 HTML 入口
├── vite.config.ts          # Vite 配置
├── tsconfig.json           # TypeScript 配置
└── package.json            # 应用依赖

## 脚本命令

### 启动服务器
```bash
# 从仓库根目录
pnpm start

# 或者在 apps/web 目录内
pnpm start
```

### 开发模式
```bash
pnpm start:dev
```

### 构建前端
```bash
pnpm build
```

### Watch 模式（前端热更新）
```bash
pnpm watch
```

### 测试
```bash
pnpm test
```

## 工作流程

1. **服务器启动**: `src/main.ts` 加载 Cordis 插件，启动 Agent-DH 服务器
2. **前端服务**: 服务器通过 `@deepseek-ai/dsh-web-app` 插件服务 `dist/` 目录
3. **前端入口**: `src/client/main.ts` 使用 `AppWebEntry` 初始化浏览器端应用

## 架构说明

参考 DeepSeek Harness 的架构：
- **apps/cli** → **apps/web/src/main.ts** (服务器启动)
- **apps/web** → **apps/web/src/client/** (前端代码)

Agent-DH 将服务器和前端整合在一个 `apps/web` 应用中。
