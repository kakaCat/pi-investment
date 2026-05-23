# 量化交易系统 - 前端项目

基于 Vue 3 + TypeScript + Vite 构建的量化交易系统前端应用。

## 技术栈

- **框架**: Vue 3 (Composition API + `<script setup>`)
- **语言**: TypeScript
- **构建工具**: Vite
- **UI 组件库**: Element Plus
- **状态管理**: Pinia
- **路由**: Vue Router
- **图表**: ECharts
- **样式**: Tailwind CSS
- **HTTP 客户端**: Axios

## 快速开始

### 环境要求

- Node.js >= 18.0.0
- npm >= 9.0.0

### 安装依赖

```bash
npm install
```

### 开发环境

```bash
npm run dev
```

应用将在 `http://localhost:3000` 启动。

### 生产构建

```bash
npm run build
```

构建产物将输出到 `dist` 目录。

### 预览生产构建

```bash
npm run preview
```

## 环境配置

项目使用环境变量进行配置，支持多环境部署。

### 配置文件

- `.env.development` - 开发环境配置
- `.env.production` - 生产环境配置
- `.env.example` - 配置示例

### 主要配置项

```bash
# API 基础地址
VITE_API_BASE_URL=http://localhost:5001

# WebSocket 地址
VITE_WS_URL=ws://localhost:5001

# 是否启用性能监控
VITE_ENABLE_PERFORMANCE_MONITOR=true

# API 请求超时时间（毫秒）
VITE_API_TIMEOUT=30000
```

更多配置项请参考 `.env.example` 文件。

## 性能优化

项目已实施全面的性能优化策略，包括：

- **代码分割**: 智能的依赖分组和路由懒加载
- **构建优化**: Terser 压缩、Tree Shaking、资源内联
- **依赖预构建**: 加速开发服务器启动和热更新
- **性能监控**: 自动收集页面和 API 性能指标

详细的优化策略和配置说明请参考 [性能优化文档](./docs/OPTIMIZATION.md)。

### 性能监控

开发环境下，性能监控自动启用。在浏览器控制台中使用以下命令查看性能数据：

```javascript
// 查看完整性能报告
window.__PERFORMANCE_MONITOR__.printReport()

// 获取页面性能指标
window.__PERFORMANCE_MONITOR__.getMetrics()

// 获取 API 性能统计
window.__PERFORMANCE_MONITOR__.getAPIStats()

// 获取内存使用情况
window.__PERFORMANCE_MONITOR__.getMemoryUsage()
```

## 项目结构

```
web-frontend/
├── docs/                    # 文档目录
│   └── OPTIMIZATION.md      # 性能优化文档
├── public/                  # 静态资源
├── src/
│   ├── assets/             # 资源文件（样式、图片等）
│   ├── components/         # 公共组件
│   │   └── layout/         # 布局组件
│   ├── router/             # 路由配置
│   ├── services/           # 服务层
│   │   └── api/            # API 接口
│   ├── stores/             # Pinia 状态管理
│   ├── types/              # TypeScript 类型定义
│   ├── utils/              # 工具函数
│   │   └── performance.ts  # 性能监控工具
│   ├── views/              # 页面组件
│   ├── App.vue             # 根组件
│   └── main.ts             # 应用入口
├── .env.development        # 开发环境配置
├── .env.production         # 生产环境配置
├── .env.example            # 配置示例
├── index.html              # HTML 模板
├── package.json            # 项目配置
├── tsconfig.json           # TypeScript 配置
├── vite.config.ts          # Vite 配置
└── README.md               # 项目说明
```

## 主要功能模块

- **仪表盘**: 系统概览和关键指标展示
- **指标 IDE**: 自定义技术指标开发
- **股票研究**: 股票数据查询和分析
- **因子分析**: 多因子分析和回测
- **交易信号**: 交易信号生成和管理
- **机会雷达**: 投资机会发现
- **回测中心**: 策略回测和快速交易
- **持仓管理**: 投资组合管理
- **订单管理**: 交易订单跟踪
- **风控检查**: 风险控制和监控
- **策略中心**: 策略运营和管理
- **ML 引擎**: 机器学习模型训练和预测
- **Agent 日志**: AI Agent 工作日志

## 开发指南

### 代码规范

- 使用 TypeScript 进行类型检查
- 遵循 Vue 3 Composition API 最佳实践
- 组件使用 `<script setup>` 语法
- 使用 ESLint 和 Prettier 保持代码风格一致

### 路由懒加载

所有页面组件都使用动态导入实现懒加载：

```typescript
{
  path: '/dashboard',
  component: () => import(/* webpackChunkName: "dashboard" */ '@/views/Dashboard/index.vue')
}
```

### API 调用

使用统一的 API 客户端进行接口调用：

```typescript
import { apiClient } from '@/services/api/client'

// GET 请求
const data = await apiClient.get('/api/endpoint')

// POST 请求
const result = await apiClient.post('/api/endpoint', { data })
```

API 客户端已集成性能监控，自动记录请求耗时。

### 性能最佳实践

1. **使用路由懒加载**: 减少初始包体积
2. **合理使用 v-memo**: 优化列表渲染
3. **避免不必要的响应式**: 使用 `shallowRef` 和 `shallowReactive`
4. **图片懒加载**: 使用 `loading="lazy"` 属性
5. **虚拟滚动**: 处理长列表时使用虚拟滚动组件

## 部署

### 构建生产版本

```bash
npm run build
```

### 部署到服务器

将 `dist` 目录的内容部署到 Web 服务器（如 Nginx、Apache）。

### Nginx 配置示例

```nginx
server {
    listen 80;
    server_name your-domain.com;
    root /path/to/dist;
    index index.html;

    # 启用 gzip 压缩
    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml application/xml+rss text/javascript;

    # SPA 路由支持
    location / {
        try_files $uri $uri/ /index.html;
    }

    # 静态资源缓存
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
```

## 故障排查

### 开发服务器启动失败

1. 检查 Node.js 版本是否符合要求
2. 删除 `node_modules` 和 `package-lock.json`，重新安装依赖
3. 检查端口 3000 是否被占用

### 构建失败

1. 检查 TypeScript 类型错误
2. 确认所有依赖已正确安装
3. 查看构建日志中的具体错误信息

### API 请求失败

1. 检查 `.env` 文件中的 API 地址配置
2. 确认后端服务已启动
3. 检查浏览器控制台的网络请求

## 相关资源

- [Vue 3 文档](https://vuejs.org/)
- [Vite 文档](https://vitejs.dev/)
- [Element Plus 文档](https://element-plus.org/)
- [TypeScript 文档](https://www.typescriptlang.org/)
- [性能优化文档](./docs/OPTIMIZATION.md)

## License

MIT
