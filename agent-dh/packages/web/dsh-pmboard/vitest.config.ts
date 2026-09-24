import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    // 包含当前目录的 tests 文件
    include: ['tests/**/*.test.ts'],
    
    // 排除
    exclude: [
      '**/node_modules/**',
      '**/dist/**',
      '**/.vite/**',
      '**/.vitest/**'
    ],
    
    // 禁用缓存（调试用）
    cache: false,
    
    // 根目录
    root: process.cwd(),
  }
});
