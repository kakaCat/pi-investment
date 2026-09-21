# Web 目录迁移说明

## 迁移概述

参考 DeepSeek Harness 的 `apps/web` 结构，为 Agent-DH 创建了标准的 Web 应用入口。

## 已完成的工作

### 1. 创建目录结构

```
agent-dh/
├── apps/
│   └── web/                           # 新创建的 Web 应用入口
│       ├── src/
│       │   ├── main.ts               # 浏览器入口（AppWebEntry）
│       │   ├── node-module-stub.ts   # Node.js 模块桩
│       │   └── vite-env.d.ts         # Vite 类型定义
│       ├── public/
│       │   └── favicon.svg           # 应用图标
│       ├── index.html                # HTML 入口
│       ├── vite.config.ts            # Vite 构建配置
│       ├── tsconfig.json             # TypeScript 配置
│       ├── package.json              # 包清单
│       ├── .gitignore                # Git 忽略文件
│       └── README.md                 # 文档
```

### 2. 更新根目录配置

- **package.json**: 添加 `apps/*` 到 workspaces

### 3. 架构对齐

参考 DeepSeek Harness 的实现：
- 使用 `@deepseek-ai/dsh-client-web` 作为 shell library
- 实现 desktop/web 双模式支持
- 配置 Vite 拒绝独立运行（需要 Agent-DH 服务器注入 boot manifest）

## 现有内容组织

Agent-DH 当前的 Web 相关内容：

```
packages/
├── agent-dh-client/          # 客户端 API 库（保持不变）
└── pages/                    # 页面组件包（保持不变）
    ├── bulletin/             # 公告板页面
    ├── dsh-pmboard/          # 项目管理看板
    ├── execution/            # 执行面板
    ├── genome/               # 基因组页面
    ├── holdings/             # 持仓页面
    ├── page-kit/             # 页面工具包
    └── web-liveness/         # Web 活跃度检测
```

**这些包无需迁移**，继续作为独立的页面组件包存在。

## 下一步操作

### 1. 安装依赖

```bash
cd /Users/yunpeng/pi-investment/agent-dh
pnpm install
```

### 2. 构建 Web 应用

```bash
pnpm --filter @pi-investment/agent-dh-web-frontend build
```

### 3. 配置 Agent-DH 服务器

确保 Agent-DH 服务器配置指向 `apps/web/dist` 目录：

- 检查 `@deepseek-ai/dsh-web-app` 插件配置
- 确认静态文件服务路径

### 4. 开发工作流

**开发模式**：
```bash
# Terminal 1: 启动 Agent-DH 服务器
pnpm start

# Terminal 2: Watch 模式重新构建前端
pnpm --filter @pi-investment/agent-dh-web-frontend watch
```

## 与 DeepSeek Harness 的对照

| DeepSeek Harness | Agent-DH | 说明 |
|------------------|----------|------|
| `apps/web/` | `apps/web/` | ✅ Web 应用入口 |
| `packages/web/web/` | `packages/agent-dh-client/` | 客户端 API 库 |
| `packages/client/web/` | 使用上游 `@deepseek-ai/dsh-client-web` | Web 启动内核 |
| UI 组件包 | `packages/pages/*` | 页面组件 |

## 注意事项

1. **不能独立运行**: `apps/web` 不能直接用 `vite dev` 运行，必须通过 Agent-DH 服务器
2. **构建产物**: `dist/` 目录会被服务器加载
3. **HMR**: 开发时使用 watch 模式配合服务器实现热更新
4. **依赖关系**: `apps/web` 依赖 `packages/agent-dh-client` 和上游 DSH 包

## 参考资料

- DeepSeek Harness: `/Volumes/ORICO/doc/github/deepseek-harness/apps/web/`
- DSH Client Web: `@deepseek-ai/dsh-client-web` 包文档
- Vite 配置: `apps/web/vite.config.ts`
