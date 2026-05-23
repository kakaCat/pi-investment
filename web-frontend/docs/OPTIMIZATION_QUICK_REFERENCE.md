# 性能优化快速参考

## 快速检查清单

### 开发环境

- [ ] 确认 `.env.development` 已配置
- [ ] 性能监控已启用 (`VITE_ENABLE_PERFORMANCE_MONITOR=true`)
- [ ] 打开浏览器控制台查看性能日志

### 生产构建前

- [ ] 更新 `.env.production` 中的 API 地址
- [ ] 关闭生产环境的性能监控和日志
- [ ] 运行 `npm run build` 检查构建产物大小
- [ ] 确认没有 console 输出泄露到生产环境

### 部署后

- [ ] 运行 Lighthouse 测试
- [ ] 检查首屏加载时间 < 2s
- [ ] 验证代码分割是否生效
- [ ] 确认静态资源缓存策略

## 常用命令

```bash
# 开发环境
npm run dev

# 生产构建
npm run build

# 预览生产构建
npm run preview

# 类型检查
npm run type-check
```

## 性能监控命令

在浏览器控制台中使用：

```javascript
// 完整性能报告
window.__PERFORMANCE_MONITOR__.printReport()

// 页面性能指标
window.__PERFORMANCE_MONITOR__.getMetrics()

// API 性能统计
window.__PERFORMANCE_MONITOR__.getAPIStats()

// 内存使用情况
window.__PERFORMANCE_MONITOR__.getMemoryUsage()

// 自定义计时
const endTimer = window.__PERFORMANCE_MONITOR__.startTimer('操作名称')
// ... 执行操作
endTimer()
```

## 代码分割策略

### 当前分组

- **vue-vendor**: Vue 核心库 (~150KB)
- **element-plus**: UI 组件库 (~500KB)
- **echarts**: 图表库 (~300KB)
- **network**: 网络请求库 (~50KB)
- **utils**: 工具库 (~30KB)
- **vendor**: 其他依赖

### 路由懒加载

所有页面组件都已配置懒加载，使用 webpackChunkName 注释：

```typescript
component: () => import(/* webpackChunkName: "dashboard" */ '@/views/Dashboard/index.vue')
```

## 性能目标

| 指标 | 目标值 |
|------|--------|
| 首屏加载时间 | < 2s |
| 首次内容绘制 (FCP) | < 1.5s |
| 最大内容绘制 (LCP) | < 2.5s |
| 首次输入延迟 (FID) | < 100ms |
| 累积布局偏移 (CLS) | < 0.1 |
| 初始包大小 (gzip) | < 500KB |

## 常见问题

### Q: 如何查看包体积分析？

A: 安装 `rollup-plugin-visualizer` 并在 `vite.config.ts` 中配置：

```bash
npm install -D rollup-plugin-visualizer
```

```typescript
import { visualizer } from 'rollup-plugin-visualizer'

export default defineConfig({
  plugins: [
    vue(),
    visualizer({ open: true })
  ]
})
```

### Q: 如何优化大型组件？

A: 使用异步组件和 Suspense：

```vue
<script setup>
import { defineAsyncComponent } from 'vue'

const HeavyComponent = defineAsyncComponent(() =>
  import('./HeavyComponent.vue')
)
</script>

<template>
  <Suspense>
    <template #default>
      <HeavyComponent />
    </template>
    <template #fallback>
      <div>加载中...</div>
    </template>
  </Suspense>
</template>
```

### Q: 如何处理长列表性能问题？

A: 使用虚拟滚动库如 `vue-virtual-scroller`：

```bash
npm install vue-virtual-scroller
```

### Q: API 请求太慢怎么办？

A: 检查性能监控数据：

```javascript
// 查看慢请求
const records = window.__PERFORMANCE_MONITOR__.getAPIRecords()
const slowRequests = records.filter(r => r.duration > 3000)
console.table(slowRequests)
```

## 优化技巧

### 1. 图片优化

```vue
<!-- 使用懒加载 -->
<img src="image.jpg" loading="lazy" alt="描述" />

<!-- 使用 WebP 格式 -->
<picture>
  <source srcset="image.webp" type="image/webp" />
  <img src="image.jpg" alt="描述" />
</picture>
```

### 2. 防抖和节流

```typescript
import { debounce } from 'lodash-es'

const handleSearch = debounce((value: string) => {
  // 搜索逻辑
}, 300)
```

### 3. 使用 v-memo 优化列表

```vue
<template>
  <div v-for="item in list" :key="item.id" v-memo="[item.id, item.status]">
    <!-- 只有 id 或 status 变化时才重新渲染 -->
  </div>
</template>
```

### 4. 合理使用 computed

```typescript
// 好的做法：使用 computed 缓存计算结果
const filteredList = computed(() => {
  return list.value.filter(item => item.active)
})

// 避免：在模板中直接计算
// <div v-for="item in list.filter(item => item.active)">
```

### 5. 避免不必要的响应式

```typescript
import { shallowRef, shallowReactive } from 'vue'

// 对于大型数据结构，使用 shallow 版本
const largeData = shallowRef({
  // 大量数据
})
```

## 监控和分析工具

- **Chrome DevTools**: 性能分析、网络分析、内存分析
- **Lighthouse**: 综合性能评分
- **Vue DevTools**: Vue 组件性能分析
- **Vite Bundle Analyzer**: 包体积分析

## 更多信息

详细的优化策略和配置说明请参考 [完整优化文档](./OPTIMIZATION.md)。
