# 性能优化文档

## 概述

本文档描述了量化交易系统前端项目的性能优化策略和配置。通过合理的代码分割、懒加载、压缩和监控，确保应用具有良好的加载速度和运行性能。

## 优化策略

### 1. 代码分割（Code Splitting）

#### 1.1 自动代码分割

Vite 配置中实现了智能的代码分割策略，将依赖库按功能分组：

- **vue-vendor**: Vue 核心库（vue, vue-router, pinia）
- **element-plus**: UI 组件库（element-plus, @element-plus/icons-vue）
- **echarts**: 图表库
- **network**: 网络请求相关（axios, socket.io-client）
- **utils**: 工具库（lodash-es, dayjs）
- **vendor**: 其他第三方依赖

#### 1.2 路由懒加载

所有页面组件都采用动态导入（Dynamic Import）方式加载：

```typescript
{
  path: '/dashboard',
  component: () => import(/* webpackChunkName: "dashboard" */ '@/views/Dashboard/index.vue')
}
```

**优势**：
- 首屏加载时间减少
- 按需加载，减少初始包体积
- 提升用户体验

### 2. 构建优化

#### 2.1 压缩配置

使用 Terser 进行代码压缩：

```typescript
minify: 'terser',
terserOptions: {
  compress: {
    drop_console: mode === 'production',  // 生产环境移除 console
    drop_debugger: true,                   // 移除 debugger
    pure_funcs: ['console.log']            // 移除 console.log
  }
}
```

#### 2.2 资源优化

- **内联阈值**: 小于 4KB 的资源自动内联为 base64
- **CSS 代码分割**: 启用 CSS 代码分割，减少关键路径
- **静态资源分类**: 按类型分目录存放（js/css/images）

#### 2.3 Tree Shaking

通过 ES Module 和 Rollup 自动移除未使用的代码。

### 3. 依赖预构建

配置 `optimizeDeps` 预构建常用依赖：

```typescript
optimizeDeps: {
  include: [
    'vue',
    'vue-router',
    'pinia',
    'element-plus',
    '@element-plus/icons-vue',
    'echarts',
    'axios',
    'dayjs',
    'lodash-es'
  ]
}
```

**优势**：
- 减少开发服务器启动时间
- 提升热更新速度
- 统一依赖版本

### 4. 路由加载优化

#### 4.1 加载状态

路由切换时显示加载动画，提升用户体验：

```typescript
router.beforeEach((to, from, next) => {
  // 延迟 200ms 显示加载状态，避免快速切换时闪烁
  loadingTimer = setTimeout(() => {
    loadingInstance = ElLoading.service({
      lock: true,
      text: '加载中...',
      background: 'rgba(0, 0, 0, 0.7)'
    })
  }, 200)
  next()
})
```

#### 4.2 预加载策略

关键页面（如 Dashboard、Portfolio）标记为 `preload: true`，可在空闲时预加载。

### 5. 性能监控

#### 5.1 页面性能指标

自动收集以下指标：

- **页面加载时间** (Page Load Time)
- **DOM 加载时间** (DOM Content Loaded)
- **资源加载时间** (Resource Load Time)
- **首次绘制时间** (First Paint)
- **首次内容绘制时间** (First Contentful Paint)

#### 5.2 API 性能监控

记录所有 API 请求的性能数据：

```typescript
performanceMonitor.recordAPICall(url, method, duration, status)
```

自动警告慢请求（超过 3 秒）。

#### 5.3 使用方式

开发环境下，性能监控自动启用：

```javascript
// 在浏览器控制台查看性能报告
window.__PERFORMANCE_MONITOR__.printReport()

// 获取性能指标
window.__PERFORMANCE_MONITOR__.getMetrics()

// 获取 API 统计
window.__PERFORMANCE_MONITOR__.getAPIStats()

// 自定义计时
const endTimer = window.__PERFORMANCE_MONITOR__.startTimer('操作名称')
// ... 执行操作
endTimer()
```

## 配置说明

### Vite 配置 (vite.config.ts)

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `target` | 目标浏览器 | es2015 |
| `assetsInlineLimit` | 资源内联阈值 | 4096 (4KB) |
| `cssCodeSplit` | CSS 代码分割 | true |
| `sourcemap` | 生成 source map | 根据环境变量 |
| `chunkSizeWarningLimit` | chunk 大小警告限制 | 1000 KB |
| `minify` | 压缩工具 | terser |

### 环境变量

#### 开发环境 (.env.development)

```bash
VITE_API_BASE_URL=http://localhost:8000
VITE_BUILD_SOURCEMAP=true
VITE_ENABLE_PERFORMANCE_MONITOR=true
VITE_ENABLE_LOG=true
```

#### 生产环境 (.env.production)

```bash
VITE_API_BASE_URL=https://api.yourdomain.com
VITE_BUILD_SOURCEMAP=false
VITE_ENABLE_PERFORMANCE_MONITOR=false
VITE_ENABLE_LOG=false
```

## 性能指标

### 目标指标

| 指标 | 目标值 | 说明 |
|------|--------|------|
| 首屏加载时间 | < 2s | 从开始加载到首屏渲染完成 |
| 首次内容绘制 (FCP) | < 1.5s | 首次渲染任何内容 |
| 最大内容绘制 (LCP) | < 2.5s | 最大内容元素渲染完成 |
| 首次输入延迟 (FID) | < 100ms | 用户首次交互响应时间 |
| 累积布局偏移 (CLS) | < 0.1 | 视觉稳定性 |

### 包体积目标

| 包类型 | 目标大小 | 说明 |
|--------|----------|------|
| 初始包 (Initial Bundle) | < 500KB | gzip 后 |
| 单个 chunk | < 200KB | gzip 后 |
| 总包大小 | < 2MB | gzip 后 |

## 优化建议

### 1. 图片优化

- 使用 WebP 格式
- 实现图片懒加载
- 使用 CDN 加速
- 压缩图片质量

### 2. 字体优化

- 使用字体子集
- 预加载关键字体
- 使用 `font-display: swap`

### 3. 网络优化

- 启用 HTTP/2
- 使用 CDN
- 启用 Gzip/Brotli 压缩
- 配置缓存策略

### 4. 运行时优化

- 使用虚拟滚动处理长列表
- 防抖和节流优化高频事件
- 使用 Web Worker 处理复杂计算
- 合理使用 Vue 的 `v-memo` 和 `v-once`

### 5. 监控和分析

- 使用 Lighthouse 定期检查
- 配置 Web Vitals 监控
- 分析 Bundle 大小（使用 `rollup-plugin-visualizer`）
- 监控真实用户性能数据 (RUM)

## 构建命令

```bash
# 开发环境
npm run dev

# 生产构建
npm run build

# 预览生产构建
npm run preview

# 分析包体积（需要安装 rollup-plugin-visualizer）
npm run build -- --mode analyze
```

## 性能检查清单

### 构建前

- [ ] 检查依赖版本是否最新
- [ ] 移除未使用的依赖
- [ ] 检查是否有重复依赖
- [ ] 确认环境变量配置正确

### 构建后

- [ ] 检查包体积是否符合目标
- [ ] 验证代码分割是否生效
- [ ] 确认 source map 配置正确
- [ ] 测试生产环境功能是否正常

### 部署后

- [ ] 运行 Lighthouse 测试
- [ ] 检查 Web Vitals 指标
- [ ] 验证 CDN 缓存是否生效
- [ ] 监控真实用户性能数据

## 故障排查

### 问题：首屏加载慢

**可能原因**：
1. 初始包体积过大
2. 未启用代码分割
3. 网络延迟高

**解决方案**：
1. 检查 `manualChunks` 配置
2. 确认路由懒加载生效
3. 使用 CDN 加速静态资源

### 问题：路由切换慢

**可能原因**：
1. 组件体积过大
2. 未使用懒加载
3. 组件初始化逻辑复杂

**解决方案**：
1. 拆分大组件
2. 使用异步组件
3. 优化组件生命周期逻辑

### 问题：内存占用高

**可能原因**：
1. 内存泄漏
2. 大量数据缓存
3. 事件监听未清理

**解决方案**：
1. 使用 Chrome DevTools 分析内存
2. 及时清理不需要的数据
3. 在组件销毁时清理事件监听

## 参考资源

- [Vite 官方文档](https://vitejs.dev/)
- [Vue 性能优化指南](https://vuejs.org/guide/best-practices/performance.html)
- [Web Vitals](https://web.dev/vitals/)
- [Lighthouse](https://developers.google.com/web/tools/lighthouse)

## 更新日志

### 2026-05-23

- 初始版本
- 实现代码分割策略
- 添加路由懒加载
- 集成性能监控工具
- 配置环境变量
