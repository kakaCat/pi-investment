import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')

  return {
    plugins: [vue()],
    resolve: {
      alias: {
        '@': resolve(__dirname, 'src')
      }
    },
    server: {
      port: 3001,
      proxy: {
        '/api': {
          target: env.VITE_API_BASE_URL || 'http://127.0.0.1:5001',
          changeOrigin: true,
        }
      }
    },
    build: {
      // 目标浏览器
      target: 'es2015',
      // 输出目录
      outDir: 'dist',
      // 静态资源目录
      assetsDir: 'assets',
      // 小于此阈值的导入或引用资源将内联为 base64 编码
      assetsInlineLimit: 4096,
      // 启用/禁用 CSS 代码拆分
      cssCodeSplit: true,
      // 构建后是否生成 source map 文件
      sourcemap: env.VITE_BUILD_SOURCEMAP === 'true',
      // chunk 大小警告的限制（以 kbs 为单位）
      chunkSizeWarningLimit: 1000,
      // 启用/禁用 gzip 压缩大小报告
      reportCompressedSize: true,
      // 压缩配置 - use esbuild for faster builds
      minify: 'esbuild',
      rollupOptions: {
        output: {
          // 静态资源分类打包
          chunkFileNames: 'assets/js/[name]-[hash].js',
          entryFileNames: 'assets/js/[name]-[hash].js',
          assetFileNames: 'assets/[ext]/[name]-[hash].[ext]',
          // 代码分割策略
          manualChunks: (id: string) => {
            // Vue 核心库
            if (id.includes('node_modules/vue') ||
                id.includes('node_modules/vue-router') ||
                id.includes('node_modules/pinia')) {
              return 'vue-vendor'
            }

            // Element Plus UI 库
            if (id.includes('node_modules/element-plus') ||
                id.includes('node_modules/@element-plus')) {
              return 'element-plus'
            }

            // ECharts 图表库
            if (id.includes('node_modules/echarts')) {
              return 'echarts'
            }

            // Axios 和网络请求相关
            if (id.includes('node_modules/axios') ||
                id.includes('node_modules/socket.io-client')) {
              return 'network'
            }

            // 工具库
            if (id.includes('node_modules/lodash-es') ||
                id.includes('node_modules/dayjs')) {
              return 'utils'
            }

            // 其他 node_modules 依赖
            if (id.includes('node_modules')) {
              return 'vendor'
            }
          }
        }
      }
    },
    // 优化依赖预构建
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
      ],
      exclude: []
    },
    // 预加载配置
    experimental: {
      renderBuiltUrl(filename: string) {
        // 可以自定义资源 URL
        return filename
      }
    }
  }
})
